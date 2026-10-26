import csv
import io
import platform
import sys
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import __version__
from ..config import ayarlar
from ..db import get_db
from ..models import Calisma, DenetimKaydi, EImza, Kullanici, Merkez, Rol
from ..models._ortak import simdi
from ..services import denetim, yetki
from ..services import kurulum as kurulum_svc
from ..services.yetki import gerekli
from ._ortak import bilgi, ip
from .sablon import goster, sablonlar

router = APIRouter(prefix="/yonetim")

# Denetim kaydini okunur cumleye ceviren sozlukler; calisma detayindaki "Son islemler" de ayni sozlugu kullanir.
ISLEM_ETIKET = {
    "olustur": "oluşturuldu", "guncelle": "güncellendi", "sil": "silindi", "giris": "giriş yaptı",
    "cikis": "çıkış yaptı", "giris_basarisiz": "başarısız giriş denemesi", "giris_engellendi": "giriş engellendi",
    "kilit": "kilitlendi", "kilit_ac": "kilidi açıldı", "parola_degistir": "parola değiştirildi", "imza": "imzalandı",
    "disa_aktar": "dışa aktarıldı", "goruntule": "görüntülendi", "yukle": "yüklendi", "senkron": "eşitlendi",
    "eslestirme": "taraması yapıldı", "tahmin": "tahmini güncellendi", "rbm": "risk göstergeleri hesaplandı",
    "dogrula": "doğrulandı", "kurulum": "kurulumu yapıldı", "yeniden_anahtarla": "takma adları yenilendi",
}
VARLIK_ETIKET = {
    "calisma": "çalışma", "kullanici": "kullanıcı", "merkez": "merkez", "calisma_merkez": "çalışma merkezi",
    "kriter": "kriter", "basvuru": "başvuru", "gonullu": "gönüllü", "protokol_versiyon": "protokol sürümü",
    "calisma_uyesi": "ekip üyesi", "belge": "belge", "hasta": "hasta kaydı", "eslestirme": "hasta eşleştirme",
    "eslestirme_sonucu": "eşleştirme önerisi", "risk_uyarisi": "risk uyarısı", "izlem_ziyareti": "izlem ziyareti",
    "protokol_sapmasi": "protokol sapması", "form": "eCRF formu", "form_kaydi": "form kaydı", "sorgu": "veri sorgusu",
    "advers_olay": "advers olay", "vizit": "vizit", "kol": "çalışma kolu", "vizit_tanimi": "vizit tanımı",
    "api_anahtari": "API anahtarı", "kurulum_ayari": "kurulum ayarı", "denetim_kaydi": "denetim izi",
    "arastirmaci": "araştırmacı", "e_imza": "e-imza", "calisma_taslagi": "çalışma taslağı",
}


def denetim_cumle(d: DenetimKaydi) -> str:
    """'çalışma oluşturuldu', 'kullanıcı kilitlendi' gibi kisa cumle; bilinmeyen kodlar oldugu gibi kalir."""
    varlik = VARLIK_ETIKET.get(d.varlik, d.varlik)
    islem = ISLEM_ETIKET.get(d.islem, d.islem)
    if d.islem in ("giris", "cikis", "giris_basarisiz", "giris_engellendi"):
        return islem
    return f"{varlik} {islem}"


sablonlar.env.globals["denetim_cumle"] = denetim_cumle


@router.get("/kullanicilar")
def kullanicilar(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db)):
    request.state.kullanici = k
    liste = db.execute(select(Kullanici).order_by(Kullanici.rol, Kullanici.ad_soyad)).scalars().all()
    merkezler = db.execute(select(Merkez).order_by(Merkez.ad)).scalars().all()
    sponsorlar = [x for (x,) in db.execute(select(Calisma.sponsor).distinct().order_by(Calisma.sponsor)).all() if x]
    ayar = kurulum_svc.ayar_getir(db)
    # tekil modda merkez secimi gizlenir ve varsayilan merkez atanir; roller moda gore daralir
    return goster(request, "yonetim/kullanicilar.html", liste=liste, roller=kurulum_svc.mod_rolleri(ayar.mod),
                  merkezler=merkezler, sponsorlar=sponsorlar, hata=None, ayar=ayar, en_az=yetki.parola_min(),
                  simdi=simdi())


@router.post("/kullanicilar")
def kullanici_ekle(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db),
                   kullanici_adi: str = Form(...), ad_soyad: str = Form(...), eposta: str = Form(...),
                   parola: str = Form(...), rol: str = Form(...), merkez_id: str = Form(""), kurum: str = Form("")):
    request.state.kullanici = k
    hata = yetki.parola_politikasi(parola)
    if hata:
        bilgi(request, hata)
        return RedirectResponse("/yonetim/kullanicilar", status_code=303)
    ayar = kurulum_svc.ayar_getir(db)
    if Rol(rol) not in kurulum_svc.mod_rolleri(ayar.mod):
        bilgi(request, "Bu rol seçili kullanım modunda sunulmuyor; modu Ayarlar'dan değiştirin.")
        return RedirectResponse("/yonetim/kullanicilar", status_code=303)
    kurum = kurum.strip()[:160]
    if Rol(rol) == Rol.SPONSOR and not kurum:
        bilgi(request, "UYARI: Sponsor kullanıcısı için kurum adı zorunludur; çalışmalar bu ada göre görünür.")
        return RedirectResponse("/yonetim/kullanicilar", status_code=303)
    kadi = kullanici_adi.strip().lower()
    if db.execute(select(Kullanici.id).where((Kullanici.kullanici_adi == kadi) | (Kullanici.eposta == eposta.strip()))).first():
        bilgi(request, "UYARI: Bu kullanıcı adı veya e-posta zaten kayıtlı.")
        return RedirectResponse("/yonetim/kullanicilar", status_code=303)
    mid = int(merkez_id) if merkez_id else None
    if ayar.mod == "tekil" and ayar.varsayilan_merkez_id:
        mid = ayar.varsayilan_merkez_id
    # gecici parolayi yonetici belirledi: ilk giriste degisim zorunlu
    y = Kullanici(kullanici_adi=kadi, ad_soyad=ad_soyad.strip(), eposta=eposta.strip(),
                  parola_hash=yetki.parola_hashle(parola), rol=Rol(rol), merkez_id=mid, kurum=kurum or None,
                  parola_degisim=simdi(), ilk_giris_degisim=True)
    db.add(y)
    db.flush()
    denetim.kaydet(db, k, "olustur", "kullanici", y.id, yeni=denetim.varlik_sozluk(y), ip=ip(request))
    db.commit()
    bilgi(request, f"{y.ad_soyad} eklendi. Geçici parolayı kendisine iletin; ilk girişte değiştirmesi istenir.")
    return RedirectResponse("/yonetim/kullanicilar", status_code=303)


@router.post("/kullanicilar/{kid}/durum")
def kullanici_durum(request: Request, kid: int, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db),
                    islem: str = Form(...)):
    y = db.get(Kullanici, kid)
    if not y:
        raise HTTPException(404)
    eski = {"aktif": y.aktif, "hatali_giris": y.hatali_giris, "kilit_bitis": y.kilit_bitis.isoformat() if y.kilit_bitis else None}
    if islem == "pasif":
        y.aktif = False
    elif islem == "aktif":
        y.aktif = True
    elif islem == "kilit_ac":
        yetki.kilit_ac(db, y)
    yeni = {"aktif": y.aktif, "hatali_giris": y.hatali_giris, "kilit_bitis": y.kilit_bitis.isoformat() if y.kilit_bitis else None}
    denetim.kaydet(db, k, "kilit_ac" if islem == "kilit_ac" else "guncelle", "kullanici", y.id, eski=eski, yeni=yeni, ip=ip(request))
    db.commit()
    return RedirectResponse("/yonetim/kullanicilar", status_code=303)


def _tarih(v: str) -> date | None:
    try:
        return date.fromisoformat(v) if v else None
    except ValueError:
        return None


def _denetim_sorgusu(varlik: str, kullanici: str, islem: str, baslangic: str, bitis: str):
    sorgu = select(DenetimKaydi).order_by(DenetimKaydi.id.desc())
    if varlik:
        sorgu = sorgu.where(DenetimKaydi.varlik == varlik)
    if kullanici:
        sorgu = sorgu.where(DenetimKaydi.kullanici_adi == kullanici)
    if islem:
        sorgu = sorgu.where(DenetimKaydi.islem == islem)
    b, s = _tarih(baslangic), _tarih(bitis)
    if b:
        sorgu = sorgu.where(DenetimKaydi.zaman >= datetime.combine(b, datetime.min.time()))
    if s:
        sorgu = sorgu.where(DenetimKaydi.zaman < datetime.combine(s + timedelta(days=1), datetime.min.time()))
    return sorgu


@router.get("/denetim")
def denetim_izi(request: Request, k: Kullanici = Depends(gerekli("denetim.goruntule")), db: Session = Depends(get_db),
                varlik: str = "", kullanici: str = "", islem: str = "", baslangic: str = "", bitis: str = "",
                sayfa: int = 1, bicim: str = ""):
    request.state.kullanici = k
    sorgu = _denetim_sorgusu(varlik, kullanici, islem, baslangic, bitis)
    if bicim == "csv":
        return _denetim_csv(db, k, sorgu, request)
    boyut = 50
    sayfa = max(1, sayfa)
    kayitlar = db.execute(sorgu.offset((sayfa - 1) * boyut).limit(boyut)).scalars().all()
    toplam = db.scalar(select(func.count()).select_from(sorgu.order_by(None).subquery()))
    varliklar = [v for (v,) in db.execute(select(DenetimKaydi.varlik).distinct().order_by(DenetimKaydi.varlik)).all()]
    islemler = [v for (v,) in db.execute(select(DenetimKaydi.islem).distinct().order_by(DenetimKaydi.islem)).all()]
    imzalar = db.execute(select(EImza).order_by(EImza.id.desc()).limit(10)).scalars().all()
    filtre = {"varlik": varlik, "islem": islem, "kullanici": kullanici, "baslangic": baslangic, "bitis": bitis}
    sorgu_dizgisi = "&".join(f"{a}={v}" for a, v in filtre.items() if v)
    return goster(request, "yonetim/denetim.html", kayitlar=kayitlar, toplam=toplam, sayfa=sayfa, boyut=boyut,
                  varliklar=varliklar, islemler=islemler, varlik=varlik, kullanici_f=kullanici, islem=islem,
                  baslangic=baslangic, bitis=bitis, imzalar=imzalar, sorgu_dizgisi=sorgu_dizgisi,
                  VARLIK_ETIKET=VARLIK_ETIKET, ISLEM_ETIKET=ISLEM_ETIKET)


def _denetim_csv(db: Session, k: Kullanici, sorgu, request: Request):
    """Filtreli kayitlarin tamami (en fazla 50.000 satir) noktali virgulle ayrilmis CSV; indirme denetim izine yazilir."""
    kayitlar = db.execute(sorgu.limit(50_000)).scalars().all()
    denetim.kaydet(db, k, "disa_aktar", "denetim_kaydi", None, yeni={"satir": len(kayitlar), "bicim": "csv"}, ip=ip(request))
    db.commit()
    tampon = io.StringIO()
    y = csv.writer(tampon, delimiter=";")
    y.writerow(["id", "zaman_utc", "kullanici", "islem", "varlik", "varlik_id", "aciklama", "gerekce", "ip", "eski", "yeni", "hash"])
    for d in kayitlar:
        y.writerow([d.id, d.zaman.isoformat(sep=" ", timespec="seconds"), d.kullanici_adi or "", d.islem, d.varlik,
                    d.varlik_id or "", denetim_cumle(d), d.gerekce or "", d.ip or "",
                    denetim._json(d.eski) if d.eski else "", denetim._json(d.yeni) if d.yeni else "", d.hash or ""])
    icerik = "\ufeff" + tampon.getvalue()
    ad = f"denetim_izi_{simdi():%Y%m%d_%H%M}.csv"
    return StreamingResponse(iter([icerik]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{ad}"'})


@router.post("/denetim/dogrula")
def denetim_dogrula(request: Request, k: Kullanici = Depends(gerekli("denetim.goruntule")), db: Session = Depends(get_db)):
    gecerli, bozuk = denetim.zinciri_dogrula(db)
    if gecerli:
        bilgi(request, "Denetim izi zinciri doğrulandı; bütünlük ihlali yok.")
    else:
        bilgi(request, f"UYARI: Denetim izi zinciri {bozuk} numaralı kayıtta bozulmuş. Kalite güvenceye bildirin.")
    denetim.kaydet(db, k, "dogrula", "denetim_kaydi", bozuk, yeni={"gecerli": gecerli}, ip=ip(request))
    db.commit()
    return RedirectResponse("/yonetim/denetim", status_code=303)


@router.get("/sistem")
def sistem(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db)):
    """Ayarlar: kurulum modu ve kurum varsayilanlari ust kartta, sistem bilgileri ikinci kartta."""
    from ..services.bdm import BDMIstemci

    request.state.kullanici = k
    a = ayarlar()
    istemci = BDMIstemci.olustur()
    bdm_durum = istemci.durum()
    sayilar = {t.name: db.scalar(select(func.count()).select_from(t)) for t in
               __import__("smartclinical.db", fromlist=["Taban"]).Taban.metadata.sorted_tables}
    merkezler = db.execute(select(Merkez).order_by(Merkez.ad)).scalars().all()
    sponsorlar = [x for (x,) in db.execute(select(Calisma.sponsor).distinct().order_by(Calisma.sponsor)).all() if x]
    return goster(request, "yonetim/sistem.html", a=a, surum=__version__, python=sys.version.split()[0],
                  platform=platform.platform(), bdm_durum=bdm_durum, sayilar=sayilar,
                  db_tur=a.db_url.split(":")[0], ayar=kurulum_svc.ayar_getir(db), modlar=kurulum_svc.MODLAR,
                  merkezler=merkezler, sponsorlar=sponsorlar)


@router.post("/ayarlar")
def ayarlar_kaydet(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db),
                   mod: str = Form(...), kurum_adi: str = Form(...), varsayilan_sponsor: str = Form(""),
                   varsayilan_merkez_id: str = Form("")):
    request.state.kullanici = k
    if mod not in kurulum_svc.MOD_ETIKET:
        bilgi(request, "Geçersiz kullanım modu.")
        return RedirectResponse("/yonetim/sistem", status_code=303)
    mid = int(varsayilan_merkez_id) if varsayilan_merkez_id else None
    if mid and not db.get(Merkez, mid):
        bilgi(request, "Seçilen merkez bulunamadı.")
        return RedirectResponse("/yonetim/sistem", status_code=303)
    if mod != "cro" and not mid:
        bilgi(request, "Tekil ve üniversite modlarında bir varsayılan merkez seçilmeli; önce Merkezler sayfasından ekleyin.")
        return RedirectResponse("/yonetim/sistem", status_code=303)
    eski = denetim.varlik_sozluk(db.get(kurulum_svc.KurulumAyari, 1))
    ayar = kurulum_svc.ayar_yaz(db, mod, kurum_adi, mid, varsayilan_sponsor)
    denetim.kaydet(db, k, "guncelle", "kurulum_ayari", ayar.id, eski=eski, yeni=denetim.varlik_sozluk(ayar), ip=ip(request))
    db.commit()
    bilgi(request, f"Ayarlar kaydedildi. Kullanım modu: {ayar.mod_etiket}.")
    return RedirectResponse("/yonetim/sistem", status_code=303)


# --- API anahtarlari -------------------------------------------------------

@router.get("/api-anahtarlari")
def api_anahtarlari(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db)):
    from ..models import ApiAnahtari

    request.state.kullanici = k
    liste = db.execute(select(ApiAnahtari).order_by(ApiAnahtari.id.desc())).scalars().all()
    kullanicilar = db.execute(select(Kullanici).where(Kullanici.aktif.is_(True)).order_by(Kullanici.kullanici_adi)).scalars().all()
    yeni = request.session.pop("yeni_anahtar", None)
    return goster(request, "yonetim/api_anahtarlari.html", liste=liste, kullanicilar=kullanicilar, yeni=yeni)


@router.post("/api-anahtarlari")
def api_anahtari_olustur(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db),
                         ad: str = Form(...), kullanici_id: int = Form(...), gecerlilik_gun: int = Form(365)):
    from datetime import timedelta

    from ..models import ApiAnahtari
    from ..models._ortak import simdi

    ham = yetki.api_anahtari_uret()
    a = ApiAnahtari(kullanici_id=kullanici_id, ad=ad, onek=ham[:11], hash=yetki.api_anahtari_hashle(ham),
                    son_gecerlilik=simdi() + timedelta(days=gecerlilik_gun) if gecerlilik_gun else None)
    db.add(a)
    db.flush()
    denetim.kaydet(db, k, "olustur", "api_anahtari", a.id, yeni={"ad": ad, "kullanici_id": kullanici_id, "onek": a.onek}, ip=ip(request))
    db.commit()
    request.session["yeni_anahtar"] = ham  # bir kez gosterilir
    return RedirectResponse("/yonetim/api-anahtarlari", status_code=303)


@router.post("/api-anahtarlari/{aid}/iptal")
def api_anahtari_iptal(request: Request, aid: int, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db)):
    from ..models import ApiAnahtari

    a = db.get(ApiAnahtari, aid)
    if not a:
        raise HTTPException(404)
    a.aktif = False
    denetim.kaydet(db, k, "guncelle", "api_anahtari", a.id, yeni={"aktif": False}, ip=ip(request))
    db.commit()
    return RedirectResponse("/yonetim/api-anahtarlari", status_code=303)
