"""Kimlik dogrulama ve rol bazli erisim denetimi."""
import hashlib
import hmac
import os
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from ..config import ayarlar
from ..db import get_db
from ..models import Calisma, CalismaMerkez, Gonullu, Kullanici, Rol
from ..models._ortak import simdi
from ..models.ekip import CalismaUyesi

ITERASYON = 200_000
MAKS_HATALI_GIRIS = 5
KILIT_DAKIKA = 15          # ilk kilit suresi; her yeni kilitte iki katina cikar
PAROLA_GECMISI = 5         # yeniden kullanilamayan son parola sayisi
# parola degisimi zorunluyken bu yollar acik kalir
_PAROLA_SERBEST = ("/hesap", "/cikis", "/giris", "/static", "/api/")


def _ayar(ad: str, env: str, varsayilan: int) -> int:
    """config.Ayarlar'daki alani okur; alan yoksa ortam degiskenine duser."""
    v = getattr(ayarlar(), ad, None)
    if v is None:
        v = os.environ.get(env, varsayilan)
    try:
        return int(v)
    except (TypeError, ValueError):
        return varsayilan


def parola_min() -> int:
    return _ayar("parola_min", "SC_PAROLA_MIN", 12)


def parola_gun() -> int:
    return _ayar("parola_gun", "SC_PAROLA_GUN", 90)


def parola_hashle(parola: str) -> str:
    tuz = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", parola.encode(), tuz.encode(), ITERASYON).hex()
    return f"pbkdf2_sha256${ITERASYON}${tuz}${h}"


def parola_dogrula(parola: str, kayit: str) -> bool:
    try:
        _, it, tuz, h = kayit.split("$")
    except ValueError:
        return False
    aday = hashlib.pbkdf2_hmac("sha256", parola.encode(), tuz.encode(), int(it)).hex()
    return hmac.compare_digest(aday, h)


def parola_politikasi(parola: str) -> str | None:
    """Hata mesaji dondurur, uygunsa None. URS-SEC-04."""
    en_az = parola_min()
    if len(parola) < en_az:
        return f"Parola en az {en_az} karakter olmalı."
    if parola.isdigit() or parola.isalpha():
        return "Parola harf ve rakam içermeli."
    return None


def parola_suresi_doldu(k: Kullanici) -> bool:
    """Son degisimden bu yana SC_PAROLA_GUN gecmisse True. Tarihi bilinmeyen hesaplarda zorlama yok."""
    return bool(k.parola_degisim and (simdi() - k.parola_degisim).days >= parola_gun())


def parola_degisimi_gerekli(k: Kullanici) -> bool:
    return bool(k.ilk_giris_degisim) or parola_suresi_doldu(k)


def kilit_suresi(hatali_giris: int) -> timedelta:
    """5. hatada 15 dk, 10. hatada 30 dk, 15. hatada 60 dk ... (her yeni kilitte iki kat)."""
    kat = max(1, hatali_giris // MAKS_HATALI_GIRIS)
    return timedelta(minutes=KILIT_DAKIKA * (2 ** (kat - 1)))


def giris_yap(db: Session, kullanici_adi: str, parola: str, ip: str | None = None) -> Kullanici | None:
    """Basarili giriste kullaniciyi doner. Hatali giris sayaci her MAKS_HATALI_GIRIS'te sureli kilit koyar;
    kilit suresi dolunca dogru parola kabul edilir. Kilitlenme denetim izine 'kilit' olarak yazilir."""
    from . import denetim

    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == kullanici_adi)).scalar_one_or_none()
    if not k or not k.aktif:
        return None
    if k.kilitli:
        return None
    if not parola_dogrula(parola, k.parola_hash):
        k.hatali_giris += 1
        if k.hatali_giris % MAKS_HATALI_GIRIS == 0:
            sure = kilit_suresi(k.hatali_giris)
            k.kilit_bitis = simdi() + sure
            denetim.kaydet(db, None, "kilit", "kullanici", k.id,
                           yeni={"kullanici_adi": k.kullanici_adi, "hatali_giris": k.hatali_giris,
                                 "dakika": int(sure.total_seconds() // 60), "kilit_bitis": k.kilit_bitis.isoformat()}, ip=ip)
        db.commit()
        return None
    k.hatali_giris = 0
    k.kilit_bitis = None
    k.son_giris = simdi()
    db.commit()
    return k


def kilit_ac(db: Session, k: Kullanici) -> None:
    """Sayac ve sureli kilidi sifirlar; denetim kaydini cagiran yazar."""
    k.hatali_giris = 0
    k.kilit_bitis = None


def parola_degistir(db: Session, k: Kullanici, eski: str, yeni: str) -> str | None:
    """Hata mesaji dondurur, basariliysa None. Son PAROLA_GECMISI parola yeniden kullanilamaz. Commit etmez."""
    if not parola_dogrula(eski, k.parola_hash):
        return "Mevcut parola doğrulanamadı."
    h = parola_politikasi(yeni)
    if h:
        return h
    if eski == yeni:
        return "Yeni parola mevcut parolayla aynı olamaz."
    gecmis = list(k.parola_gecmisi or [])
    for kayit in [k.parola_hash] + gecmis:
        if parola_dogrula(yeni, kayit):
            return f"Son {PAROLA_GECMISI} paroladan biri yeniden kullanılamaz."
    gecmis = ([k.parola_hash] + gecmis)[:PAROLA_GECMISI]
    k.parola_gecmisi = gecmis
    k.parola_hash = parola_hashle(yeni)
    k.parola_degisim = simdi()
    k.ilk_giris_degisim = False
    return None


def api_anahtari_uret() -> str:
    return "sc_" + os.urandom(24).hex()


def api_anahtari_hashle(anahtar: str) -> str:
    return hashlib.sha256(anahtar.encode()).hexdigest()


def _anahtarla_kullanici(db: Session, anahtar: str) -> Kullanici | None:
    from ..models import ApiAnahtari

    k = db.execute(select(ApiAnahtari).where(ApiAnahtari.hash == api_anahtari_hashle(anahtar),
                                             ApiAnahtari.aktif.is_(True))).scalar_one_or_none()
    if not k or (k.son_gecerlilik and k.son_gecerlilik < simdi()):
        return None
    k.son_kullanim = simdi()
    db.commit()
    return k.kullanici if k.kullanici.aktif else None


def mevcut_kullanici(request: Request, db: Session = Depends(get_db)) -> Kullanici:
    # Makine-makine entegrasyon: X-SC-Anahtar basligi oturum cerezine alternatiftir
    anahtar = request.headers.get("X-SC-Anahtar")
    if anahtar:
        k = _anahtarla_kullanici(db, anahtar)
        if not k:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API anahtarı geçersiz")
        request.state.api_anahtari = True
        return k
    kid = request.session.get("kid")
    if not kid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Oturum bulunamadı")
    k = db.get(Kullanici, kid)
    if not k or not k.aktif:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Oturum geçersiz")
    # ilk giris / suresi dolmus parola: web sayfalari /hesap/parola'ya yonlenir (401 -> /giris -> /hesap/parola)
    if parola_degisimi_gerekli(k) and not request.url.path.startswith(_PAROLA_SERBEST):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Devam etmek için parolanızı değiştirin")
    return k


def mevcut_kullanici_opsiyonel(request: Request, db: Session = Depends(get_db)) -> Kullanici | None:
    kid = request.session.get("kid")
    return db.get(Kullanici, kid) if kid else None


# Rol -> izin verilen islemler. Rol globaldir; calisma bazli gorunurluk icin bkz. calisma_erisimi (#142)
IZINLER: dict[str, set[Rol]] = {
    # sponsor salt okunur; arastirmaci kendi kurdugu calismayi duzenler (bkz. calisma_duzenleyebilir)
    "calisma.olustur": {Rol.YONETICI, Rol.PROJE_YONETICISI, Rol.ARASTIRMACI},
    "calisma.duzenle": {Rol.YONETICI, Rol.PROJE_YONETICISI, Rol.ARASTIRMACI},
    "kriter.onayla": {Rol.YONETICI, Rol.PROJE_YONETICISI, Rol.ARASTIRMACI},
    "eslestirme.calistir": {Rol.YONETICI, Rol.ARASTIRMACI, Rol.KOORDINATOR, Rol.PROJE_YONETICISI},
    "eslestirme.incele": {Rol.YONETICI, Rol.ARASTIRMACI, Rol.KOORDINATOR},
    "hasta.goruntule": {Rol.YONETICI, Rol.ARASTIRMACI, Rol.KOORDINATOR},
    "veri.gir": {Rol.YONETICI, Rol.ARASTIRMACI, Rol.KOORDINATOR},
    "veri.sdv": {Rol.YONETICI, Rol.CRA},
    "veri.kilitle": {Rol.YONETICI, Rol.VERI_YONETICISI},
    "sorgu.ac": {Rol.YONETICI, Rol.CRA, Rol.VERI_YONETICISI},
    "sorgu.cevapla": {Rol.YONETICI, Rol.ARASTIRMACI, Rol.KOORDINATOR},
    "guvenlik.bildir": {Rol.YONETICI, Rol.ARASTIRMACI, Rol.KOORDINATOR, Rol.FARMAKOVIJILANS},
    "rbm.goruntule": {Rol.YONETICI, Rol.CRA, Rol.PROJE_YONETICISI, Rol.SPONSOR, Rol.DENETCI},
    "rbm.yonet": {Rol.YONETICI, Rol.CRA, Rol.PROJE_YONETICISI},
    "merkez.yonet": {Rol.YONETICI, Rol.PROJE_YONETICISI, Rol.CRA},
    "belge.yukle": {Rol.YONETICI, Rol.PROJE_YONETICISI, Rol.CRA, Rol.KOORDINATOR},
    "denetim.goruntule": {Rol.YONETICI, Rol.DENETCI, Rol.PROJE_YONETICISI},
    "kullanici.yonet": {Rol.YONETICI},
    "bdm.kullan": {Rol.YONETICI, Rol.ARASTIRMACI, Rol.KOORDINATOR, Rol.PROJE_YONETICISI, Rol.CRA},
    "disa_aktar": {Rol.YONETICI, Rol.VERI_YONETICISI, Rol.ISTATISTIKCI},
    "ekip.yonet": {Rol.YONETICI, Rol.PROJE_YONETICISI},
    "analiz.goruntule": {Rol.YONETICI, Rol.PROJE_YONETICISI, Rol.ARASTIRMACI, Rol.VERI_YONETICISI, Rol.ISTATISTIKCI},
}

# Calisma ekibine atanabilen roller. Diger roller baska bir yoldan erisir:
# yonetici/denetci her calismaya, sponsor kurumuna, arastirmaci/koordinator merkezine gore.
ATANABILIR_ROLLER = {Rol.PROJE_YONETICISI, Rol.CRA, Rol.VERI_YONETICISI, Rol.ISTATISTIKCI, Rol.FARMAKOVIJILANS}
MERKEZ_ROLLERI = (Rol.ARASTIRMACI, Rol.KOORDINATOR)


def izinli(kullanici: Kullanici, izin: str) -> bool:
    roller = IZINLER.get(izin)
    if roller is None:
        return kullanici.rol == Rol.YONETICI
    return kullanici.rol in roller


def gerekli(izin: str):
    def _bagimlilik(k: Kullanici = Depends(mevcut_kullanici)) -> Kullanici:
        if not izinli(k, izin):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Bu işlem için yetkiniz yok ({izin})")
        return k

    return _bagimlilik


# --- Calisma bazli gorunurluk -----------------------------------------------

def kisit_aktif(db: Session) -> bool:
    """Herhangi bir calismada atama varsa True. Tek count sorgusu; tablo bosken (tekil kurulum) kisit yok."""
    return (db.scalar(select(func.count(CalismaUyesi.id))) or 0) > 0


def _kurum(k: Kullanici) -> str:
    return (k.kurum or "").casefold().strip()


def calisma_erisimi(db: Session, k: Kullanici, c: Calisma) -> bool:
    if k.rol in (Rol.YONETICI, Rol.DENETCI):
        return True
    if k.rol == Rol.SPONSOR:
        return bool(_kurum(k)) and (c.sponsor or "").casefold().strip() == _kurum(k)
    if k.rol in MERKEZ_ROLLERI:
        # merkezi tanimsiz arastirmaci/koordinator icin mevcut davranis korunur (kisit yok)
        return not k.merkez_id or any(cm.merkez_id == k.merkez_id for cm in c.merkezler)
    if k.rol in ATANABILIR_ROLLER:
        if not kisit_aktif(db):
            return True
        return db.scalar(select(CalismaUyesi.id).where(CalismaUyesi.calisma_id == c.id,
                                                       CalismaUyesi.kullanici_id == k.id).limit(1)) is not None
    return False


def calisma_filtresi(db: Session, k: Kullanici, sorgu):
    """select(Calisma) sorgusunu calisma_erisimi ile ayni kurallarla daraltir.

    Merkez join'i satir cogaltabilir; cagiran .unique() kullanmali.
    """
    if k.rol in (Rol.YONETICI, Rol.DENETCI):
        return sorgu
    if k.rol == Rol.SPONSOR:
        if not _kurum(k):
            return sorgu.where(false())
        return sorgu.where(func.lower(func.trim(Calisma.sponsor)) == _kurum(k))
    if k.rol in MERKEZ_ROLLERI:
        if not k.merkez_id:
            return sorgu
        return sorgu.join(Calisma.merkezler).where(CalismaMerkez.merkez_id == k.merkez_id)
    if k.rol in ATANABILIR_ROLLER:
        if not kisit_aktif(db):
            return sorgu
        uyelik = select(CalismaUyesi.calisma_id).where(CalismaUyesi.kullanici_id == k.id)
        return sorgu.where(Calisma.id.in_(uyelik))
    return sorgu.where(false())


def calisma_duzenleyebilir(db: Session, k: Kullanici, c: Calisma) -> bool:
    """Tasarim ve duzenleme: yonetici/PY her zaman; arastirmaci yalnizca kendi kurdugu ya da
    bas arastirmacisi kendi merkezinden olan calismada."""
    if k.rol in (Rol.YONETICI, Rol.PROJE_YONETICISI):
        return True
    if k.rol != Rol.ARASTIRMACI:
        return False
    if c.olusturan_id and c.olusturan_id == k.id:
        return True
    if not k.merkez_id:
        return False
    return any(cm.bas_arastirmaci and cm.bas_arastirmaci.merkez_id == k.merkez_id for cm in c.merkezler)


def merkez_erisimi(k: Kullanici, merkez_id: int | None) -> bool:
    """Hasta havuzu ve HBYS islemleri merkez sinirlidir: yonetici her merkeze, merkez rolleri kendi merkezine."""
    if k.rol == Rol.YONETICI:
        return True
    if k.rol in MERKEZ_ROLLERI:
        return bool(k.merkez_id) and k.merkez_id == merkez_id
    return False


def gonullu_erisimi(db: Session, k: Kullanici, g: Gonullu) -> bool:
    """Gonullu detay/form: calisma erisimi + sponsor haric + merkez rolleri yalnizca kendi merkezinin gonullusu."""
    if k.rol == Rol.SPONSOR:
        return False
    if not calisma_erisimi(db, k, g.calisma):
        return False
    if k.rol in MERKEZ_ROLLERI and k.merkez_id:
        return bool(g.calisma_merkez) and g.calisma_merkez.merkez_id == k.merkez_id
    return True
