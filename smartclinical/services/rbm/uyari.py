"""Erken uyari motoru: KRI esikleri + merkezler arasi anomali -> RiskUyarisi kayitlari."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from ...models import (
    GonulluDurumu,
    KaliteToleransLimiti,
    ProtokolSapmasi,
    RiskGostergesi,
    RiskUyarisi,
)
from .anomali import anomali_tespit
from .gostergeler import VARSAYILAN_KRILER, kri_hesapla

log = logging.getLogger(__name__)


def _simdi():
    return datetime.now(UTC).replace(tzinfo=None)


def calisma_krileri(db, calisma):
    """Calismaya ozel tanimlar varsa onlar, yoksa genel sablon (calisma_id=None), o da yoksa varsayilanlar."""
    ozel = db.scalars(select(RiskGostergesi).where(RiskGostergesi.calisma_id == calisma.id,
                                                   RiskGostergesi.aktif.is_(True))).all()
    if ozel:
        return ozel
    genel = db.scalars(select(RiskGostergesi).where(RiskGostergesi.calisma_id.is_(None),
                                                    RiskGostergesi.aktif.is_(True))).all()
    return genel if genel else VARSAYILAN_KRILER


def _alan(k, ad):
    return k[ad] if isinstance(k, dict) else getattr(k, ad)


def _esik_seviyesi(deger, k):
    yon = _alan(k, "yon")
    uyari, aksiyon = _alan(k, "esik_uyari"), _alan(k, "esik_aksiyon")
    if deger is None:
        return None
    if yon == "yuksek":
        if aksiyon is not None and deger >= aksiyon:
            return "aksiyon"
        if uyari is not None and deger >= uyari:
            return "uyari"
    else:
        if aksiyon is not None and deger <= aksiyon:
            return "aksiyon"
        if uyari is not None and deger <= uyari:
            return "uyari"
    return None


def _normalize(deger, k):
    """KRI degerini 0-1 risk katkisina cevirir (aksiyon esiginde 1)."""
    if deger is None:
        return 0.0
    yon = _alan(k, "yon")
    uyari, aksiyon = _alan(k, "esik_uyari"), _alan(k, "esik_aksiyon")
    if uyari is None or aksiyon is None or uyari == aksiyon:
        return 0.0
    if yon == "yuksek":
        oran = (deger - uyari * 0.5) / (aksiyon - uyari * 0.5)
    else:
        oran = (uyari * 1.5 - deger) / (uyari * 1.5 - aksiyon)
    return max(0.0, min(1.2, oran))


def bilesik_risk_puani(degerler, kriler):
    """Agirlikli 0-100 puan."""
    toplam_w = 0.0
    toplam = 0.0
    for k in kriler:
        kod = _alan(k, "kod")
        if kod not in degerler or degerler[kod] is None:
            continue
        w = float(_alan(k, "agirlik") or 1.0)
        toplam_w += w
        toplam += w * _normalize(degerler[kod], k)
    if toplam_w == 0:
        return None
    return round(min(100.0, 100.0 * toplam / toplam_w), 1)


def izlem_onerisi(cm):
    p = cm.risk_puani
    if p is None:
        return "Henuz yeterli veri yok; standart izlem plani uygulanir."
    if p >= 60:
        return "Yuksek risk: 2 hafta icinde tetiklenmis yerinde ziyaret, kritik verilerde %100 SDV."
    if p >= 35:
        return "Orta risk: yerinde ziyaret sikligi artirilir (6 haftada bir), kritik verilerde %50 SDV, aylik uzaktan izlem."
    if p >= 15:
        return "Dusuk-orta risk: standart ziyaret plani, risk bazli SDV (%20), aylik uzaktan veri incelemesi."
    return "Dusuk risk: uzaktan izlem yeterli, yerinde ziyaret 3 ayda bir, SDV ornekleme %10."


def erken_uyari_calistir(db, calisma, kullanici_id=None):
    """KRI'leri hesaplar, esik ve anomali kontrolu yapar, RiskUyarisi uretir/gunceller. commit etmez."""
    kriler = calisma_krileri(db, calisma)
    degerler = kri_hesapla(db, calisma, kriler)
    cm_map = {cm.id: cm for cm in calisma.merkezler}
    uretilen = []

    acik_uyarilar = db.scalars(select(RiskUyarisi).where(RiskUyarisi.calisma_id == calisma.id,
                                                         RiskUyarisi.durum.in_(("acik", "inceleniyor")))).all()
    acik_map = {(u.calisma_merkez_id, u.kri_kod): u for u in acik_uyarilar}

    for k in kriler:
        kod = _alan(k, "kod")
        yon = _alan(k, "yon")
        ad = _alan(k, "ad")
        birim = _alan(k, "birim") or ""
        kri_degerler = {cm_id: d.get(kod) for cm_id, d in degerler.items()}
        anomali = anomali_tespit(kri_degerler, yon)

        for cm_id, deger in kri_degerler.items():
            if deger is None:
                continue
            cm = cm_map[cm_id]
            seviye = _esik_seviyesi(deger, k)
            an = anomali.get(cm_id)
            aykiri = bool(an and an.aykiri)
            if seviye is None and not aykiri:
                continue
            if seviye is None:
                seviye = "uyari"
            if aykiri and seviye == "uyari" and an.z is not None and an.z >= 4:
                seviye = "aksiyon"

            esik = _alan(k, "esik_aksiyon") if seviye == "aksiyon" else _alan(k, "esik_uyari")
            merkez_ad = cm.merkez.ad if cm.merkez else f"Merkez {cm.merkez_no}"
            mesaj = f"{merkez_ad} ({cm.merkez_no}): {ad} = {deger:g} {birim}".rstrip()
            nedenler = []
            if _esik_seviyesi(deger, k):
                yon_metin = "ustunde" if yon == "yuksek" else "altinda"
                nedenler.append(f"Deger {esik:g} {birim} {seviye} esiginin {yon_metin}.".replace("  ", " "))
            if an:
                nedenler.append(an.aciklama)
            nedenler.append(f"Gostergenin bilesik risk puanindaki agirligi {_alan(k, 'agirlik'):g}.")
            aciklama = " ".join(nedenler)

            mevcut = acik_map.get((cm_id, kod))
            if mevcut:
                mevcut.deger = deger
                mevcut.esik = esik
                mevcut.seviye = seviye
                mevcut.mesaj = mesaj
                mevcut.aciklama = aciklama
                uretilen.append(mevcut)
                continue
            u = RiskUyarisi(calisma_id=calisma.id, calisma_merkez_id=cm_id, kri_kod=kod, deger=deger,
                            esik=esik, seviye=seviye, mesaj=mesaj, aciklama=aciklama,
                            atanan_id=kullanici_id)
            db.add(u)
            acik_map[(cm_id, kod)] = u
            uretilen.append(u)

    # degeri normale donen acik uyarilari kapat
    for (cm_id, kod), u in list(acik_map.items()):
        if u in uretilen:
            continue
        degerlendirildi = cm_id in degerler and any(_alan(k, "kod") == kod for k in kriler)
        if degerlendirildi:
            u.durum = "kapandi"
            u.kapanis = _simdi()
            u.kapanis_notu = "Gosterge esik altina dondu (otomatik kapanis)."

    for cm_id, d in degerler.items():
        cm_map[cm_id].risk_puani = bilesik_risk_puani(d, kriler)

    log.info("Erken uyari: calisma %s, %d uyari", calisma.kod, len(uretilen))
    return uretilen


# --- QTL --------------------------------------------------------------

def _qtl_erken_ayrilma(db, calisma):
    kayitli = [g for g in calisma.gonulluler if g.durum in (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE,
                                                            GonulluDurumu.TAKIPTE, GonulluDurumu.TAMAMLADI,
                                                            GonulluDurumu.AYRILDI)]
    if not kayitli:
        return None
    return round(100.0 * sum(1 for g in kayitli if g.durum == GonulluDurumu.AYRILDI) / len(kayitli), 1)


def _qtl_major_sapma(db, calisma):
    kayitli = [g for g in calisma.gonulluler if g.randomizasyon_tarihi]
    if not kayitli:
        return None
    cm_ids = [cm.id for cm in calisma.merkezler]
    n = len(db.scalars(select(ProtokolSapmasi.id).where(ProtokolSapmasi.calisma_merkez_id.in_(cm_ids),
                                                        ProtokolSapmasi.onem == "major")).all())
    return round(100.0 * n / len(kayitli), 1)


def _qtl_uygunluk_ihlali(db, calisma):
    kayitli = [g for g in calisma.gonulluler if g.randomizasyon_tarihi]
    if not kayitli:
        return None
    cm_ids = [cm.id for cm in calisma.merkezler]
    n = len(db.scalars(select(ProtokolSapmasi.id).where(ProtokolSapmasi.calisma_merkez_id.in_(cm_ids),
                                                        ProtokolSapmasi.kategori == "uygunluk")).all())
    return round(100.0 * n / len(kayitli), 1)


def _qtl_tarama_basarisiz(db, calisma):
    taranan = [g for g in calisma.gonulluler if g.durum not in (GonulluDurumu.ADAY, GonulluDurumu.ON_TARAMA,
                                                                GonulluDurumu.ONAM)]
    if not taranan:
        return None
    return round(100.0 * sum(1 for g in taranan if g.durum == GonulluDurumu.TARAMA_BASARISIZ) / len(taranan), 1)


QTL_HESAPLAYICILAR = {
    "erken_ayrilma": _qtl_erken_ayrilma,
    "major_sapma": _qtl_major_sapma,
    "uygunluk_ihlali": _qtl_uygunluk_ihlali,
    "tarama_basarisiz": _qtl_tarama_basarisiz,
}

VARSAYILAN_QTLLER = [
    {"parametre": "Erken ayrilma orani", "hesaplama": "erken_ayrilma", "limit": 20.0, "ikincil_limit": 15.0, "birim": "%",
     "gerekce": "Birincil sonlanim icin guc hesabinda %20 kayip varsayildi."},
    {"parametre": "Major protokol sapmasi orani", "hesaplama": "major_sapma", "limit": 10.0, "ikincil_limit": 7.0, "birim": "%",
     "gerekce": "Per-protokol populasyonunun butunlugu."},
    {"parametre": "Uygunluk kriteri ihlali", "hesaplama": "uygunluk_ihlali", "limit": 5.0, "ikincil_limit": 3.0, "birim": "%",
     "gerekce": "Yanlis populasyon kaydi birincil analizi tehdit eder."},
]


def qtl_guncelle(db, calisma):
    qtller = db.scalars(select(KaliteToleransLimiti).where(KaliteToleransLimiti.calisma_id == calisma.id)).all()
    for q in qtller:
        fn = QTL_HESAPLAYICILAR.get(q.hesaplama)
        if fn is None:
            continue
        q.mevcut_deger = fn(db, calisma)
        q.son_hesaplama = _simdi()
    return qtller


def varsayilan_qtlleri_yukle(db, calisma):
    mevcut = {q.hesaplama for q in db.scalars(select(KaliteToleransLimiti).where(
        KaliteToleransLimiti.calisma_id == calisma.id)).all()}
    eklenen = []
    for q in VARSAYILAN_QTLLER:
        if q["hesaplama"] in mevcut:
            continue
        kayit = KaliteToleransLimiti(calisma_id=calisma.id, **q)
        db.add(kayit)
        eklenen.append(kayit)
    return eklenen
