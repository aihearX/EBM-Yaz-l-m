from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Kullanici
from ..services import denetim
from ..services.yetki import gerekli
from ._ortak import ip
from .sablon import goster

router = APIRouter(prefix="/araclar")

# Arac sayfasi yonetim menusunde; ornek metin sentetiktir, gercek hasta verisi burada islenmez.

ORNEK_METIN = """HASTA: Ayşe Yılmaz  TC: 10000000146  Doğum: 14.03.1962  Protokol No: 2024/88213
Tel: 0532 417 22 85   Adres: Çankaya / Ankara

EPİKRİZ
58 yaşında kadın hasta, Marmara Kuzey Üniversitesi Tıp Fakültesi Hastanesi'ne sol memede ele gelen kitle şikayetiyle 02.05.2024 tarihinde başvurdu. Tru-cut biyopsi sonucu invaziv duktal karsinom, ER (+) %90, PR (+) %60, HER2 negatif (IHC 1+), Ki-67 %25. ECOG performans skoru 1. Evreleme PET-BT'de uzak metastaz saptanmadı; klinik evre T2N1M0.
Laboratuvar: Hb 11,8 g/dL, nötrofil 2,9 x10³/µL, trombosit 215 x10³/µL, kreatinin 0,8 mg/dL, AST 24 U/L, ALT 19 U/L.
Özgeçmiş: 8 yıldır tip 2 diyabet, metformin 2x1000 mg kullanıyor. Bilinen kalp hastalığı yok. Gebe değil, postmenopozal.
Dr. Mehmet Kaya tarafından neoadjuvan kemoterapi planlandı. Kontrol: 16.05.2024."""


@router.get("/kimliksizlestirme")
def kimliksizlestirme_sayfa(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet"))):
    request.state.kullanici = k
    return goster(request, "araclar/kimliksizlestirme.html", metin=ORNEK_METIN, sonuc=None, mod="maske")


@router.post("/kimliksizlestirme")
def kimliksizlestirme_calistir(request: Request, k: Kullanici = Depends(gerekli("kullanici.yonet")),
                               db: Session = Depends(get_db), metin: str = Form(...), mod: str = Form("maske")):
    request.state.kullanici = k
    from ..services.kimliksizlestirme import kimliksizlestir, metni_dogrula

    sonuc = kimliksizlestir(metin, mod=mod)
    uyarilar = metni_dogrula(sonuc.metin)
    denetim.kaydet(db, k, "kimliksizlestir", "metin", None,
                   yeni={"mod": mod, "uzunluk": len(metin), "bulgu": dict(sonuc.istatistik)}, ip=ip(request))
    db.commit()
    return goster(request, "araclar/kimliksizlestirme.html", metin=metin, sonuc=sonuc, mod=mod, uyarilar=uyarilar)
