from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import __version__
from ..config import ayarlar
from ..db import get_db

router = APIRouter()


@router.get("/saglik")
def saglik(db: Session = Depends(get_db)):
    """Yuk dengeleyici / izleme icin. Kimlik dogrulama gerektirmez."""
    db.execute(text("SELECT 1"))
    a = ayarlar()
    return {"durum": "ok", "surum": __version__, "ortam": a.ortam, "bdm": a.bdm_saglayici}


@router.get("/surum")
def surum():
    return {"urun": "EBM SmartClinical", "surum": __version__, "api": "v1"}
