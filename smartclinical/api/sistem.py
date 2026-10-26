from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import __version__
from ..config import ayarlar
from ..db import get_db
from ..models import Kullanici
from ..services.yetki import mevcut_kullanici

router = APIRouter()


@router.get("/saglik")
def saglik(db: Session = Depends(get_db)):
    """Yuk dengeleyici / izleme icin. Kimlik dogrulama gerektirmez; bu yuzden surum ve ortam bilgisi vermez."""
    db.execute(text("SELECT 1"))
    return {"durum": "ok"}


@router.get("/surum")
def surum(k: Kullanici = Depends(mevcut_kullanici)):
    """Surum ve ortam bilgisi yalnizca oturumlu kullaniciya."""
    a = ayarlar()
    return {"urun": "EBM SmartClinical", "surum": __version__, "api": "v1", "ortam": a.ortam, "bdm": a.bdm_saglayici}
