"""Dahili randomizasyon: ayar, e-imzali liste uretimi ve kol sutunu gizli ozet."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, Kullanici
from ..models._ortak import simdi
from ..models.randomizasyon import STRATA_ETIKET, RandomizasyonAyari
from ..services import denetim
from ..services import randomizasyon as rnd
from ..services.yetki import gerekli, parola_dogrula
from ._ortak import bilgi, calisma_getir, ip
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}/randomizasyon")


def _sayfa(request: Request, db: Session, c: Calisma, k: Kullanici):
    ayar = rnd.ayar_getir(db, c)
    return goster(request, "gonulluler/randomizasyon.html", c=c, ayar=ayar, ozet=rnd.ozet(db, c),
                  son_tahsis=rnd.son_tahsis(db, c), STRATA_ETIKET=STRATA_ETIKET,
                  blok_hatasi=rnd.blok_boyutu_dogrula(c, (ayar.blok_boyutu if ayar else 4)),
                  toplam_oran=sum(max(1, x.oran or 1) for x in c.kollar), kullanici=k)


@router.get("")
def goruntule(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
              db: Session = Depends(get_db)):
    return _sayfa(request, db, c, k)


@router.post("/uret")
def uret(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
         db: Session = Depends(get_db), blok_boyutu: int = Form(4), strata: str = Form("yok"),
         kayit_sayisi: str = Form(""), parola: str = Form("")):
    yol = f"/calismalar/{c.id}/randomizasyon"
    if not parola or not parola_dogrula(parola, k.parola_hash):
        bilgi(request, "E-imza için parola doğrulanamadı; liste üretilmedi.")
        return RedirectResponse(yol, status_code=303)
    ayar = rnd.ayar_getir(db, c)
    if not ayar:
        ayar = RandomizasyonAyari(calisma_id=c.id)
        db.add(ayar)
    ayar.blok_boyutu = blok_boyutu
    ayar.strata = strata if strata in rnd.STRATALAR else "yok"
    try:
        kayitlar = rnd.liste_uret(db, c, ayar.blok_boyutu, ayar.strata,
                                  kayit_sayisi=int(kayit_sayisi) if kayit_sayisi.strip().isdigit() else None)
    except ValueError as e:
        db.rollback()
        bilgi(request, str(e))
        return RedirectResponse(yol, status_code=303)
    ayar.olusturan_id = k.id
    ayar.imza_zamani = simdi()
    db.flush()
    ozet = {"blok_boyutu": ayar.blok_boyutu, "strata": ayar.strata, "kayit": len(kayitlar),
            "kollar": [x.ad for x in c.kollar]}
    # kol dizilimi denetim izine yazilmaz; imza listenin ozetini muhurler
    denetim.kaydet(db, k, "randomizasyon_listesi", "calisma", c.id, yeni=ozet, ip=ip(request))
    denetim.imzala(db, k, "randomizasyon_ayari", ayar.id, "Randomizasyon listesi üretimi",
                   {**ozet, "kayit_idleri": [x.id for x in kayitlar]}, ip=ip(request))
    db.commit()
    bilgi(request, f"Randomizasyon listesi üretildi: {len(kayitlar)} kayıt, blok boyutu {ayar.blok_boyutu}.")
    return RedirectResponse(yol, status_code=303)
