import pytest

from ml.degerlendirme import metrikler as M


def test_karisiklik_ve_duyarlilik():
    g = ["saglandi", "saglandi", "saglanmadi", "belirsiz", "saglandi"]
    t = ["saglandi", "belirsiz", "saglanmadi", "saglandi", "saglandi"]
    k = M.karisiklik(g, t)
    assert k == {"tp": 2, "fp": 1, "fn": 1, "tn": 1}
    assert M.duyarlilik(k) == pytest.approx(2 / 3)
    assert M.ozgulluk(k) == pytest.approx(0.5)
    assert M.f1(k) == pytest.approx(2 / 3)


def test_karisiklik_uzunluk_hatasi():
    with pytest.raises(ValueError):
        M.karisiklik(["saglandi"], [])


def test_kanit_kaynakta_turkce_normalize():
    kaynak = "Laboratuvar: Hb 10.8 g/dL, İmmünohistokimya HER2 skor 1+ (negatif)."
    assert M.kanit_kaynakta_mi("HER2 skor 1+ (negatif)", kaynak)
    assert M.kanit_kaynakta_mi("immünohistokimya her2 skor 1+", kaynak)  # büyük İ
    assert not M.kanit_kaynakta_mi("HER2 skor 3+ pozitif", kaynak)
    assert M.kanit_kaynakta_mi(None, kaynak)  # çekimser model halüsinasyon değildir


def test_halusinasyon_orani():
    ciftler = [("Hb 10.8 g/dL", "Hb 10.8 g/dL ölçüldü"), ("uydurma cümle", "başka bir metin"), (None, "x")]
    assert M.halusinasyon_orani(ciftler) == pytest.approx(0.5)
    assert M.halusinasyon_orani([]) == 0.0


def test_kanit_ortusme():
    assert M.kanit_ortusme("ECOG PS: 2", ["ECOG PS: 2"]) == pytest.approx(1.0)
    assert 0 < M.kanit_ortusme("Genel durum orta, ECOG PS 2", ["ECOG PS: 2"]) < 1
    assert M.kanit_ortusme(None, ["x"]) == 0.0


def test_yapilandirma_eslesme():
    beklenen = {"alan": "lab", "loinc": "718-7", "op": ">=", "deger": 9, "birim": "g/dL", "son_gun": None}
    tam = {"alan": "lab", "loinc": "718-7", "op": ">=", "deger": 9.0, "birim": "g/dl"}
    assert M.yapilandirma_eslesme(beklenen, tam)["tam"] is True
    kismi = {"alan": "lab", "loinc": "718-7", "op": ">", "deger": 9, "birim": "g/dL"}
    e = M.yapilandirma_eslesme(beklenen, kismi)
    assert e["tam"] is False and e["alan_orani"] == pytest.approx(4 / 5)
    assert M.yapilandirma_eslesme(None, None)["tam"] is True


def test_cohen_kappa():
    a = ["saglandi"] * 8 + ["saglanmadi"] * 8 + ["belirsiz"] * 4
    assert M.cohen_kappa(a, a) == pytest.approx(1.0)
    b = list(a)
    b[0], b[9] = "belirsiz", "saglandi"
    assert 0.7 < M.cohen_kappa(a, b) < 1.0


def test_kalibrasyon():
    r = M.guven_kalibrasyonu([0.95, 0.9, 0.2, 0.3], [True, True, False, False], kova=5)
    assert r["ece"] < 0.3
    assert M.guven_kalibrasyonu([], [])["ece"] == 0.0
