"""Kural tabanli kriter ayristirici.

Protokoldeki dahil etme / haric tutma cumlesini hesaplanabilir sorguya cevirir.
BDM erisilemediginde ya da BDM ciktisi dogrulanamadiginda bu yol kullanilir.
Sorgu bicimi:
    {"alan": "yas", "op": ">=", "deger": 18}
    {"ve": [ {...}, {...} ]} / {"veya": [...]} / {"degil": {...}}
"""

import re
from dataclasses import asdict, dataclass, field

from . import sozluk as S

KATEGORILER = ("yas", "cinsiyet", "tani", "lab", "ilac", "performans", "gebelik",
               "organ_fonksiyon", "zaman", "tedavi_gecmisi", "serbest")


@dataclass
class KriterYapisi:
    kategori: str
    sorgu: dict | None
    guven: float
    yontem: str = "kural"
    notlar: list[str] = field(default_factory=list)
    metin: str = ""
    tip: str = "dahil"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------

_SAYI = r"(\d{1,3}(?:\.\d{3})+(?![.,]\d)|\d+(?:[.,]\d+)?)"

# operator kaliplari: (regex, op, sayi_onde?)  - metin normalize edilmis halde aranir
_OP_SONRA = [  # sayi ... kalip
    (r"ve (uzeri|üzeri|ustu|üstü|ustunde|üstünde|uzerinde|üzerinde)", ">="),
    (r"(veya|ya da) (daha )?(fazla|buyuk|büyük|yuksek|yüksek)", ">="),
    (r"(buyuk|büyük) (veya|ya da) (esit|eşit)", ">="),
    (r"(kucuk|küçük) (veya|ya da) (esit|eşit)", "<="),
    (r"(dan|den|tan|ten|ndan|nden) (buyuk|büyük|fazla|yuksek|yüksek)", ">"),
    (r"(buyuk|büyük|fazla)", ">"),
    (r"(nin|nın|nun|nün|in|ın|un|ün) (ustunde|üstünde|uzerinde|üzerinde)", ">"),
    (r"ve (alti|altı|altinda|altında|asagisi|aşağısı)", "<="),
    (r"(veya|ya da) (daha )?(az|dusuk|düşük|kucuk|küçük)", "<="),
    (r"(dan|den|tan|ten|ndan|nden) (kucuk|küçük|az|dusuk|düşük)", "<"),
    (r"(kucuk|küçük|dusuk|düşük)", "<"),
    (r"(nin|nın|nun|nün|in|ın|un|ün) (altinda|altında)", "<"),
    (r"or (older|greater|more|higher|above)", ">="),
    (r"or (younger|less|lower|below|fewer)", "<="),
    (r"and (older|above|over|greater)", ">="),
    (r"and (younger|below|under|less)", "<="),
]
_OP_ONCE = [  # kalip ... sayi
    (r">=|≥|⩾", ">="), (r"<=|≤|⩽", "<="), (r">", ">"), (r"<", "<"),
    (r"en az", ">="), (r"at least", ">="), (r"minimum", ">="), (r"min\.", ">="),
    (r"en fazla", "<="), (r"en cok|en çok", "<="), (r"at most", "<="), (r"maximum", "<="), (r"maks\.|max\.", "<="),
    (r"(older|greater|more|higher) than", ">"), (r"(above|over|exceeding)", ">"),
    (r"(younger|less|lower|fewer) than", "<"), (r"(below|under)", "<"),
    (r"(buyuk|büyük) (veya|ya da) esit|(büyük|buyuk) esit", ">="),
    (r"(kucuk|küçük) (veya|ya da) esit|(küçük|kucuk) esit", "<="),
    (r"(esit|eşit|equal to|=)", "=="),
]

_NEGASYON = [r"\bolmayan\b", r"\bolmamasi\b", r"\bolmaması\b", r"\bbulunmayan\b", r"\bbulunmamasi\b",
             r"\bbulunmaması\b", r"\byoksa\b", r"\byok\b", r"\bdisi\b", r"\bdışı\b", r"\bno\b", r"\bnot\b",
             r"\bwithout\b", r"\babsence of\b", r"\bfree of\b", r"\bnegatif\b(?! meme| her2| hormon)", r"\bgecirmemis\b",
             r"\bgeçirmemiş\b", r"\bkullanmayan\b", r"\balmamis\b", r"\balmamış\b"]

_ROMEN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}


def _sayilar(m: str) -> list[float]:
    out = []
    for s in re.findall(_SAYI, m):
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
            out.append(float(s.replace(".", "")))  # 100.000 -> 100000
        else:
            out.append(S.sayi(s))
    return out


def _op_bul(m: str, sayi_pos: int, sayi_son: int) -> str | None:
    """Sayinin hemen oncesinde/sonrasinda operator kalibi arar."""
    sonra = m[sayi_son:sayi_son + 40]
    for k, op in _OP_SONRA:
        if re.match(r"\s*(?:yas|yaş|yasinda|yaşında|yasindan|yaşından|years?|yrs|y|g/dl|%)?\s*" + k, sonra):
            return op
    once = m[max(0, sayi_pos - 40):sayi_pos]
    for k, op in _OP_ONCE:
        if re.search(k + r"\s*(?:[a-zçğıöşü/]+\s*){0,3}$", once):
            return op
    return None


def _aralik(m: str) -> tuple[float, float] | None:
    """'18-75', '18 ile 75 arasi', 'between 18 and 75', '18 to 75', '0, 1 veya 2' """
    e = re.search(_SAYI + r"\s*%?\s*(?:-|–|ile|to|and|ila|arasi|arası)\s*%?\s*" + _SAYI, m)
    if e and not re.search(r"(?:<|>|≥|≤)\s*$", m[:e.start()]):
        a, b = _sayilar(e.group(0))[:2]
        if a <= b:
            return a, b
    # "0, 1 veya 2" / "0, 1 or 2"
    e = re.search(_SAYI + r"(?:\s*,\s*" + _SAYI + r")+\s*(?:veya|ya da|or)\s*" + _SAYI, m)
    if e:
        s = _sayilar(e.group(0))
        return min(s), max(s)
    return None


def _negasyon(m: str) -> bool:
    # "HER2-negatif", "ER negatif", "ISH negatif" gibi biyobelirtec durumlari kriterin olumsuzlanmasi degildir
    temiz = re.sub(r"\b(her2|er|pr|[iı]sh|f[iı]sh|[iı]hc|egfr|alk|pd-l1|braf|kras|ms[iı]|hr|reseptor[uü])\s*-?\s*negatif\b", " ", m)
    temiz = re.sub(r"\bnegatif\s*\(", " (", temiz)
    return any(re.search(k, temiz) for k in _NEGASYON)


def _sar(sorgu: dict, negatif: bool) -> dict:
    return {"degil": sorgu} if negatif else sorgu


# ---------------------------------------------------------------------------
# Kategori ayristiricilari
# ---------------------------------------------------------------------------

def _yas(m: str) -> tuple[dict, float] | None:
    if not re.search(r"\b(yas|yaş)[a-zçğıöşü]*\b|\b(age|aged|years? old|yrs)\b", m):
        return None
    ar = _aralik(m)
    if ar:
        return {"alan": "yas", "op": "arasi", "deger": [ar[0], ar[1]]}, 0.9
    e = re.search(_SAYI, m)
    if not e:
        return None
    deger = _sayilar(e.group(0))[0]
    op = _op_bul(m, e.start(), e.end())
    if op is None:
        # "18 yas" ya da "yetiskin" -> >= varsayiyoruz, guven dusuk
        op = ">="
        return {"alan": "yas", "op": op, "deger": deger}, 0.6
    return {"alan": "yas", "op": op, "deger": deger}, 0.9


def _gebelik(m: str) -> tuple[dict, float] | None:
    if any(t in m for t in S.GEBELIK_TERIMLERI):
        return {"alan": "gebelik", "deger": True}, 0.9
    return None


def _cinsiyet(m: str) -> tuple[dict, float] | None:
    sm = S.sade(m)
    if re.search(r"\b(kadin|kadinlar|female|women|woman|bayan)\b", sm):
        return {"alan": "cinsiyet", "deger": "K"}, 0.85
    if re.search(r"\b(erkek|erkekler|male|men|man)\b", sm):
        return {"alan": "cinsiyet", "deger": "E"}, 0.85
    return None


def _performans(m: str) -> tuple[dict, float] | None:
    for terim, tanim in S.PERFORMANS_OLCEKLERI.items():
        if terim not in S.sade(m):
            continue
        # romen rakamlarini sayiya cevir (NYHA II-III)
        mm = re.sub(r"\b(iv|iii|ii|i)\b(?!\.)", lambda x: str(_ROMEN[x.group(1)]), S.sade(m))
        mm = re.sub(r"\b(sinif|class|skoru|skor|score|performans|performance|status|durumu)\b", " ", mm)
        ar = _aralik(mm)
        if ar:
            return {"alan": "performans", "olcek": tanim["alan"], "op": "arasi", "deger": [ar[0], ar[1]]}, 0.9
        e = re.search(_SAYI, mm)
        if not e:
            return {"alan": "performans", "olcek": tanim["alan"], "op": "belirsiz"}, 0.3
        deger = _sayilar(e.group(0))[0]
        op = _op_bul(mm, e.start(), e.end()) or "=="
        return {"alan": "performans", "olcek": tanim["alan"], "op": op, "deger": deger}, 0.85
    return None


_ULN = r"(x|×|\*)\s*(uln|nus|nüs|normalin ust siniri|normalin üst sınırı|upper limit of normal)"


def _lab_tek(parca: str) -> dict | None:
    bul = S.lab_bul(parca)
    if not bul:
        return None
    ad, tanim = bul
    m = S.sade(parca)
    sorgu = {"alan": "lab", "loinc": tanim["loinc"], "ad": ad, "birim": tanim["birim"]}
    uln = re.search(_SAYI + r"\s*" + _ULN, m)
    if uln:
        kat = _sayilar(uln.group(1))[0]
        op = _op_bul(m, uln.start(), uln.start() + len(uln.group(1))) or "<="
        sorgu.update({"op": op, "uln_kat": kat})
        return sorgu
    ar = _aralik(m)
    if ar:
        sorgu.update({"op": "arasi", "deger": [ar[0], ar[1]]})
    else:
        # lab adindan sonraki ilk sayi
        adpos = m.find(S.sade(ad))
        bas = adpos + len(S.sade(ad)) if adpos >= 0 else 0
        aday = next(iter(re.finditer(_SAYI, m[bas:])), None) or next(iter(re.finditer(_SAYI, m)), None)
        if aday is None:
            return None
        if aday.start() + bas <= len(m) and m[bas:].startswith(aday.group(0), aday.start()):
            # offset duzeltmesi
            aday = next(e for e in re.finditer(_SAYI, m) if e.start() >= bas) if re.search(_SAYI, m[bas:]) else aday
        deger = _sayilar(aday.group(0))[0]
        op = _op_bul(m, aday.start(), aday.end()) or ">="
        # "100.000/ul" gibi degerler: birim eki
        bir = re.match(r"\s*([a-z0-9^*/µμ.³⁹%]+(?:\s*/\s*1\.73\s*m?2?)?)", m[aday.end():])
        birim = S.birim_normalize(bir.group(1)) if bir and not re.match(r"\s*(ve|veya|and|or|yas|yaş)", m[aday.end():]) else ""
        if birim and birim != tanim["birim"] and birim in ("/uL", "10^9/L", "g/L", "umol/L", "mmol/L", "mg/dL", "%", "mL/min", "mL/min/1.73m2", "U/L"):
            cev = S.birim_cevir(deger, birim, tanim["birim"])
            if cev is not None:
                deger = round(cev, 4)
            else:
                sorgu["birim"] = birim
        sorgu.update({"op": op, "deger": deger})
    pencere = S.zaman_penceresi_gun(parca)
    if pencere:
        sorgu["son_gun"] = pencere
    return sorgu


def _lab(metin: str) -> tuple[dict, float] | None:
    if not S.lab_bul(metin):
        return None
    # "AST ve ALT <= 2.5 x ULN" -> ayni kosul iki teste
    parcalar = [p for p in re.split(r";|,(?!\d)|(?<!\d),|\s+ve\s+|\s+and\s+|\s+veya\s+|\s+or\s+", metin) if p.strip()]
    sorgular = []
    son_kosul = None
    # sondan basa: kosulu olmayan lab terimleri sonraki kosulu paylasir
    bekleyen = []
    for p in reversed(parcalar):
        b = S.lab_bul(p)
        if not b:
            continue
        s = _lab_tek(p)
        if s and ("deger" in s or "uln_kat" in s):
            son_kosul = s
            sorgular.append(s)
            for ad, tanim in bekleyen:
                k = dict(son_kosul)
                k.update({"loinc": tanim["loinc"], "ad": ad, "birim": tanim["birim"]})
                sorgular.append(k)
            bekleyen = []
        elif son_kosul is None:
            bekleyen.append(b)
        else:
            k = dict(son_kosul)
            k.update({"loinc": b[1]["loinc"], "ad": b[0], "birim": b[1]["birim"]})
            sorgular.append(k)
    if not sorgular:
        return {"alan": "lab", "ad": S.lab_bul(metin)[0], "op": "belirsiz"}, 0.3
    sorgular.reverse()
    baglac = "veya" if re.search(r"\s(veya|or)\s", S.normalize(metin)) and len(sorgular) > 1 else "ve"
    if len(sorgular) == 1:
        return sorgular[0], 0.85
    return {baglac: sorgular}, 0.8


def _ilac(m: str) -> tuple[dict, float] | None:
    sm = S.sade(m)
    bulunan = [t for t in S.ILAC_TERIMLERI if re.search(r"(?<![a-z])" + re.escape(S.sade(t)) + r"(?![a-z])", sm)]
    if not bulunan:
        return None
    atc = sorted({a for t in bulunan for a in S.ILAC_SOZLUGU[t]})
    sorgu = {"alan": "ilac", "atc": atc, "terimler": bulunan}
    pencere = S.zaman_penceresi_gun(m)
    if pencere:
        sorgu["son_gun"] = pencere
    if re.search(r"\b(onceden|daha once|gecmis|prior|previous|previously|history of)\b", sm) \
            and not pencere:
        sorgu["gecmis"] = True
    return sorgu, 0.75 if atc else 0.5


_TANI_NITELEYICI = [r"histolojik(?: olarak)?(?: dogrulanmis| doğrulanmış)?", r"sitolojik", r"metastatik", r"lokal ileri",
                    r"ileri evre", r"evre [i1-4v]+[abc]?", r"stage [i1-4v]+[abc]?", r"her2[- ]?(negatif|pozitif|negative|positive)",
                    r"er[- ]?(pozitif|negatif)", r"hormon reseptoru? (pozitif|negatif)", r"egfr mutasyon(u|lu)?",
                    r"alk[- ]?pozitif", r"pd-l1", r"nuks", r"nüks", r"refrakter", r"rezeke edilemeyen", r"unresectable",
                    r"newly diagnosed", r"yeni tani", r"yeni tanı", r"relapsed", r"refractory", r"aktif", r"kontrolsuz", r"kontrolsüz",
                    r"semptomatik", r"dekompanse", r"uncontrolled", r"symptomatic"]


def _tani(m: str) -> tuple[dict, float] | None:
    sm = S.sade(m)
    bulunan = []
    kalan = sm
    for t in S.TANI_TERIMLERI:
        st = S.sade(t)
        if re.search(r"(?<![a-z])" + re.escape(st) + r"(?![a-z])", kalan):
            bulunan.append(t)
            kalan = kalan.replace(st, " ")
    if not bulunan:
        return None
    icd = sorted({c for t in bulunan for c in S.TANI_SOZLUGU[t]})
    niteleyiciler = [e.group(0) for k in _TANI_NITELEYICI for e in re.finditer(k, sm)]
    sorgu = {"alan": "tani", "icd10": icd, "terimler": bulunan}
    if niteleyiciler:
        sorgu["niteleyiciler"] = niteleyiciler
    pencere = S.zaman_penceresi_gun(m)
    if pencere:
        sorgu["son_ay"] = max(1, round(pencere / 30))
    return sorgu, 0.8 if not niteleyiciler else 0.65


def _organ_fonksiyon(m: str) -> tuple[dict, float] | None:
    sm = S.sade(m)
    if re.search(r"(yeterli|uygun|adequate|normal) (organ|karaciger|bobrek|kemik iligi|hematolojik|renal|hepatic|bone marrow)", sm):
        return {"alan": "organ_fonksiyon", "terimler": re.findall(r"(karaciger|bobrek|kemik iligi|hematolojik|renal|hepatic|bone marrow|organ)", sm)}, 0.4
    return None


def _tedavi_gecmisi(m: str) -> tuple[dict, float] | None:
    sm = S.sade(m)
    if re.search(r"\b(onceden|daha once|gecmis(te)?|prior|previous(ly)?|history of|tedavi almis|tedavi gormus|uygulanmis|radyoterapi|cerrahi|ameliyat|transplant|nakil|surgery|radiotherapy)\b", sm):
        kelimeler = re.findall(r"\b(radyoterapi|cerrahi|ameliyat|transplant|nakil|surgery|radiotherapy|kemoterapi|immunoterapi|hedefe yonelik|targeted therapy|hormonoterapi)\b", sm)
        sorgu = {"alan": "tedavi_gecmisi", "terimler": sorted(set(kelimeler))}
        pencere = S.zaman_penceresi_gun(m)
        if pencere:
            sorgu["son_gun"] = pencere
        return sorgu, 0.5
    return None


def _zaman(m: str) -> tuple[dict, float] | None:
    pencere = S.zaman_penceresi_gun(m)
    if pencere and re.search(r"(tani|tanı|diagnos|gecmis|geçmiş|since|sonra|once|önce|ago)", m):
        return {"alan": "zaman", "gun": pencere, "metin": m}, 0.4
    return None


# ---------------------------------------------------------------------------
# Ana giris
# ---------------------------------------------------------------------------

def yapilandir(metin: str, tip: str = "dahil") -> KriterYapisi:
    """Kriter cumlesini hesaplanabilir sorguya cevirir. Hicbir kalip tutmazsa 'serbest'."""
    if not metin or not metin.strip():
        return KriterYapisi("serbest", None, 0.0, metin=metin or "", tip=tip)
    m = S.normalize(metin)
    negatif = _negasyon(m)
    notlar: list[str] = []

    # Gebelik, cinsiyet kaliplarini da kapsar; once bakiyoruz
    g = _gebelik(m)
    if g:
        return KriterYapisi("gebelik", _sar(g[0], negatif), g[1], notlar=notlar, metin=metin, tip=tip)

    y = _yas(m)
    p = _performans(m)
    lb = _lab(metin)
    il = _ilac(m)
    tn = _tani(m)
    cs = _cinsiyet(m)

    # "Daha once X icin sistemik tedavi almis olmak" -> tani degil, tedavi gecmisi.
    # Aksi halde hastada X tanisi var diye haric kriteri saglanmis sayiliyordu (#167).
    if not lb and not il and re.search(r"\b(onceden|daha once|prior|previous(ly)?|history of|tedavi almis|tedavi gormus)\b", S.sade(m)):
        tg = _tedavi_gecmisi(m) or ({"alan": "tedavi_gecmisi", "terimler": []}, 0.5)
        sorgu = dict(tg[0])
        ek = re.findall(r"\b(sistemik tedavi|kemoterapi|endokrin tedavi|hormonoterapi|immunoterapi|radyoterapi|cerrahi|tedavi)\b", S.sade(m))
        sorgu["terimler"] = sorted(set(sorgu.get("terimler", [])) | set(ek))
        if tn:
            sorgu["tani_terimleri"] = tn[0].get("terimler", [])
        return KriterYapisi("tedavi_gecmisi", _sar(sorgu, negatif), 0.55, notlar=notlar + ["tedavi gecmisi; metin kaniti gerekir"], metin=metin, tip=tip)

    # Birden fazla bilesen varsa "ve" ile birlestir; kategori baskin bilesen
    bilesenler: list[tuple[str, dict, float]] = []
    if y:
        bilesenler.append(("yas", y[0], y[1]))
    if p:
        bilesenler.append(("performans", p[0], p[1]))
    if lb:
        bilesenler.append(("lab", lb[0], lb[1]))
    if il:
        bilesenler.append(("ilac", il[0], il[1]))
    if tn:
        bilesenler.append(("tani", tn[0], tn[1]))
    if cs and not (tn and len(bilesenler) > 1):
        bilesenler.append(("cinsiyet", cs[0], cs[1]))

    if bilesenler:
        # yas + cinsiyet gibi bagimsiz bilesenler: "ve"
        # lab icinde zaten ilac/tani terimi gecebilir (ör. "insulin kullanan hastalarda HbA1c..."), lab baskin
        if len(bilesenler) == 1:
            kat, sorgu, guven = bilesenler[0]
        else:
            oncelik = ["lab", "performans", "yas", "tani", "ilac", "cinsiyet"]
            bilesenler.sort(key=lambda b: oncelik.index(b[0]))
            kat = bilesenler[0][0]
            # tani + ilac birlikte: genellikle "X tanisi icin Y tedavisi almis" -> tedavi gecmisi
            if {"tani", "ilac"} <= {b[0] for b in bilesenler} and "lab" not in {b[0] for b in bilesenler}:
                kat = "ilac"
            sorgu = {"ve": [b[1] for b in bilesenler]}
            guven = min(b[2] for b in bilesenler) * 0.95
            notlar.append("birden fazla bilesen birlestirildi")
        if negatif and kat not in ("yas",):
            sorgu = {"degil": sorgu}
            notlar.append("olumsuz ifade")
        return KriterYapisi(kat, sorgu, round(guven, 2), notlar=notlar, metin=metin, tip=tip)

    for kat, fn in (("organ_fonksiyon", _organ_fonksiyon), ("tedavi_gecmisi", _tedavi_gecmisi), ("zaman", _zaman)):
        r = fn(m)
        if r:
            return KriterYapisi(kat, _sar(r[0], negatif), r[1], notlar=notlar, metin=metin, tip=tip)

    notlar.append("kalip bulunamadi; BDM yapilandirmasi onerilir")
    return KriterYapisi("serbest", {"alan": "serbest", "metin": metin.strip()}, 0.2, notlar=notlar, metin=metin, tip=tip)
