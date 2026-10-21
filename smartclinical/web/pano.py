from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    AdversOlay,
    Basvuru,
    Calisma,
    CalismaDurumu,
    CalismaMerkez,
    EslestirmeSonucu,
    Gonullu,
    GonulluDurumu,
    IzlemZiyareti,
    Kullanici,
    RiskUyarisi,
    Rol,
    Sorgu,
    Vizit,
)
from ._ortak import oturumlu
from .sablon import goster

router = APIRouter()


def _ozet_sayilar(db: Session) -> dict:
    s = {}
    s["calisma"] = db.scalar(select(func.count(Calisma.id)))
    s["aktif_calisma"] = db.scalar(select(func.count(Calisma.id)).where(
        Calisma.durum.in_([CalismaDurumu.AKTIVASYON, CalismaDurumu.KAYIT, CalismaDurumu.IZLEM])))
    s["merkez"] = db.scalar(select(func.count(CalismaMerkez.id)).where(CalismaMerkez.durum == "aktif"))
    s["kayitli"] = db.scalar(select(func.count(Gonullu.id)).where(
        Gonullu.durum.in_([GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE,
                           GonulluDurumu.TAMAMLADI])))
    s["acik_sorgu"] = db.scalar(select(func.count(Sorgu.id)).where(Sorgu.durum == "acik"))
    s["acik_uyari"] = db.scalar(select(func.count(RiskUyarisi.id)).where(RiskUyarisi.durum == "acik"))
    s["aksiyon_uyari"] = db.scalar(select(func.count(RiskUyarisi.id)).where(
        RiskUyarisi.durum == "acik", RiskUyarisi.seviye == "aksiyon"))
    s["bekleyen_basvuru"] = db.scalar(select(func.count(Basvuru.id)).where(Basvuru.karar == "beklemede"))
    s["bekleyen_eslestirme"] = db.scalar(select(func.count(EslestirmeSonucu.id)).where(
        EslestirmeSonucu.inceleme_karari.is_(None), EslestirmeSonucu.karar.in_(["uygun", "olasi"])))
    return s


@router.get("/")
def pano(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    sayilar = _ozet_sayilar(db)
    bugun = date.today()
    calismalar = db.execute(select(Calisma)).scalars().all()
    # aktif calismalar once, arsiv en sonda
    sira = {CalismaDurumu.KAYIT: 0, CalismaDurumu.IZLEM: 0, CalismaDurumu.AKTIVASYON: 1, CalismaDurumu.BASVURU: 2,
            CalismaDurumu.FIZIBILITE: 2, CalismaDurumu.TASARIM: 3, CalismaDurumu.KAPANIS: 4, CalismaDurumu.ANALIZ: 4,
            CalismaDurumu.ARSIV: 9}
    calismalar = sorted(calismalar, key=lambda c: (sira.get(c.durum, 5), c.kod))[:8]

    # calisma basina kayit ilerlemesi
    ilerleme = []
    for c in calismalar:
        kayitli = sum(1 for g in c.gonulluler if g.durum in (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE,
                                                            GonulluDurumu.TAKIPTE, GonulluDurumu.TAMAMLADI))
        aktif_merkez = sum(1 for m in c.merkezler if m.durum == "aktif")
        ilerleme.append({"c": c, "kayitli": kayitli, "aktif_merkez": aktif_merkez,
                         "oran": (100 * kayitli / c.hedef_hasta) if c.hedef_hasta else 0})

    uyarilar = db.execute(select(RiskUyarisi).where(RiskUyarisi.durum == "acik")
                          .order_by(RiskUyarisi.seviye.desc(), RiskUyarisi.olusturma.desc()).limit(8)).scalars().all()

    # rol bazli "bugun ne yapmaliyim" listesi
    gorevler = []
    if k.rol in (Rol.ARASTIRMACI, Rol.KOORDINATOR, Rol.YONETICI):
        yakin = db.execute(select(Vizit).where(Vizit.durum == "planli", Vizit.planlanan <= bugun + timedelta(days=7))
                           .order_by(Vizit.planlanan).limit(6)).scalars().all()
        for v in yakin:
            gorevler.append({"tur": "vizit", "metin": f"{v.gonullu.gonullu_no} – {v.ad} viziti", "tarih": v.planlanan,
                             "url": f"/gonulluler/{v.gonullu_id}"})
        bekleyen = db.execute(select(EslestirmeSonucu).where(EslestirmeSonucu.inceleme_karari.is_(None),
                              EslestirmeSonucu.karar.in_(["uygun", "olasi"]))
                              .order_by(EslestirmeSonucu.skor.desc()).limit(5)).scalars().all()
        for e in bekleyen:
            gorevler.append({"tur": "eslestirme", "metin": f"Aday hasta incelemesi – {e.calisma.kod} / {e.hasta.kayit_no}",
                             "tarih": e.olusturma, "url": f"/calismalar/{e.calisma_id}/eslestirme/{e.id}"})
        sorgular = db.execute(select(Sorgu).where(Sorgu.durum == "acik").order_by(Sorgu.acilis).limit(5)).scalars().all()
        for s in sorgular:
            gorevler.append({"tur": "sorgu", "metin": f"Açık sorgu: {s.form_kaydi.gonullu.gonullu_no} / {s.alan}",
                             "tarih": s.acilis, "url": f"/gonulluler/{s.form_kaydi.gonullu_id}"})
    if k.rol in (Rol.CRA, Rol.PROJE_YONETICISI, Rol.YONETICI):
        ziyaretler = db.execute(select(IzlemZiyareti).where(IzlemZiyareti.gerceklesen.is_(None))
                                .order_by(IzlemZiyareti.planlanan).limit(5)).scalars().all()
        for z in ziyaretler:
            gorevler.append({"tur": "ziyaret", "metin": f"{z.tip} ziyareti – {z.calisma_merkez.merkez.ad}",
                             "tarih": z.planlanan, "url": f"/calismalar/{z.calisma_merkez.calisma_id}/izlem"})
        for u in uyarilar[:5]:
            gorevler.append({"tur": "uyari", "metin": u.mesaj, "tarih": u.olusturma,
                             "url": f"/calismalar/{u.calisma_id}/rbm"})
    if k.rol in (Rol.FARMAKOVIJILANS, Rol.YONETICI):
        saeler = db.execute(select(AdversOlay).where(AdversOlay.ciddi.is_(True), AdversOlay.titck_bildirim.is_(None))
                            .limit(5)).scalars().all()
        for a in saeler:
            gorevler.append({"tur": "sae", "metin": f"SAE bildirimi bekliyor: {a.gonullu.gonullu_no} – {a.terim}",
                             "tarih": a.farkindalik_tarihi, "url": f"/gonulluler/{a.gonullu_id}"})
    gorevler.sort(key=lambda g: str(g["tarih"] or ""))

    # son 12 ay kumulatif randomizasyon egrisi (tum calismalar). Veritabani bagimsiz
    # olsun diye gruplamayi python tarafinda yapiyoruz.
    tarihler = [t for (t,) in db.execute(select(Gonullu.randomizasyon_tarihi)
                                         .where(Gonullu.randomizasyon_tarihi.isnot(None))).all()]
    aylar, kumulatif = [], []
    for i in range(11, -1, -1):
        y, m = bugun.year, bugun.month - i
        while m <= 0:
            y, m = y - 1, m + 12
        ay_sonu = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
        aylar.append(f"{m:02d}/{str(y)[2:]}")
        kumulatif.append(sum(1 for t in tarihler if t <= ay_sonu))

    return goster(request, "pano.html", sayilar=sayilar, ilerleme=ilerleme, uyarilar=uyarilar,
                  gorevler=gorevler[:12], grafik={"etiketler": aylar, "degerler": kumulatif})
