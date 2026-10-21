"""Yapisal kriter sorgusunu hasta kaydi uzerinde degerlendirir.

Hasta nesnesi models.Hasta olabilir ya da ayni alanlara sahip dict/obje.
Yapisal veri yoksa 'belirsiz' doner; metin tabanli kanit BDM/RAG katmanindan gelir.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from . import sozluk as S

SONUCLAR = ("saglandi", "saglanmadi", "belirsiz")


@dataclass
class Degerlendirme:
    sonuc: str
    kanit: str | None = None
    guven: float = 0.0
    kullanilan_veri: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _al(hasta, ad, varsayilan=None):
    if hasta is None:
        return varsayilan
    if isinstance(hasta, dict):
        return hasta.get(ad, varsayilan)
    return getattr(hasta, ad, varsayilan)


def _yas_al(hasta) -> int | None:
    y = _al(hasta, "yas")
    if y is not None:
        return int(y)
    dy = _al(hasta, "dogum_yili")
    return date.today().year - int(dy) if dy else None


def _tarih(s) -> date | None:
    if not s:
        return None
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    for f in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m"):
        try:
            return datetime.strptime(str(s)[:19], f).date()
        except ValueError:
            continue
    return None


def _karsilastir(deger: float, op: str, hedef) -> bool:
    if op == ">=":
        return deger >= hedef
    if op == ">":
        return deger > hedef
    if op == "<=":
        return deger <= hedef
    if op == "<":
        return deger < hedef
    if op == "==":
        return abs(deger - hedef) < 1e-9
    if op == "arasi":
        return hedef[0] <= deger <= hedef[1]
    raise ValueError(f"bilinmeyen operator: {op}")


def _op_metin(op: str, hedef, birim: str = "") -> str:
    b = f" {birim}" if birim else ""
    if op == "arasi":
        return f"{hedef[0]:g}-{hedef[1]:g}{b} arasi"
    return f"{op} {hedef:g}{b}"


# ---------------------------------------------------------------------------

def _yas(s: dict, hasta) -> Degerlendirme:
    yas = _yas_al(hasta)
    if yas is None:
        return Degerlendirme("belirsiz", "dogum yili kayitli degil", 0.0)
    ok = _karsilastir(yas, s["op"], s["deger"])
    return Degerlendirme("saglandi" if ok else "saglanmadi", f"yas {yas} ({_op_metin(s['op'], s['deger'])})",
                         0.98, {"yas": yas})


def _cinsiyet(s: dict, hasta) -> Degerlendirme:
    c = _al(hasta, "cinsiyet")
    if not c:
        return Degerlendirme("belirsiz", "cinsiyet kayitli degil", 0.0)
    c = str(c).upper()[0]
    c = {"F": "K", "M": "E"}.get(c, c)
    ok = c == s["deger"]
    return Degerlendirme("saglandi" if ok else "saglanmadi", f"cinsiyet {c}", 0.98, {"cinsiyet": c})


def _gebelik(s: dict, hasta) -> Degerlendirme:
    c = _al(hasta, "cinsiyet")
    yas = _yas_al(hasta)
    if c and str(c).upper()[0] in ("E", "M"):
        return Degerlendirme("saglanmadi", "erkek hasta", 0.97, {"cinsiyet": "E"})
    v = _al(hasta, "vitaller") or {}
    if isinstance(v, dict) and v.get("gebelik_testi") in ("negatif", "pozitif"):
        poz = v["gebelik_testi"] == "pozitif"
        return Degerlendirme("saglandi" if poz else "saglanmadi", f"gebelik testi {v['gebelik_testi']}", 0.9, {"gebelik_testi": v["gebelik_testi"]})
    if c and yas is not None and yas >= 60:
        return Degerlendirme("saglanmadi", f"kadin, {yas} yas; gebelik beklenmiyor", 0.7, {"yas": yas})
    return Degerlendirme("belirsiz", "gebelik/emzirme durumu yapisal veride yok", 0.0)


def _performans(s: dict, hasta) -> Degerlendirme:
    p = _al(hasta, "performans") or {}
    if not isinstance(p, dict):
        return Degerlendirme("belirsiz", None, 0.0)
    deger = p.get(s["olcek"])
    if deger is None or s.get("op") == "belirsiz":
        return Degerlendirme("belirsiz", f"{s['olcek'].upper()} skoru kayitli degil", 0.0)
    ok = _karsilastir(float(deger), s["op"], s["deger"])
    return Degerlendirme("saglandi" if ok else "saglanmadi",
                         f"{s['olcek'].upper()} {deger} ({_op_metin(s['op'], s['deger'])})", 0.95, {s["olcek"]: deger})


def _lab_kayitlari(hasta, s: dict) -> list[dict]:
    kayitlar = _al(hasta, "laboratuvar") or []
    ad = s.get("ad", "")
    es = {S.sade(ad)} | {S.sade(e) for e in S.LAB_SOZLUGU.get(ad, {}).get("es", [])}
    uygun = []
    for k in kayitlar:
        if not isinstance(k, dict):
            continue
        if s.get("loinc") and k.get("loinc") == s["loinc"]:
            uygun.append(k)
        elif S.sade(str(k.get("ad", ""))) in es:
            uygun.append(k)
    uygun.sort(key=lambda k: _tarih(k.get("tarih")) or date.min, reverse=True)
    return uygun


def _lab(s: dict, hasta) -> Degerlendirme:
    if s.get("op") == "belirsiz":
        return Degerlendirme("belirsiz", "kriterde esik deger yok", 0.0)
    kayitlar = _lab_kayitlari(hasta, s)
    if not kayitlar:
        return Degerlendirme("belirsiz", f"{s.get('ad')} sonucu kayitli degil", 0.0)
    k = kayitlar[0]
    t = _tarih(k.get("tarih"))
    if s.get("son_gun") and t and (date.today() - t).days > s["son_gun"]:
        return Degerlendirme("belirsiz", f"son {s['ad']} sonucu {t} tarihli, {s['son_gun']} gun penceresi disinda", 0.3)
    try:
        deger = float(k.get("deger"))
    except (TypeError, ValueError):
        return Degerlendirme("belirsiz", f"{s['ad']} degeri sayisal degil", 0.0)
    if "uln_kat" in s:
        ust = k.get("ust_sinir") or k.get("ref_ust")
        if not ust:
            return Degerlendirme("belirsiz", f"{s['ad']} icin referans ust siniri yok", 0.2, {"deger": deger})
        hedef = s["uln_kat"] * float(ust)
        ok = _karsilastir(deger, s["op"], hedef)
        return Degerlendirme("saglandi" if ok else "saglanmadi",
                             f"{s['ad']} {deger:g} {k.get('birim', '')} (ULN {float(ust):g}; {s['op']} {s['uln_kat']}xULN)",
                             0.9, {"deger": deger, "ust_sinir": ust, "tarih": str(t or "")})
    cev = S.birim_cevir(deger, k.get("birim"), s.get("birim"))
    if cev is None:
        return Degerlendirme("belirsiz", f"{s['ad']} birimi ({k.get('birim')}) {s.get('birim')} birimine cevrilemedi", 0.2, {"deger": deger})
    ok = _karsilastir(cev, s["op"], s["deger"])
    return Degerlendirme("saglandi" if ok else "saglanmadi",
                         f"{s['ad']} {cev:g} {s.get('birim', '')} ({_op_metin(s['op'], s['deger'], s.get('birim', ''))}; {t or 'tarihsiz'})",
                         0.93, {"deger": cev, "birim": s.get("birim"), "tarih": str(t or "")})


def _tani(s: dict, hasta) -> Degerlendirme:
    tanilar = _al(hasta, "tanilar") or []
    eslesen = []
    for t in tanilar:
        if not isinstance(t, dict):
            continue
        kod = str(t.get("icd10", "")).upper()
        ad = S.sade(str(t.get("ad", "")))
        if any(kod.startswith(p.upper()) for p in s.get("icd10", [])) or \
                any(S.sade(term) in ad for term in s.get("terimler", []) if len(term) > 3):
            eslesen.append(t)
    if not eslesen:
        if not tanilar:
            return Degerlendirme("belirsiz", "tani listesi bos", 0.0)
        # tani listesi var ama eslesme yok: muhtemelen saglanmadi, metinle teyit gerekebilir
        # Kod yoklugu hastaligin yoklugu demek degil (kodlama eksik olabilir); guveni dusuk tutup
        # metin katmaninin da bakmasini sagliyoruz.
        return Degerlendirme("saglanmadi", f"ICD-10 {','.join(s.get('icd10', []))} kaydi yok", 0.6, {"tani_sayisi": len(tanilar)})
    if s.get("son_ay"):
        esik = date.today().toordinal() - s["son_ay"] * 30
        yeni = [t for t in eslesen if (_tarih(t.get("tarih")) or date.min).toordinal() >= esik]
        if not yeni:
            tarihli = [t for t in eslesen if _tarih(t.get("tarih"))]
            if not tarihli:
                return Degerlendirme("belirsiz", "tani tarihi bilinmiyor", 0.3)
            return Degerlendirme("saglanmadi", f"tani mevcut ama son {s['son_ay']} ay disinda", 0.85)
        eslesen = yeni
    e = eslesen[0]
    guven = 0.9 if not s.get("niteleyiciler") else 0.6
    kanit = f"{e.get('icd10', '')} {e.get('ad', '')}".strip() + (f" ({e.get('tarih')})" if e.get("tarih") else "")
    if s.get("niteleyiciler"):
        kanit += f" [niteleyiciler yapisal veride dogrulanamadi: {', '.join(s['niteleyiciler'])}]"
    return Degerlendirme("saglandi", kanit, guven, {"tani": e})


def _ilac(s: dict, hasta) -> Degerlendirme:
    ilaclar = _al(hasta, "ilaclar") or []
    if not ilaclar:
        return Degerlendirme("belirsiz", "ilac listesi bos", 0.0)
    eslesen = []
    for i in ilaclar:
        if not isinstance(i, dict):
            continue
        atc = str(i.get("atc", "")).upper()
        ad = S.sade(str(i.get("ad", "")))
        if any(atc.startswith(p.upper()) for p in s.get("atc", []) if p) or \
                any(S.sade(t) in ad for t in s.get("terimler", [])):
            eslesen.append(i)
    if not eslesen:
        return Degerlendirme("saglanmadi", f"{'/'.join(s.get('terimler', []))} kaydi yok", 0.7, {"ilac_sayisi": len(ilaclar)})
    if s.get("son_gun"):
        esik = date.today().toordinal() - s["son_gun"]
        aktif = [i for i in eslesen if i.get("aktif") or (_tarih(i.get("bitis") or i.get("tarih")) or date.min).toordinal() >= esik]
        if not aktif:
            return Degerlendirme("saglanmadi", f"{eslesen[0].get('ad')} var ama {s['son_gun']} gun penceresi disinda", 0.75)
        eslesen = aktif
    e = eslesen[0]
    return Degerlendirme("saglandi", f"{e.get('ad', '')} ({e.get('atc', '')}){' aktif' if e.get('aktif') else ''}", 0.88, {"ilac": e})


_ALANLAR = {"yas": _yas, "cinsiyet": _cinsiyet, "gebelik": _gebelik, "performans": _performans,
            "lab": _lab, "tani": _tani, "ilac": _ilac}


def degerlendir(yapisal: dict | None, hasta) -> Degerlendirme:
    """Sorguyu hasta uzerinde degerlendirir. Mantiksal baglaclari ozyinelemeli cozer."""
    if not yapisal:
        return Degerlendirme("belirsiz", "yapisal sorgu yok", 0.0)
    if "degil" in yapisal:
        ic = degerlendir(yapisal["degil"], hasta)
        ters = {"saglandi": "saglanmadi", "saglanmadi": "saglandi", "belirsiz": "belirsiz"}
        return Degerlendirme(ters[ic.sonuc], ic.kanit, ic.guven, ic.kullanilan_veri)
    if "ve" in yapisal:
        sonuclar = [degerlendir(s, hasta) for s in yapisal["ve"]]
        olumsuz = [r for r in sonuclar if r.sonuc == "saglanmadi"]
        if olumsuz:
            return Degerlendirme("saglanmadi", olumsuz[0].kanit, olumsuz[0].guven, olumsuz[0].kullanilan_veri)
        if any(r.sonuc == "belirsiz" for r in sonuclar):
            b = next(r for r in sonuclar if r.sonuc == "belirsiz")
            return Degerlendirme("belirsiz", b.kanit, min(r.guven for r in sonuclar), b.kullanilan_veri)
        return Degerlendirme("saglandi", "; ".join(r.kanit for r in sonuclar if r.kanit),
                             min(r.guven for r in sonuclar), {"bilesenler": [r.kullanilan_veri for r in sonuclar]})
    if "veya" in yapisal:
        sonuclar = [degerlendir(s, hasta) for s in yapisal["veya"]]
        olumlu = [r for r in sonuclar if r.sonuc == "saglandi"]
        if olumlu:
            return olumlu[0]
        if any(r.sonuc == "belirsiz" for r in sonuclar):
            return Degerlendirme("belirsiz", "bilesenlerden biri degerlendirilemedi", 0.0)
        return Degerlendirme("saglanmadi", "; ".join(r.kanit for r in sonuclar if r.kanit), min(r.guven for r in sonuclar))
    alan = yapisal.get("alan")
    fn = _ALANLAR.get(alan)
    if fn is None:
        # serbest, organ_fonksiyon, tedavi_gecmisi, zaman -> metin katmanina birakiyoruz
        return Degerlendirme("belirsiz", f"'{alan}' alani yapisal olarak degerlendirilemiyor", 0.0)
    try:
        return fn(yapisal, hasta)
    except (KeyError, TypeError, ValueError) as e:  # bozuk sorgu
        return Degerlendirme("belirsiz", f"sorgu degerlendirilemedi: {e}", 0.0)
