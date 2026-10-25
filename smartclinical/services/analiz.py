"""On analiz: toplanan eCRF verisi uzerinde betimleyici istatistik ve kol karsilastirmasi.

Butun ciktilar sozluk/liste olarak doner; sablonlar hesap yapmaz. Test secimi kural tabanlidir
(normallik + grup sayisi + beklenen siklik); nihai analiz istatistiksel analiz planina gore yapilir.
numpy ve scipy disinda bagimlilik yok.
"""
import math
import warnings

import numpy as np
from scipy import stats

from ..models.hasta import GonulluDurumu

# Analize giren form kaydi durumlari; taslaklar disarida
ANALIZ_DURUMLARI = ("tamamlandi", "sdv", "kilitli")
SAYISAL = "sayisal"
KATEGORIK = "kategorik"
KOL_YOK = "Kol atanmamış"
ALFA = 0.05

_TIP_ESLEME = {"sayi": SAYISAL, "secim": KATEGORIK, "evet_hayir": KATEGORIK}

_RANDOMIZE_SONRASI = (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE,
                      GonulluDurumu.TAMAMLADI)
_TARANDI = (GonulluDurumu.TARAMA, GonulluDurumu.TARAMA_BASARISIZ, GonulluDurumu.AYRILDI) + _RANDOMIZE_SONRASI


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------
def sayiya(v):
    """'12,5' gibi virgullu degerleri de float'a cevirir; cevrilemezse None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if math.isnan(v) else float(v)
    s = str(v).strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")  # 1.250,5 bicimi
    try:
        return float(s)
    except ValueError:
        return None


def alan_tipi(alan: dict) -> str | None:
    """Analize giren alan tipi; metin, tarih ve coklu secim disarida kalir."""
    return _TIP_ESLEME.get(alan.get("tip"))


def _kol_adi(g) -> str:
    return g.kol.ad if g.kol else KOL_YOK


def _kol_adlari(calisma) -> list[str]:
    adlar = [k.ad for k in calisma.kollar]
    if any(g.kol is None for g in calisma.gonulluler):
        adlar.append(KOL_YOK)
    return adlar


def _formlar(calisma):
    return sorted(calisma.formlar, key=lambda f: (f.sira, f.id))


def _kayitlar(calisma):
    """Analize giren form kayitlari, gonullu no ve vizit sirasina gore."""
    liste = []
    for g in calisma.gonulluler:
        for fk in g.form_kayitlari:
            if fk.durum in ANALIZ_DURUMLARI:
                liste.append(fk)
    liste.sort(key=lambda fk: (fk.gonullu.gonullu_no, fk.vizit.sira if fk.vizit else -1, fk.form.sira, fk.id))
    return liste


def _r(v, basamak=2):
    return None if v is None else round(float(v), basamak)


# ---------------------------------------------------------------------------
# Veri seti ve degisken listesi
# ---------------------------------------------------------------------------
def veri_seti(calisma) -> tuple[list[str], list[dict]]:
    """Genis tablo: her satir bir form kaydi (taslaklar haric) + gonullu no, kol, vizit.

    Sutunlar 'FORMKOD.ALANKOD' bicimindedir; sayi alanlari float, digerleri metin.
    """
    sutunlar = ["gonullu_no", "kol", "vizit"]
    tipler = {}
    for f in _formlar(calisma):
        for a in f.alanlar:
            kod = f"{f.kod}.{a['kod']}"
            sutunlar.append(kod)
            tipler[kod] = a.get("tip")
    satirlar = []
    for fk in _kayitlar(calisma):
        satir = {s: None for s in sutunlar}
        satir["gonullu_no"] = fk.gonullu.gonullu_no
        satir["kol"] = _kol_adi(fk.gonullu)
        satir["vizit"] = fk.vizit.ad if fk.vizit else ""
        onek = fk.form.kod + "."
        for alan_kod, v in (fk.veriler or {}).items():
            kod = onek + alan_kod
            if kod not in tipler:
                continue  # formdan kaldirilmis alan
            if tipler[kod] == "sayi":
                satir[kod] = sayiya(v)
            elif isinstance(v, list):
                satir[kod] = "; ".join(str(x) for x in v)
            else:
                satir[kod] = "" if v is None else str(v)
        satirlar.append(satir)
    return sutunlar, satirlar


def degiskenler(calisma) -> list[dict]:
    """Analiz edilebilir degiskenler: [{kod, etiket, tip, form, vizitler, duzeyler}]."""
    # formun gercekte hangi vizitlerde kaydi var (vizit sirasina gore)
    gozlenen: dict[int, dict[str, int]] = {}
    for fk in _kayitlar(calisma):
        if fk.vizit:
            gozlenen.setdefault(fk.form_id, {}).setdefault(fk.vizit.ad, fk.vizit.sira)
    liste = []
    for f in _formlar(calisma):
        vizitler = sorted(gozlenen.get(f.id, {}), key=lambda ad: gozlenen[f.id][ad]) or list(f.vizit_listesi)
        for a in f.alanlar:
            tip = alan_tipi(a)
            if not tip:
                continue
            etiket = a.get("etiket") or a["kod"]
            if a.get("birim"):
                etiket = f"{etiket} ({a['birim']})"
            duzeyler = a.get("secenekler") or (["Evet", "Hayır"] if a.get("tip") == "evet_hayir" else [])
            if isinstance(duzeyler, str):
                duzeyler = [x.strip() for x in duzeyler.split(";") if x.strip()]
            liste.append({"kod": f"{f.kod}.{a['kod']}", "etiket": etiket, "tip": tip, "form": f.ad,
                          "form_kod": f.kod, "vizitler": vizitler, "duzeyler": [str(d) for d in duzeyler]})
    return liste


def degisken_bul(calisma, kod: str) -> dict | None:
    for d in degiskenler(calisma):
        if d["kod"] == kod:
            return d
    return None


def kol_degerleri(calisma, kod: str, vizit: str | None = None) -> dict[str, list]:
    """Secilen degiskenin kol bazinda degerleri (eksikler None). Vizit verilirse yalniz o vizit."""
    form_kod, _, alan_kod = kod.partition(".")
    form = next((f for f in _formlar(calisma) if f.kod == form_kod), None)
    if form is None:
        return {}
    alan = next((a for a in form.alanlar if a["kod"] == alan_kod), None)
    if alan is None:
        return {}
    tip = alan_tipi(alan)
    gruplar: dict[str, list] = {ad: [] for ad in _kol_adlari(calisma)}
    for fk in _kayitlar(calisma):
        if fk.form_id != form.id:
            continue
        if vizit and (not fk.vizit or fk.vizit.ad != vizit):
            continue
        v = (fk.veriler or {}).get(alan_kod)
        if tip == SAYISAL:
            v = sayiya(v)
        else:
            v = None if v in (None, "", []) else str(v)
        gruplar.setdefault(_kol_adi(fk.gonullu), []).append(v)
    return gruplar


# ---------------------------------------------------------------------------
# Betimleyici istatistik
# ---------------------------------------------------------------------------
def betimle(degerler, tip: str, duzeyler: list[str] | None = None) -> dict:
    """Sayisal: n, eksik, ortalama, ss, medyan, caa, min, maks. Kategorik: duzey sayilari ve yuzdeler."""
    degerler = list(degerler)
    if tip == SAYISAL:
        degerler = [sayiya(v) for v in degerler]  # ham metin de gelebilir; cevrilemeyen eksik sayilir
    eksik = sum(1 for v in degerler if v is None)
    if tip == SAYISAL:
        x = np.array([v for v in degerler if v is not None], dtype=float)
        n = int(x.size)
        if n == 0:
            return {"tip": SAYISAL, "n": 0, "eksik": eksik, "ortalama": None, "ss": None, "medyan": None,
                    "caa": None, "min": None, "maks": None}
        q1, q3 = np.percentile(x, [25, 75])
        return {"tip": SAYISAL, "n": n, "eksik": eksik, "ortalama": _r(x.mean()),
                "ss": _r(x.std(ddof=1)) if n >= 2 else None, "medyan": _r(np.median(x)),
                "caa": _r(q3 - q1), "min": _r(x.min()), "maks": _r(x.max())}
    sayilar: dict[str, int] = {d: 0 for d in (duzeyler or [])}
    for v in degerler:
        if v is not None:
            sayilar[str(v)] = sayilar.get(str(v), 0) + 1
    n = sum(sayilar.values())
    return {"tip": KATEGORIK, "n": n, "eksik": eksik,
            "duzeyler": [{"deger": d, "n": s, "yuzde": _r(100 * s / n, 1) if n else None} for d, s in sayilar.items()]}


def kutu_verisi(degerler) -> dict | None:
    """Kutu grafigi icin: biyik uclari (1.5 x CAA kurali), ceyrekler, medyan ve aykiri noktalar."""
    x = np.array([v for v in degerler if v is not None], dtype=float)
    if x.size == 0:
        return None
    q1, med, q3 = np.percentile(x, [25, 50, 75])
    caa = q3 - q1
    alt, ust = q1 - 1.5 * caa, q3 + 1.5 * caa
    icerde = x[(x >= alt) & (x <= ust)]
    aykiri = x[(x < alt) | (x > ust)]
    return {"n": int(x.size), "min": _r(icerde.min()), "c1": _r(q1), "medyan": _r(med), "c3": _r(q3),
            "maks": _r(icerde.max()), "aykiri": [_r(v) for v in aykiri.tolist()]}


# ---------------------------------------------------------------------------
# Kol karsilastirmasi: uygun testin otomatik secimi
# ---------------------------------------------------------------------------
def _normal_mi(gruplar: dict[str, np.ndarray]) -> tuple[bool, list[str]]:
    notlar, normal = [], True
    for ad, x in gruplar.items():
        if np.ptp(x) == 0:
            notlar.append(f"{ad}: tüm değerler aynı")
            normal = False
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p = float(stats.shapiro(x).pvalue)
        notlar.append(f"{ad}: Shapiro-Wilk p={p:.3f}".replace(".", ","))
        if p <= ALFA:
            normal = False
    return normal, notlar


def _sonuc(test, istatistik, p, gerekce, **ek) -> dict:
    s = {"test": test, "istatistik": _r(istatistik, 3), "p": _r(p, 4), "gerekce": gerekce}
    s.update(ek)
    return s


def kol_karsilastir(gruplar: dict[str, list], tip: str) -> dict:
    """{'test', 'istatistik', 'p', 'gerekce'}; test yapilamiyorsa test None ve gerekce aciklar.

    Sayisal, 2 kol: her grupta n >= 3 ve Shapiro-Wilk p > 0,05 ise Welch t, degilse Mann-Whitney U.
    Sayisal, 3+ kol: normal ise tek yonlu ANOVA, degilse Kruskal-Wallis.
    Kategorik: beklenen sikliklarin tamami >= 5 ise ki-kare; 2x2 ve kucuk beklenen degerde Fisher.
    """
    temiz = {ad: [v for v in d if v is not None] for ad, d in gruplar.items()}
    temiz = {ad: d for ad, d in temiz.items() if d}
    n_metni = ", ".join(f"{ad} n={len(d)}" for ad, d in temiz.items())
    if len(temiz) < 2:
        return _sonuc(None, None, None, "Karşılaştırma için verisi olan en az iki kol gerekir.")
    kucuk = [ad for ad, d in temiz.items() if len(d) < 3]
    if kucuk:
        return _sonuc(None, None, None, f"{', '.join(kucuk)} kolunda n < 3; test yapılmadı ({n_metni}).")

    if tip == SAYISAL:
        diziler = {ad: np.array(d, dtype=float) for ad, d in temiz.items()}
        normal, notlar = _normal_mi(diziler)
        dagilim = "normal dağılım varsayımı sağlandı" if normal else "normal dağılım varsayımı sağlanmadı"
        on = f"{n_metni}; {'; '.join(notlar)}; {dagilim}"
        x = list(diziler.values())
        if len(x) == 2:
            if normal:
                r = stats.ttest_ind(x[0], x[1], equal_var=False)
                return _sonuc("Welch t testi", r.statistic, r.pvalue, f"İki kol, {on}. Varyans eşitliği varsayılmadı.")
            r = stats.mannwhitneyu(x[0], x[1], alternative="two-sided")
            return _sonuc("Mann-Whitney U testi", r.statistic, r.pvalue, f"İki kol, {on}; parametrik olmayan test seçildi.")
        if normal:
            r = stats.f_oneway(*x)
            return _sonuc("Tek yönlü ANOVA", r.statistic, r.pvalue,
                          f"{len(x)} kol, {on}. İkili karşılaştırma ve çoklu karşılaştırma düzeltmesi yapılmadı.")
        r = stats.kruskal(*x)
        return _sonuc("Kruskal-Wallis testi", r.statistic, r.pvalue,
                      f"{len(x)} kol, {on}; parametrik olmayan test seçildi. Çoklu karşılaştırma düzeltmesi yapılmadı.")

    # kategorik: kol x duzey tablosu
    duzeyler = sorted({str(v) for d in temiz.values() for v in d})
    if len(duzeyler) < 2:
        return _sonuc(None, None, None, f"Tek düzey gözlendi ({duzeyler[0]}); karşılaştırma yapılamaz ({n_metni}).")
    tablo = np.array([[sum(1 for v in d if str(v) == dz) for dz in duzeyler] for d in temiz.values()], dtype=float)
    _, _, _, beklenen = stats.chi2_contingency(tablo, correction=False)
    kucuk_hucre = int((beklenen < 5).sum())
    boyut = f"{tablo.shape[0]}x{tablo.shape[1]} tablo, {n_metni}"
    if kucuk_hucre == 0:
        r = stats.chi2_contingency(tablo, correction=False)
        return _sonuc("Ki-kare testi", r[0], r[1], f"{boyut}; tüm beklenen sıklıklar ≥ 5.", tablo=tablo.tolist(), duzeyler=duzeyler)
    if tablo.shape == (2, 2):
        _, p = stats.fisher_exact(tablo)
        return _sonuc("Fisher kesin testi", None, p, f"{boyut}; {kucuk_hucre} hücrede beklenen sıklık < 5.",
                      tablo=tablo.tolist(), duzeyler=duzeyler)
    r = stats.chi2_contingency(tablo, correction=False)
    return _sonuc("Ki-kare testi", r[0], r[1],
                  f"{boyut}; {kucuk_hucre} hücrede beklenen sıklık < 5, sonuç ihtiyatla yorumlanmalı (Fisher yalnızca 2x2 tabloda uygulanır).",
                  tablo=tablo.tolist(), duzeyler=duzeyler)


def degisken_analizi(calisma, kod: str, vizit: str | None = None) -> dict | None:
    """Web icin tek giris: kol bazinda betimleme, toplam, test ve grafik verisi."""
    d = degisken_bul(calisma, kod)
    if d is None:
        return None
    gruplar = {ad: g for ad, g in kol_degerleri(calisma, kod, vizit).items() if g}  # kaydi olmayan kol gosterilmez
    hepsi = [v for g in gruplar.values() for v in g]
    # duzey sirasi tum kollarda ayni olsun: tanimli secenekler + gozlenen ek degerler
    duzeyler = list(d["duzeyler"])
    for v in hepsi:
        if v is not None and str(v) not in duzeyler:
            duzeyler.append(str(v))
    kollar = [{"ad": ad, "ozet": betimle(g, d["tip"], duzeyler)} for ad, g in gruplar.items()]
    sonuc = {"degisken": d, "vizit": vizit, "kollar": kollar, "toplam": betimle(hepsi, d["tip"], duzeyler),
             "test": kol_karsilastir({ad: g for ad, g in gruplar.items() if any(v is not None for v in g)}, d["tip"])}
    if d["tip"] == SAYISAL:
        sonuc["grafik"] = [{"ad": ad, **(kutu_verisi(g) or {})} for ad, g in gruplar.items() if kutu_verisi(g)]
    else:
        sonuc["grafik"] = {"etiketler": [k["ad"] for k in kollar],
                           "seriler": [{"ad": dz, "degerler": [sum(1 for v in gruplar[k["ad"]] if v is not None and str(v) == dz)
                                                               for k in kollar]} for dz in duzeyler]}
    return sonuc


# ---------------------------------------------------------------------------
# Veri durumu, gonullu akisi, advers olay ozeti
# ---------------------------------------------------------------------------
def veri_durumu(calisma) -> dict:
    hepsi = [fk for g in calisma.gonulluler for fk in g.form_kayitlari]
    analiz = [fk for fk in hepsi if fk.durum in ANALIZ_DURUMLARI]
    kilitli = sum(1 for fk in analiz if fk.durum == "kilitli")
    oran = (100 * kilitli / len(analiz)) if analiz else 0.0
    return {"toplam": len(hepsi), "analiz": len(analiz), "taslak": len(hepsi) - len(analiz), "kilitli": kilitli,
            "kilitli_oran": round(oran, 1), "on_analiz": oran < 100}


def gonullu_akisi(calisma) -> dict:
    """Kol bazinda gonullu akisi. 'tarandi' ile 'tarama_oncesi' toplami calisma gonullu sayisina esittir."""
    kollar = _kol_adlari(calisma)
    tanimlar = [
        ("tarama_oncesi", "Tarama öncesi (aday, ön tarama, onam)", lambda g: g.durum not in _TARANDI, None),
        ("tarandi", "Tarandı", lambda g: g.durum in _TARANDI, None),
        ("tarama_basarisiz", "Tarama başarısız", lambda g: g.durum == GonulluDurumu.TARAMA_BASARISIZ, "tarama_basarisizlik_nedeni"),
        ("taramada", "Taramada", lambda g: g.durum == GonulluDurumu.TARAMA, None),
        ("randomize", "Randomize", lambda g: g.durum in _RANDOMIZE_SONRASI or g.randomizasyon_tarihi is not None, None),
        ("tedavide", "Tedavide / takipte", lambda g: g.durum in (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE), None),
        ("tamamladi", "Tamamladı", lambda g: g.durum == GonulluDurumu.TAMAMLADI, None),
        ("ayrildi", "Ayrıldı", lambda g: g.durum == GonulluDurumu.AYRILDI, "ayrilma_nedeni"),
    ]
    satirlar = []
    for anahtar, etiket, kosul, neden_alani in tanimlar:
        sayilar = {k: 0 for k in kollar}
        nedenler: dict[str, int] = {}
        for g in calisma.gonulluler:
            if not kosul(g):
                continue
            sayilar[_kol_adi(g)] = sayilar.get(_kol_adi(g), 0) + 1
            if neden_alani:
                neden = getattr(g, neden_alani) or "Belirtilmemiş"
                nedenler[neden] = nedenler.get(neden, 0) + 1
        satirlar.append({"anahtar": anahtar, "etiket": etiket, "kollar": sayilar, "toplam": sum(sayilar.values()),
                         "nedenler": sorted(nedenler.items(), key=lambda x: -x[1]) if neden_alani else None})
    return {"kollar": kollar, "satirlar": satirlar, "toplam_gonullu": len(calisma.gonulluler)}


def advers_olay_ozeti(calisma) -> dict:
    """Kol x sistem-organ sinifi: olay ve gonullu sayilari; kol bazinda ciddi ve derece >= 3 sayilari."""
    kollar = _kol_adlari(calisma)
    bos = lambda: {"olay": 0, "gonullu": set()}  # noqa: E731
    soc_tablo: dict[str, dict[str, dict]] = {}
    ozet = {k: {"gonullu_toplam": 0, "olayli_gonullu": set(), "olay": 0, "ciddi": 0, "derece3": 0,
                "ciddi_gonullu": set(), "derece3_gonullu": set()} for k in kollar}
    for g in calisma.gonulluler:
        kol = _kol_adi(g)
        oz = ozet.setdefault(kol, {"gonullu_toplam": 0, "olayli_gonullu": set(), "olay": 0, "ciddi": 0, "derece3": 0,
                                   "ciddi_gonullu": set(), "derece3_gonullu": set()})
        oz["gonullu_toplam"] += 1
        for a in g.advers_olaylar:
            soc = a.meddra_soc or "Kodlanmamış"
            h = soc_tablo.setdefault(soc, {}).setdefault(kol, bos())
            h["olay"] += 1
            h["gonullu"].add(g.id)
            oz["olay"] += 1
            oz["olayli_gonullu"].add(g.id)
            if a.ciddi:
                oz["ciddi"] += 1
                oz["ciddi_gonullu"].add(g.id)
            if a.siddet and a.siddet.isdigit() and int(a.siddet) >= 3:
                oz["derece3"] += 1
                oz["derece3_gonullu"].add(g.id)
    satirlar = []
    for soc, hucreler in soc_tablo.items():
        satir = {"soc": soc, "kollar": {}, "toplam": {"olay": 0, "gonullu": 0}}
        for k in kollar:
            h = hucreler.get(k, bos())
            satir["kollar"][k] = {"olay": h["olay"], "gonullu": len(h["gonullu"])}
            satir["toplam"]["olay"] += h["olay"]
            satir["toplam"]["gonullu"] += len(h["gonullu"])
        satirlar.append(satir)
    satirlar.sort(key=lambda s: (-s["toplam"]["olay"], s["soc"]))
    kol_ozet = {k: {"gonullu_toplam": o["gonullu_toplam"], "olay": o["olay"], "olayli_gonullu": len(o["olayli_gonullu"]),
                    "ciddi": o["ciddi"], "ciddi_gonullu": len(o["ciddi_gonullu"]), "derece3": o["derece3"],
                    "derece3_gonullu": len(o["derece3_gonullu"])} for k, o in ozet.items()}
    return {"kollar": kollar, "satirlar": satirlar, "ozet": kol_ozet,
            "toplam_olay": sum(o["olay"] for o in kol_ozet.values())}
