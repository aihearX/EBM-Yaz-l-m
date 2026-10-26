"""Merkez secimi icin siralama. Bilesenler 0-1'e normalize edilir, agirlikli toplanir."""

VARSAYILAN_AGIRLIKLAR = {
    "kazanim": 0.35,
    "gecikme": 0.20,
    "kalite": 0.20,
    "deneyim": 0.15,
    "rekabet": 0.05,
    "cografya": 0.05,
}

BILESEN_ETIKET = {
    "kazanim": "Hasta kazanım tahmini",
    "gecikme": "Aktivasyon gecikme riski",
    "kalite": "Kalite geçmişi",
    "deneyim": "Deneyim",
    "rekabet": "Rekabet",
    "cografya": "Coğrafi dağılım",
}


def _kucuk(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def _kirp(x, alt=0.0, ust=1.0):
    return max(alt, min(ust, x))


def _bilesenler(a, maks_kazanim):
    """Aday sozlugunden 0-1 arasi bilesen puanlari."""
    kazanim = _kirp((a.get("tahmini_kazanim") or 0) / maks_kazanim) if maks_kazanim > 0 else 0.0
    gecikme = 1.0 - _kirp(a.get("gecikme_riski") or 0.5)
    sapma = a.get("sapma_orani")      # sapma / gonullu
    sorgu = a.get("sorgu_orani")      # sorgu / form
    if sapma is None and sorgu is None:
        kalite = 0.6  # bilinmiyor: notr biraz altinda
    else:
        k = []
        if sapma is not None:
            k.append(1.0 - _kirp(sapma / 0.5))
        if sorgu is not None:
            k.append(1.0 - _kirp(sorgu / 0.3))
        kalite = sum(k) / len(k)
    deneyim = _kirp((a.get("tamamlanan_calisma") or 0) / 10)
    if a.get("gcp_egitim_guncel") is False:
        deneyim *= 0.7
    rekabet = 1.0 - _kirp((a.get("rekabet") or 0) / 4)
    cografya = 1.0 if a.get("bolge_bos", True) else 0.4
    return {"kazanim": kazanim, "gecikme": gecikme, "kalite": kalite,
            "deneyim": deneyim, "rekabet": rekabet, "cografya": cografya}


def _gerekce(a, b, katkilar):
    guclu = sorted(katkilar.items(), key=lambda kv: -kv[1])[:2]
    zayif = min(b.items(), key=lambda kv: kv[1])
    parcalar = []
    if a.get("tahmini_kazanim") is not None:
        parcalar.append(f"Beklenen kazanım {a['tahmini_kazanim']:.2f} hasta/ay".replace(".", ","))
    if a.get("gecikme_riski") is not None:
        parcalar.append(f"aktivasyon gecikme riski %{a['gecikme_riski'] * 100:.0f}")
    c1 = ", ".join(parcalar) + "." if parcalar else ""
    c2 = "En güçlü yönleri: " + " ve ".join(_kucuk(BILESEN_ETIKET[k]) for k, _ in guclu) + "."
    c3 = f"Dikkat edilmesi gereken bileşen: {_kucuk(BILESEN_ETIKET[zayif[0]])} ({zayif[1] * 100:.0f}/100)."
    return " ".join(p for p in (c1, c2, c3) if p)


def merkez_sirala(adaylar, agirliklar=None):
    """adaylar: [{"merkez_id", "ad", "tahmini_kazanim", "gecikme_riski", "sapma_orani", "sorgu_orani",
                  "tamamlanan_calisma", "rekabet", "bolge_bos", "gcp_egitim_guncel"}]
    Donus: puan (0-100), katkilar, gerekce eklenmis ve puana gore sirali kopya.
    """
    w = dict(VARSAYILAN_AGIRLIKLAR)
    if agirliklar:
        w.update(agirliklar)
    toplam_w = sum(w.values()) or 1.0
    w = {k: v / toplam_w for k, v in w.items()}

    maks_kazanim = max((a.get("tahmini_kazanim") or 0) for a in adaylar) if adaylar else 0
    sonuc = []
    for a in adaylar:
        b = _bilesenler(a, maks_kazanim)
        katkilar = {k: round(w[k] * b[k] * 100, 1) for k in w}
        puan = round(sum(katkilar.values()), 1)
        kopya = dict(a)
        kopya.update({"puan": puan, "katkilar": katkilar, "bilesenler": {k: round(v, 2) for k, v in b.items()},
                      "gerekce": _gerekce(a, b, katkilar)})
        sonuc.append(kopya)
    sonuc.sort(key=lambda s: -s["puan"])
    for i, s in enumerate(sonuc, 1):
        s["sira"] = i
    return sonuc
