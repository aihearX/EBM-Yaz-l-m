"""Merkezler arasi anomali tespiti. Robust z-skor (medyan/MAD) + Tukey citleri."""

from dataclasses import dataclass

import numpy as np

MIN_MERKEZ = 4       # bundan az merkezle istatistiksel karsilastirma anlamli degil
Z_ESIK = 2.5
MAD_OLCEK = 1.4826   # normal dagilim icin MAD -> sigma


@dataclass
class AnomaliSonucu:
    z: float | None
    aykiri: bool
    aciklama: str
    sira: int | None = None   # 1 = en kotu
    n: int = 0


def anomali_tespit(degerler, yon="yuksek", z_esik=Z_ESIK):
    """degerler: {cm_id: float|None}. yon: 'yuksek' -> buyuk deger kotu, 'dusuk' -> kucuk deger kotu."""
    gecerli = {k: float(v) for k, v in degerler.items() if v is not None and np.isfinite(v)}
    n = len(gecerli)
    sonuc = {}
    if n == 0:
        return {k: AnomaliSonucu(None, False, "Veri yok", None, 0) for k in degerler}

    x = np.array(list(gecerli.values()))
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med))) * MAD_OLCEK
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    ust_cit, alt_cit = q3 + 1.5 * iqr, q1 - 1.5 * iqr

    # kotu yone gore siralama
    sirali = sorted(gecerli.items(), key=lambda kv: -kv[1] if yon == "yuksek" else kv[1])
    siralar = {k: i + 1 for i, (k, _) in enumerate(sirali)}

    for k in degerler:
        if k not in gecerli:
            sonuc[k] = AnomaliSonucu(None, False, "Veri yok", None, n)
            continue
        v = gecerli[k]
        if n < MIN_MERKEZ:
            sonuc[k] = AnomaliSonucu(None, False, f"{n} merkezle karsilastirma yapilamadi (en az {MIN_MERKEZ} gerekli).",
                                     siralar[k], n)
            continue
        if mad > 0:
            z = (v - med) / mad
        else:
            z = 0.0 if v == med else (np.inf if v > med else -np.inf)
        z_yon = z if yon == "yuksek" else -z
        tukey = v > ust_cit if yon == "yuksek" else v < alt_cit
        aykiri = bool(z_yon >= z_esik or (tukey and z_yon > 1.0))
        if aykiri:
            acik = (f"Merkez degeri {v:.2f}, diger merkezlerin medyani {med:.2f}; robust z-skor {z_yon:.1f} "
                    f"(esik {z_esik}). {n} merkez arasinda {siralar[k]}. sirada.")
        else:
            acik = f"Merkez degeri {v:.2f}, medyan {med:.2f}; merkezler arasi dagilimin icinde ({siralar[k]}/{n})."
        sonuc[k] = AnomaliSonucu(float(z_yon) if np.isfinite(z_yon) else None, aykiri, acik, siralar[k], n)
    return sonuc


def cusum(seri, k=0.5, h=4.0):
    """Tek tarafli (yukari) CUSUM. seri standartlastirilmis olmali; donus: (S listesi, alarm indeksleri)."""
    s = 0.0
    S = []
    alarmlar = []
    for i, x in enumerate(seri):
        s = max(0.0, s + x - k)
        S.append(s)
        if s > h:
            alarmlar.append(i)
            s = 0.0  # alarm sonrasi sifirla
    return S, alarmlar
