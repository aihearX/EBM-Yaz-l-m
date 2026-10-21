import platform
import sys

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import __version__
from ..config import ayarlar
from ..db import get_db
from ..models import DenetimKaydi, EImza, Kullanici, Merkez, Rol
from ..models._ortak import simdi
from ..services import denetim, yetki
from ..services.yetki import gerekli
from ._ortak import bilgi, ip
from .sablon import goster

router = APIRouter(prefix="/yonetim")


@router.get("/kullanicilar")
def kullanicilar(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db)):
    request.state.kullanici = k
    liste = db.execute(select(Kullanici).order_by(Kullanici.rol, Kullanici.ad_soyad)).scalars().all()
    merkezler = db.execute(select(Merkez).order_by(Merkez.ad)).scalars().all()
    return goster(request, "yonetim/kullanicilar.html", liste=liste, roller=Rol, merkezler=merkezler, hata=None)


@router.post("/kullanicilar")
def kullanici_ekle(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db),
                   kullanici_adi: str = Form(...), ad_soyad: str = Form(...), eposta: str = Form(...),
                   parola: str = Form(...), rol: str = Form(...), merkez_id: str = Form("")):
    request.state.kullanici = k
    hata = yetki.parola_politikasi(parola)
    if hata:
        bilgi(request, hata)
        return RedirectResponse("/yonetim/kullanicilar", status_code=303)
    y = Kullanici(kullanici_adi=kullanici_adi.strip().lower(), ad_soyad=ad_soyad, eposta=eposta,
                  parola_hash=yetki.parola_hashle(parola), rol=Rol(rol), merkez_id=int(merkez_id) if merkez_id else None,
                  parola_degisim=simdi())
    db.add(y)
    db.flush()
    denetim.kaydet(db, k, "olustur", "kullanici", y.id, yeni=denetim.varlik_sozluk(y), ip=ip(request))
    db.commit()
    return RedirectResponse("/yonetim/kullanicilar", status_code=303)


@router.post("/kullanicilar/{kid}/durum")
def kullanici_durum(request: Request, kid: int, k: Kullanici = Depends(gerekli("kullanici.yonet")), db: Session = Depends(get_db),
                    islem: str = Form(...)):
    y = db.get(Kullanici, kid)
    if not y:
        raise HTTPException(404)
    eski = {"aktif": y.aktif, "hatali_giris": y.hatali_giris}
    if islem == "pasif":
        y.aktif = False
    elif islem == "aktif":
        y.aktif = True
    elif islem == "kilit_ac":
        y.hatali_giris = 0
    denetim.kaydet(db, k, "guncelle", "kullanici", y.id, eski=eski, yeni={"aktif": y.aktif, "hatali_giris": y.hatali_giris}, ip=ip(request))
    db.commit()
    return RedirectResponse("/yonetim/kullanicilar", status_code=303)


@router.get("/denetim")
def denetim_izi(request: Request, k: Kullanici = Depends(gerekli("denetim.goruntule")), db: Session = Depends(get_db),
                varlik: str = "", kullanici: str = "", islem: str = "", sayfa: int = 1):
    request.state.kullanici = k
    sorgu = select(DenetimKaydi).order_by(DenetimKaydi.id.desc())
    if varlik:
        sorgu = sorgu.where(DenetimKaydi.varlik == varlik)
    if kullanici:
        sorgu = sorgu.where(DenetimKaydi.kullanici_adi == kullanici)
    if islem:
        sorgu = sorgu.where(DenetimKaydi.islem == islem)
    boyut = 50
    kayitlar = db.execute(sorgu.offset((sayfa - 1) * boyut).limit(boyut)).scalars().all()
    toplam = db.scalar(select(func.count(DenetimKaydi.id)))
    varliklar = [v for (v,) in db.execute(select(DenetimKaydi.varlik).distinct().order_by(DenetimKaydi.varlik)).all()]
    islemler = [v for (v,) in db.execute(select(DenetimKaydi.islem).distinct().order_by(DenetimKaydi.islem)).all()]
    imzalar = db.execute(select(EImza).order_by(EImza.id.desc()).limit(10)).scalars().all()
    return goster(request, "yonetim/denetim.html", kayitlar=kayitlar, toplam=toplam, sayfa=sayfa, boyut=boyut,
                  varliklar=varliklar, islemler=islemler, varlik=varlik, kullanici_f=kullanici, islem=islem, imzalar=imzalar)


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
    from ..services.bdm import BDMIstemci

    request.state.kullanici = k
    a = ayarlar()
    istemci = BDMIstemci.olustur()
    bdm_durum = istemci.durum()
    sayilar = {t.name: db.scalar(select(func.count()).select_from(t)) for t in
               __import__("smartclinical.db", fromlist=["Taban"]).Taban.metadata.sorted_tables}
    return goster(request, "yonetim/sistem.html", a=a, surum=__version__, python=sys.version.split()[0],
                  platform=platform.platform(), bdm_durum=bdm_durum, sayilar=sayilar,
                  db_tur=a.db_url.split(":")[0])
