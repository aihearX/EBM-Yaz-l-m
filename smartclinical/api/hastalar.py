
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Hasta, Kullanici
from ..models._ortak import simdi
from ..services import denetim
from ..services.yetki import gerekli
from . import semalar

router = APIRouter(prefix="/hastalar")


@router.post("", status_code=201)
def hasta_ekle(g: semalar.HastaGirdi, db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("hasta.goruntule"))):
    """Kimliksizlestirilmis hasta kaydi ekler. Metinler kaydedilmeden once tekrar kimliksizlestirme suzgecinden gecer."""
    from ..services.kimliksizlestirme import kimliksizlestir, metni_dogrula

    metinler = []
    for m in g.metinler:
        s = kimliksizlestir(m.get("metin", ""), mod="maske")
        if metni_dogrula(s.metin):
            raise HTTPException(422, "Metinde kimlik verisi şüphesi var; kayıt reddedildi.")
        metinler.append({**m, "metin": s.metin})
    mevcut = db.execute(select(Hasta).where(Hasta.merkez_id == g.merkez_id, Hasta.kayit_no == g.kayit_no)).scalar_one_or_none()
    h = mevcut or Hasta(merkez_id=g.merkez_id, kayit_no=g.kayit_no)
    h.dogum_yili, h.cinsiyet, h.tanilar, h.ilaclar, h.laboratuvar = g.dogum_yili, g.cinsiyet, g.tanilar, g.ilaclar, g.laboratuvar
    h.performans, h.metinler, h.kaynak, h.son_senkron = g.performans, metinler, "api", simdi()
    db.add(h)
    db.flush()
    denetim.kaydet(db, k, "guncelle" if mevcut else "olustur", "hasta", h.id, yeni={"kayit_no": h.kayit_no, "api": True})
    db.commit()
    return {"id": h.id, "kayit_no": h.kayit_no, "guncellendi": mevcut is not None}


@router.get("/{hid}")
def hasta(hid: int, db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("hasta.goruntule"))):
    h = db.get(Hasta, hid)
    if not h:
        raise HTTPException(404)
    denetim.kaydet(db, k, "goruntule", "hasta", h.id, yeni={"api": True})
    db.commit()
    return {"id": h.id, "kayit_no": h.kayit_no, "merkez_id": h.merkez_id, "yas": h.yas, "cinsiyet": h.cinsiyet,
            "tanilar": h.tanilar, "ilaclar": h.ilaclar, "laboratuvar": h.laboratuvar, "performans": h.performans,
            "metin_sayisi": len(h.metinler or [])}
