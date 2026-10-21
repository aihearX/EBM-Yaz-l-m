"""Ar-Ge gostergeleri paneli: model performansi, hedefler ve etki hesaplayici."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import ayarlar
from ..db import get_db
from ..models import Kullanici
from ..services import arge
from ._ortak import oturumlu
from .sablon import goster

router = APIRouter(prefix="/arge")


@router.get("")
def gostergeler(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    g = arge.tum_gostergeler(db)
    a = ayarlar()
    return goster(request, "arge/gostergeler.html", g=g, bdm=a.bdm_saglayici, bdm_model=a.bdm_model)
