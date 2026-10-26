"""Merkez aktivasyon gecikme riski - Weibull AFT (sansurlu veri).

log(T) = mu + beta'x + sigma*eps, eps ~ Gumbel(min). Sansurlu kayitlar icin
log-olabilirlik elle yazildi (lifelines bagimliligi eklemek istemedik).
"""

import logging
import math
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, stats

log = logging.getLogger(__name__)

KURUM_TIPLERI = ["universite", "egitim_arastirma", "sehir", "ozel"]
CALISMA_TURLERI = ["ilac", "biyobenzer", "tibbi_cihaz", "tani_kiti", "gozlemsel", "akademik",
                   "biyoesdegerlik", "ileri_tedavi", "kayit"]

# Veri yokken kullanilan oncul katsayilar (log-sure uzerinde; pozitif = daha uzun sure).
# Kaynak: EBM 2021-2024 aktivasyon gunlukleri, kaba ortalamalar.
ONCUL = {
    "shape": 1.6,
    "scale_gun": 120.0,
    "beta": {
        "kurum_universite": 0.10,
        "kurum_egitim_arastirma": 0.00,
        "kurum_sehir": -0.05,
        "kurum_ozel": -0.25,
        "etik_kurul_gun": 0.0045,       # ortalama etik kurul suresinin 60 gunden sapmasi basina
        "sozlesme_sablonu_var": -0.22,
        "daha_once_calisildi": -0.18,
        "tur_tibbi_cihaz": 0.08,
        "tur_gozlemsel": -0.20,
        "tur_akademik": -0.10,
        "tur_ileri_tedavi": 0.30,
    },
}

ETIKET = {
    "kurum_universite": "Üniversite hastanesi",
    "kurum_egitim_arastirma": "Eğitim ve araştırma hastanesi",
    "kurum_sehir": "Şehir hastanesi",
    "kurum_ozel": "Özel hastane",
    "etik_kurul_gun": "Etik kurul ortalama süresi",
    "sozlesme_sablonu_var": "Hazır sözleşme şablonu",
    "daha_once_calisildi": "Daha önce birlikte çalışıldı",
    "tur_tibbi_cihaz": "Tıbbi cihaz çalışması",
    "tur_gozlemsel": "Gözlemsel çalışma",
    "tur_akademik": "Akademik çalışma",
    "tur_ileri_tedavi": "İleri tedavi çalışması",
}


@dataclass
class GecikmeRiski:
    olasilik_gecikme: float
    medyan_gun: float
    p25: float
    p75: float
    aciklama: list = field(default_factory=list)
    katkilar: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "olasilik_gecikme": round(self.olasilik_gecikme, 3),
            "medyan_gun": round(self.medyan_gun, 1),
            "p25": round(self.p25, 1),
            "p75": round(self.p75, 1),
            "aciklama": self.aciklama,
            "katkilar": {k: round(v, 1) for k, v in self.katkilar.items()},
        }


def _tasarim_vektoru(kov):
    """Kovaryat sozlugunu ozellik vektorune cevirir (sabit sira)."""
    kov = kov or {}
    x = {}
    kurum = kov.get("kurum_tipi", "egitim_arastirma")
    for k in KURUM_TIPLERI:
        x[f"kurum_{k}"] = 1.0 if kurum == k else 0.0
    x["etik_kurul_gun"] = float(kov.get("etik_kurul_ortalama_gun", 60)) - 60.0
    x["sozlesme_sablonu_var"] = 1.0 if kov.get("sozlesme_sablonu_var") else 0.0
    x["daha_once_calisildi"] = 1.0 if kov.get("daha_once_calisildi") else 0.0
    tur = kov.get("calisma_turu", "ilac")
    for t in ("tibbi_cihaz", "gozlemsel", "akademik", "ileri_tedavi"):
        x[f"tur_{t}"] = 1.0 if tur == t else 0.0
    return x


OZELLIKLER = list(_tasarim_vektoru({}).keys())


class GecikmeModeli:
    def __init__(self):
        self.shape = ONCUL["shape"]
        self.mu = math.log(ONCUL["scale_gun"])
        self.beta = {k: ONCUL["beta"].get(k, 0.0) for k in OZELLIKLER}
        self.n_egitim = 0
        self.egitildi = False

    # --- egitim -------------------------------------------------------
    def fit(self, kayitlar, l2=0.5):
        """kayitlar: [{"sure_gun": float, "gozlendi": bool, "kovaryatlar": {...}}]

        Weibull AFT: S(t) = exp(-(t/exp(mu+bx))^k). l2 oncule dogru hafif ridge cezasi;
        az veriyle katsayilarin ucmasini engelliyor.
        """
        kayitlar = [k for k in kayitlar if k.get("sure_gun", 0) > 0]
        if len(kayitlar) < 8:
            log.info("Aktivasyon modeli: %d kayit yetersiz, oncul parametreler kullaniliyor", len(kayitlar))
            self.n_egitim = len(kayitlar)
            return self

        X = np.array([[_tasarim_vektoru(k.get("kovaryatlar"))[o] for o in OZELLIKLER] for k in kayitlar])
        t = np.array([k["sure_gun"] for k in kayitlar], dtype=float)
        d = np.array([1.0 if k.get("gozlendi", True) else 0.0 for k in kayitlar])
        # kurum tipi dummy'leri tam kolinear - egitim_arastirma referans; katsayisini sabitliyoruz
        ref = OZELLIKLER.index("kurum_egitim_arastirma")
        serbest = [i for i in range(len(OZELLIKLER)) if i != ref]
        oncul_b = np.array([ONCUL["beta"].get(o, 0.0) for o in OZELLIKLER])

        def neg_ll(p):
            log_k, mu = p[0], p[1]
            b = oncul_b.copy()
            b[serbest] = p[2:]
            k = math.exp(log_k)
            eta = mu + X @ b
            z = (np.log(t) - eta) * k  # log(t/scale)^k = exp(z)
            ll = d * (log_k - np.log(t) + z) - np.exp(z)
            ceza = l2 * np.sum((b[serbest] - oncul_b[serbest]) ** 2)
            return -ll.sum() + ceza

        p0 = np.concatenate([[math.log(self.shape), self.mu], oncul_b[serbest]])
        son = optimize.minimize(neg_ll, p0, method="L-BFGS-B")
        if not son.success:
            log.warning("Weibull AFT optimizasyonu yakinsamadi: %s", son.message)
        self.shape = float(math.exp(son.x[0]))
        self.mu = float(son.x[1])
        b = oncul_b.copy()
        b[serbest] = son.x[2:]
        self.beta = dict(zip(OZELLIKLER, b.tolist()))
        self.n_egitim = len(kayitlar)
        self.egitildi = True
        return self

    # --- tahmin -------------------------------------------------------
    def _olcek(self, kov):
        x = _tasarim_vektoru(kov)
        eta = self.mu + sum(self.beta[o] * x[o] for o in OZELLIKLER)
        return math.exp(eta), x

    def sagkalim(self, kov, gun):
        olcek, _ = self._olcek(kov)
        return float(stats.weibull_min.sf(gun, self.shape, scale=olcek))

    def tahmin(self, kovaryatlar, hedef_gun):
        olcek, x = self._olcek(kovaryatlar)
        dagilim = stats.weibull_min(self.shape, scale=olcek)
        p_gec = float(dagilim.sf(hedef_gun))
        medyan = float(dagilim.median())
        p25, p75 = (float(v) for v in dagilim.ppf([0.25, 0.75]))

        # Katkilar: her kovaryatin medyan sureye gun cinsinden etkisi (referansa gore)
        taban_olcek = math.exp(self.mu)
        taban_medyan = taban_olcek * math.log(2) ** (1 / self.shape)
        katkilar = {}
        for o in OZELLIKLER:
            if x[o] == 0:
                continue
            etki = taban_medyan * (math.exp(self.beta[o] * x[o]) - 1)
            if abs(etki) >= 1:
                katkilar[ETIKET.get(o, o)] = etki

        aciklama = [
            f"Beklenen aktivasyon süresi medyan {medyan:.0f} gün (çeyrekler {p25:.0f}–{p75:.0f}).",
            f"{hedef_gun} günlük hedefi aşma olasılığı %{p_gec * 100:.0f}.",
        ]
        for ad, etki in sorted(katkilar.items(), key=lambda kv: -abs(kv[1]))[:3]:
            yon = "uzatıyor" if etki > 0 else "kısaltıyor"
            aciklama.append(f"{ad}: süreyi yaklaşık {abs(etki):.0f} gün {yon}.")
        if not self.egitildi:
            aciklama.append("Model öncül parametrelerle çalışıyor (yeterli eğitim verisi yok).")
        return GecikmeRiski(p_gec, medyan, p25, p75, aciklama, katkilar)


def kaplan_meier(sureler, gozlendi):
    """Donus: [(t, S(t))], t=0'dan baslar."""
    sureler = np.asarray(sureler, dtype=float)
    gozlendi = np.asarray(gozlendi, dtype=bool)
    sira = np.argsort(sureler)
    sureler, gozlendi = sureler[sira], gozlendi[sira]
    egri = [(0.0, 1.0)]
    s = 1.0
    riskte = len(sureler)
    i = 0
    while i < len(sureler):
        t = sureler[i]
        olay = 0
        toplam = 0
        while i < len(sureler) and sureler[i] == t:
            olay += int(gozlendi[i])
            toplam += 1
            i += 1
        if olay and riskte:
            s *= 1 - olay / riskte
            egri.append((float(t), float(s)))
        riskte -= toplam
    return egri


def auc(gercek_etiket, skor):
    """Mann-Whitney U ile ROC AUC."""
    y = np.asarray(gercek_etiket, dtype=int)
    s = np.asarray(skor, dtype=float)
    poz, neg = s[y == 1], s[y == 0]
    if len(poz) == 0 or len(neg) == 0:
        return float("nan")
    u = stats.mannwhitneyu(poz, neg, alternative="greater").statistic
    return float(u / (len(poz) * len(neg)))
