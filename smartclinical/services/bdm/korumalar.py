"""BDM ciktisi icin koruma katmani: halusinasyon, belirsizlik, JSON dogrulama, PHI sizintisi."""

import json
import logging
import re
from collections import Counter

log = logging.getLogger(__name__)

GUVEN_ESIGI = 0.6          # altindaki sonuclar belirsize cekilir
KANIT_BENZERLIK_ESIGI = 0.8

_TR = str.maketrans("İIÇĞÖŞÜ", "iıçğöşü")


class KorumaIhlali(Exception):
    pass


def _norm(s: str) -> str:
    s = (s or "").translate(_TR).lower()
    s = re.sub(r"[^\w\s%/.,<>=-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def kanit_dogrula(kanit: str, parcalar: list[str], indeks: int | None = None) -> tuple[bool, int | None]:
    """Modelin verdigi kanit cumlesi kaynak parcalarda birebir geciyor mu?

    Kucuk farklara (bosluk, noktalama) tolerans var; kelime bazinda %85 ortusme yoksa reddedilir.
    Kaynakta olmayan 'kanit' halusinasyonun en sik bicimi, o yuzden kati davraniyoruz.
    """
    k = _norm(kanit)
    if not k:
        return False, None
    sira = [indeks] if indeks is not None and 0 <= indeks < len(parcalar) else []
    sira += [i for i in range(len(parcalar)) if i not in sira]
    for i in sira:
        p = _norm(parcalar[i])
        if k in p:
            return True, i
        # kelime ortusmesi (model bazen virgul/noktayi degistiriyor)
        kk = [w.strip(".,;:") for w in k.split()]
        if len(kk) >= 4:
            pk = {w.strip(".,;:") for w in p.split()}
            oran = sum(1 for w in kk if w in pk) / len(kk)
            if oran >= KANIT_BENZERLIK_ESIGI:
                return True, i
    return False, None


def json_ayikla(metin: str) -> dict | None:
    """Model ciktisindaki ilk JSON nesnesini ayiklar. Markdown ``` bloklarini da tolere eder."""
    if not metin:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", metin, re.S)
    aday = m.group(1) if m else None
    if aday is None:
        bas = metin.find("{")
        if bas < 0:
            return None
        derinlik = 0
        for i in range(bas, len(metin)):
            if metin[i] == "{":
                derinlik += 1
            elif metin[i] == "}":
                derinlik -= 1
                if derinlik == 0:
                    aday = metin[bas:i + 1]
                    break
    if not aday:
        return None
    try:
        v = json.loads(aday)
    except json.JSONDecodeError:
        # tek tirnak / sondaki virgul gibi sik hatalar
        try:
            v = json.loads(re.sub(r",\s*([}\]])", r"\1", aday.replace("'", '"')))
        except json.JSONDecodeError:
            log.debug("JSON ayiklanamadi: %.120s", aday)
            return None
    return v if isinstance(v, dict) else None


def sema_dogrula(veri: dict | None, zorunlu: dict[str, type | tuple]) -> bool:
    if not isinstance(veri, dict):
        return False
    for alan, tip in zorunlu.items():
        if alan not in veri or not isinstance(veri[alan], tip):
            return False
    return True


def belirsizlik_uygula(sonuc: str, guven: float, esik: float = GUVEN_ESIGI) -> tuple[str, float]:
    """Dusuk guvenli kararlari 'belirsiz'e ceker; arastirmaci incelemesine duser."""
    try:
        g = float(guven)
    except (TypeError, ValueError):
        return "belirsiz", 0.0
    g = max(0.0, min(1.0, g))
    if sonuc not in ("saglandi", "saglanmadi", "belirsiz"):
        return "belirsiz", g
    if sonuc != "belirsiz" and g < esik:
        return "belirsiz", g
    return sonuc, g


def cogunluk_oyu(sonuclar: list[tuple[str, float]]) -> tuple[str, float]:
    """Self-consistency: ayni soru n kez sorulur, cogunluk karari alinir, guven = oy orani * ort. guven."""
    if not sonuclar:
        return "belirsiz", 0.0
    sayac = Counter(s for s, _ in sonuclar)
    karar, adet = sayac.most_common(1)[0]
    if adet * 2 <= len(sonuclar):  # salt cogunluk yoksa
        return "belirsiz", 0.0
    ort = sum(g for s, g in sonuclar if s == karar) / adet
    return karar, round(ort * adet / len(sonuclar), 3)


# TCKN: 11 hane, ilk hane 0 degil, son hane cift. Tam algoritma kimliksizlestirme modulunde;
# burada istemin disari gitmemesi icin kaba kontrol yeterli.
_TCKN = re.compile(r"(?<!\d)[1-9]\d{9}[02468](?!\d)")
_TEL = re.compile(r"(?<!\d)(?:\+90|0)?\s?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)")
_EPOSTA = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def phi_kontrol(istem: str) -> None:
    """Istem icinde kimlik verisi varsa modele gonderilmez. Kimliksizlestirme atlandiysa burada yakalanir."""
    for ad, kalip in (("TCKN", _TCKN), ("telefon", _TEL), ("e-posta", _EPOSTA)):
        if kalip.search(istem or ""):
            log.warning("BDM istemi engellendi: %s kalibi tespit edildi", ad)
            raise KorumaIhlali(f"İstem içinde {ad} kalıbı tespit edildi; metin kimliksizleştirilmeden modele gönderilemez.")
