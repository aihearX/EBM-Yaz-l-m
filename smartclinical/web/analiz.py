"""On analiz sayfalari: veri durumu, gonullu akisi, degisken ozetleri, kol karsilastirmasi, vizitler arasi
degisim, baslangic ozeti (Tablo 1), AE ozeti, veri seti."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, Kullanici
from ..services import analiz, denetim
from ..services.yetki import MERKEZ_ROLLERI, gerekli
from ._ortak import calisma_getir, ip
from .calismalar import _ozet
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}/analiz")

ON_ANALIZ_NOTU = "Bu sayfa ön analiz içindir; nihai analiz istatistiksel analiz planına göre yapılır."
MERKEZ_NOTU = "Yalnızca merkezinizin gönüllüleri gösteriliyor; çalışma geneli için proje yöneticisine başvurun."


def yetkili(request: Request, k: Kullanici = Depends(gerekli("analiz.goruntule"))) -> Kullanici:
    """Erisim kurali yetki.IZINLER['analiz.goruntule']; sekme gorunurlugu de ayni izne bakar."""
    request.state.kullanici = k
    return k


def _merkez_siniri(k: Kullanici) -> int | None:
    """Arastirmaci / koordinator yalnizca kendi merkezinin verisini gorur."""
    return k.merkez_id if k.rol in MERKEZ_ROLLERI and k.merkez_id else None


def _ortak(db: Session, c: Calisma, k: Kullanici) -> dict:
    merkez_id = _merkez_siniri(k)
    return {"c": c, "o": _ozet(db, c), "sekme": "analiz", "durum": analiz.veri_durumu(c, merkez_id),
            "on_analiz_notu": ON_ANALIZ_NOTU, "kol_yok": analiz.KOL_YOK, "merkez_id": merkez_id,
            "merkez_notu": MERKEZ_NOTU if merkez_id else None}


def _vizit_secenekleri(c: Calisma, liste: list[dict]) -> list[str]:
    """Semadaki vizitler; sema yoksa kayitlarda gozlenen vizitlerin birlesimi."""
    adlar = analiz.vizit_adlari(c)
    if adlar:
        return adlar
    gorulen: list[str] = []
    for d in liste:
        for v in d["vizitler"]:
            if v not in gorulen:
                gorulen.append(v)
    return gorulen


@router.get("")
def ozet(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(yetkili),
         db: Session = Depends(get_db), degisken: str | None = None, vizit: str | None = None,
         mod: str | None = None, vizit1: str | None = None, vizit2: str | None = None):
    merkez_id = _merkez_siniri(k)
    liste = analiz.degiskenler(c, merkez_id)
    formlar: dict[str, list] = {}
    for d in liste:
        formlar.setdefault(d["form"], []).append(d)
    vizitler = _vizit_secenekleri(c, liste)
    varsayilan = analiz.varsayilan_vizit(c) or (vizitler[0] if vizitler else None)
    tek_kollu = len(c.kollar) <= 1
    if mod not in ("vizit", "degisim"):
        # tek kollu calismada kol karsilastirmasi anlamsiz; varsayilan gorunum vizitler arasi degisim
        mod = "degisim" if tek_kollu and len(vizitler) >= 2 else "vizit"
    if vizit is None:
        vizit = varsayilan or analiz.TUM_VIZITLER
    secili = None
    if degisken and mod == "degisim":
        v1 = vizit1 or varsayilan or (vizitler[0] if vizitler else "")
        sonrakiler = vizitler[vizitler.index(v1) + 1:] if v1 in vizitler else vizitler
        v2 = vizit2 or (sonrakiler[0] if sonrakiler else (vizitler[-1] if vizitler else ""))
        vizit1, vizit2 = v1, v2
        secili = analiz.vizit_degisimi(c, degisken, v1, v2, merkez_id)
    elif degisken:
        secili = analiz.degisken_analizi(c, degisken, None if vizit in ("", analiz.TUM_VIZITLER) else vizit, merkez_id)
    if degisken and secili is None:
        raise HTTPException(404, "Değişken bulunamadı")
    return goster(request, "analiz/ozet.html", **_ortak(db, c, k), akis=analiz.gonullu_akisi(c, merkez_id), formlar=formlar,
                  degisken_sayisi=len(liste), degisken=degisken or "", vizit=vizit, vizitler=vizitler, mod=mod,
                  vizit1=vizit1 or "", vizit2=vizit2 or "", secili=secili, tek_kollu=tek_kollu, varsayilan_vizit=varsayilan,
                  TUM=analiz.TUM_VIZITLER)


@router.get("/tablo1")
def tablo1(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(yetkili),
           db: Session = Depends(get_db), vizit: str | None = None):
    merkez_id = _merkez_siniri(k)
    vizitler = _vizit_secenekleri(c, analiz.degiskenler(c, merkez_id))
    if vizit is None:
        vizit = analiz.varsayilan_vizit(c) or (vizitler[0] if vizitler else analiz.TUM_VIZITLER)
    t = analiz.tablo1(c, None if vizit in ("", analiz.TUM_VIZITLER) else vizit, merkez_id)
    return goster(request, "analiz/tablo1.html", **_ortak(db, c, k), t=t, vizit=vizit, vizitler=vizitler,
                  TUM=analiz.TUM_VIZITLER)


@router.get("/tablo1.csv")
def tablo1_csv(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(yetkili),
               db: Session = Depends(get_db), vizit: str | None = None):
    merkez_id = _merkez_siniri(k)
    if vizit is None:
        vizit = analiz.varsayilan_vizit(c) or analiz.TUM_VIZITLER
    secili = None if vizit in ("", analiz.TUM_VIZITLER) else vizit
    t = analiz.tablo1(c, secili, merkez_id)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\n")
    for satir in analiz.tablo1_csv_satirlari(t):
        w.writerow(satir)
    denetim.kaydet(db, k, "disa_aktar", "calisma", c.id, yeni={"calisma": c.kod, "bicim": "tablo1_csv", "vizit": secili or "tum",
                   "satir": len(t["satirlar"]), "merkez_id": merkez_id}, ip=ip(request))
    db.commit()
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{c.kod}_tablo1.csv"'})


@router.get("/advers-olaylar")
def advers_olaylar(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(yetkili),
                   db: Session = Depends(get_db)):
    return goster(request, "analiz/advers_olaylar.html", **_ortak(db, c, k), ae=analiz.advers_olay_ozeti(c, _merkez_siniri(k)))


def _hucre(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return (str(int(v)) if v.is_integer() else f"{v}").replace(".", ",")
    return str(v)


@router.get("/veri-seti.csv")
def veri_seti_csv(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(yetkili),
                  db: Session = Depends(get_db)):
    """Analiz veri seti: her satir bir form kaydi; taslaklar haric. Noktali virgul ayracli, ondalik virgul."""
    merkez_id = _merkez_siniri(k)
    sutunlar, satirlar = analiz.veri_seti(c, merkez_id)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\n")
    w.writerow(sutunlar)
    for s in satirlar:
        w.writerow([_hucre(s[kk]) for kk in sutunlar])
    denetim.kaydet(db, k, "disa_aktar", "calisma", c.id, yeni={"calisma": c.kod, "bicim": "analiz_csv", "satir": len(satirlar),
                   "merkez_id": merkez_id}, ip=ip(request))
    db.commit()
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{c.kod}_analiz_veri_seti.csv"'})
