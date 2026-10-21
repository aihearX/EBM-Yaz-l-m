"""Merkez zekasi: hasta kazanim tahmini, aktivasyon gecikme riski, merkez siralama."""

import logging
from datetime import date

from sqlalchemy import select

from ...models import Calisma, CalismaMerkez, GonulluDurumu
from .aktivasyon import GecikmeModeli, GecikmeRiski, auc, kaplan_meier
from .kazanim import KazanimTahmini, calisma_kazanim_projeksiyonu, kazanim_tahmini, mape
from .siralama import VARSAYILAN_AGIRLIKLAR, merkez_sirala

log = logging.getLogger(__name__)

__all__ = [
    "VARSAYILAN_AGIRLIKLAR",
    "GecikmeModeli",
    "GecikmeRiski",
    "KazanimTahmini",
    "auc",
    "calisma_kazanim_projeksiyonu",
    "calisma_tahmin_guncelle",
    "gecmis_aktivasyon_verisi",
    "gecmis_kazanim_verisi",
    "kaplan_meier",
    "kazanim_tahmini",
    "mape",
    "merkez_sirala",
]

HEDEF_AKTIVASYON_GUN = 120


def _ay_farki(bas, son):
    if not bas or not son:
        return 0.0
    return max(0.0, (son - bas).days / 30.44)


def gecmis_kazanim_verisi(db, calisma):
    """Diger calismalardaki merkez performansi: {merkez_id: [{hasta, ay}]} ve ayni alandaki havuz."""
    digerleri = db.scalars(select(CalismaMerkez).where(CalismaMerkez.calisma_id != calisma.id)).all()
    bugun = date.today()
    merkez_gecmis = {}
    havuz = []
    for cm in digerleri:
        bas = cm.ilk_hasta_tarihi or cm.aktivasyon_tarihi
        if not bas:
            continue
        bitis = bugun
        if cm.calisma and cm.calisma.planlanan_bitis and cm.calisma.planlanan_bitis < bugun:
            bitis = cm.calisma.planlanan_bitis
        if cm.durum in ("kayit_kapali", "kapali") and cm.gonulluler:
            son_rand = [g.randomizasyon_tarihi for g in cm.gonulluler if g.randomizasyon_tarihi]
            if son_rand:
                bitis = min(bitis, max(son_rand))
        ay = _ay_farki(bas, bitis)
        if ay < 0.5:
            continue
        n = sum(1 for g in cm.gonulluler if g.randomizasyon_tarihi
                and g.durum not in (GonulluDurumu.TARAMA_BASARISIZ, GonulluDurumu.ADAY, GonulluDurumu.ON_TARAMA))
        kayit = {"hasta": n, "ay": ay}
        merkez_gecmis.setdefault(cm.merkez_id, []).append(kayit)
        if cm.calisma and cm.calisma.terapotik_alan == calisma.terapotik_alan:
            havuz.append(kayit)
    if len(havuz) < 3:
        # alan eslesmesi az; tum calismalari havuza al
        havuz = [k for lst in merkez_gecmis.values() for k in lst]
    return merkez_gecmis, havuz


def gecmis_aktivasyon_verisi(db, calisma):
    digerleri = db.scalars(select(CalismaMerkez).where(CalismaMerkez.calisma_id != calisma.id)).all()
    kayitlar = []
    bugun = date.today()
    for cm in digerleri:
        if not cm.secim_tarihi:
            continue
        if cm.aktivasyon_tarihi:
            sure, gozlendi = (cm.aktivasyon_tarihi - cm.secim_tarihi).days, True
        else:
            sure, gozlendi = (bugun - cm.secim_tarihi).days, False
        if sure <= 0:
            continue
        kayitlar.append({"sure_gun": sure, "gozlendi": gozlendi, "kovaryatlar": _aktivasyon_kovaryat(db, cm)})
    return kayitlar


def _aktivasyon_kovaryat(db, cm):
    merkez = cm.merkez
    once = db.scalar(select(CalismaMerkez.id).where(CalismaMerkez.merkez_id == cm.merkez_id,
                                                     CalismaMerkez.id != cm.id,
                                                     CalismaMerkez.aktivasyon_tarihi.is_not(None)).limit(1))
    return {
        "kurum_tipi": merkez.kurum_tipi if merkez else "egitim_arastirma",
        "etik_kurul_ortalama_gun": 60,  # TODO(selin): basvuru tablosundan merkez bazli hesapla
        "sozlesme_sablonu_var": bool(once),
        "daha_once_calisildi": bool(once),
        "calisma_turu": cm.calisma.tur.value if cm.calisma else "ilac",
    }


def calisma_tahmin_guncelle(db, calisma, ufuk_ay=None):
    """Calismanin merkezleri icin kazanim ve gecikme tahminlerini hesaplar ve CalismaMerkez'e yazar.
    commit etmez."""
    merkez_gecmis, havuz = gecmis_kazanim_verisi(db, calisma)
    if ufuk_ay is None:
        if calisma.baslangic and calisma.planlanan_bitis:
            ufuk_ay = max(1, int(_ay_farki(calisma.baslangic, calisma.planlanan_bitis)))
        else:
            ufuk_ay = 12

    model = GecikmeModeli()
    try:
        model.fit(gecmis_aktivasyon_verisi(db, calisma))
    except Exception as e:  # pragma: no cover
        log.warning("Aktivasyon modeli egitilemedi, oncul kullaniliyor: %s", e)

    rekabet_sayac = {}
    for cm in db.scalars(select(CalismaMerkez).join(Calisma).where(
            Calisma.terapotik_alan == calisma.terapotik_alan, Calisma.id != calisma.id,
            CalismaMerkez.durum.in_(("aktif", "siv", "sozlesme", "etik")))).all():
        rekabet_sayac[cm.merkez_id] = rekabet_sayac.get(cm.merkez_id, 0) + 1

    guncellenen = []
    for cm in calisma.merkezler:
        merkez = cm.merkez
        gecmis = merkez_gecmis.get(cm.merkez_id, [])
        kovaryat = {
            "kurum_tipi": merkez.kurum_tipi if merkez else None,
            "alan_deneyimi": len(gecmis),
            "rekabet": rekabet_sayac.get(cm.merkez_id, 0),
        }
        try:
            kt = kazanim_tahmini(gecmis, havuz, ufuk_ay, kovaryat)
            cm.tahmini_kazanim = kt.hasta_ay_ort
            cm.tahmin_alt = kt.hasta_ay_alt
            cm.tahmin_ust = kt.hasta_ay_ust
        except Exception as e:  # pragma: no cover
            log.warning("Kazanim tahmini basarisiz (merkez %s): %s", cm.merkez_id, e)
        try:
            gr = model.tahmin(_aktivasyon_kovaryat(db, cm), HEDEF_AKTIVASYON_GUN)
            cm.gecikme_riski = gr.olasilik_gecikme
        except Exception as e:  # pragma: no cover
            log.warning("Gecikme tahmini basarisiz (merkez %s): %s", cm.merkez_id, e)
        guncellenen.append(cm)
    return guncellenen
