"""Yapisal kriter sorgusunu okunur Turkce cumleye cevirir.

Protokol sayfasinda JSON yerine 'Yaş ≥ 18 VE Cinsiyet = Kadın' gibi bir cumle gosterilir; JSON ayrinti
icinde kalir. Girdi KriterYapisi.to_dict() ciktisi (icinde 'sorgu') ya da dogrudan sorgu sozlugu olabilir.
"""

_OP = {">=": "≥", "<=": "≤", ">": ">", "<": "<", "==": "=", "=": "="}
_CINSIYET = {"K": "Kadın", "E": "Erkek"}
_OLCEK = {"ecog": "ECOG", "nyha": "NYHA", "karnofsky": "Karnofsky", "mrs": "mRS", "gcs": "GKS"}


def _sayi(v) -> str:
    if isinstance(v, (list, tuple)):
        return "–".join(_sayi(x) for x in v)
    if isinstance(v, bool):
        return "evet" if v else "hayır"
    if isinstance(v, (int, float)):
        v = float(v)
        s = str(int(v)) if v == int(v) else f"{v:.4g}"
        return s.replace(".", ",")
    return str(v)


def _liste(v, en_cok: int = 3) -> str:
    if not isinstance(v, (list, tuple)):
        return str(v)
    parcalar = [str(x) for x in v if str(x).strip()]
    if len(parcalar) > en_cok:
        return ", ".join(parcalar[:en_cok]) + f" (+{len(parcalar) - en_cok})"
    return ", ".join(parcalar)


def _karsilastirma(ad: str, s: dict, birim: str = "") -> str:
    op = s.get("op")
    birim_s = f" {birim}" if birim else ""
    if op == "arasi" and isinstance(s.get("deger"), (list, tuple)):
        return f"{ad} {_sayi(s['deger'])}{birim_s} arası"
    if op == "belirsiz" or op is None and "deger" not in s:
        return f"{ad} (değer belirsiz)"
    if s.get("uln_kat") is not None:
        return f"{ad} {_OP.get(op, op)} {_sayi(s['uln_kat'])} × NÜS"
    return f"{ad} {_OP.get(op, op or '=')} {_sayi(s.get('deger'))}{birim_s}"


def _zaman_eki(s: dict) -> str:
    if s.get("son_gun"):
        return f" (son {_sayi(s['son_gun'])} gün)"
    if s.get("son_ay"):
        return f" (son {_sayi(s['son_ay'])} ay)"
    return ""


def _tek(s: dict) -> str:
    alan = s.get("alan")
    if alan == "yas":
        return _karsilastirma("Yaş", s)
    if alan == "cinsiyet":
        return f"Cinsiyet = {_CINSIYET.get(str(s.get('deger', '')).upper(), s.get('deger'))}"
    if alan == "gebelik":
        return "Gebe ya da emziriyor" if s.get("deger", True) else "Gebe değil"
    if alan == "performans":
        olcek = str(s.get("olcek") or "performans")
        return _karsilastirma(f"{_OLCEK.get(olcek.lower(), olcek.upper())} skoru", s)
    if alan == "lab":
        ad = str(s.get("ad") or "Laboratuvar")
        ad = ad.upper() if len(ad) <= 4 else ad[:1].upper() + ad[1:]
        return _karsilastirma(ad, s, "" if s.get("uln_kat") is not None else str(s.get("birim") or "")) + _zaman_eki(s)
    if alan == "ilac":
        terim = _liste(s.get("terimler") or [])
        atc = _liste(s.get("atc") or [])
        c = f"İlaç kullanımı: {terim or 'belirtilen ilaç'}"
        if atc:
            c += f" (ATC {atc})"
        if s.get("gecmis"):
            c += ", geçmişte"
        return c + _zaman_eki(s)
    if alan == "tani":
        terim = _liste(s.get("terimler") or [])
        nitel = _liste(s.get("niteleyiciler") or [])
        icd = _liste(s.get("icd10") or [])
        c = f"Tanı: {(nitel + ' ') if nitel else ''}{terim or 'belirtilen tanı'}"
        if icd:
            c += f" (ICD-10 {icd})"
        return c + _zaman_eki(s)
    if alan == "organ_fonksiyon":
        return f"Yeterli organ işlevi: {_liste(s.get('terimler') or []) or 'genel'}"
    if alan == "tedavi_gecmisi":
        terim = _liste(s.get("terimler") or [])
        tani = _liste(s.get("tani_terimleri") or [])
        c = f"Tedavi geçmişi: {terim or 'belirtilen tedavi'}"
        if tani:
            c += f" ({tani} için)"
        return c + _zaman_eki(s)
    if alan == "zaman":
        return f"Zaman penceresi: {_sayi(s.get('gun'))} gün"
    if alan == "serbest":
        return f"Serbest metin: {str(s.get('metin') or '').strip()}"
    if alan:
        return str(alan)
    return "?"


def _cumle(s, derinlik: int = 0) -> str:
    if not isinstance(s, dict):
        return "?"
    if "ve" in s:
        parcalar = [_cumle(x, derinlik + 1) for x in s["ve"]]
        c = " VE ".join(parcalar)
        return f"({c})" if derinlik and len(parcalar) > 1 else c
    if "veya" in s:
        parcalar = [_cumle(x, derinlik + 1) for x in s["veya"]]
        c = " VEYA ".join(parcalar)
        return f"({c})" if derinlik and len(parcalar) > 1 else c
    if "degil" in s:
        ic = _cumle(s["degil"], derinlik + 1)
        return f"DEĞİL ({ic})" if " VE " in ic or " VEYA " in ic else f"DEĞİL: {ic}"
    return _tek(s)


def kriter_cumlesi(yapisal) -> str:
    """'Yaş ≥ 18 VE Cinsiyet = Kadın'. Sorgu yoksa 'Hesaplanabilir sorgu yok'."""
    if not isinstance(yapisal, dict):
        return "Hesaplanabilir sorgu yok"
    sorgu = yapisal.get("sorgu") if "sorgu" in yapisal or "kategori" in yapisal else yapisal
    if not sorgu:
        return "Hesaplanabilir sorgu yok"
    return _cumle(sorgu)
