"""Kural tabanli metin degerlendirme.

BDM sunucusu olmadiginda (ya da BDM 'belirsiz' dondugunde) serbest metinden
sayisal/kalip tabanli kanit cikarmaya calisir. Amac kapsamli NLP degil; epikrizlerde
cok sik gecen kaliplari (lab degeri, ECOG, TNM evre, reseptor durumu, yil) yakalamak.
Her sonuc kaynak cumleyle doner; cumle bulunamazsa None (= belirsiz).
"""
import re
from datetime import date

from ..kriter import sozluk as S

_SAYI = r"(\d+(?:[.,]\d+)?)"


def _f(x: str) -> float:
    return float(x.replace(",", "."))


def _karsilastir(deger: float, op: str, hedef) -> bool | None:
    if op == "arasi" and isinstance(hedef, (list, tuple)) and len(hedef) == 2:
        return hedef[0] <= deger <= hedef[1]
    try:
        h = float(hedef)
    except (TypeError, ValueError):
        return None
    return {">=": deger >= h, ">": deger > h, "<=": deger <= h, "<": deger < h, "=": deger == h, "==": deger == h}.get(op)


def _hedef_metin(op, hedef, birim=""):
    if op == "arasi":
        return f"{hedef[0]:g}-{hedef[1]:g} {birim}".strip()
    return f"{op} {float(hedef):g} {birim}".strip()


# --- lab ---------------------------------------------------------------------

def _lab(sorgu: dict, cumle: str):
    ad = sorgu.get("ad")
    if not ad or sorgu.get("op") in (None, "belirsiz"):
        return None
    adlar = [ad] + list(S.LAB_SOZLUGU.get(ad, {}).get("es", []))
    sc = S.sade(cumle)
    for a in sorted(adlar, key=len, reverse=True):
        m = re.search(r"\b" + re.escape(S.sade(a)) + r"\b[^0-9%]{0,12}%?\s*" + _SAYI, sc)
        if not m:
            continue
        deger = _f(m.group(1))
        if "uln_kat" in sorgu:
            return None  # ULN karsilastirmasi icin referans araligi gerekir
        ok = _karsilastir(deger, sorgu["op"], sorgu.get("deger"))
        if ok is None:
            return None
        return ("saglandi" if ok else "saglanmadi", 0.78,
                f"{ad} {deger:g} ({_hedef_metin(sorgu['op'], sorgu['deger'], sorgu.get('birim', ''))})")
    return None


# --- yas ---------------------------------------------------------------------

def _yas(sorgu: dict, cumle: str):
    m = re.search(r"\b(\d{1,3})\s*(yasinda|yas|years? old|y/o|yasindaki)\b", S.sade(cumle))
    if not m:
        return None
    yas = int(m.group(1))
    op, hedef = sorgu.get("op"), sorgu.get("deger")
    ok = _karsilastir(yas, op, hedef)
    if ok is None:
        return None
    return ("saglandi" if ok else "saglanmadi", 0.85, f"yas {yas} ({_hedef_metin(op, hedef)})")


# --- performans ---------------------------------------------------------------

def _performans(sorgu: dict, cumle: str):
    olcek = (sorgu.get("olcek") or "").lower()
    sc = S.sade(cumle)
    kalip = {"ecog": r"\becog\b[^0-9]{0,30}(\d)", "karnofsky": r"\bkarnofsky\b[^0-9]{0,20}(\d{2,3})",
             "nyha": r"\bnyha\b(?:\s*(?:sinif|class|fonksiyonel sinif|fc))?\s*(iv|i{1,3}|[1-4])\b"}.get(olcek)
    if not kalip:
        return None
    m = re.search(kalip, sc)
    if not m:
        return None
    v = m.group(1)
    if olcek == "nyha" and not v.isdigit():
        v = {"i": 1, "ii": 2, "iii": 3, "iv": 4}[v]
    deger = float(v)
    ok = _karsilastir(deger, sorgu.get("op"), sorgu.get("deger"))
    if ok is None:
        return None
    return ("saglandi" if ok else "saglanmadi", 0.85, f"{olcek.upper()} {deger:g} ({_hedef_metin(sorgu.get('op'), sorgu.get('deger'))})")


# --- TNM evre -----------------------------------------------------------------

_TNM_KRITER = re.compile(r"t(\d)\s*-\s*t(\d)|t(\d)", re.I)


def _evre(kriter_metni: str, cumle: str):
    km = S.sade(kriter_metni)
    if "evre" not in km and "stage" not in km:
        return None
    t_aralik = re.search(r"\bt(\d)\s*-\s*t(\d)\b", km)
    n_aralik = re.search(r"\bn(\d)\s*-\s*n(\d)\b", km)
    m0 = re.search(r"\bm0\b", km)
    tnm = re.search(r"\bt(\d)[a-c]?\s*n(\d)[a-c]?\s*m(\d)\b", S.sade(cumle))
    if not tnm or not (t_aralik or n_aralik or m0):
        return None
    t, n, m_ = int(tnm.group(1)), int(tnm.group(2)), int(tnm.group(3))
    ok = True
    if t_aralik:
        ok &= int(t_aralik.group(1)) <= t <= int(t_aralik.group(2))
    if n_aralik:
        ok &= int(n_aralik.group(1)) <= n <= int(n_aralik.group(2))
    if m0:
        ok &= m_ == 0
    return ("saglandi" if ok else "saglanmadi", 0.8, f"TNM T{t}N{n}M{m_}")


# --- reseptor / biyobelirtec ---------------------------------------------------

def _biyobelirtec(kriter_metni: str, cumle: str):
    km = S.sade(kriter_metni)
    sc = S.sade(cumle)
    bulgular = []
    if re.search(r"\b(hormon reseptor|er ve/veya pr|er/pr|hr\+|hr pozitif|hormone receptor)", km):
        er = re.search(r"\ber\s*\(?\s*(\+|-|pozitif|negatif)", sc)
        pr = re.search(r"\bpr\s*\(?\s*(\+|-|pozitif|negatif)", sc)
        if er or pr:
            poz = any(x and x.group(1) in ("+", "pozitif") for x in (er, pr))
            istenen_poz = "pozitif" in km or "+" in km
            bulgular.append(("saglandi" if poz == istenen_poz else "saglanmadi", 0.8, "ER/PR durumu metinden"))
    if "her2" in km:
        neg = re.search(r"her2[\s-]*(?:skor|score|ihc)?\s*[:]?\s*(negatif|\(-\)|0\b|1\+|2\+ ish negatif|negative)", sc) or re.search(r"ish negatif", sc)
        poz = re.search(r"her2[\s-]*(?:skor|score|ihc)?\s*[:]?\s*(pozitif|\(\+\)|3\+|positive)", sc) or re.search(r"ish pozitif", sc)
        if neg or poz:
            istenen_neg = "negatif" in km or "negative" in km
            durum_neg = bool(neg) and not poz
            bulgular.append(("saglandi" if durum_neg == istenen_neg else "saglanmadi", 0.8, "HER2 durumu metinden"))
    # genel belirtec: kriterde "<token> pozitif|negatif" (HBsAg, anti-HCV, HIV, EGFR, ALK, PD-L1 ...)
    for m in re.finditer(r"\b([a-z0-9][a-z0-9\-]{1,12})\s*(pozitif|negatif)\b", km):
        token, istenen = m.group(1), m.group(2)
        if token in ("her2", "er", "pr", "reseptoru", "reseptor"):
            continue
        d = re.search(r"\b" + re.escape(token) + r"\s*[:]?\s*(pozitif|negatif|\(\+\)|\(-\))", sc)
        if d:
            durum = "pozitif" if d.group(1) in ("pozitif", "(+)") else "negatif"
            bulgular.append(("saglandi" if durum == istenen else "saglanmadi", 0.8, f"{token} {durum}"))
    if not bulgular:
        return None
    if any(b[0] == "saglanmadi" for b in bulgular):
        return next(b for b in bulgular if b[0] == "saglanmadi")
    return bulgular[0]


# --- gebelik ------------------------------------------------------------------

def _gebelik(kriter_metni: str, cumle: str):
    if not re.search(r"\b(gebe|hamile|emzir|pregnan|lactat)", S.sade(kriter_metni)):
        return None
    sc = S.sade(cumle)
    if re.search(r"\b(gebe degil|hamile degil|gebelik yok|gebelik dislandi|emzirmiyor|emzirmemekte|postmenopozal|post-menopozal|menopozda|"
                 r"not pregnant|postmenopausal|erkek hasta|erkek)\b", sc):
        return ("saglanmadi", 0.8, "gebelik dislandi")
    if re.search(r"\b(gebe|hamile|gebelik haftasi|emzir\w*|laktasyon|lohusa)\b", sc) and not re.search(r"\bdegil\b", sc):
        return ("saglandi", 0.75, "gebelik/emzirme ifadesi")
    return None


# --- tedavi gecmisi -----------------------------------------------------------

_GECMIS_BAGLAM = re.compile(r"\b(daha once|onceden|almis|almamis|gormus|gormemis|uygulanmis|uygulanmamis|oykusu|"
                            r"gecmisinde|gecirmis|tamamlamis|prior|previous|previously|history of|received)\b")


def _tedavi_gecmisi(sorgu: dict, cumle: str):
    terimler = [t for t in sorgu.get("terimler", []) if t]
    if not terimler:
        return None
    sc = S.sade(cumle)
    if not any(re.search(r"\b" + re.escape(S.sade(t)), sc) for t in terimler):
        return None
    if not _GECMIS_BAGLAM.search(sc):
        return None  # "neoadjuvan tedavi planlandi" gibi gelecek/plan ifadeleri kanit degildir
    olumsuz = re.search(r"\b(almamis|gormemis|uygulanmamis|yok|degil|not|no)\b", sc)
    return ("saglanmadi" if olumsuz else "saglandi", 0.72, "tedavi gecmisi ifadesi")


def _uln_var(sorgu: dict) -> bool:
    yigin = [sorgu]
    while yigin:
        s = yigin.pop()
        if not isinstance(s, dict):
            continue
        if "uln_kat" in s:
            return True
        for k in ("ve", "veya"):
            yigin.extend(s.get(k, []))
        if "degil" in s:
            yigin.append(s["degil"])
    return False


# --- zaman penceresi ----------------------------------------------------------

def _zaman_penceresi(sorgu: dict, cumle: str):
    """'Son 6 ay icinde MI' gibi kriterde olay cumlede yil ile veriliyorsa pencereyi kontrol eder."""
    son_ay = sorgu.get("son_ay") or (sorgu.get("son_gun") and sorgu["son_gun"] / 30.4)
    if not son_ay:
        return None
    sc = S.sade(cumle)
    yil = re.search(r"\b(19\d{2}|20\d{2})\s*(yilinda|de|da|yili)\b", sc)
    yil_once = re.search(r"\b(\d{1,2})\s*yil once\b", sc)
    ay_once = re.search(r"\b(\d{1,2})\s*ay once\b", sc)
    gecen_ay = None
    if yil:
        gecen_ay = (date.today().year - int(yil.group(1))) * 12  # yil hassasiyeti; ihtiyatli (yil basi varsayimi yok)
    elif yil_once:
        gecen_ay = int(yil_once.group(1)) * 12
    elif ay_once:
        gecen_ay = int(ay_once.group(1))
    if gecen_ay is None:
        return None
    if gecen_ay > son_ay:
        return ("saglanmadi", 0.7, f"olay yaklasik {gecen_ay} ay once; pencere {son_ay:g} ay")
    return ("saglandi", 0.7, f"olay son {son_ay:g} ay icinde")


_KRITER_OP = re.compile(r"(<=|>=|<|>|=)\s*%?\s*" + _SAYI)
_KRITER_ARALIK = re.compile(_SAYI + r"\s*-\s*" + _SAYI + r"\s*(mm|cm|ms|%|mg|g/dl|kg/m2|ml/dk|ay|yil|gun|hafta)")


def _genel_sayisal(kriter_metni: str, cumle: str, terimler: list[str]):
    """Sozlukte olmayan olcumler icin ("lezyon uzunlugu <= 32 mm", "referans damar capi 2,5-4,0 mm"):
    kriterdeki esik/araligi alir, cumlede terimden sonra gelen ilk sayiyla karsilastirir."""
    km = S.sade(kriter_metni)
    op = _KRITER_OP.search(km)
    aralik = _KRITER_ARALIK.search(km)
    if not op and not aralik:
        return None
    sc = S.sade(cumle)
    anlamli = [S.sade(t) for t in terimler if len(t) >= 4 and not re.search(r"\d", t)]
    for t in sorted(anlamli, key=len, reverse=True):
        m = re.search(r"\b" + re.escape(t) + r"[^0-9]{0,30}?%?\s*" + _SAYI, sc)
        if not m:
            continue
        deger = _f(m.group(1))
        if aralik:
            alt, ust = _f(aralik.group(1)), _f(aralik.group(2))
            if alt > ust:
                return None
            ok = alt <= deger <= ust
            return ("saglandi" if ok else "saglanmadi", 0.7, f"{t} {deger:g} ({alt:g}-{ust:g})")
        ok = _karsilastir(deger, op.group(1), _f(op.group(2)))
        if ok is None:
            return None
        return ("saglandi" if ok else "saglanmadi", 0.7, f"{t} {deger:g} ({op.group(1)} {_f(op.group(2)):g})")
    return None


def degerlendir(sorgu: dict | None, kriter_metni: str, cumle: str, terim_var: bool, terimler: list[str] | None = None):
    """Kalip tabanli degerlendirme. Donus: (sonuc, guven, aciklama) ya da None.

    terim_var: kriter terimlerinden en az biri cumlede geciyor mu (zaman penceresi gibi
    baglama bagli kurallar icin gerekli).
    """
    sorgu = sorgu or {}
    if "degil" in sorgu and isinstance(sorgu["degil"], dict):
        ic = degerlendir(sorgu["degil"], kriter_metni, cumle, terim_var)
        if ic:
            ters = {"saglandi": "saglanmadi", "saglanmadi": "saglandi"}[ic[0]]
            return (ters, ic[1], ic[2] + " (olumsuz kriter)")
        return None
    if "ve" in sorgu or "veya" in sorgu:
        alt = sorgu.get("ve") or sorgu.get("veya")
        sonuclar = [degerlendir(a, kriter_metni, cumle, terim_var) for a in alt if isinstance(a, dict)]
        sonuclar = [x for x in sonuclar if x]
        if not sonuclar:
            return None
        if "ve" in sorgu:
            kotu = [x for x in sonuclar if x[0] == "saglanmadi"]
            return kotu[0] if kotu else (sonuclar[0] if len(sonuclar) == len(alt) else None)
        iyi = [x for x in sonuclar if x[0] == "saglandi"]
        return iyi[0] if iyi else None
    alan = sorgu.get("alan")
    r = None
    if alan == "lab":
        r = _lab(sorgu, cumle)
    elif alan == "yas":
        r = _yas(sorgu, cumle)
    elif alan == "performans":
        r = _performans(sorgu, cumle)
    elif alan == "gebelik":
        r = _gebelik(kriter_metni, cumle)
    elif alan == "tedavi_gecmisi":
        r = _tedavi_gecmisi(sorgu, cumle)
    if r:
        return r
    r = _evre(kriter_metni, cumle) or _biyobelirtec(kriter_metni, cumle) or _gebelik(kriter_metni, cumle)
    if r:
        return r
    if alan in (None, "serbest") and terimler:
        r = _genel_sayisal(kriter_metni, cumle, terimler)
        if r:
            return r
    if terim_var and (sorgu.get("son_ay") or sorgu.get("son_gun")):
        return _zaman_penceresi(sorgu, cumle)
    return None
