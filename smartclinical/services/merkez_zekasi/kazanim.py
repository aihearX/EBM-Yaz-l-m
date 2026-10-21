"""Hasta kazanim tahmini - hiyerarsik Bayes (Gamma-Poisson).

Merkez i icin aylik kazanim orani lambda_i ~ Gamma(alfa, beta). Havuz (benzer
calismalardaki gecmis merkezler) uzerinden alfa/beta ampirik Bayes ile kestirilir,
sonra merkezin kendi gecmisi ile posterior Gamma(alfa + n, beta + t) alinir.
Az veri olan merkez havuz ortalamasina dogru buzulur (shrinkage); bunu
aciklama satirlarinda kullaniciya yaziyoruz.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from scipy import optimize, special, stats

log = logging.getLogger(__name__)

# Kovaryat duzeltme katsayilari (carpimsal). EBM 2019-2024 operasyon verisinden
# kaba kestirim; model yeniden egitildiginde guncellenecek.
# TODO(selin): katsayilari havuzdan otomatik kestiren surume gec
KURUM_KATSAYI = {
    "universite": 1.00,
    "egitim_arastirma": 0.95,
    "sehir": 1.10,
    "ozel": 0.80,
}
DENEYIM_KATSAYI = {0: 0.75, 1: 0.90, 2: 1.00, 3: 1.10}  # alanda tamamlanan calisma sayisi (3+ ayni)
REKABET_KATSAYI = {0: 1.00, 1: 0.90, 2: 0.80, 3: 0.70}  # ayni endikasyonda rekabet eden calisma (3+ ayni)

# Havuz bos veya tek merkezse kullanilan oncul (hasta/ay)
ONCUL_ALFA = 2.0
ONCUL_BETA = 4.0  # ortalama 0.5 hasta/ay


@dataclass
class KazanimTahmini:
    hasta_ay_ort: float
    hasta_ay_alt: float
    hasta_ay_ust: float
    beklenen_toplam: float
    toplam_alt: float
    toplam_ust: float
    kazanim_egrisi: list = field(default_factory=list)  # [(ay, kumulatif beklenen)]
    aciklama: list = field(default_factory=list)
    shrinkage: float = 0.0
    alfa_post: float = 0.0
    beta_post: float = 0.0

    def to_dict(self):
        return {
            "hasta_ay_ort": round(self.hasta_ay_ort, 3),
            "hasta_ay_alt": round(self.hasta_ay_alt, 3),
            "hasta_ay_ust": round(self.hasta_ay_ust, 3),
            "beklenen_toplam": round(self.beklenen_toplam, 1),
            "toplam_alt": round(self.toplam_alt, 1),
            "toplam_ust": round(self.toplam_ust, 1),
            "kazanim_egrisi": [(int(a), round(float(k), 2)) for a, k in self.kazanim_egrisi],
            "aciklama": self.aciklama,
            "shrinkage": round(self.shrinkage, 3),
        }


def _moment_kestirim(havuz):
    """Gamma hiperparametreleri icin moment yontemi. Oranlar hasta/ay."""
    oranlar = np.array([h["hasta"] / h["ay"] for h in havuz if h.get("ay", 0) > 0], dtype=float)
    if len(oranlar) < 2:
        return ONCUL_ALFA, ONCUL_BETA
    m = oranlar.mean()
    v = oranlar.var(ddof=1)
    # Poisson gurultusunu varyanstan dus (yaklasik)
    ort_ay = np.mean([h["ay"] for h in havuz if h.get("ay", 0) > 0])
    v_duz = max(v - m / ort_ay, 1e-4)
    if m <= 0:
        return ONCUL_ALFA, ONCUL_BETA
    beta = m / v_duz
    alfa = m * beta
    return float(alfa), float(beta)


def _mle_kestirim(havuz, baslangic):
    """Gamma-Poisson marjinali (negatif binom) uzerinden MLE. Moment kestirimi baslangic olarak kullanilir."""
    n = np.array([h["hasta"] for h in havuz], dtype=float)
    t = np.array([h["ay"] for h in havuz], dtype=float)
    gecerli = t > 0
    n, t = n[gecerli], t[gecerli]
    if len(n) < 3:
        return baslangic

    def neg_ll(p):
        a, b = np.exp(p)
        # P(n|a,b,t) = Gamma(n+a)/(Gamma(a) n!) * (b/(b+t))^a * (t/(b+t))^n
        ll = (special.gammaln(n + a) - special.gammaln(a) - special.gammaln(n + 1)
              + a * np.log(b / (b + t)) + n * np.log(t / (b + t)))
        return -ll.sum()

    try:
        son = optimize.minimize(neg_ll, np.log(baslangic), method="Nelder-Mead",
                                options={"maxiter": 400, "xatol": 1e-4, "fatol": 1e-4})
        if son.success or son.fun < neg_ll(np.log(baslangic)):
            a, b = np.exp(son.x)
            if 0.05 < a < 500 and 0.05 < b < 5000:
                return float(a), float(b)
    except Exception as e:  # pragma: no cover
        log.warning("MLE kestirimi basarisiz, moment kestirimi kullaniliyor: %s", e)
    return baslangic


def kovaryat_katsayisi(kovaryat):
    """Carpimsal duzeltme ve aciklama satirlari."""
    if not kovaryat:
        return 1.0, []
    k = 1.0
    notlar = []
    kurum = kovaryat.get("kurum_tipi")
    if kurum in KURUM_KATSAYI:
        k *= KURUM_KATSAYI[kurum]
        if KURUM_KATSAYI[kurum] != 1.0:
            notlar.append(f"Kurum tipi ({kurum}) icin x{KURUM_KATSAYI[kurum]:.2f} duzeltme uygulandi.")
    deneyim = kovaryat.get("alan_deneyimi")
    if deneyim is not None:
        d = DENEYIM_KATSAYI[min(int(deneyim), 3)]
        k *= d
        notlar.append(f"Terapotik alanda {deneyim} calisma deneyimi: x{d:.2f}.")
    rekabet = kovaryat.get("rekabet")
    if rekabet:
        r = REKABET_KATSAYI[min(int(rekabet), 3)]
        k *= r
        notlar.append(f"Ayni endikasyonda {rekabet} rekabet eden calisma: x{r:.2f}.")
    return k, notlar


def kazanim_tahmini(merkez_gecmis, havuz, ufuk_ay, kovaryat=None, guven=0.90, mle=True):
    havuz = [h for h in (havuz or []) if h.get("ay", 0) > 0]
    alfa0, beta0 = _moment_kestirim(havuz)
    if mle and havuz:
        alfa0, beta0 = _mle_kestirim(havuz, (alfa0, beta0))

    n = sum(int(g.get("hasta", 0)) for g in (merkez_gecmis or []))
    t = sum(float(g.get("ay", 0)) for g in (merkez_gecmis or []))

    alfa_p = alfa0 + n
    beta_p = beta0 + t
    # posterior ortalamanin ne kadari oncul(havuz)dan geliyor
    shrinkage = beta0 / beta_p if beta_p > 0 else 1.0

    katsayi, kov_notlar = kovaryat_katsayisi(kovaryat)

    post = stats.gamma(a=alfa_p, scale=1.0 / beta_p)
    ort = post.mean() * katsayi
    q = (1 - guven) / 2
    alt = post.ppf(q) * katsayi
    ust = post.ppf(1 - q) * katsayi

    # Toplam: negatif binom (Gamma-Poisson marjinali) - ufuk boyunca
    # NB parametreleri: n=alfa_p, p=beta_p/(beta_p + T*katsayi)
    T = float(ufuk_ay)
    p = beta_p / (beta_p + T * katsayi)
    nb = stats.nbinom(alfa_p, p)
    beklenen = ort * T
    toplam_alt = float(nb.ppf(q))
    toplam_ust = float(nb.ppf(1 - q))

    egri = [(ay, float(ort) * ay) for ay in range(1, int(ufuk_ay) + 1)]

    aciklama = []
    if havuz:
        aciklama.append(f"Havuzdaki {len(havuz)} benzer merkezin ortalamasi {alfa0 / beta0:.2f} hasta/ay.")
    else:
        aciklama.append("Benzer calisma havuzu bulunamadi; genel oncul (0.5 hasta/ay) kullanildi.")
    if t > 0:
        aciklama.append(f"Merkezin kendi gecmisi: {t:.0f} ayda {n} hasta ({n / t:.2f} hasta/ay).")
    else:
        aciklama.append("Merkezin bu alanda kayitli gecmisi yok; tahmin tamamen havuza dayaniyor.")
    aciklama.append(f"Tahminin %{shrinkage * 100:.0f}'i havuz bilgisinden geliyor (buzulme)." if shrinkage > 0.5
                    else f"Tahmin agirlikli olarak merkezin kendi verisine dayaniyor (havuz payi %{shrinkage * 100:.0f}).")
    aciklama.extend(kov_notlar)
    aciklama.append(f"{ufuk_ay} ayda beklenen {beklenen:.1f} hasta (%{guven * 100:.0f} aralik {toplam_alt:.0f}-{toplam_ust:.0f}).")

    return KazanimTahmini(
        hasta_ay_ort=float(ort), hasta_ay_alt=float(alt), hasta_ay_ust=float(ust),
        beklenen_toplam=float(beklenen), toplam_alt=toplam_alt, toplam_ust=toplam_ust,
        kazanim_egrisi=egri, aciklama=aciklama, shrinkage=float(shrinkage),
        alfa_post=float(alfa_p), beta_post=float(beta_p),
    )


def mape(gercek, tahmin):
    g = np.array(gercek, dtype=float)
    t = np.array(tahmin, dtype=float)
    m = g != 0
    if not m.any():
        return float("nan")
    return float(np.mean(np.abs((g[m] - t[m]) / g[m])) * 100)


def calisma_kazanim_projeksiyonu(merkez_tahminleri, hedef_hasta, baslangic, planlanan_bitis=None,
                                 maks_ay=60, n_sim=2000, seed=42):
    """Merkez tahminlerinden calisma duzeyinde hedefe ulasma projeksiyonu (Monte Carlo).

    merkez_tahminleri: KazanimTahmini listesi (ya da alfa_post/beta_post iceren dict'ler).
    Her simulasyonda merkez orani posterior Gamma'dan cekilir, aylik sayimlar Poisson.
    """
    rng = np.random.default_rng(seed)
    params = []
    for mt in merkez_tahminleri:
        if isinstance(mt, KazanimTahmini):
            a, b, k = mt.alfa_post, mt.beta_post, (mt.hasta_ay_ort * mt.beta_post / mt.alfa_post if mt.alfa_post else 1.0)
        else:
            a, b, k = mt["alfa_post"], mt["beta_post"], mt.get("katsayi", 1.0)
        params.append((a, b, k))

    if not params or hedef_hasta <= 0:
        return {"hedefe_ulasma_ay": None, "olasilik_zamaninda": None, "egri": [], "ulasma_ay_dagilimi": {}}

    ulasma = np.full(n_sim, np.nan)
    kumulatif = np.zeros((n_sim, maks_ay))
    for s in range(n_sim):
        oranlar = np.array([rng.gamma(a, 1.0 / b) * k for a, b, k in params])
        aylik = rng.poisson(oranlar.sum(), size=maks_ay)
        kum = np.cumsum(aylik)
        kumulatif[s] = kum
        idx = np.argmax(kum >= hedef_hasta)
        if kum[idx] >= hedef_hasta:
            ulasma[s] = idx + 1

    medyan_ay = float(np.nanmedian(ulasma)) if np.isfinite(ulasma).any() else None
    egri = [(ay + 1, float(np.median(kumulatif[:, ay])), float(np.percentile(kumulatif[:, ay], 5)),
             float(np.percentile(kumulatif[:, ay], 95))) for ay in range(maks_ay)]

    olasilik = None
    if planlanan_bitis and baslangic:
        plan_ay = max(1, (planlanan_bitis.year - baslangic.year) * 12 + planlanan_bitis.month - baslangic.month)
        olasilik = float(np.mean(np.nan_to_num(ulasma, nan=maks_ay + 1) <= plan_ay))

    dagilim = {}
    for p in (10, 25, 50, 75, 90):
        v = np.nanpercentile(ulasma, p) if np.isfinite(ulasma).any() else None
        dagilim[f"p{p}"] = None if v is None else int(math.ceil(v))

    tahmini_tarih = None
    if medyan_ay is not None and baslangic:
        ay = baslangic.month - 1 + int(math.ceil(medyan_ay))
        tahmini_tarih = date(baslangic.year + ay // 12, ay % 12 + 1, 1)

    return {
        "hedefe_ulasma_ay": None if medyan_ay is None else int(math.ceil(medyan_ay)),
        "tahmini_tarih": tahmini_tarih,
        "olasilik_zamaninda": olasilik,
        "egri": egri,
        "ulasma_ay_dagilimi": dagilim,
    }
