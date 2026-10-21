from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Arastirmaci, Hasta, Kullanici, Merkez
from ..services import denetim
from ..services.yetki import gerekli
from ._ortak import ip, oturumlu
from .sablon import goster

router = APIRouter(prefix="/merkezler")


def _performans(m: Merkez) -> dict:
    """Merkezin gecmis calismalardaki performans ozeti (merkez zekasi girdisi)."""
    cms = m.calismalar
    toplam_kayit = 0
    toplam_ay = 0.0
    akt_sureleri = []
    for cm in cms:
        kayitli = [g for g in cm.gonulluler if g.randomizasyon_tarihi]
        toplam_kayit += len(kayitli)
        if cm.aktivasyon_tarihi:
            bitis = date.today()
            toplam_ay += max(0.5, (bitis - cm.aktivasyon_tarihi).days / 30.4)
            if cm.secim_tarihi:
                akt_sureleri.append((cm.aktivasyon_tarihi - cm.secim_tarihi).days)
    return {
        "calisma": len(cms), "kayit": toplam_kayit,
        "hasta_ay": (toplam_kayit / toplam_ay) if toplam_ay else None,
        "aktivasyon_gun": (sum(akt_sureleri) / len(akt_sureleri)) if akt_sureleri else None,
    }


@router.get("")
def liste(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db), q: str = ""):
    sorgu = select(Merkez).order_by(Merkez.ad)
    if q:
        sorgu = sorgu.where(Merkez.ad.ilike(f"%{q}%") | Merkez.sehir.ilike(f"%{q}%"))
    merkezler = db.execute(sorgu).scalars().all()
    satirlar = [{"m": m, "p": _performans(m), "hasta": db.scalar(select(Hasta.id).where(Hasta.merkez_id == m.id).limit(1)) is not None}
                for m in merkezler]
    return goster(request, "merkezler/liste.html", satirlar=satirlar, q=q)


@router.get("/{mid}")
def detay(request: Request, mid: int, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    m = db.get(Merkez, mid)
    if not m:
        raise HTTPException(404)
    hasta_n = len(db.execute(select(Hasta.id).where(Hasta.merkez_id == m.id)).all())
    return goster(request, "merkezler/detay.html", m=m, p=_performans(m), hasta_n=hasta_n)


@router.post("")
def ekle(request: Request, k: Kullanici = Depends(gerekli("merkez.yonet")), db: Session = Depends(get_db),
         kod: str = Form(...), ad: str = Form(...), sehir: str = Form(...), kurum_tipi: str = Form(...),
         yatak_sayisi: str = Form(""), hbys: str = Form(""), terapotik_alanlar: str = Form("")):
    m = Merkez(kod=kod.strip().upper(), ad=ad, sehir=sehir, kurum_tipi=kurum_tipi,
               yatak_sayisi=int(yatak_sayisi) if yatak_sayisi else None, hbys=hbys or None,
               terapotik_alanlar=[t.strip() for t in terapotik_alanlar.split(",") if t.strip()] or None)
    db.add(m)
    db.flush()
    denetim.kaydet(db, k, "olustur", "merkez", m.id, yeni=denetim.varlik_sozluk(m), ip=ip(request))
    db.commit()
    return RedirectResponse(f"/merkezler/{m.id}", status_code=303)


@router.post("/{mid}/arastirmaci")
def arastirmaci_ekle(request: Request, mid: int, k: Kullanici = Depends(gerekli("merkez.yonet")), db: Session = Depends(get_db),
                     ad_soyad: str = Form(...), unvan: str = Form(""), uzmanlik: str = Form(""), gcp_egitim_tarihi: str = Form("")):
    a = Arastirmaci(merkez_id=mid, ad_soyad=ad_soyad, unvan=unvan or None, uzmanlik=uzmanlik or None,
                    gcp_egitim_tarihi=date.fromisoformat(gcp_egitim_tarihi) if gcp_egitim_tarihi else None)
    db.add(a)
    db.flush()
    denetim.kaydet(db, k, "olustur", "arastirmaci", a.id, yeni={"merkez_id": mid, "ad_soyad": ad_soyad}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/merkezler/{mid}", status_code=303)
