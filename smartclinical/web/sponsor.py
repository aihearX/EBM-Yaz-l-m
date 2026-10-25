"""Merkez performans endeksi (sponsor ve denetci icin anonim). Sponsor portfoy ozeti genel bakista."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Kullanici, Rol
from ..services import kiyaslama
from ._ortak import oturumlu
from .sablon import goster

router = APIRouter()


@router.get("/merkezler/endeks")
def merkez_endeksi(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    anonim = k.rol in (Rol.SPONSOR, Rol.DENETCI)
    e = kiyaslama.endeks(db, anonim=anonim)
    return goster(request, "merkezler/endeks.html", e=e, anonim=anonim)
