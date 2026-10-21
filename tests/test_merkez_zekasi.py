import os
from datetime import date

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import numpy as np
import pytest

from smartclinical.services.merkez_zekasi import (
    GecikmeModeli,
    auc,
    calisma_kazanim_projeksiyonu,
    calisma_tahmin_guncelle,
    kaplan_meier,
    kazanim_tahmini,
    mape,
    merkez_sirala,
)
from smartclinical.services.merkez_zekasi.kazanim import _moment_kestirim


def _sentetik_havuz(rng, n=40, alfa=3.0, beta=4.0):
    """Gercek oranlar Gamma'dan, sayimlar Poisson'dan."""
    oranlar = rng.gamma(alfa, 1 / beta, size=n)
    aylar = rng.uniform(6, 18, size=n)
    hastalar = rng.poisson(oranlar * aylar)
    return oranlar, [{"hasta": int(h), "ay": float(a)} for h, a in zip(hastalar, aylar)]


def test_kazanim_tahmini_temel():
    rng = np.random.default_rng(1)
    _, havuz = _sentetik_havuz(rng)
    kt = kazanim_tahmini([{"hasta": 4, "ay": 8}], havuz, ufuk_ay=12)
    assert kt.hasta_ay_alt < kt.hasta_ay_ort < kt.hasta_ay_ust
    assert kt.beklenen_toplam == pytest.approx(kt.hasta_ay_ort * 12)
    assert len(kt.kazanim_egrisi) == 12
    assert kt.kazanim_egrisi[-1][1] == pytest.approx(kt.beklenen_toplam)
    assert 0 < kt.shrinkage < 1
    assert any("havuz" in a.lower() for a in kt.aciklama)


def test_kazanim_havuz_yok_oncul():
    kt = kazanim_tahmini([], [], ufuk_ay=6)
    assert kt.hasta_ay_ort == pytest.approx(0.5, abs=0.05)
    assert kt.shrinkage == 1.0
    assert any("oncul" in a for a in kt.aciklama)


def test_kazanim_buzulme_az_veride_daha_fazla():
    rng = np.random.default_rng(2)
    _, havuz = _sentetik_havuz(rng)
    az = kazanim_tahmini([{"hasta": 1, "ay": 1}], havuz, 12)
    cok = kazanim_tahmini([{"hasta": 30, "ay": 36}], havuz, 12)
    assert az.shrinkage > cok.shrinkage


def test_kazanim_kovaryat_etkisi():
    rng = np.random.default_rng(3)
    _, havuz = _sentetik_havuz(rng)
    taban = kazanim_tahmini([{"hasta": 5, "ay": 10}], havuz, 12)
    ozel = kazanim_tahmini([{"hasta": 5, "ay": 10}], havuz, 12, {"kurum_tipi": "ozel", "rekabet": 2})
    assert ozel.hasta_ay_ort < taban.hasta_ay_ort
    assert any("Kurum tipi" in a for a in ozel.aciklama)
    assert any("rekabet" in a for a in ozel.aciklama)


def test_moment_kestirim_oncule_duser():
    assert _moment_kestirim([{"hasta": 2, "ay": 4}]) == (2.0, 4.0)


def test_mape_hedefi_sentetik_veride():
    """MAPE <= %25 hedefi calisma duzeyinde: 8 merkezli 10 calisma, 6 aylik gozlemle sonraki 12 ay.

    Merkez duzeyinde Poisson gurultusu tek basina %30+ MAPE uretir; proje hedefi
    calisma toplam kazanimi icin tanimli.
    """
    rng = np.random.default_rng(7)
    oranlar, havuz = _sentetik_havuz(rng, n=120)
    gercek, tahmin = [], []
    for c in range(10):
        toplam_tahmin, toplam_gercek = 0.0, 0
        for lam in oranlar[c * 8:(c + 1) * 8]:
            gozlem = int(rng.poisson(lam * 6))
            kt = kazanim_tahmini([{"hasta": gozlem, "ay": 6.0}], havuz, 12)
            toplam_tahmin += kt.beklenen_toplam
            toplam_gercek += int(rng.poisson(lam * 12))
        gercek.append(toplam_gercek)
        tahmin.append(toplam_tahmin)
    assert mape(gercek, tahmin) <= 25.0


def test_mape_sifir_gercek_atlanir():
    assert mape([0, 10], [5, 12]) == pytest.approx(20.0)
    assert np.isnan(mape([0], [1]))


def test_projeksiyon_monte_carlo():
    rng = np.random.default_rng(4)
    _, havuz = _sentetik_havuz(rng)
    tahminler = [kazanim_tahmini([{"hasta": 6, "ay": 6}], havuz, 12) for _ in range(5)]
    p = calisma_kazanim_projeksiyonu(tahminler, hedef_hasta=40, baslangic=date(2026, 1, 1),
                                     planlanan_bitis=date(2027, 6, 1), n_sim=300)
    assert p["hedefe_ulasma_ay"] is not None and p["hedefe_ulasma_ay"] > 0
    assert 0 <= p["olasilik_zamaninda"] <= 1
    assert p["ulasma_ay_dagilimi"]["p10"] <= p["ulasma_ay_dagilimi"]["p90"]
    assert p["tahmini_tarih"] > date(2026, 1, 1)
    # ayni seed ayni sonuc
    p2 = calisma_kazanim_projeksiyonu(tahminler, 40, date(2026, 1, 1), date(2027, 6, 1), n_sim=300)
    assert p2["hedefe_ulasma_ay"] == p["hedefe_ulasma_ay"]


def test_projeksiyon_bos():
    p = calisma_kazanim_projeksiyonu([], 10, date.today())
    assert p["hedefe_ulasma_ay"] is None


# --- aktivasyon -------------------------------------------------------

def _sentetik_aktivasyon(rng, n=150):
    kayitlar, etiket = [], []
    for _ in range(n):
        kov = {
            "kurum_tipi": rng.choice(["universite", "egitim_arastirma", "sehir", "ozel"]),
            "etik_kurul_ortalama_gun": float(rng.uniform(30, 120)),
            "sozlesme_sablonu_var": bool(rng.random() < 0.5),
            "daha_once_calisildi": bool(rng.random() < 0.5),
            "calisma_turu": "ilac",
        }
        eta = np.log(110) + 0.5 * (kov["kurum_tipi"] == "universite") - 0.5 * (kov["kurum_tipi"] == "ozel") \
            + 0.006 * (kov["etik_kurul_ortalama_gun"] - 60) - 0.4 * kov["sozlesme_sablonu_var"] - 0.3 * kov["daha_once_calisildi"]
        sure = float(np.exp(eta) * rng.weibull(1.8))
        sansur = rng.random() < 0.15
        kayitlar.append({"sure_gun": min(sure, 300) if sansur else sure, "gozlendi": not sansur, "kovaryatlar": kov})
        etiket.append(sure > 120)
    return kayitlar, etiket


def test_gecikme_modeli_oncul():
    m = GecikmeModeli()
    r = m.tahmin({"kurum_tipi": "universite"}, 120)
    assert 0 < r.olasilik_gecikme < 1
    assert r.p25 < r.medyan_gun < r.p75
    assert any("oncul" in a for a in r.aciklama)
    assert "Universite hastanesi" in r.katkilar


def test_gecikme_kovaryat_yonu():
    m = GecikmeModeli()
    hizli = m.tahmin({"kurum_tipi": "ozel", "sozlesme_sablonu_var": True, "daha_once_calisildi": True}, 120)
    yavas = m.tahmin({"kurum_tipi": "universite", "etik_kurul_ortalama_gun": 120}, 120)
    assert hizli.olasilik_gecikme < yavas.olasilik_gecikme
    assert hizli.medyan_gun < yavas.medyan_gun


def test_gecikme_fit_az_veri():
    m = GecikmeModeli().fit([{"sure_gun": 90, "gozlendi": True, "kovaryatlar": {}}] * 3)
    assert not m.egitildi and m.n_egitim == 3


def test_gecikme_fit_ve_auc():
    rng = np.random.default_rng(11)
    egitim, _ = _sentetik_aktivasyon(rng, 200)
    test, etiket = _sentetik_aktivasyon(rng, 150)
    m = GecikmeModeli().fit(egitim)
    assert m.egitildi
    assert 1.0 < m.shape < 3.0
    skor = [m.tahmin(k["kovaryatlar"], 120).olasilik_gecikme for k in test]
    assert auc(etiket, skor) >= 0.80


def test_kaplan_meier():
    egri = kaplan_meier([5, 8, 8, 12, 20], [True, True, False, True, False])
    assert egri[0] == (0.0, 1.0)
    assert egri[1] == (5.0, pytest.approx(0.8))
    assert egri[-1][1] == pytest.approx(0.8 * 0.75 * 0.5)
    assert all(egri[i][1] >= egri[i + 1][1] for i in range(len(egri) - 1))


def test_auc_sinirlar():
    assert auc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == 1.0
    assert auc([1, 0], [0.5, 0.5]) == pytest.approx(0.5)
    assert np.isnan(auc([1, 1], [0.1, 0.2]))


# --- siralama ---------------------------------------------------------

def test_merkez_sirala():
    adaylar = [
        {"ad": "A", "tahmini_kazanim": 1.5, "gecikme_riski": 0.2, "sapma_orani": 0.1, "tamamlanan_calisma": 8},
        {"ad": "B", "tahmini_kazanim": 0.4, "gecikme_riski": 0.7, "sapma_orani": 0.6, "tamamlanan_calisma": 1},
        {"ad": "C", "tahmini_kazanim": 1.0, "gecikme_riski": 0.4},
    ]
    s = merkez_sirala(adaylar)
    assert [x["ad"] for x in s] == ["A", "C", "B"]
    assert s[0]["sira"] == 1 and 0 < s[0]["puan"] <= 100
    assert set(s[0]["katkilar"]) == {"kazanim", "gecikme", "kalite", "deneyim", "rekabet", "cografya"}
    assert sum(s[0]["katkilar"].values()) == pytest.approx(s[0]["puan"], abs=0.2)
    assert "hasta/ay" in s[0]["gerekce"]


def test_merkez_sirala_agirlik_ezme():
    adaylar = [{"ad": "A", "tahmini_kazanim": 2.0, "gecikme_riski": 0.9},
               {"ad": "B", "tahmini_kazanim": 0.5, "gecikme_riski": 0.1}]
    s = merkez_sirala(adaylar, {"kazanim": 0.0, "gecikme": 1.0, "kalite": 0, "deneyim": 0, "rekabet": 0, "cografya": 0})
    assert s[0]["ad"] == "B"


# --- db entegrasyonu -------------------------------------------------

def test_calisma_tahmin_guncelle_bos_db():
    from smartclinical.db import db_oturumu, sifirla
    from smartclinical.models import Calisma, CalismaMerkez, CalismaTuru, Merkez

    sifirla()
    with db_oturumu() as db:
        m = Merkez(kod="M1", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
        c = Calisma(kod="T-1", baslik="t", kisa_ad="t", tur=CalismaTuru.ILAC, sponsor="s",
                    terapotik_alan="Onkoloji", baslangic=date(2026, 1, 1), planlanan_bitis=date(2027, 1, 1))
        db.add_all([m, c])
        db.flush()
        cm = CalismaMerkez(calisma_id=c.id, merkez_id=m.id, merkez_no="01", durum="secildi", hedef_hasta=10,
                           secim_tarihi=date(2026, 2, 1))
        db.add(cm)
        db.flush()
        db.refresh(c)
        sonuc = calisma_tahmin_guncelle(db, c)
        assert len(sonuc) == 1
        assert sonuc[0].tahmini_kazanim is not None and sonuc[0].tahmini_kazanim > 0
        assert 0 <= sonuc[0].gecikme_riski <= 1
