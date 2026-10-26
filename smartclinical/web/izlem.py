"""Izlem dongusu: ziyaret planlama, ziyaret raporu ve PY onayi, bulgu takibi, protokol sapmasi kapatma.

Rotalar /calismalar/{id}/izlem altinda calisir; merkez rolleri yalnizca kendi merkezinin kayitlarini gorur.
"""
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, IzlemZiyareti, Kullanici, ProtokolSapmasi, RiskUyarisi, Rol
from ..models._ortak import simdi
from ..models.izlem import (
    BULGU_ONEM_ETIKET,
    SAPMA_KATEGORI,
    SAPMA_ONEM_ETIKET,
    ZIYARET_DURUM_ETIKET,
    ZIYARET_KONTROL,
    ZIYARET_TIP_ETIKET,
)
from ..services import denetim
from ..services.yetki import gerekli, parola_dogrula
from ._ortak import bilgi, calisma_getir, ip, oturumlu
from .calismalar import _gorunur_cm, _merkez_sinirli, _ozet, sekme_kontrol
from .sablon import goster, sablonlar

router = APIRouter(prefix="/calismalar/{calisma_id}/izlem")

# ziyaret raporunu onaylayabilen roller (PY e-imzasi)
RAPOR_ONAY_ROLLERI = (Rol.PROJE_YONETICISI, Rol.YONETICI)

sablonlar.env.globals.update({
    "ZIYARET_TIP_ETIKET": ZIYARET_TIP_ETIKET,
    "ZIYARET_DURUM_ETIKET": ZIYARET_DURUM_ETIKET,
    "ZIYARET_KONTROL": ZIYARET_KONTROL,
    "BULGU_ONEM_ETIKET": BULGU_ONEM_ETIKET,
    "SAPMA_ONEM_ETIKET": SAPMA_ONEM_ETIKET,
})


def _tarih(v: str) -> date | None:
    return date.fromisoformat(v) if v else None


def _cm_ids(k: Kullanici, c: Calisma) -> list[int]:
    return [m.id for m in _gorunur_cm(k, c)]


def _ziyaret(db: Session, k: Kullanici, c: Calisma, zid: int) -> IzlemZiyareti:
    z = db.get(IzlemZiyareti, zid)
    if not z or z.calisma_merkez.calisma_id != c.id:
        raise HTTPException(404, "Ziyaret bulunamadı")
    if _merkez_sinirli(k) and z.calisma_merkez.merkez_id != k.merkez_id:
        raise HTTPException(403, "Bu merkezin ziyaretlerine erişiminiz yok")
    return z


def _sapma(db: Session, k: Kullanici, c: Calisma, sid: int) -> ProtokolSapmasi:
    s = db.get(ProtokolSapmasi, sid)
    if not s or s.calisma_merkez.calisma_id != c.id:
        raise HTTPException(404, "Sapma bulunamadı")
    if _merkez_sinirli(k) and s.calisma_merkez.merkez_id != k.merkez_id:
        raise HTTPException(403, "Bu merkezin sapmalarına erişiminiz yok")
    return s


def onceki_acik_bulgular(db: Session, cm_id: int, haric_id: int | None = None) -> list[dict]:
    """Ayni merkezin en son raporlanmis ziyaretindeki acik bulgular; yeni ziyarete tasinir."""
    sorgu = select(IzlemZiyareti).where(IzlemZiyareti.calisma_merkez_id == cm_id, IzlemZiyareti.bulgular.isnot(None))
    if haric_id:
        sorgu = sorgu.where(IzlemZiyareti.id != haric_id)
    onceki = db.execute(sorgu.order_by(IzlemZiyareti.id.desc())).scalars().all()
    for z in onceki:
        if z.bulgular:
            return [dict(b, tasindi_ziyaret_id=z.id) for b in z.bulgular if not b.get("kapali")]
    return []


def ziyaret_olustur(db: Session, k: Kullanici, cm_id: int, tip: str, planlanan: date,
                    tetikleyen_uyari_id: int | None = None, ip_adresi: str | None = None) -> IzlemZiyareti:
    z = IzlemZiyareti(calisma_merkez_id=cm_id, tip=tip, planlanan=planlanan, cra_id=k.id,
                      tetikleyen_uyari_id=tetikleyen_uyari_id, bulgular=onceki_acik_bulgular(db, cm_id) or None)
    db.add(z)
    db.flush()
    denetim.kaydet(db, k, "olustur", "izlem_ziyareti", z.id, yeni=denetim.varlik_sozluk(z), ip=ip_adresi)
    return z


# --- Liste ------------------------------------------------------------------

@router.get("")
def izlem(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
          db: Session = Depends(get_db), merkez_id: int | None = None):
    sekme_kontrol(k, "izlem")
    cm_ids = _cm_ids(k, c)
    ziyaretler = db.execute(select(IzlemZiyareti).where(IzlemZiyareti.calisma_merkez_id.in_(cm_ids))
                            .order_by(IzlemZiyareti.planlanan.desc())).scalars().all() if cm_ids else []
    sapmalar = db.execute(select(ProtokolSapmasi).where(ProtokolSapmasi.calisma_merkez_id.in_(cm_ids))
                          .order_by(ProtokolSapmasi.kapali, ProtokolSapmasi.tarih.desc())).scalars().all() if cm_ids else []
    # aksiyon seviyesindeki acik uyarilar: tek tikla tetiklenmis ziyaret
    uyarilar = db.execute(select(RiskUyarisi).where(RiskUyarisi.calisma_id == c.id, RiskUyarisi.seviye == "aksiyon",
                          RiskUyarisi.durum.in_(("acik", "inceleniyor")))
                          .order_by(RiskUyarisi.olusturma.desc())).scalars().all()
    tetiklenen = {z.tetikleyen_uyari_id for z in ziyaretler if z.tetikleyen_uyari_id}
    return goster(request, "calismalar/izlem.html", c=c, o=_ozet(db, c), sekme="izlem", ziyaretler=ziyaretler,
                  sapmalar=sapmalar, kategoriler=SAPMA_KATEGORI, merkezler=_gorunur_cm(k, c), uyarilar=uyarilar,
                  tetiklenen=tetiklenen, secili_merkez=merkez_id, bugun=date.today())


# --- Ziyaret ----------------------------------------------------------------

@router.post("/ziyaret")
def ziyaret_planla(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("rbm.yonet")),
                   db: Session = Depends(get_db), calisma_merkez_id: int = Form(...), tip: str = Form(...),
                   planlanan: str = Form(...), tetikleyen_uyari_id: str = Form("")):
    if calisma_merkez_id not in [m.id for m in c.merkezler]:
        raise HTTPException(404, "Merkez bulunamadı")
    if tip not in ZIYARET_TIP_ETIKET:
        raise HTTPException(400, "Geçersiz ziyaret tipi")
    uyari_id = int(tetikleyen_uyari_id) if tetikleyen_uyari_id else None
    z = ziyaret_olustur(db, k, calisma_merkez_id, tip, date.fromisoformat(planlanan), uyari_id, ip(request))
    db.commit()
    if z.bulgular:
        bilgi(request, f"Ziyaret planlandı; önceki ziyaretten {len(z.bulgular)} açık bulgu taşındı.")
    return RedirectResponse(f"/calismalar/{c.id}/izlem/ziyaret/{z.id}", status_code=303)


@router.post("/tetikle/{uyari_id}")
def tetiklenmis_ziyaret(request: Request, uyari_id: int, c: Calisma = Depends(calisma_getir),
                        k: Kullanici = Depends(gerekli("rbm.yonet")), db: Session = Depends(get_db)):
    """Aksiyon seviyesindeki uyaridan tek tikla tetiklenmis ziyaret olusturur."""
    u = db.get(RiskUyarisi, uyari_id)
    if not u or u.calisma_id != c.id:
        raise HTTPException(404, "Uyarı bulunamadı")
    if not u.calisma_merkez_id:
        raise HTTPException(400, "Uyarı bir merkeze bağlı değil; ziyareti elle planlayın")
    mevcut = db.scalar(select(IzlemZiyareti.id).where(IzlemZiyareti.tetikleyen_uyari_id == u.id).limit(1))
    if mevcut:
        bilgi(request, "Bu uyarı için tetiklenmiş ziyaret zaten var.")
        return RedirectResponse(f"/calismalar/{c.id}/izlem/ziyaret/{mevcut}", status_code=303)
    z = ziyaret_olustur(db, k, u.calisma_merkez_id, "tetiklenmis", date.today(), u.id, ip(request))
    if u.durum == "acik":
        u.durum = "inceleniyor"
        u.atanan_id = u.atanan_id or k.id
        denetim.kaydet(db, k, "guncelle", "risk_uyarisi", u.id, eski={"durum": "acik"},
                       yeni={"durum": "inceleniyor", "ziyaret_id": z.id}, ip=ip(request))
    db.commit()
    bilgi(request, "Tetiklenmiş ziyaret oluşturuldu; uyarı inceleme durumuna alındı.")
    return RedirectResponse(f"/calismalar/{c.id}/izlem/ziyaret/{z.id}", status_code=303)


@router.get("/ziyaret/{zid}")
def ziyaret(request: Request, zid: int, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
            db: Session = Depends(get_db)):
    sekme_kontrol(k, "izlem")
    z = _ziyaret(db, k, c, zid)
    return goster(request, "izlem/ziyaret.html", c=c, o=_ozet(db, c), sekme="izlem", z=z,
                  onaylayabilir=k.rol in RAPOR_ONAY_ROLLERI, bugun=date.today())


@router.post("/ziyaret/{zid}")
def ziyaret_kaydet(request: Request, zid: int, c: Calisma = Depends(calisma_getir),
                   k: Kullanici = Depends(gerekli("rbm.yonet")), db: Session = Depends(get_db),
                   gerceklesen: str = Form(""), katilimcilar: str = Form(""), sdv_orani: str = Form(""),
                   rapor: str = Form(""), kontrol: list[str] = Form([])):
    z = _ziyaret(db, k, c, zid)
    if z.rapor_onay:
        bilgi(request, "Onaylanmış rapor değiştirilemez.")
        return RedirectResponse(f"/calismalar/{c.id}/izlem/ziyaret/{z.id}", status_code=303)
    eski = denetim.varlik_sozluk(z, ["gerceklesen", "katilimcilar", "sdv_orani", "rapor", "kontrol_listesi"])
    z.gerceklesen = _tarih(gerceklesen)
    z.katilimcilar = katilimcilar.strip() or None
    z.sdv_orani = float(sdv_orani.replace(",", ".")) if sdv_orani.strip() else None
    z.rapor = rapor.strip() or None
    z.kontrol_listesi = {anahtar: anahtar in kontrol for anahtar in ZIYARET_KONTROL}
    denetim.kaydet(db, k, "guncelle", "izlem_ziyareti", z.id, eski=eski,
                   yeni=denetim.varlik_sozluk(z, ["gerceklesen", "katilimcilar", "sdv_orani", "rapor", "kontrol_listesi"]),
                   ip=ip(request))
    db.commit()
    bilgi(request, "Ziyaret kaydı güncellendi.")
    return RedirectResponse(f"/calismalar/{c.id}/izlem/ziyaret/{z.id}", status_code=303)


@router.post("/ziyaret/{zid}/bulgu")
def bulgu_ekle(request: Request, zid: int, c: Calisma = Depends(calisma_getir),
               k: Kullanici = Depends(gerekli("rbm.yonet")), db: Session = Depends(get_db),
               konu: str = Form(...), onem: str = Form("minor"), aksiyon: str = Form(""), sorumlu: str = Form(""),
               hedef_tarih: str = Form("")):
    z = _ziyaret(db, k, c, zid)
    if z.rapor_onay:
        raise HTTPException(400, "Onaylanmış rapora bulgu eklenemez")
    bulgu = {"konu": konu.strip(), "onem": onem if onem in BULGU_ONEM_ETIKET else "minor",
             "aksiyon": aksiyon.strip() or None, "sorumlu": sorumlu.strip() or None,
             "hedef_tarih": hedef_tarih or None, "kapali": False}
    z.bulgular = list(z.bulgular or []) + [bulgu]
    denetim.kaydet(db, k, "guncelle", "izlem_ziyareti", z.id, yeni={"bulgu": bulgu}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/izlem/ziyaret/{z.id}", status_code=303)


@router.post("/ziyaret/{zid}/bulgu/{sira}/kapat")
def bulgu_kapat(request: Request, zid: int, sira: int, c: Calisma = Depends(calisma_getir),
                k: Kullanici = Depends(gerekli("rbm.yonet")), db: Session = Depends(get_db), not_: str = Form("", alias="not")):
    z = _ziyaret(db, k, c, zid)
    bulgular = list(z.bulgular or [])
    if sira < 0 or sira >= len(bulgular):
        raise HTTPException(404, "Bulgu bulunamadı")
    b = dict(bulgular[sira])
    b["kapali"] = True
    b["kapanis"] = date.today().isoformat()
    if not_.strip():
        b["kapanis_notu"] = not_.strip()
    bulgular[sira] = b
    z.bulgular = bulgular
    denetim.kaydet(db, k, "guncelle", "izlem_ziyareti", z.id, eski={"bulgu": bulgular[sira]["konu"], "kapali": False},
                   yeni={"bulgu": b["konu"], "kapali": True}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/izlem/ziyaret/{z.id}", status_code=303)


@router.post("/ziyaret/{zid}/onay")
def rapor_onayla(request: Request, zid: int, c: Calisma = Depends(calisma_getir),
                 k: Kullanici = Depends(gerekli("rbm.yonet")), db: Session = Depends(get_db), parola: str = Form(...)):
    """Proje yoneticisi e-imzasi: rapor ve bulgular ozetlenir, imza kaydi olusur, rapor kilitlenir."""
    if k.rol not in RAPOR_ONAY_ROLLERI:
        raise HTTPException(403, "Ziyaret raporunu proje yöneticisi onaylar")
    z = _ziyaret(db, k, c, zid)
    hedef = f"/calismalar/{c.id}/izlem/ziyaret/{z.id}"
    if z.rapor_onay:
        bilgi(request, "Rapor zaten onaylı.")
        return RedirectResponse(hedef, status_code=303)
    if not z.gerceklesen or not z.rapor:
        bilgi(request, "Onay için gerçekleşen tarih ve rapor metni gerekli.")
        return RedirectResponse(hedef, status_code=303)
    if not parola_dogrula(parola, k.parola_hash):
        bilgi(request, "E-imza için parola doğrulanamadı.")
        return RedirectResponse(hedef, status_code=303)
    z.rapor_onay = simdi()
    z.onaylayan_id = k.id
    icerik = denetim.varlik_sozluk(z, ["gerceklesen", "katilimcilar", "sdv_orani", "rapor", "kontrol_listesi", "bulgular"])
    denetim.imzala(db, k, "izlem_ziyareti", z.id, "Ziyaret raporu onaylandı", icerik, ip=ip(request))
    db.commit()
    bilgi(request, "Ziyaret raporu elektronik imza ile onaylandı.")
    return RedirectResponse(hedef, status_code=303)


# --- Sapmalar ---------------------------------------------------------------

@router.post("/sapma")
def sapma_ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("rbm.yonet")),
               db: Session = Depends(get_db), calisma_merkez_id: int = Form(...), gonullu_id: str = Form(""),
               tarih: str = Form(...), kategori: str = Form(...), onem: str = Form("minor"), aciklama: str = Form(...)):
    if calisma_merkez_id not in [m.id for m in c.merkezler]:
        raise HTTPException(404, "Merkez bulunamadı")
    s = ProtokolSapmasi(calisma_merkez_id=calisma_merkez_id, gonullu_id=int(gonullu_id) if gonullu_id else None,
                        tarih=date.fromisoformat(tarih), kategori=kategori,
                        onem=onem if onem in SAPMA_ONEM_ETIKET else "minor", aciklama=aciklama)
    db.add(s)
    db.flush()
    denetim.kaydet(db, k, "olustur", "protokol_sapmasi", s.id, yeni=denetim.varlik_sozluk(s), ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/izlem/sapma/{s.id}", status_code=303)


@router.get("/sapma/{sid}")
def sapma(request: Request, sid: int, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
          db: Session = Depends(get_db)):
    sekme_kontrol(k, "izlem")
    s = _sapma(db, k, c, sid)
    kullanicilar = db.execute(select(Kullanici).where(Kullanici.aktif.is_(True)).order_by(Kullanici.ad_soyad)).scalars().all()
    return goster(request, "izlem/sapma.html", c=c, o=_ozet(db, c), sekme="izlem", s=s, kullanicilar=kullanicilar)


@router.post("/sapma/{sid}")
def sapma_guncelle(request: Request, sid: int, c: Calisma = Depends(calisma_getir),
                   k: Kullanici = Depends(gerekli("rbm.yonet")), db: Session = Depends(get_db),
                   kok_neden: str = Form(""), duzeltici_faaliyet: str = Form(""), sorumlu_id: str = Form(""),
                   hedef_tarih: str = Form(""), etik_bildirim: str = Form(""), kapat: str = Form("")):
    s = _sapma(db, k, c, sid)
    hedef = f"/calismalar/{c.id}/izlem/sapma/{s.id}"
    alanlar = ["kok_neden", "duzeltici_faaliyet", "sorumlu_id", "hedef_tarih", "etik_bildirim", "kapali", "kapanis_tarihi"]
    eski = denetim.varlik_sozluk(s, alanlar)
    s.kok_neden = kok_neden.strip() or None
    s.duzeltici_faaliyet = duzeltici_faaliyet.strip() or None
    s.sorumlu_id = int(sorumlu_id) if sorumlu_id else None
    s.hedef_tarih = _tarih(hedef_tarih)
    s.etik_bildirim = _tarih(etik_bildirim)
    mesaj = "Sapma kaydı güncellendi."
    if kapat:
        eksik = []
        if not s.kok_neden:
            eksik.append("kök neden")
        if not s.duzeltici_faaliyet:
            eksik.append("düzeltici faaliyet")
        if s.etik_bildirim_gerekli and not s.etik_bildirim:
            eksik.append("etik kurul bildirim tarihi (majör sapma)")
        if eksik:
            db.rollback()
            bilgi(request, "Sapma kapatılamaz; eksik: " + ", ".join(eksik) + ".")
            return RedirectResponse(hedef, status_code=303)
        s.kapali = True
        s.kapanis_tarihi = date.today()
        mesaj = "Sapma kapatıldı."
    denetim.kaydet(db, k, "guncelle", "protokol_sapmasi", s.id, eski=eski, yeni=denetim.varlik_sozluk(s, alanlar), ip=ip(request))
    db.commit()
    bilgi(request, mesaj)
    return RedirectResponse(hedef, status_code=303)
