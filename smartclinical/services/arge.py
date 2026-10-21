"""Ar-Ge gostergeleri: yapay zeka bilesenlerinin olculebilir performansi.

TUSEB proje basari olcutleri (duyarlilik >= %90, MAPE <= %25, AUC >= 0,80, on tarama suresinde >= %50
azalma) ile mevcut durumu yan yana koyar. Olcumler gercek hesaplamadir: altin standart set uzerinde
calistirilan degerlendirme, golge mod karsilastirmasi, aktif merkezlerde tahmin-gozlem farki.
Sentetik/laboratuvar verisi ile elde edilen degerler arayuzde ayrica etiketlenir.
"""
import json
import logging
from datetime import date
from functools import lru_cache

from sqlalchemy import select

from ..config import KOK_DIZIN
from ..models import Calisma, CalismaDurumu, CalismaMerkez, EslestirmeSonucu, RiskUyarisi
from .eslestirme import golge_mod_karsilastir
from .merkez_zekasi.aktivasyon import GecikmeModeli, auc
from .merkez_zekasi.kazanim import mape

log = logging.getLogger(__name__)

HEDEFLER = {
    "duyarlilik": 0.90, "halusinasyon": 0.02, "yapilandirma": 0.85, "mape": 25.0, "auc": 0.80,
    "on_tarama_azalma": 50.0, "deid_recall": 0.98,
}
MANUEL_ON_TARAMA_DK = 25.0  # klinisyen dosya incelemesi, hasta basina (pilot olcumleri ile guncellenecek)
AKTIVASYON_HEDEF_GUN = 120


@lru_cache(maxsize=4)
def _altin_standart(saglayici: str, mtime: float) -> dict:
    """Altin standart set uzerinde mevcut BDM yapilandirmasiyla degerlendirme (dosya degismedikce onbellekte)."""
    from ml.degerlendirme.degerlendir import _altin_oku, degerlendir

    from .bdm import BDMIstemci

    yol = KOK_DIZIN / "ml" / "degerlendirme" / "ornek_altin_standart.jsonl"
    kayitlar = _altin_oku(yol)
    return degerlendir(kayitlar, BDMIstemci.olustur(), ["kriter_eslestirme", "kanit_cikar", "kriter_yapilandir"])


def altin_standart_sonuclari() -> dict | None:
    from ..config import ayarlar

    yol = KOK_DIZIN / "ml" / "degerlendirme" / "ornek_altin_standart.jsonl"
    if not yol.exists():
        return None
    try:
        return _altin_standart(ayarlar().bdm_saglayici, yol.stat().st_mtime)
    except Exception as e:  # ml paketi eksikse panel yine acilsin
        log.warning("altin standart degerlendirmesi yapilamadi: %s", e)
        return None


@lru_cache(maxsize=2)
def _kimliksizlestirme(mtime: float) -> dict:
    from .kimliksizlestirme import kimliksizlestir

    yol = KOK_DIZIN / "ml" / "degerlendirme" / "ornek_kimliksizlestirme.jsonl"
    tp = fp = fn = 0
    for satir in yol.read_text(encoding="utf-8").splitlines():
        if not satir.strip():
            continue
        k = json.loads(satir)
        beklenen = sorted(k["varliklar"])
        bulunan = sorted({b.tur for b in kimliksizlestir(k["metin"]).bulgular})
        b_set, e_set = set(bulunan), set(beklenen)
        tp += len(b_set & e_set)
        fp += len(b_set - e_set)
        fn += len(e_set - b_set)
    recall = tp / (tp + fn) if tp + fn else 1.0
    precision = tp / (tp + fp) if tp + fp else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"recall": recall, "precision": precision, "f1": f1, "n": tp + fn}


def kimliksizlestirme_sonuclari() -> dict | None:
    yol = KOK_DIZIN / "ml" / "degerlendirme" / "ornek_kimliksizlestirme.jsonl"
    if not yol.exists():
        return None
    return _kimliksizlestirme(yol.stat().st_mtime)


def golge_mod_ozet(db) -> list[dict]:
    sonuc = []
    for c in db.scalars(select(Calisma).where(Calisma.durum != CalismaDurumu.ARSIV)):
        s = db.scalars(select(EslestirmeSonucu).where(EslestirmeSonucu.calisma_id == c.id,
                                                       EslestirmeSonucu.inceleme_karari.is_not(None))).all()
        if len(s) < 5:
            continue
        m = golge_mod_karsilastir(s, {x.hasta_id: x.inceleme_karari == "onay" for x in s})
        m["calisma"] = c.kod
        sonuc.append(m)
    return sonuc


def kazanim_backtest(db) -> dict | None:
    """Aktif merkezlerde model tahmini (hasta/ay) ile gozlenen hiz; calisma duzeyinde MAPE."""
    bugun = date.today()
    gercek, tahmin, satirlar = [], [], []
    for c in db.scalars(select(Calisma).where(Calisma.durum.in_([CalismaDurumu.KAYIT, CalismaDurumu.IZLEM]))):
        g_top = t_top = 0.0
        n = 0
        for cm in c.merkezler:
            if not (cm.aktivasyon_tarihi and cm.tahmini_kazanim):
                continue
            ay = (bugun - cm.aktivasyon_tarihi).days / 30.4
            if ay < 3:
                continue
            g = sum(1 for x in cm.gonulluler if x.randomizasyon_tarihi) / ay
            g_top += g
            t_top += cm.tahmini_kazanim
            n += 1
        if n >= 2 and g_top > 0:
            gercek.append(g_top)
            tahmin.append(t_top)
            satirlar.append({"calisma": c.kod, "merkez": n, "gozlenen": round(g_top, 2), "tahmin": round(t_top, 2)})
    if not gercek:
        return None
    return {"mape": mape(gercek, tahmin), "satirlar": satirlar, "n": len(gercek)}


def gecikme_backtest(db) -> dict | None:
    """Secim-aktivasyon suresi gozlenmis merkezlerde Weibull modelinin ayirt edicilik gucu (AUC).

    Ornek-ici degerlendirmedir; gercek dogrulama pilot calismada prospektif yapilacaktir.
    """
    from .merkez_zekasi import _aktivasyon_kovaryat

    cms = [cm for cm in db.scalars(select(CalismaMerkez)) if cm.secim_tarihi and cm.aktivasyon_tarihi]
    if len(cms) < 10:
        return None
    kayitlar = []
    for cm in cms:
        sure = (cm.aktivasyon_tarihi - cm.secim_tarihi).days
        if sure > 0:
            kayitlar.append({"sure_gun": sure, "gozlendi": True, "kovaryatlar": _aktivasyon_kovaryat(db, cm), "cm": cm})
    model = GecikmeModeli().fit([{k: v for k, v in r.items() if k != "cm"} for r in kayitlar])
    etiket = [1 if r["sure_gun"] > AKTIVASYON_HEDEF_GUN else 0 for r in kayitlar]
    skor = [model.tahmin(r["kovaryatlar"], AKTIVASYON_HEDEF_GUN).olasilik_gecikme for r in kayitlar]
    if len(set(etiket)) < 2:
        return None
    return {"auc": auc(etiket, skor), "n": len(kayitlar), "gecikme_orani": sum(etiket) / len(etiket)}


def on_tarama_suresi(db) -> dict | None:
    sureler = [s.sure_ms for s in db.scalars(select(EslestirmeSonucu)) if s.sure_ms]
    if not sureler:
        return None
    ort_ms = sum(sureler) / len(sureler)
    # Arastirmaci incelemesi: motor onerisini kanitlariyla gozden gecirme (pilot on olcumu ~4 dk)
    inceleme_dk = 4.0
    toplam_dk = ort_ms / 60000 + inceleme_dk
    return {"motor_ms": ort_ms, "inceleme_dk": inceleme_dk, "toplam_dk": toplam_dk, "manuel_dk": MANUEL_ON_TARAMA_DK,
            "azalma": 100 * (1 - toplam_dk / MANUEL_ON_TARAMA_DK), "n": len(sureler)}


def kri_uyari_kalitesi(db) -> dict:
    uyarilar = db.scalars(select(RiskUyarisi)).all()
    kapanan = [u for u in uyarilar if u.durum in ("kapandi", "yanlis_alarm")]
    yanlis = sum(1 for u in kapanan if u.durum == "yanlis_alarm")
    return {"toplam": len(uyarilar), "acik": sum(1 for u in uyarilar if u.durum == "acik"),
            "kapanan": len(kapanan), "yanlis_alarm_orani": (yanlis / len(kapanan)) if kapanan else None}


def tum_gostergeler(db) -> dict:
    return {
        "hedefler": HEDEFLER,
        "altin": altin_standart_sonuclari(),
        "deid": kimliksizlestirme_sonuclari(),
        "golge": golge_mod_ozet(db),
        "kazanim": kazanim_backtest(db),
        "gecikme": gecikme_backtest(db),
        "on_tarama": on_tarama_suresi(db),
        "kri": kri_uyari_kalitesi(db),
        "ciktilar": sorted(p.name for p in (KOK_DIZIN / "ml" / "ciktilar").glob("*.json")) if (KOK_DIZIN / "ml" / "ciktilar").exists() else [],
    }
