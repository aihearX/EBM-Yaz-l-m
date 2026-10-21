"""Sponsor portali: salt okunur portfoy gorunumu ve merkez performans endeksi."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, CalismaDurumu, GonulluDurumu, Kullanici, RiskUyarisi, Rol
from ..services import denetim, kiyaslama
from ._ortak import ip, oturumlu
from .sablon import goster

router = APIRouter()
KAYITLI = (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE, GonulluDurumu.TAMAMLADI)


@router.get("/sponsor")
def portal(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    if k.rol not in (Rol.SPONSOR, Rol.YONETICI, Rol.PROJE_YONETICISI):
        raise HTTPException(403, "Sponsor portalı yalnızca sponsor ve proje yönetimi rollerine açıktır")
    sorgu = select(Calisma).where(Calisma.durum != CalismaDurumu.ARSIV)
    if k.rol == Rol.SPONSOR and k.kurum:
        sorgu = sorgu.where(Calisma.sponsor == k.kurum)
    calismalar = db.scalars(sorgu.order_by(Calisma.kod)).all()
    bugun = date.today()
    satirlar = []
    for c in calismalar:
        kayitli = sum(1 for g in c.gonulluler if g.durum in KAYITLI)
        aktif = [m for m in c.merkezler if m.durum == "aktif"]
        hiz = sum(m.tahmini_kazanim or 0 for m in aktif)
        kalan = max(0, c.hedef_hasta - kayitli)
        tahmini_ay = (kalan / hiz) if hiz else None
        uyarilar = db.scalars(select(RiskUyarisi).where(RiskUyarisi.calisma_id == c.id, RiskUyarisi.durum == "acik")).all()
        sae = [a for g in c.gonulluler for a in g.advers_olaylar if a.ciddi]
        plan_ay = ((c.planlanan_bitis - bugun).days / 30.4) if c.planlanan_bitis else None
        satirlar.append({
            "c": c, "kayitli": kayitli, "oran": (100 * kayitli / c.hedef_hasta) if c.hedef_hasta else 0,
            "aktif_merkez": len(aktif), "hiz": hiz, "tahmini_ay": tahmini_ay, "plan_ay": plan_ay,
            "takvim": ("zamaninda" if tahmini_ay is not None and plan_ay is not None and tahmini_ay <= plan_ay else
                       ("risk" if tahmini_ay is not None and plan_ay is not None else "belirsiz")),
            "uyari": len(uyarilar), "aksiyon": sum(1 for u in uyarilar if u.seviye == "aksiyon"),
            "sae": len(sae), "bekleyen_sae": sum(1 for a in sae if not a.titck_bildirim),
            "en_riskli": max(aktif, key=lambda m: m.risk_puani or 0) if aktif else None,
        })
    denetim.kaydet(db, k, "goruntule", "sponsor_portal", None, yeni={"calisma": len(satirlar)}, ip=ip(request))
    db.commit()
    return goster(request, "sponsor/portal.html", satirlar=satirlar, bugun=bugun)


@router.get("/merkezler/endeks")
def merkez_endeksi(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    anonim = k.rol in (Rol.SPONSOR, Rol.DENETCI)
    e = kiyaslama.endeks(db, anonim=anonim)
    return goster(request, "merkezler/endeks.html", e=e, anonim=anonim)
