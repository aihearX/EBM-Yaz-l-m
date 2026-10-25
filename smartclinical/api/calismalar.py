
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, GonulluDurumu, Kriter, Kullanici, RiskUyarisi
from ..models._ortak import simdi
from ..services import denetim
from ..services.yetki import calisma_erisimi, calisma_filtresi, gerekli, mevcut_kullanici
from . import semalar

router = APIRouter()

KAYITLI = (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE, GonulluDurumu.TAMAMLADI)


def _c(db: Session, cid: int, k: Kullanici) -> Calisma:
    c = db.get(Calisma, cid)
    if not c:
        raise HTTPException(404, "Çalışma bulunamadı")
    if not calisma_erisimi(db, k, c):
        raise HTTPException(403, "Bu çalışmaya erişiminiz yok")
    return c


@router.get("", response_model=list[semalar.CalismaOzet])
def liste(db: Session = Depends(get_db), k: Kullanici = Depends(mevcut_kullanici)):
    sorgu = calisma_filtresi(db, k, select(Calisma).order_by(Calisma.kod))
    cs = db.execute(sorgu).scalars().unique().all()
    return [semalar.CalismaOzet(id=c.id, kod=c.kod, kisa_ad=c.kisa_ad, tur=c.tur.value, faz=c.faz, sponsor=c.sponsor,
                                durum=c.durum.value, hedef_hasta=c.hedef_hasta,
                                kayitli=sum(1 for g in c.gonulluler if g.durum in KAYITLI),
                                aktif_merkez=sum(1 for m in c.merkezler if m.durum == "aktif")) for c in cs]


@router.get("/{cid}/kriterler", response_model=list[semalar.KriterCikti])
def kriterler(cid: int, db: Session = Depends(get_db), k: Kullanici = Depends(mevcut_kullanici)):
    c = _c(db, cid, k)
    return [semalar.KriterCikti(id=x.id, tip=x.tip, sira=x.sira, metin=x.metin, yapisal=x.yapisal, guven=x.guven,
                                onaylandi=bool(x.onaylandi)) for x in c.kriterler]


@router.post("/{cid}/kriterler", response_model=semalar.KriterCikti, status_code=201)
def kriter_ekle(cid: int, g: semalar.KriterGirdi, db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("calisma.duzenle"))):
    from ..services.bdm import BDMIstemci

    c = _c(db, cid, k)
    y = BDMIstemci.olustur().kriter_yapilandir(g.metin, g.tip)
    kr = Kriter(calisma_id=c.id, tip=g.tip, sira=len(c.kriterler) + 1, metin=g.metin, yapisal=y.to_dict(), guven=y.guven)
    db.add(kr)
    db.flush()
    denetim.kaydet(db, k, "olustur", "kriter", kr.id, yeni={"calisma": c.kod, "metin": g.metin, "api": True})
    db.commit()
    return semalar.KriterCikti(id=kr.id, tip=kr.tip, sira=kr.sira, metin=kr.metin, yapisal=kr.yapisal, guven=kr.guven, onaylandi=False)


@router.post("/{cid}/eslestirme", response_model=semalar.EslestirmeOzet)
def eslestir(cid: int, istek: semalar.EslestirmeIstek, db: Session = Depends(get_db),
             k: Kullanici = Depends(gerekli("eslestirme.calistir"))):
    from ..services.eslestirme import Eslestirici

    c = _c(db, cid, k)
    t0 = simdi()
    e = Eslestirici()
    sonuclar = e.calisma_icin_tara(db, c, merkez_id=istek.merkez_id, limit=istek.limit, golge_mod=istek.golge_mod)
    sure = (simdi() - t0).total_seconds()
    say = {kk: sum(1 for s in sonuclar if s.karar == kk) for kk in ("uygun", "olasi", "belirsiz", "uygun_degil")}
    denetim.kaydet(db, k, "eslestirme", "eslestirme", c.id, yeni={"calisma": c.kod, "hasta": len(sonuclar), **say, "api": True})
    db.commit()
    return semalar.EslestirmeOzet(taranan=len(sonuclar), sure_sn=round(sure, 2), model=e.model_surumu, **say)


@router.get("/{cid}/uyarilar", response_model=list[semalar.UyariCikti])
def uyarilar(cid: int, durum: str = "acik", db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("rbm.goruntule"))):
    c = _c(db, cid, k)
    us = db.execute(select(RiskUyarisi).where(RiskUyarisi.calisma_id == c.id, RiskUyarisi.durum == durum)).scalars().all()
    return [semalar.UyariCikti(id=u.id, kri_kod=u.kri_kod, seviye=u.seviye, mesaj=u.mesaj, deger=u.deger, esik=u.esik,
                               durum=u.durum, merkez=u.calisma_merkez.merkez.ad if u.calisma_merkez else None,
                               olusturma=u.olusturma) for u in us]


@router.post("/{cid}/rbm/calistir")
def rbm_calistir(cid: int, db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("rbm.yonet"))):
    from ..services.rbm import erken_uyari_calistir, qtl_guncelle

    c = _c(db, cid, k)
    us = erken_uyari_calistir(db, c, kullanici_id=k.id)
    qtl_guncelle(db, c)
    db.commit()
    return {"uyari": len(us)}
