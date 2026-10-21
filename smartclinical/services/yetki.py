"""Kimlik dogrulama ve rol bazli erisim denetimi."""
import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Kullanici, Rol
from ..models._ortak import simdi

ITERASYON = 200_000
MAKS_HATALI_GIRIS = 5


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
    if len(parola) < 10:
        return "Parola en az 10 karakter olmalı."
    if parola.isdigit() or parola.isalpha():
        return "Parola harf ve rakam içermeli."
    return None


def giris_yap(db: Session, kullanici_adi: str, parola: str) -> Kullanici | None:
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == kullanici_adi)).scalar_one_or_none()
    if not k or not k.aktif:
        return None
    if k.hatali_giris >= MAKS_HATALI_GIRIS:
        return None  # hesap kilitli; yonetici acar
    if not parola_dogrula(parola, k.parola_hash):
        k.hatali_giris += 1
        db.commit()
        return None
    k.hatali_giris = 0
    k.son_giris = simdi()
    db.commit()
    return k


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
    return k


def mevcut_kullanici_opsiyonel(request: Request, db: Session = Depends(get_db)) -> Kullanici | None:
    kid = request.session.get("kid")
    return db.get(Kullanici, kid) if kid else None


# Rol -> izin verilen islemler. Ince taneli yetkiler icin yeterli; ileride
# calisma bazli atama (kullanici x calisma x rol) eklenecek. TODO(mert): bkz. #142
IZINLER: dict[str, set[Rol]] = {
    "calisma.olustur": {Rol.YONETICI, Rol.SPONSOR, Rol.PROJE_YONETICISI},
    "calisma.duzenle": {Rol.YONETICI, Rol.SPONSOR, Rol.PROJE_YONETICISI},
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
}


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
