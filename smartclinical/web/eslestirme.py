"""Yapay zeka destekli moduller: protokol-hasta eslestirme, merkez zekasi, risk bazli izlem."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ayarlar
from ..db import get_db
from ..models import (
    Calisma,
    CalismaMerkez,
    EslestirmeSonucu,
    Gonullu,
    GonulluDurumu,
    Hasta,
    KaliteToleransLimiti,
    Kullanici,
    RiskGostergesi,
    RiskUyarisi,
)
from ..models._ortak import simdi
from ..services import denetim
from ..services.yetki import gerekli
from ._ortak import bilgi, calisma_getir, ip, oturumlu
from .calismalar import _ozet
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}")


# --- Protokol-hasta eslestirme ---------------------------------------------

@router.get("/eslestirme")
def eslestirme(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
               db: Session = Depends(get_db), karar: str | None = None, merkez: int | None = None):
    sorgu = select(EslestirmeSonucu).where(EslestirmeSonucu.calisma_id == c.id).order_by(EslestirmeSonucu.skor.desc())
    if karar:
        sorgu = sorgu.where(EslestirmeSonucu.karar == karar)
    sonuclar = db.execute(sorgu).scalars().all()
    if merkez:
        sonuclar = [s for s in sonuclar if s.hasta.merkez_id == merkez]
    # arastirmaci sadece kendi merkezini gorur
    if k.rol.value in ("arastirmaci", "koordinator") and k.merkez_id:
        sonuclar = [s for s in sonuclar if s.hasta.merkez_id == k.merkez_id]
    ozet = {"uygun": 0, "olasi": 0, "belirsiz": 0, "uygun_degil": 0}
    for s in db.execute(select(EslestirmeSonucu).where(EslestirmeSonucu.calisma_id == c.id)).scalars():
        ozet[s.karar] = ozet.get(s.karar, 0) + 1
    hasta_havuzu = len(db.execute(select(Hasta.id).where(Hasta.merkez_id.in_([m.merkez_id for m in c.merkezler]))).all()) if c.merkezler else 0
    son_tarama = db.scalar(select(EslestirmeSonucu.olusturma).where(EslestirmeSonucu.calisma_id == c.id)
                           .order_by(EslestirmeSonucu.olusturma.desc()).limit(1))
    onaysiz_kriter = sum(1 for kr in c.kriterler if not kr.onaylandi)
    a = ayarlar()
    return goster(request, "eslestirme/liste.html", c=c, o=_ozet(db, c), sekme="eslestirme", sonuclar=sonuclar,
                  ozet=ozet, hasta_havuzu=hasta_havuzu, son_tarama=son_tarama, karar=karar, merkez=merkez,
                  onaysiz_kriter=onaysiz_kriter, bdm=a.bdm_saglayici, bdm_model=a.bdm_model)


@router.post("/eslestirme/calistir")
def eslestirme_calistir(request: Request, c: Calisma = Depends(calisma_getir),
                        k: Kullanici = Depends(gerekli("eslestirme.calistir")), db: Session = Depends(get_db),
                        merkez_id: str = Form(""), golge_mod: str = Form("0")):
    from ..services.eslestirme import Eslestirici

    if not c.kriterler:
        bilgi(request, "Önce protokol kriterlerini tanımlayın.")
        return RedirectResponse(f"/calismalar/{c.id}/protokol", status_code=303)
    baslangic = simdi()
    e = Eslestirici()
    sonuclar = e.calisma_icin_tara(db, c, merkez_id=int(merkez_id) if merkez_id else None, golge_mod=golge_mod == "1")
    sure = (simdi() - baslangic).total_seconds()
    uygun = sum(1 for s in sonuclar if s.karar == "uygun")
    olasi = sum(1 for s in sonuclar if s.karar == "olasi")
    denetim.kaydet(db, k, "eslestirme", "eslestirme", c.id,
                   yeni={"calisma": c.kod, "hasta": len(sonuclar), "uygun": uygun, "olasi": olasi,
                         "model": e.model_surumu, "sure_sn": round(sure, 1), "golge_mod": golge_mod == "1"}, ip=ip(request))
    db.commit()
    bilgi(request, f"{len(sonuclar)} hasta kaydı tarandı ({sure:.1f} sn). {uygun} uygun, {olasi} olası aday bulundu; "
                   f"öneriler araştırmacı incelemesini bekliyor.")
    return RedirectResponse(f"/calismalar/{c.id}/eslestirme", status_code=303)


@router.get("/eslestirme/{sonuc_id}")
def eslestirme_detay(request: Request, sonuc_id: int, c: Calisma = Depends(calisma_getir),
                     k: Kullanici = Depends(gerekli("eslestirme.incele")), db: Session = Depends(get_db)):
    request.state.kullanici = k
    s = db.get(EslestirmeSonucu, sonuc_id)
    if not s or s.calisma_id != c.id:
        raise HTTPException(404)
    denetim.kaydet(db, k, "goruntule", "hasta", s.hasta_id, yeni={"baglam": "eslestirme", "calisma": c.kod}, ip=ip(request))
    db.commit()
    kriter_map = {kr.id: kr for kr in c.kriterler}
    satirlar = []
    for ks in s.kriter_sonuclari:
        satirlar.append({**ks, "kriter": kriter_map.get(ks.get("kriter_id"))})
    merkezler = [m for m in c.merkezler if m.merkez_id == s.hasta.merkez_id]
    mevcut_gonullu = next((g for g in c.gonulluler if g.hasta_id == s.hasta_id), None)
    return goster(request, "eslestirme/detay.html", c=c, o=_ozet(db, c), sekme="eslestirme", s=s, satirlar=satirlar,
                  merkezler=merkezler, mevcut_gonullu=mevcut_gonullu)


@router.post("/eslestirme/{sonuc_id}/incele")
def eslestirme_incele(request: Request, sonuc_id: int, c: Calisma = Depends(calisma_getir),
                      k: Kullanici = Depends(gerekli("eslestirme.incele")), db: Session = Depends(get_db),
                      karar: str = Form(...), not_: str = Form("", alias="not"), calisma_merkez_id: str = Form("")):
    s = db.get(EslestirmeSonucu, sonuc_id)
    if not s or s.calisma_id != c.id:
        raise HTTPException(404)
    s.inceleme_karari = karar
    s.inceleme_notu = not_ or None
    s.inceleyen_id = k.id
    s.inceleme_zamani = simdi()
    denetim.kaydet(db, k, "guncelle", "eslestirme_sonucu", s.id, yeni={"calisma": c.kod, "karar": karar, "not": not_ or None,
                   "model_karari": s.karar, "skor": s.skor}, ip=ip(request))
    if karar == "onay" and calisma_merkez_id:
        cm = db.get(CalismaMerkez, int(calisma_merkez_id))
        if cm and not any(g.hasta_id == s.hasta_id for g in c.gonulluler):
            g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, hasta_id=s.hasta_id,
                        gonullu_no=f"{cm.merkez_no}-{len(cm.gonulluler) + 1:03d}", durum=GonulluDurumu.ON_TARAMA)
            db.add(g)
            db.flush()
            denetim.kaydet(db, k, "olustur", "gonullu", g.id, yeni={"kaynak": "eslestirme", "sonuc_id": s.id,
                           "gonullu_no": g.gonullu_no}, ip=ip(request))
            bilgi(request, f"Hasta ön tarama listesine alındı: {g.gonullu_no}. Onam görüşmesi planlayın.")
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/eslestirme", status_code=303)


@router.get("/eslestirme-golge")
def golge_mod(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
              db: Session = Depends(get_db)):
    """Golge mod: model onerisi vs arastirmaci karari karsilastirmasi (pilot dogrulama)."""
    from ..services.eslestirme import golge_mod_karsilastir

    sonuclar = db.execute(select(EslestirmeSonucu).where(EslestirmeSonucu.calisma_id == c.id,
                          EslestirmeSonucu.inceleme_karari.isnot(None))).scalars().all()
    manuel = {s.hasta_id: s.inceleme_karari == "onay" for s in sonuclar}
    metrikler = golge_mod_karsilastir(sonuclar, manuel) if sonuclar else None
    return goster(request, "eslestirme/golge.html", c=c, o=_ozet(db, c), sekme="eslestirme", metrikler=metrikler,
                  sonuclar=sonuclar)


# --- Merkez zekasi ----------------------------------------------------------

@router.get("/merkez-zekasi")
def merkez_zekasi(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
                  db: Session = Depends(get_db)):
    from ..services.merkez_zekasi import calisma_kazanim_projeksiyonu, merkez_sirala

    satirlar = []
    adaylar = []
    bugun = simdi().date()
    for cm in c.merkezler:
        kayitli = sum(1 for g in cm.gonulluler if g.randomizasyon_tarihi)
        ay = ((bugun - cm.aktivasyon_tarihi).days / 30.4) if cm.aktivasyon_tarihi else 0
        gercek_hiz = kayitli / ay if ay >= 1 else None
        satirlar.append({"cm": cm, "kayitli": kayitli, "ay": ay, "gercek_hiz": gercek_hiz})
        adaylar.append({
            "merkez_id": cm.merkez_id, "cm_id": cm.id, "ad": f"{cm.merkez_no} {cm.merkez.ad}",
            "tahmini_kazanim": cm.tahmini_kazanim or 0.0, "gecikme_riski": cm.gecikme_riski if cm.gecikme_riski is not None else 0.5,
            "sapma_orani": 0.0, "sorgu_orani": 0.0,
            "tamamlanan_calisma": sum(1 for x in cm.merkez.calismalar if x.durum == "kapali"),
            "rekabet": sum(1 for x in cm.merkez.calismalar if x.calisma_id != c.id and x.durum == "aktif"
                           and x.calisma.terapotik_alan == c.terapotik_alan),
            "bolge_bos": not any(x.merkez.sehir == cm.merkez.sehir for x in c.merkezler if x.id != cm.id),
            "gcp_egitim_guncel": bool(cm.bas_arastirmaci and cm.bas_arastirmaci.gcp_egitim_tarihi
                                      and (bugun - cm.bas_arastirmaci.gcp_egitim_tarihi).days < 730),
        })
    siralama = merkez_sirala(adaylar) if adaylar else []

    # Projeksiyon: CalismaMerkez'de posterior parametreleri tutmuyoruz; ortalama ve %90 araliktan
    # Gamma parametrelerini geri turetiyoruz (sd ~ aralik/3.29). Yeterince iyi bir yaklasim.
    projeksiyon = None
    mevcut = sum(s["kayitli"] for s in satirlar)
    if c.hedef_hasta and any(cm.tahmini_kazanim for cm in c.merkezler):
        params = []
        for cm in c.merkezler:
            if not cm.tahmini_kazanim or cm.durum in ("kapali", "kayit_kapali"):
                continue
            m = cm.tahmini_kazanim
            sd = max(1e-3, ((cm.tahmin_ust or m * 1.5) - (cm.tahmin_alt or m * 0.5)) / 3.29)
            a = (m / sd) ** 2
            params.append({"alfa_post": a, "beta_post": a / m, "katsayi": 1.0})
        kalan = max(1, c.hedef_hasta - mevcut)
        p = calisma_kazanim_projeksiyonu(params, kalan, bugun, planlanan_bitis=c.planlanan_bitis)
        if p["egri"]:
            ufuk = 24
            if c.planlanan_bitis and c.planlanan_bitis > bugun:
                ufuk = min(60, (c.planlanan_bitis.year - bugun.year) * 12 + c.planlanan_bitis.month - bugun.month + 6)
            egri = []
            for ay, med, p5, p95 in p["egri"][:ufuk]:
                yil, m_ = bugun.year, bugun.month + ay
                while m_ > 12:
                    yil, m_ = yil + 1, m_ - 12
                egri.append({"ay": f"{m_:02d}/{str(yil)[2:]}", "medyan": min(c.hedef_hasta, mevcut + med),
                             "p10": min(c.hedef_hasta, mevcut + p5), "p90": min(c.hedef_hasta, mevcut + p95)})
            p["egri"] = egri
        projeksiyon = p
    son_guncelleme = max((cm.guncelleme for cm in c.merkezler), default=None)
    return goster(request, "eslestirme/merkez_zekasi.html", c=c, o=_ozet(db, c), sekme="merkez-zekasi",
                  satirlar=satirlar, siralama=siralama, projeksiyon=projeksiyon, son_guncelleme=son_guncelleme)


@router.post("/merkez-zekasi/guncelle")
def merkez_zekasi_guncelle(request: Request, c: Calisma = Depends(calisma_getir),
                           k: Kullanici = Depends(gerekli("merkez.yonet")), db: Session = Depends(get_db)):
    from ..services.merkez_zekasi import calisma_tahmin_guncelle

    guncellenen = calisma_tahmin_guncelle(db, c)
    denetim.kaydet(db, k, "tahmin", "calisma", c.id, yeni={"calisma": c.kod, "merkez": len(guncellenen)}, ip=ip(request))
    db.commit()
    bilgi(request, f"{len(guncellenen)} merkez için kazanım ve aktivasyon tahmini güncellendi.")
    return RedirectResponse(f"/calismalar/{c.id}/merkez-zekasi", status_code=303)


# --- Risk bazli izlem -------------------------------------------------------

@router.get("/rbm")
def rbm(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("rbm.goruntule")),
        db: Session = Depends(get_db)):
    from ..services.rbm import izlem_onerisi, kri_hesapla

    request.state.kullanici = k
    kriler = db.execute(select(RiskGostergesi).where(RiskGostergesi.aktif.is_(True),
                        (RiskGostergesi.calisma_id == c.id) | (RiskGostergesi.calisma_id.is_(None)))
                        .order_by(RiskGostergesi.kod)).scalars().all()
    # calisma ozel tanim varsa genel sablonu ezer
    kri_map = {}
    for kr in kriler:
        if kr.kod not in kri_map or kr.calisma_id == c.id:
            kri_map[kr.kod] = kr
    kriler = list(kri_map.values())
    degerler = kri_hesapla(db, c)
    uyarilar = db.execute(select(RiskUyarisi).where(RiskUyarisi.calisma_id == c.id)
                          .order_by(RiskUyarisi.durum, RiskUyarisi.seviye.desc(), RiskUyarisi.olusturma.desc())).scalars().all()
    qtller = db.execute(select(KaliteToleransLimiti).where(KaliteToleransLimiti.calisma_id == c.id)).scalars().all()
    merkezler = sorted(c.merkezler, key=lambda m: -(m.risk_puani or 0))
    oneriler = {m.id: izlem_onerisi(m) for m in merkezler}
    son = max((u.olusturma for u in uyarilar), default=None)

    def seviye(kr, v):
        if v is None or kr.esik_uyari is None:
            return ""
        kotu = (v >= kr.esik_uyari) if kr.yon == "yuksek" else (v <= kr.esik_uyari)
        aksiyon = kr.esik_aksiyon is not None and ((v >= kr.esik_aksiyon) if kr.yon == "yuksek" else (v <= kr.esik_aksiyon))
        return "aksiyon" if aksiyon else ("uyari" if kotu else "normal")

    return goster(request, "eslestirme/rbm.html", c=c, o=_ozet(db, c), sekme="rbm", kriler=kriler, degerler=degerler,
                  uyarilar=uyarilar, qtller=qtller, merkezler=merkezler, oneriler=oneriler, seviye=seviye, son=son)


@router.post("/rbm/calistir")
def rbm_calistir(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("rbm.yonet")),
                 db: Session = Depends(get_db)):
    from ..services.rbm import erken_uyari_calistir, qtl_guncelle

    uyarilar = erken_uyari_calistir(db, c, kullanici_id=k.id)
    qtl_guncelle(db, c)
    denetim.kaydet(db, k, "rbm", "calisma", c.id, yeni={"calisma": c.kod, "uyari": len(uyarilar)}, ip=ip(request))
    db.commit()
    bilgi(request, f"Risk göstergeleri yeniden hesaplandı; {len(uyarilar)} uyarı oluşturuldu/güncellendi.")
    return RedirectResponse(f"/calismalar/{c.id}/rbm", status_code=303)


@router.post("/rbm/uyari/{uyari_id}")
def uyari_islem(request: Request, uyari_id: int, c: Calisma = Depends(calisma_getir),
                k: Kullanici = Depends(gerekli("rbm.yonet")), db: Session = Depends(get_db),
                durum: str = Form(...), kapanis_notu: str = Form("")):
    u = db.get(RiskUyarisi, uyari_id)
    if not u or u.calisma_id != c.id:
        raise HTTPException(404)
    eski = u.durum
    u.durum = durum
    u.atanan_id = k.id
    if durum in ("kapandi", "yanlis_alarm"):
        u.kapanis = simdi()
        u.kapanis_notu = kapanis_notu or None
    if durum == "inceleniyor" and kapanis_notu:
        u.kapanis_notu = kapanis_notu
    denetim.kaydet(db, k, "guncelle", "risk_uyarisi", u.id, eski={"durum": eski}, yeni={"durum": durum, "not": kapanis_notu or None}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/rbm", status_code=303)
