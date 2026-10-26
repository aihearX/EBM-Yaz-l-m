"""Genel bakis: rol bazli uc gorunum (merkez, izlem, portfoy)."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    AdversOlay,
    Calisma,
    CalismaDurumu,
    CalismaMerkez,
    EslestirmeSonucu,
    FormKaydi,
    Gonullu,
    Hasta,
    IzlemZiyareti,
    Kullanici,
    RiskUyarisi,
    Rol,
    Sorgu,
    Vizit,
)
from ..services.yetki import calisma_filtresi, izinli
from ._ortak import oturumlu
from .calismalar import KAYITLI_DURUMLAR as KAYITLI
from .sablon import goster

router = APIRouter()

SORGU_GECIKME_GUN = 14
# aktif calismalar once, arsiv en sonda
_SIRA = {CalismaDurumu.KAYIT: 0, CalismaDurumu.IZLEM: 0, CalismaDurumu.AKTIVASYON: 1, CalismaDurumu.BASVURU: 2,
         CalismaDurumu.FIZIBILITE: 2, CalismaDurumu.TASARIM: 3, CalismaDurumu.KAPANIS: 4, CalismaDurumu.ANALIZ: 4,
         CalismaDurumu.ARSIV: 9}


def gorunum(k: Kullanici) -> str:
    if k.rol in (Rol.ARASTIRMACI, Rol.KOORDINATOR):
        return "merkez"
    if k.rol in (Rol.CRA, Rol.VERI_YONETICISI, Rol.FARMAKOVIJILANS):
        return "izlem"
    return "portfoy"


def _calismalar(db: Session, k: Kullanici) -> list[Calisma]:
    sorgu = calisma_filtresi(db, k, select(Calisma))
    liste = db.execute(sorgu).scalars().unique().all()
    return sorted(liste, key=lambda c: (_SIRA.get(c.durum, 5), c.kod))


def _merkez_filtre(sorgu, k: Kullanici):
    """Gonullu uzerinden giden sorgulari kullanicinin merkeziyle sinirlar."""
    if k.merkez_id:
        sorgu = sorgu.join(Gonullu.calisma_merkez).where(CalismaMerkez.merkez_id == k.merkez_id)
    return sorgu


def _saeler(db: Session, k: Kullanici | None = None) -> list[AdversOlay]:
    sorgu = select(AdversOlay).join(AdversOlay.gonullu).where(AdversOlay.ciddi.is_(True), AdversOlay.titck_bildirim.is_(None))
    if k is not None:
        sorgu = _merkez_filtre(sorgu, k)
    saeler = db.execute(sorgu).scalars().all()
    return sorted(saeler, key=lambda a: (a.bildirim_suresi_gun if a.bildirim_suresi_gun is not None else 99))


def _merkez_gorunumu(db: Session, k: Kullanici, bugun: date) -> dict:
    yakin = db.execute(_merkez_filtre(select(Vizit).join(Vizit.gonullu), k).where(
        Vizit.durum == "planli", Vizit.planlanan >= bugun, Vizit.planlanan <= bugun + timedelta(days=7))
        .order_by(Vizit.planlanan)).scalars().all()
    # planlanan tarih gecmis ama pencere henuz kapanmamis vizitler
    gecmis = db.execute(_merkez_filtre(select(Vizit).join(Vizit.gonullu), k).where(
        Vizit.durum == "planli", Vizit.planlanan < bugun).order_by(Vizit.planlanan)).scalars().all()
    pencere = [v for v in gecmis if v.planlanan + timedelta(days=v.pencere_gun) >= bugun]
    taslaklar = db.execute(_merkez_filtre(select(FormKaydi).join(FormKaydi.gonullu), k)
                           .where(FormKaydi.durum == "taslak").order_by(FormKaydi.guncelleme.desc())).scalars().all()
    sorgular = db.execute(_merkez_filtre(select(Sorgu).join(Sorgu.form_kaydi).join(FormKaydi.gonullu), k)
                          .where(Sorgu.durum == "acik").order_by(Sorgu.acilis)).scalars().all()
    es = select(EslestirmeSonucu).where(EslestirmeSonucu.inceleme_karari.is_(None),
                                        EslestirmeSonucu.karar.in_(["uygun", "olasi"]))
    if k.merkez_id:
        es = es.join(EslestirmeSonucu.hasta).where(Hasta.merkez_id == k.merkez_id)
    eslestirmeler = db.execute(es.order_by(EslestirmeSonucu.skor.desc())).scalars().all()
    return {"yakin_vizit": yakin[:10], "pencere_vizit": pencere[:10], "taslaklar": taslaklar[:10],
            "sorgular": sorgular[:10], "saeler": _saeler(db, k)[:10], "eslestirmeler": eslestirmeler[:10],
            "sayilar": {"yakin_vizit": len(yakin), "pencere_vizit": len(pencere), "taslak": len(taslaklar),
                        "sorgu": len(sorgular), "eslestirme": len(eslestirmeler)}}


def _sayi(db: Session, sorgu) -> int:
    return db.scalar(select(func.count()).select_from(sorgu.order_by(None).subquery())) or 0


def _izlem_gorunumu(db: Session, k: Kullanici, bugun: date) -> dict:
    """CRA / veri yoneticisi / farmakovijilans: yalnizca erisebildigi calismalarin kayitlari (calisma_filtresi)."""
    calisma_ids = calisma_filtresi(db, k, select(Calisma.id)).subquery()
    uyari_s = (select(RiskUyarisi).where(RiskUyarisi.durum == "acik", RiskUyarisi.calisma_id.in_(select(calisma_ids)))
               .order_by(RiskUyarisi.seviye.desc(), RiskUyarisi.olusturma.desc()))
    uyarilar = db.execute(uyari_s.limit(10)).scalars().all()
    uyari_n = _sayi(db, uyari_s)
    aksiyon_n = _sayi(db, uyari_s.where(RiskUyarisi.seviye == "aksiyon"))
    # gecikmis sorgu: acilis tarihi esikten eski olan acik sorgular (SQL tarafinda)
    esik = datetime.combine(bugun - timedelta(days=SORGU_GECIKME_GUN), datetime.min.time())
    sorgu_s = (select(Sorgu).join(Sorgu.form_kaydi).join(FormKaydi.gonullu)
               .where(Sorgu.durum == "acik", Sorgu.acilis < esik, Gonullu.calisma_id.in_(select(calisma_ids)))
               .order_by(Sorgu.acilis))
    gecikmis = db.execute(sorgu_s.limit(10)).scalars().all()
    sdv_s = (select(FormKaydi).join(FormKaydi.gonullu)
             .where(FormKaydi.durum == "tamamlandi", Gonullu.calisma_id.in_(select(calisma_ids)))
             .order_by(FormKaydi.guncelleme))
    sdv_bekleyen = db.execute(sdv_s.limit(10)).scalars().all()
    ziyaret_s = (select(IzlemZiyareti).join(IzlemZiyareti.calisma_merkez)
                 .where(IzlemZiyareti.gerceklesen.is_(None), CalismaMerkez.calisma_id.in_(select(calisma_ids)))
                 .order_by(IzlemZiyareti.planlanan))
    bana = ziyaret_s.where(IzlemZiyareti.cra_id == k.id)
    merkezlerim = ziyaret_s.where((IzlemZiyareti.cra_id != k.id) | (IzlemZiyareti.cra_id.is_(None)))
    sae_s = (select(AdversOlay).join(AdversOlay.gonullu)
             .where(AdversOlay.ciddi.is_(True), AdversOlay.titck_bildirim.is_(None), Gonullu.calisma_id.in_(select(calisma_ids))))
    saeler = db.execute(sae_s).scalars().all()
    saeler = sorted(saeler, key=lambda a: (a.bildirim_suresi_gun if a.bildirim_suresi_gun is not None else 99))
    return {"uyarilar": uyarilar, "gecikmis_sorgular": gecikmis, "sdv_bekleyen": sdv_bekleyen,
            "bana_atanan": db.execute(bana.limit(10)).scalars().all(),
            "merkez_ziyaretleri": db.execute(merkezlerim.limit(10)).scalars().all(), "saeler": saeler[:10],
            "sayilar": {"uyari": uyari_n, "aksiyon": aksiyon_n, "gecikmis_sorgu": _sayi(db, sorgu_s),
                        "sdv": _sayi(db, sdv_s), "ziyaret": _sayi(db, ziyaret_s), "bana_atanan": _sayi(db, bana),
                        "sae": len(saeler), "gec_sae": sum(1 for a in saeler if (a.bildirim_suresi_gun or 0) < 0)}}


def _portfoy_satiri(db: Session, c: Calisma, bugun: date) -> dict:
    kayitli = sum(1 for g in c.gonulluler if g.durum in KAYITLI)
    aktif = [m for m in c.merkezler if m.durum == "aktif"]
    hiz = sum(m.tahmini_kazanim or 0 for m in aktif)
    kalan = max(0, c.hedef_hasta - kayitli)
    tahmini_ay = (kalan / hiz) if hiz else None
    plan_ay = ((c.planlanan_bitis - bugun).days / 30.4) if c.planlanan_bitis else None
    uyarilar = db.execute(select(RiskUyarisi).where(RiskUyarisi.calisma_id == c.id, RiskUyarisi.durum == "acik")).scalars().all()
    sae = [a for g in c.gonulluler for a in g.advers_olaylar if a.ciddi]
    if c.durum == CalismaDurumu.ARSIV:
        # arsivdeki calismada takvim sutunlari bos
        tahmini_ay = plan_ay = None
        takvim = "arsiv"
    elif tahmini_ay is None or plan_ay is None:
        takvim = "belirsiz"
    else:
        takvim = "zamaninda" if tahmini_ay <= plan_ay else "risk"
    return {
        "c": c, "kayitli": kayitli, "oran": (100 * kayitli / c.hedef_hasta) if c.hedef_hasta else 0,
        "aktif_merkez": len(aktif), "hiz": hiz, "tahmini_ay": tahmini_ay, "plan_ay": plan_ay, "takvim": takvim,
        "uyari": len(uyarilar), "aksiyon": sum(1 for u in uyarilar if u.seviye == "aksiyon"),
        "sae": len(sae), "bekleyen_sae": sum(1 for a in sae if not a.titck_bildirim),
        "en_riskli": max(aktif, key=lambda m: m.risk_puani or 0) if aktif else None,
    }


def _kumulatif_randomizasyon(db: Session, calisma_ids: list[int], bugun: date) -> dict:
    # Veritabani bagimsiz olsun diye gruplama python tarafinda
    tarihler = [t for (t,) in db.execute(select(Gonullu.randomizasyon_tarihi).where(
        Gonullu.randomizasyon_tarihi.isnot(None), Gonullu.calisma_id.in_(calisma_ids))).all()]
    aylar, kumulatif = [], []
    for i in range(11, -1, -1):
        y, m = bugun.year, bugun.month - i
        while m <= 0:
            y, m = y - 1, m + 12
        ay_sonu = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
        aylar.append(f"{m:02d}/{str(y)[2:]}")
        kumulatif.append(sum(1 for t in tarihler if t <= ay_sonu))
    return {"etiketler": aylar, "degerler": kumulatif}


@router.get("/")
def pano(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    bugun = date.today()
    g = gorunum(k)
    calismalar = _calismalar(db, k)
    if not calismalar:
        toplam = db.scalar(select(func.count(Calisma.id)))
        bos = "olustur" if (toplam == 0 and izinli(k, "calisma.olustur")) else "atanmamis"
        return goster(request, "pano.html", gorunum=g, bos=bos, calismalar=[], bugun=bugun)

    baglam = {"gorunum": g, "bos": None, "calismalar": calismalar, "bugun": bugun}
    if g == "merkez":
        baglam.update(_merkez_gorunumu(db, k, bugun))
    elif g == "izlem":
        baglam.update(_izlem_gorunumu(db, k, bugun))
    else:
        satirlar = [_portfoy_satiri(db, c, bugun) for c in calismalar]
        baglam["satirlar"] = satirlar
        baglam["sayilar"] = {
            "aktif": sum(1 for c in calismalar if c.durum in (CalismaDurumu.AKTIVASYON, CalismaDurumu.KAYIT, CalismaDurumu.IZLEM)),
            "merkez": sum(s["aktif_merkez"] for s in satirlar),
            "kayitli": sum(s["kayitli"] for s in satirlar),
            "hedef": sum(c.hedef_hasta for c in calismalar),
            "takvim_riski": sum(1 for s in satirlar if s["takvim"] == "risk"),
            "uyari": sum(s["uyari"] for s in satirlar),
            "aksiyon": sum(s["aksiyon"] for s in satirlar),
            "bekleyen_sae": sum(s["bekleyen_sae"] for s in satirlar),
        }
        baglam["grafik"] = _kumulatif_randomizasyon(db, [c.id for c in calismalar], bugun) if len(calismalar) >= 2 else None
        baglam["uyarilar"] = db.execute(select(RiskUyarisi).where(
            RiskUyarisi.durum == "acik", RiskUyarisi.calisma_id.in_([c.id for c in calismalar]))
            .order_by(RiskUyarisi.seviye.desc(), RiskUyarisi.olusturma.desc()).limit(8)).scalars().all()
    return goster(request, "pano.html", **baglam)
