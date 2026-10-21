"""Saf Python metrik fonksiyonları. Dış bağımlılık yok; test edilebilir."""

import re
import unicodedata

ETIKETLER = ("saglandi", "saglanmadi", "belirsiz")


def karisiklik(gercek: list[str], tahmin: list[str], pozitif: str = "saglandi") -> dict:
    if len(gercek) != len(tahmin):
        raise ValueError("gercek ve tahmin uzunlukları farklı")
    tp = fp = fn = tn = 0
    for g, t in zip(gercek, tahmin):
        gp, tp_ = g == pozitif, t == pozitif
        if gp and tp_:
            tp += 1
        elif not gp and tp_:
            fp += 1
        elif gp and not tp_:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def duyarlilik(k: dict) -> float:
    payda = k["tp"] + k["fn"]
    return k["tp"] / payda if payda else 0.0


def ozgulluk(k: dict) -> float:
    payda = k["tn"] + k["fp"]
    return k["tn"] / payda if payda else 0.0


def kesinlik(k: dict) -> float:
    payda = k["tp"] + k["fp"]
    return k["tp"] / payda if payda else 0.0


def f1(k: dict) -> float:
    p, r = kesinlik(k), duyarlilik(k)
    return 2 * p * r / (p + r) if (p + r) else 0.0


def dogruluk(gercek: list[str], tahmin: list[str]) -> float:
    if not gercek:
        return 0.0
    return sum(1 for g, t in zip(gercek, tahmin) if g == t) / len(gercek)


def makro_f1(gercek: list[str], tahmin: list[str], etiketler=ETIKETLER) -> float:
    return sum(f1(karisiklik(gercek, tahmin, e)) for e in etiketler) / len(etiketler)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """İki etiketleyici arası uyum."""
    if len(a) != len(b) or not a:
        raise ValueError("boş ya da eşit olmayan listeler")
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    etiketler = set(a) | set(b)
    pe = sum((a.count(e) / n) * (b.count(e) / n) for e in etiketler)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


_BOSLUK = re.compile(r"\s+")
_NOKTALAMA = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(metin: str) -> str:
    # Büyük İ / ı Türkçe'ye özgü; lower() öncesi düzelt
    metin = unicodedata.normalize("NFC", metin).replace("İ", "i").replace("I", "ı").lower()
    metin = _NOKTALAMA.sub(" ", metin)
    return _BOSLUK.sub(" ", metin).strip()


def kanit_kaynakta_mi(kanit: str | None, kaynak: str) -> bool:
    """Modelin verdiği kanıt cümlesi kaynak metinde birebir (normalize) geçiyor mu.

    Geçmiyorsa halüsinasyon sayılır. Boş kanıt halüsinasyon değildir (model çekimser).
    """
    if not kanit:
        return True
    return normalize(kanit) in normalize(kaynak)


def kanit_ortusme(kanit: str | None, span_metinleri: list[str]) -> float:
    """Model kanıtı ile klinisyen kanıt aralıkları arasında token Jaccard (en iyi eşleşme)."""
    if not kanit or not span_metinleri:
        return 0.0
    a = set(normalize(kanit).split())
    en_iyi = 0.0
    for s in span_metinleri:
        b = set(normalize(s).split())
        if not a or not b:
            continue
        en_iyi = max(en_iyi, len(a & b) / len(a | b))
    return en_iyi


def halusinasyon_orani(ciftler: list[tuple[str | None, str]]) -> float:
    """ciftler: [(model_kaniti, kaynak_metin)]. Kanıt veren örnekler arasında kaynakta olmayan oranı."""
    kanitli = [(k, s) for k, s in ciftler if k]
    if not kanitli:
        return 0.0
    return sum(1 for k, s in kanitli if not kanit_kaynakta_mi(k, s)) / len(kanitli)


def _duzlestir(d, onek=""):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from _duzlestir(v, f"{onek}{k}.")
    elif isinstance(d, list):
        for i, v in enumerate(d):
            yield from _duzlestir(v, f"{onek}{i}.")
    else:
        yield onek.rstrip("."), d


def _deger_esit(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-6
    if isinstance(a, str) and isinstance(b, str):
        # operatörler (>=, <) noktalama; normalize edilirse silinir, birebir karşılaştır
        if not a.strip(" ").isalnum() and len(a.strip()) <= 3:
            return a.strip() == b.strip()
        return normalize(a) == normalize(b)
    return a == b


def yapilandirma_eslesme(beklenen: dict | None, tahmin: dict | None) -> dict:
    """Kriter yapılandırma doğruluğu: tam eşleşme + alan bazlı kısmi eşleşme.

    Sadece beklenen yapıdaki alanlar sayılır; None değerli alanlar (son_ay: null) yok sayılır.
    """
    if not beklenen:
        return {"tam": tahmin in (None, {}), "alan_orani": 1.0 if tahmin in (None, {}) else 0.0}
    tahmin = tahmin or {}
    b = {k: v for k, v in _duzlestir(beklenen) if v is not None}
    t = dict(_duzlestir(tahmin))
    if not b:
        return {"tam": True, "alan_orani": 1.0}
    eslesen = sum(1 for k, v in b.items() if k in t and _deger_esit(v, t[k]))
    return {"tam": eslesen == len(b), "alan_orani": eslesen / len(b)}


def guven_kalibrasyonu(guvenler: list[float], dogru: list[bool], kova: int = 5) -> dict:
    """Beklenen kalibrasyon hatası (ECE). Belirsizlik katmanının eşik seçimi için."""
    if not guvenler:
        return {"ece": 0.0, "kovalar": []}
    kovalar = []
    ece = 0.0
    n = len(guvenler)
    for i in range(kova):
        alt, ust = i / kova, (i + 1) / kova
        idx = [j for j, g in enumerate(guvenler) if alt <= g < ust or (i == kova - 1 and g == 1.0)]
        if not idx:
            continue
        ort_guven = sum(guvenler[j] for j in idx) / len(idx)
        ort_dogru = sum(1 for j in idx if dogru[j]) / len(idx)
        ece += len(idx) / n * abs(ort_guven - ort_dogru)
        kovalar.append({"aralik": (alt, ust), "n": len(idx), "guven": ort_guven, "dogruluk": ort_dogru})
    return {"ece": ece, "kovalar": kovalar}
