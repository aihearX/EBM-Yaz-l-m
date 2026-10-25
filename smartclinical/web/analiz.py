"""On analiz sayfalari: veri durumu, gonullu akisi, degisken ozetleri, kol karsilastirmasi, AE ozeti, veri seti."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, Kullanici, Rol
from ..services import analiz, denetim
from ..services.yetki import mevcut_kullanici
from ._ortak import calisma_getir, ip
from .calismalar import _ozet
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}/analiz")

# TODO(mert): yetki.IZINLER'e 'analiz.goruntule' olarak tasinacak; o zaman gerekli("analiz.goruntule") kullanilir
ROLLER = {Rol.YONETICI, Rol.PROJE_YONETICISI, Rol.ARASTIRMACI, Rol.VERI_YONETICISI, Rol.ISTATISTIKCI}

ON_ANALIZ_NOTU = "Bu sayfa ön analiz içindir; nihai analiz istatistiksel analiz planına göre yapılır."


def yetkili(request: Request, k: Kullanici = Depends(mevcut_kullanici)) -> Kullanici:
    if k.rol not in ROLLER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Analiz sayfaları rolünüze açık değil")
    request.state.kullanici = k
    return k


def _ortak(db: Session, c: Calisma) -> dict:
    return {"c": c, "o": _ozet(db, c), "sekme": "analiz", "durum": analiz.veri_durumu(c), "on_analiz_notu": ON_ANALIZ_NOTU,
            "kol_yok": analiz.KOL_YOK}


@router.get("")
def ozet(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(yetkili),
         db: Session = Depends(get_db), degisken: str | None = None, vizit: str | None = None):
    liste = analiz.degiskenler(c)
    formlar: dict[str, list] = {}
    for d in liste:
        formlar.setdefault(d["form"], []).append(d)
    secili = None
    if degisken:
        secili = analiz.degisken_analizi(c, degisken, vizit or None)
        if secili is None:
            raise HTTPException(404, "Değişken bulunamadı")
    return goster(request, "analiz/ozet.html", **_ortak(db, c), akis=analiz.gonullu_akisi(c), formlar=formlar,
                  degisken_sayisi=len(liste), degisken=degisken or "", vizit=vizit or "", secili=secili)


@router.get("/advers-olaylar")
def advers_olaylar(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(yetkili),
                   db: Session = Depends(get_db)):
    return goster(request, "analiz/advers_olaylar.html", **_ortak(db, c), ae=analiz.advers_olay_ozeti(c))


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
    sutunlar, satirlar = analiz.veri_seti(c)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\n")
    w.writerow(sutunlar)
    for s in satirlar:
        w.writerow([_hucre(s[k]) for k in sutunlar])
    denetim.kaydet(db, k, "disa_aktar", "calisma", c.id, yeni={"calisma": c.kod, "bicim": "analiz_csv", "satir": len(satirlar)},
                   ip=ip(request))
    db.commit()
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{c.kod}_analiz_veri_seti.csv"'})
