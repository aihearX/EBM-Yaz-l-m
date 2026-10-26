"""Hesap: parola degisimi. Ilk giriste ve parola suresi dolunca zorunlu (bkz. yetki.mevcut_kullanici)."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Kullanici
from ..services import denetim, yetki
from ..services.yetki import mevcut_kullanici
from ._ortak import bilgi, ip
from .sablon import goster

router = APIRouter(prefix="/hesap")


def _sayfa(request: Request, k: Kullanici, hata: str | None = None):
    request.state.kullanici = k
    return goster(request, "hesap/parola.html", hata=hata, zorunlu=yetki.parola_degisimi_gerekli(k),
                  en_az=yetki.parola_min(), gun=yetki.parola_gun(), gecmis=yetki.PAROLA_GECMISI)


@router.get("/parola")
def parola_formu(request: Request, k: Kullanici = Depends(mevcut_kullanici)):
    return _sayfa(request, k)


@router.post("/parola")
def parola_kaydet(request: Request, k: Kullanici = Depends(mevcut_kullanici), db: Session = Depends(get_db),
                  eski: str = Form(...), yeni: str = Form(...), yeni_tekrar: str = Form("")):
    if yeni_tekrar and yeni != yeni_tekrar:
        return _sayfa(request, k, "Yeni parola tekrarıyla uyuşmuyor.")
    hata = yetki.parola_degistir(db, k, eski, yeni)
    if hata:
        db.rollback()
        return _sayfa(request, k, hata)
    denetim.kaydet(db, k, "parola_degistir", "kullanici", k.id, yeni={"kullanici_adi": k.kullanici_adi}, ip=ip(request))
    db.commit()
    bilgi(request, "Parolanız değiştirildi.")
    return RedirectResponse("/", status_code=303)
