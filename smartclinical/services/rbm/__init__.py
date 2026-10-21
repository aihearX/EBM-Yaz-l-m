"""Risk bazli izlem (RBM): KRI hesaplama, anomali tespiti, erken uyari ve QTL takibi."""

from sqlalchemy import select

from ...models import RiskGostergesi
from .anomali import AnomaliSonucu, anomali_tespit, cusum
from .gostergeler import HESAPLAYICILAR, KRI_SOZLUK, VARSAYILAN_KRILER, kri_hesapla
from .uyari import (
    VARSAYILAN_QTLLER,
    bilesik_risk_puani,
    calisma_krileri,
    erken_uyari_calistir,
    izlem_onerisi,
    qtl_guncelle,
    varsayilan_qtlleri_yukle,
)

__all__ = [
    "HESAPLAYICILAR",
    "KRI_SOZLUK",
    "VARSAYILAN_KRILER",
    "VARSAYILAN_QTLLER",
    "AnomaliSonucu",
    "anomali_tespit",
    "bilesik_risk_puani",
    "calisma_krileri",
    "cusum",
    "erken_uyari_calistir",
    "izlem_onerisi",
    "kri_hesapla",
    "qtl_guncelle",
    "varsayilan_krileri_yukle",
    "varsayilan_qtlleri_yukle",
]


def varsayilan_krileri_yukle(db, calisma_id=None):
    """Varsayilan KRI tanimlarini RiskGostergesi tablosuna yazar (varsa atlar). commit etmez."""
    mevcut = {k.kod for k in db.scalars(select(RiskGostergesi).where(RiskGostergesi.calisma_id == calisma_id)).all()}
    eklenen = []
    for k in VARSAYILAN_KRILER:
        if k["kod"] in mevcut:
            continue
        kayit = RiskGostergesi(calisma_id=calisma_id, **k)
        db.add(kayit)
        eklenen.append(kayit)
    return eklenen
