from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import denetim, yetki
from ._ortak import ip
from .sablon import goster

router = APIRouter()


@router.get("/giris")
def giris_formu(request: Request, sonraki: str = "/"):
    if request.session.get("kid"):
        return RedirectResponse("/", status_code=303)
    return goster(request, "giris.html", sonraki=sonraki, hata=None)


@router.post("/giris")
def giris(request: Request, kullanici_adi: str = Form(...), parola: str = Form(...),
          sonraki: str = Form("/"), db: Session = Depends(get_db)):
    k = yetki.giris_yap(db, kullanici_adi.strip(), parola)
    if not k:
        denetim.kaydet(db, None, "giris_basarisiz", "kullanici", yeni={"kullanici_adi": kullanici_adi}, ip=ip(request))
        db.commit()
        return goster(request, "giris.html", sonraki=sonraki,
                      hata="Kullanıcı adı veya parola hatalı. 5 hatalı denemeden sonra hesap kilitlenir.")
    request.session["kid"] = k.id
    denetim.kaydet(db, k, "giris", "kullanici", k.id, ip=ip(request))
    db.commit()
    if not sonraki.startswith("/") or sonraki.startswith("//"):
        sonraki = "/"
    return RedirectResponse(sonraki, status_code=303)


@router.get("/cikis")
def cikis(request: Request, db: Session = Depends(get_db)):
    kid = request.session.get("kid")
    if kid:
        from ..models import Kullanici

        k = db.get(Kullanici, kid)
        denetim.kaydet(db, k, "cikis", "kullanici", kid, ip=ip(request))
        db.commit()
    request.session.clear()
    return RedirectResponse("/giris", status_code=303)
