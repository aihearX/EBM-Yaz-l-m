from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from ..config import ayarlar
from ..db import get_db
from ..models import Kullanici
from ..services import denetim
from ..services.yetki import gerekli
from ._ortak import ip, oturumlu
from .sablon import goster

router = APIRouter(prefix="/araclar")

ORNEK_METIN = """HASTA: Ayşe Yılmaz  TC: 10000000146  Doğum: 14.03.1962  Protokol No: 2024/88213
Tel: 0532 417 22 85   Adres: Çankaya / Ankara

EPİKRİZ
58 yaşında kadın hasta, Marmara Kuzey Üniversitesi Tıp Fakültesi Hastanesi'ne sol memede ele gelen kitle şikayetiyle 02.05.2024 tarihinde başvurdu. Tru-cut biyopsi sonucu invaziv duktal karsinom, ER (+) %90, PR (+) %60, HER2 negatif (IHC 1+), Ki-67 %25. ECOG performans skoru 1. Evreleme PET-BT'de uzak metastaz saptanmadı; klinik evre T2N1M0.
Laboratuvar: Hb 11,8 g/dL, nötrofil 2,9 x10³/µL, trombosit 215 x10³/µL, kreatinin 0,8 mg/dL, AST 24 U/L, ALT 19 U/L.
Özgeçmiş: 8 yıldır tip 2 diyabet, metformin 2x1000 mg kullanıyor. Bilinen kalp hastalığı yok. Gebe değil, postmenopozal.
Dr. Mehmet Kaya tarafından neoadjuvan kemoterapi planlandı. Kontrol: 16.05.2024."""


@router.get("/kimliksizlestirme")
def kimliksizlestirme_sayfa(request: Request, k: Kullanici = Depends(oturumlu)):
    return goster(request, "araclar/kimliksizlestirme.html", metin=ORNEK_METIN, sonuc=None, mod="maske")


@router.post("/kimliksizlestirme")
def kimliksizlestirme_calistir(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db),
                               metin: str = Form(...), mod: str = Form("maske")):
    from ..services.kimliksizlestirme import kimliksizlestir, metni_dogrula

    sonuc = kimliksizlestir(metin, mod=mod)
    uyarilar = metni_dogrula(sonuc.metin)
    denetim.kaydet(db, k, "kimliksizlestir", "metin", None,
                   yeni={"mod": mod, "uzunluk": len(metin), "bulgu": dict(sonuc.istatistik)}, ip=ip(request))
    db.commit()
    return goster(request, "araclar/kimliksizlestirme.html", metin=metin, sonuc=sonuc, mod=mod, uyarilar=uyarilar)


@router.get("/bdm")
def bdm_sayfa(request: Request, k: Kullanici = Depends(gerekli("bdm.kullan"))):
    request.state.kullanici = k
    a = ayarlar()
    return goster(request, "araclar/bdm.html", a=a, gorev="kriter", girdi="", baglam="", cikti=None, meta=None)


@router.post("/bdm")
def bdm_calistir(request: Request, k: Kullanici = Depends(gerekli("bdm.kullan")), db: Session = Depends(get_db),
                 gorev: str = Form("kriter"), girdi: str = Form(...), baglam: str = Form("")):
    import json
    import time

    from ..services.bdm import BDMIstemci

    request.state.kullanici = k
    a = ayarlar()
    istemci = BDMIstemci.olustur()
    t0 = time.perf_counter()
    cikti, meta = None, {}
    if gorev == "kriter":
        y = istemci.kriter_yapilandir(girdi, "dahil")
        cikti = json.dumps(y.to_dict(), ensure_ascii=False, indent=2)
        meta = {"yontem": y.yontem, "guven": y.guven, "kategori": y.kategori}
    elif gorev == "kanit":
        parcalar = [p.strip() for p in baglam.split("\n\n") if p.strip()] or [baglam]
        ks = istemci.kanit_cikar(girdi, parcalar)
        cikti = json.dumps({"sonuc": ks.sonuc, "kanit_cumlesi": ks.kanit_cumlesi, "guven": ks.guven,
                            "parca_indeks": ks.parca_indeks}, ensure_ascii=False, indent=2)
        meta = {"guven": ks.guven}
    elif gorev == "ozet":
        cikti = "\n".join(f"- {m}" for m in istemci.klinik_ozet(girdi))
    else:
        cikti = json.dumps(istemci.soru_cevap(girdi, baglam), ensure_ascii=False, indent=2)
    meta["sure_ms"] = int((time.perf_counter() - t0) * 1000)
    meta["model"] = istemci.model_adi
    denetim.kaydet(db, k, "bdm", "bdm", None, yeni={"gorev": gorev, "uzunluk": len(girdi), "model": istemci.model_adi,
                   "sure_ms": meta["sure_ms"]}, ip=ip(request))
    db.commit()
    return goster(request, "araclar/bdm.html", a=a, gorev=gorev, girdi=girdi, baglam=baglam, cikti=cikti, meta=meta)
