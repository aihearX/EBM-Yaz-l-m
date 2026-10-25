"""Web katmani icin ortak bagimliliklar."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, Kullanici
from ..services.yetki import calisma_erisimi, mevcut_kullanici


def oturumlu(request: Request, k: Kullanici = Depends(mevcut_kullanici)) -> Kullanici:
    request.state.kullanici = k
    return k


def calisma_getir(calisma_id: int, request: Request, db: Session = Depends(get_db),
                  k: Kullanici = Depends(mevcut_kullanici)) -> Calisma:
    """/calismalar/{id}/* altindaki tum sayfalarin tek giris noktasi; erisim kurali yetki.calisma_erisimi'dir."""
    c = db.get(Calisma, calisma_id)
    if not c:
        raise HTTPException(404, "Çalışma bulunamadı")
    if not calisma_erisimi(db, k, c):
        raise HTTPException(403, "Bu çalışmaya erişiminiz yok")
    request.state.kullanici = k
    return c


def bilgi(request: Request, metin: str):
    request.session["mesaj"] = metin


def ip(request: Request) -> str | None:
    return request.client.host if request.client else None
