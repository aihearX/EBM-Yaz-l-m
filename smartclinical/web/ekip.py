"""Calisma ekibi: kullanici x calisma atamasi ve gorunurluk kisiti."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, Kullanici
from ..models.ekip import CalismaUyesi
from ..services import denetim
from ..services.yetki import ATANABILIR_ROLLER, MERKEZ_ROLLERI, gerekli, kisit_aktif
from ._ortak import bilgi, calisma_getir, ip, oturumlu
from .calismalar import _ozet, sekme_kontrol
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}/ekip")


def _uye(db: Session, c: Calisma, uye_id: int) -> CalismaUyesi:
    u = db.get(CalismaUyesi, uye_id)
    if not u or u.calisma_id != c.id:
        raise HTTPException(404, "Ekip üyesi bulunamadı")
    return u


@router.get("")
def sayfa(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
          db: Session = Depends(get_db), q: str = ""):
    sekme_kontrol(k, "ekip")
    uyeler = db.execute(select(CalismaUyesi).join(CalismaUyesi.kullanici).where(CalismaUyesi.calisma_id == c.id)
                        .order_by(Kullanici.ad_soyad)).scalars().all()
    uye_kid = {u.kullanici_id for u in uyeler}
    sorgu = select(Kullanici).where(Kullanici.aktif.is_(True), Kullanici.rol.in_(ATANABILIR_ROLLER)).order_by(Kullanici.ad_soyad)
    if q.strip():
        q = q.strip()
        sorgu = sorgu.where(Kullanici.ad_soyad.ilike(f"%{q}%") | Kullanici.kullanici_adi.ilike(f"%{q}%"))
    adaylar = [u for u in db.execute(sorgu).scalars() if u.id not in uye_kid]
    # arastirmaci/koordinator atanmaz; calismanin merkezlerinden biri kendi merkeziyse zaten erisir
    merkez_ids = {cm.merkez_id for cm in c.merkezler}
    merkezden = db.execute(select(Kullanici).where(Kullanici.aktif.is_(True), Kullanici.rol.in_(MERKEZ_ROLLERI),
                                                   Kullanici.merkez_id.in_(merkez_ids))
                           .order_by(Kullanici.ad_soyad)).scalars().all() if merkez_ids else []
    return goster(request, "ekip/liste.html", c=c, o=_ozet(db, c), sekme="ekip", uyeler=uyeler, adaylar=adaylar,
                  merkezden=merkezden, q=q, kisit=kisit_aktif(db))


@router.post("/ekle")
def ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("ekip.yonet")),
         db: Session = Depends(get_db), kullanici_id: int = Form(...)):
    u = db.get(Kullanici, kullanici_id)
    if not u or not u.aktif or u.rol not in ATANABILIR_ROLLER:
        bilgi(request, "UYARI: Bu kullanıcı ekibe eklenemez; yalnızca atanabilir rollerdeki aktif kullanıcılar eklenir.")
        return RedirectResponse(f"/calismalar/{c.id}/ekip", status_code=303)
    var = db.scalar(select(CalismaUyesi.id).where(CalismaUyesi.calisma_id == c.id, CalismaUyesi.kullanici_id == u.id))
    if var:
        bilgi(request, f"{u.ad_soyad} zaten ekipte.")
        return RedirectResponse(f"/calismalar/{c.id}/ekip", status_code=303)
    ilk = not kisit_aktif(db)
    uye = CalismaUyesi(calisma_id=c.id, kullanici_id=u.id, ekleyen_id=k.id)
    db.add(uye)
    db.flush()
    denetim.kaydet(db, k, "olustur", "calisma_uyesi", uye.id,
                   yeni={"calisma": c.kod, "kullanici": u.kullanici_adi, "rol": u.rol.value}, ip=ip(request))
    db.commit()
    mesaj = f"{u.ad_soyad} ekibe eklendi."
    if ilk:
        mesaj += " Bu ilk atamayla birlikte atanabilir roller yalnızca atandıkları çalışmaları görmeye başladı."
    bilgi(request, mesaj)
    return RedirectResponse(f"/calismalar/{c.id}/ekip", status_code=303)


@router.post("/{uye_id}/cikar")
def cikar(request: Request, uye_id: int, c: Calisma = Depends(calisma_getir),
          k: Kullanici = Depends(gerekli("ekip.yonet")), db: Session = Depends(get_db)):
    uye = _uye(db, c, uye_id)
    if uye.kullanici_id == k.id:
        bilgi(request, "UYARI: Kendinizi ekipten çıkaramazsınız; bunu başka bir proje yöneticisi veya sistem yöneticisi yapmalı.")
        return RedirectResponse(f"/calismalar/{c.id}/ekip", status_code=303)
    u = uye.kullanici
    denetim.kaydet(db, k, "sil", "calisma_uyesi", uye.id,
                   eski={"calisma": c.kod, "kullanici": u.kullanici_adi, "rol": u.rol.value}, ip=ip(request))
    db.delete(uye)
    db.commit()
    bilgi(request, f"{u.ad_soyad} ekipten çıkarıldı.")
    return RedirectResponse(f"/calismalar/{c.id}/ekip", status_code=303)
