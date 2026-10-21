"""Web katmani icin ortak bagimliliklar."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, Kullanici
from ..services.yetki import mevcut_kullanici


def oturumlu(request: Request, k: Kullanici = Depends(mevcut_kullanici)) -> Kullanici:
    request.state.kullanici = k
    return k


def calisma_getir(calisma_id: int, db: Session = Depends(get_db)) -> Calisma:
    c = db.get(Calisma, calisma_id)
    if not c:
        raise HTTPException(404, "Çalışma bulunamadı")
    return c


def bilgi(request: Request, metin: str):
    request.session["mesaj"] = metin


def ip(request: Request) -> str | None:
    return request.client.host if request.client else None
