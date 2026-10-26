"""HBYS / EDC entegrasyon uc noktalari (FHIR R4)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ayarlar
from ..db import get_db
from ..models import Calisma, Gonullu, Hasta, Kullanici, Merkez
from ..models._ortak import simdi
from ..services import denetim
from ..services.yetki import calisma_erisimi, gerekli, merkez_erisimi

router = APIRouter()


@router.get("/fhir/ResearchStudy/{cid}")
def research_study(cid: int, db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("disa_aktar"))):
    from ..services.fhir import calisma_to_research_study

    c = db.get(Calisma, cid)
    if not c:
        raise HTTPException(404)
    if not calisma_erisimi(db, k, c):
        raise HTTPException(403, "Bu çalışmaya erişiminiz yok")
    return calisma_to_research_study(c)


@router.get("/fhir/ResearchSubject/{gid}")
def research_subject(gid: int, db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("disa_aktar"))):
    from ..services.fhir import gonullu_to_research_subject

    g = db.get(Gonullu, gid)
    if not g:
        raise HTTPException(404)
    if not calisma_erisimi(db, k, g.calisma):
        raise HTTPException(403, "Bu çalışmaya erişiminiz yok")
    return gonullu_to_research_subject(g)


@router.post("/fhir/Bundle")
def bundle_al(bundle: dict, merkez_id: int, db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("hasta.goruntule"))):
    """HBYS'den gelen FHIR Bundle'i kimliksizlestirip Hasta tablosuna yazar."""
    from ..services.fhir import FHIRHatasi, bundle_to_hasta

    if not merkez_erisimi(k, merkez_id):
        raise HTTPException(403, "Bu merkezin hasta havuzuna erişiminiz yok")
    try:
        veri = bundle_to_hasta(bundle, merkez_id)
    except FHIRHatasi as e:
        raise HTTPException(422, str(e))
    mevcut = db.execute(select(Hasta).where(Hasta.merkez_id == merkez_id, Hasta.kayit_no == veri["kayit_no"])).scalar_one_or_none()
    h = mevcut or Hasta(merkez_id=merkez_id)
    for a, v in veri.items():
        setattr(h, a, v)
    h.son_senkron = simdi()
    db.add(h)
    db.flush()
    denetim.kaydet(db, k, "guncelle" if mevcut else "olustur", "hasta", h.id, yeni={"kayit_no": h.kayit_no, "kaynak": "fhir"})
    db.commit()
    return {"id": h.id, "kayit_no": h.kayit_no}


@router.post("/hbys/senkron")
def hbys_senkron(merkez_id: int, tani_kodlari: list[str], son_ay: int = 12, db: Session = Depends(get_db),
                 k: Kullanici = Depends(gerekli("hasta.goruntule"))):
    """Merkezin FHIR uc noktasindan belirtilen tani kodlarina sahip hastalari ceker."""
    from ..services.fhir.hbys import HBYSHatasi, adaptor_olustur

    m = db.get(Merkez, merkez_id)
    if not m:
        raise HTTPException(404, "Merkez bulunamadı")
    if not merkez_erisimi(k, merkez_id):
        raise HTTPException(403, "Bu merkezin HBYS eşitlemesini tetikleme yetkiniz yok")
    a = ayarlar()
    adaptor = adaptor_olustur(m.fhir_uc_noktasi or a.fhir_sunucu_url, a.fhir_token)
    try:
        hastalar = adaptor.hastalari_cek(tani_kodlari, son_ay=son_ay, merkez_id=merkez_id)
    except HBYSHatasi as e:
        raise HTTPException(502, str(e))
    yeni, guncel = 0, 0
    for veri in hastalar:
        mevcut = db.execute(select(Hasta).where(Hasta.merkez_id == merkez_id, Hasta.kayit_no == veri["kayit_no"])).scalar_one_or_none()
        h = mevcut or Hasta(merkez_id=merkez_id)
        for alan, v in veri.items():
            setattr(h, alan, v)
        h.son_senkron = simdi()
        db.add(h)
        guncel += mevcut is not None
        yeni += mevcut is None
    denetim.kaydet(db, k, "senkron", "merkez", merkez_id, yeni={"yeni": yeni, "guncel": guncel, "tani": tani_kodlari})
    db.commit()
    return {"yeni": yeni, "guncellenen": guncel, "kaynak": type(adaptor).__name__}
