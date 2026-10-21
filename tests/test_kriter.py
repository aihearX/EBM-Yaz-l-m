from smartclinical.services.kriter import degerlendir, yapilandir
from smartclinical.services.kriter.sozluk import birim_cevir, lab_bul, zaman_penceresi_gun


def test_yas_ve_uzeri():
    y = yapilandir("18 yaş ve üzeri")
    assert y.kategori == "yas"
    assert y.sorgu == {"alan": "yas", "op": ">=", "deger": 18}
    assert y.guven >= 0.8


def test_yas_aralik_ingilizce():
    y = yapilandir("Patients aged 18 to 75 years")
    assert y.kategori == "yas"
    assert y.sorgu["op"] == "arasi" and y.sorgu["deger"] == [18, 75]


def test_yas_kesme_isareti():
    y = yapilandir("Yaşı 18'den küçük")
    assert y.sorgu == {"alan": "yas", "op": "<", "deger": 18}


def test_yas_buyuk():
    assert yapilandir("65 yaşından büyük").sorgu["op"] == ">"


def test_tani_her2_negatif():
    y = yapilandir("Histolojik olarak doğrulanmış HER2-negatif meme kanseri")
    assert y.kategori == "tani"
    assert y.sorgu["icd10"] == ["C50"]
    assert "her2-negatif" in y.sorgu["niteleyiciler"]
    assert y.guven < 0.8  # niteleyiciler yapisal veride dogrulanamaz


def test_tani_zaman_penceresi():
    y = yapilandir("Son 6 ay içinde miyokard enfarktüsü", tip="haric")
    assert y.kategori == "tani"
    assert set(y.sorgu["icd10"]) == {"I21", "I22"}
    assert y.sorgu["son_ay"] == 6
    assert y.tip == "haric"


def test_performans_ecog():
    y = yapilandir("ECOG performans skoru 0-1")
    assert y.kategori == "performans"
    assert y.sorgu == {"alan": "performans", "olcek": "ecog", "op": "arasi", "deger": [0, 1]}


def test_performans_karnofsky_ve_nyha():
    assert yapilandir("Karnofsky ≥ 70").sorgu["op"] == ">="
    y = yapilandir("NYHA sınıf II-III kalp yetmezliği")
    assert y.kategori == "performans"
    assert y.sorgu["ve"][0]["deger"] == [2, 3]


def test_lab_hemoglobin():
    y = yapilandir("Hemoglobin ≥ 9 g/dL")
    assert y.kategori == "lab"
    assert y.sorgu["loinc"] == "718-7" and y.sorgu["op"] == ">=" and y.sorgu["deger"] == 9


def test_lab_egfr():
    y = yapilandir("eGFR < 30 mL/min/1.73m2")
    assert y.sorgu["ad"] == "egfr" and y.sorgu["op"] == "<" and y.sorgu["deger"] == 30


def test_lab_uln_coklu():
    y = yapilandir("AST ve ALT ≤ 2.5 × ULN")
    assert "ve" in y.sorgu and len(y.sorgu["ve"]) == 2
    assert all(s["uln_kat"] == 2.5 and s["op"] == "<=" for s in y.sorgu["ve"])


def test_lab_binlik_ayirici_ve_birim_cevirimi():
    y = yapilandir("Trombosit sayısı ≥ 100.000/µL")
    assert y.sorgu["deger"] == 100 and y.sorgu["birim"] == "10^9/L"


def test_lab_turkce_virgul_ve_yuzde_aralik():
    y = yapilandir("HbA1c %7,5 ile %10 arası")
    assert y.sorgu["op"] == "arasi" and y.sorgu["deger"] == [7.5, 10]
    assert yapilandir("Kreatinin < 1,5 mg/dL").sorgu["deger"] == 1.5


def test_lab_altinda():
    y = yapilandir("Hemoglobin 10 g/dL'nin altında")
    assert y.sorgu["op"] == "<" and y.sorgu["deger"] == 10


def test_gebelik():
    y = yapilandir("Gebe veya emziren kadınlar", tip="haric")
    assert y.kategori == "gebelik"
    assert y.sorgu == {"alan": "gebelik", "deger": True}


def test_cinsiyet():
    assert yapilandir("Kadın hastalar").sorgu == {"alan": "cinsiyet", "deger": "K"}


def test_ilac_zaman_penceresi():
    y = yapilandir("Son 4 hafta içinde sistemik kortikosteroid kullanımı", tip="haric")
    assert y.kategori == "ilac"
    assert y.sorgu["atc"] == ["H02"] and y.sorgu["son_gun"] == 28


def test_olumsuz_ilac():
    y = yapilandir("Daha önce kemoterapi almamış")
    assert "degil" in y.sorgu and y.sorgu["degil"]["alan"] == "ilac"


def test_serbest_kriter():
    y = yapilandir("Araştırmacının görüşüne göre çalışmaya uyumu engelleyecek durum")
    assert y.kategori == "serbest" and y.guven < 0.5


def test_bos_metin():
    assert yapilandir("").kategori == "serbest"


def test_sozluk_yardimcilari():
    assert lab_bul("mutlak nötrofil sayısı")[0] == "notrofil"
    assert birim_cevir(150000, "/uL", "10^9/L") == 150
    assert zaman_penceresi_gun("within the last 12 months") == 360


# ---------------------------------------------------------------------------
# degerlendirici
# ---------------------------------------------------------------------------

HASTA = {
    "dogum_yili": 1970, "cinsiyet": "K",
    "tanilar": [{"icd10": "C50.9", "ad": "Meme malign neoplazmı", "tarih": "2024-03-01"},
                {"icd10": "I10", "ad": "Esansiyel hipertansiyon", "tarih": "2015-01-01"}],
    "ilaclar": [{"atc": "L01FD01", "ad": "Trastuzumab", "aktif": True}, {"atc": "C08CA01", "ad": "Amlodipin", "aktif": True}],
    "laboratuvar": [{"loinc": "718-7", "ad": "Hemoglobin", "deger": 11.2, "birim": "g/dL", "tarih": "2026-10-01"},
                    {"ad": "AST", "deger": 30, "birim": "U/L", "ust_sinir": 40, "tarih": "2026-10-01"},
                    {"ad": "ALT", "deger": 95, "birim": "U/L", "ust_sinir": 35, "tarih": "2026-10-01"},
                    {"ad": "Trombosit", "deger": 180000, "birim": "/uL", "tarih": "2026-10-01"}],
    "performans": {"ecog": 1},
}


def _d(metin, hasta=HASTA, tip="dahil"):
    return degerlendir(yapilandir(metin, tip).sorgu, hasta)


def test_degerlendir_yas_saglandi():
    d = _d("18 yaş ve üzeri")
    assert d.sonuc == "saglandi" and "56" in d.kanit


def test_degerlendir_lab_birim_cevirimi():
    d = _d("Trombosit sayısı ≥ 100.000/µL")
    assert d.sonuc == "saglandi" and d.kullanilan_veri["deger"] == 180


def test_degerlendir_uln():
    d = _d("AST ve ALT ≤ 2.5 × ULN")
    assert d.sonuc == "saglanmadi"  # ALT 95 > 2.5*35
    assert "alt" in d.kanit


def test_degerlendir_tani_niteleyici_dusuk_guven():
    d = _d("Histolojik olarak doğrulanmış HER2-negatif meme kanseri")
    assert d.sonuc == "saglandi" and d.guven < 0.7


def test_degerlendir_tani_yok():
    d = _d("Tip 2 diyabet", tip="haric")
    assert d.sonuc == "saglanmadi"


def test_degerlendir_zaman_penceresi_disinda():
    d = _d("Son 6 ay içinde hipertansiyon tanısı")
    assert d.sonuc == "saglanmadi"


def test_degerlendir_gebelik_erkek():
    d = _d("Gebe veya emziren kadınlar", {"cinsiyet": "E", "dogum_yili": 1980})
    assert d.sonuc == "saglanmadi"


def test_degerlendir_gebelik_belirsiz():
    assert _d("Gebe veya emziren kadınlar", {"cinsiyet": "K", "dogum_yili": 1995}).sonuc == "belirsiz"


def test_degerlendir_olumsuz():
    d = _d("Daha önce kemoterapi almamış")
    assert d.sonuc == "saglandi"  # trastuzumab sitotoksik kemoterapi degil


def test_degerlendir_eksik_veri_belirsiz():
    assert _d("Hemoglobin ≥ 9 g/dL", {"dogum_yili": 1970}).sonuc == "belirsiz"
    assert _d("ECOG 0-1", {"dogum_yili": 1970}).sonuc == "belirsiz"


def test_degerlendir_veya():
    s = {"veya": [{"alan": "yas", "op": "<", "deger": 18}, {"alan": "cinsiyet", "deger": "K"}]}
    assert degerlendir(s, HASTA).sonuc == "saglandi"


def test_degerlendir_bozuk_sorgu():
    assert degerlendir({"alan": "lab", "op": "??", "ad": "x", "deger": 1}, HASTA).sonuc == "belirsiz"
    assert degerlendir(None, HASTA).sonuc == "belirsiz"
