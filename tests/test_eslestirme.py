import os

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

from datetime import date  # noqa: E402

import pytest  # noqa: E402

from smartclinical import db as _db  # noqa: E402
from smartclinical.models import (  # noqa: E402
    Calisma,
    CalismaMerkez,
    CalismaTuru,
    EslestirmeSonucu,
    Hasta,
    Kriter,
    Merkez,
)
from smartclinical.services.bdm import BDMIstemci  # noqa: E402
from smartclinical.services.bdm.saglayicilar import KuralTabanliSaglayici  # noqa: E402
from smartclinical.services.eslestirme import Eslestirici, golge_mod_karsilastir  # noqa: E402
from smartclinical.services.kriter import yapilandir  # noqa: E402

EPIKRIZ_UYGUN = (
    "Hasta 54 yaşında kadın. Tru-cut biyopsi sonucu invaziv duktal karsinom olarak raporlandı. "
    "İmmünohistokimyasal incelemede ER pozitif, HER2 negatif saptandı. Gebelik yok, emzirmiyor. "
    "ECOG performans durumu 1. Daha önce kemoterapi almamış. Toraks BT'de metastaz lehine bulgu izlenmedi."
)
EPIKRIZ_HARIC = (
    "Hasta 61 yaşında kadın. Meme karsinomu tanısı ile izlenmekte. HER2 negatif. "
    "Üç ay önce geçirilmiş miyokard enfarktüsü nedeniyle kardiyoloji takibinde. ECOG 1."
)

KRITERLER = [
    ("dahil", "18 yaş ve üzeri"),
    ("dahil", "Kadın hastalar"),
    ("dahil", "Histolojik olarak doğrulanmış HER2-negatif meme kanseri"),
    ("dahil", "ECOG performans skoru 0-1"),
    ("dahil", "Hemoglobin ≥ 9 g/dL"),
    ("haric", "Son 6 ay içinde miyokard enfarktüsü"),
    ("haric", "Gebe veya emziren kadınlar"),
    ("haric", "Daha önce kemoterapi almış hastalar"),
]


@pytest.fixture
def db():
    _db.sifirla()
    s = _db.oturum_fabrikasi()()
    yield s
    s.close()


@pytest.fixture
def calisma(db):
    m = Merkez(kod="M01", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
    c = Calisma(kod="EBM-TST-001", baslik="Test", kisa_ad="TST", tur=CalismaTuru.ILAC, sponsor="X", terapotik_alan="Onkoloji")
    db.add_all([m, c])
    db.flush()
    db.add(CalismaMerkez(calisma_id=c.id, merkez_id=m.id, merkez_no="01"))
    for i, (tip, metin) in enumerate(KRITERLER):
        db.add(Kriter(calisma_id=c.id, tip=tip, sira=i, metin=metin, yapisal=yapilandir(metin, tip).sorgu))
    db.commit()
    db.refresh(c)
    return c


def _hasta(merkez_id, **k):
    v = dict(merkez_id=merkez_id, kayit_no="H1", dogum_yili=1972, cinsiyet="K",
             tanilar=[{"icd10": "C50.4", "ad": "Meme malign neoplazmı", "tarih": "2026-08-10"}],
             ilaclar=[{"atc": "C08CA01", "ad": "Amlodipin", "aktif": True}],
             laboratuvar=[{"loinc": "718-7", "ad": "Hemoglobin", "deger": 12.1, "birim": "g/dL", "tarih": str(date.today())}],
             performans={"ecog": 1}, metinler=[{"tur": "epikriz", "tarih": "2026-09-01", "metin": EPIKRIZ_UYGUN}])
    v.update(k)
    return Hasta(**v)


@pytest.fixture
def eslestirici():
    return Eslestirici(BDMIstemci(KuralTabanliSaglayici()))


def test_uygun_hasta(db, calisma, eslestirici):
    h = _hasta(calisma.merkezler[0].merkez_id)
    c = eslestirici.hasta_degerlendir(calisma, h)
    assert c.karar == "uygun", c.aciklama
    assert c.skor >= 0.85
    assert len(c.kriter_sonuclari) == len(KRITERLER)
    assert all(s["sonuc"] in ("saglandi", "saglanmadi") for s in c.kriter_sonuclari)
    # haric kriterler saglanmamis olmali, kanit cumlesi kaynakta olmali
    gebelik = next(s for s in c.kriter_sonuclari if "Gebe" in s["metin"])
    assert gebelik["sonuc"] == "saglanmadi" and gebelik["kanit"] in EPIKRIZ_UYGUN


def test_haric_kriter_ihlali(db, calisma, eslestirici):
    h = _hasta(calisma.merkezler[0].merkez_id, kayit_no="H2", dogum_yili=1965,
               tanilar=[{"icd10": "C50.9", "ad": "Meme ca", "tarih": "2025-01-01"},
                        {"icd10": "I21.0", "ad": "Akut MI", "tarih": str(date.today().replace(day=1))}],
               metinler=[{"tur": "epikriz", "metin": EPIKRIZ_HARIC}])
    c = eslestirici.hasta_degerlendir(calisma, h)
    assert c.karar == "uygun_degil" and c.skor < 0.1
    assert "miyokard" in c.aciklama.lower()


def test_dahil_kriteri_saglanmayan(db, calisma, eslestirici):
    h = _hasta(calisma.merkezler[0].merkez_id, kayit_no="H3", cinsiyet="E")
    c = eslestirici.hasta_degerlendir(calisma, h)
    assert c.karar == "uygun_degil"
    assert "Kadın" in c.aciklama


def test_yapisal_veri_yok_belirsiz(db, calisma, eslestirici):
    h = _hasta(calisma.merkezler[0].merkez_id, kayit_no="H4", tanilar=None, laboratuvar=None, performans=None, metinler=None)
    c = eslestirici.hasta_degerlendir(calisma, h)
    assert c.karar in ("belirsiz", "olasi")
    assert c.belirsiz_sayisi >= 3


def test_metin_ile_teyit(db, calisma, eslestirici):
    # yapisal lab yok ama epikrizde ECOG ve metastaz var: metin kaniti devreye girer
    h = _hasta(calisma.merkezler[0].merkez_id, kayit_no="H5", performans=None)
    c = eslestirici.hasta_degerlendir(calisma, h)
    ecog = next(s for s in c.kriter_sonuclari if "ECOG" in s["metin"])
    assert ecog["sonuc"] == "saglandi" and ecog["yontem"] == "kural"


def test_kaydet_ve_guncelle(db, calisma, eslestirici):
    h = _hasta(calisma.merkezler[0].merkez_id)
    db.add(h)
    db.commit()
    c = eslestirici.hasta_degerlendir(calisma, h)
    s = eslestirici.kaydet(db, calisma, h, c)
    db.commit()
    assert s.id and s.karar == "uygun" and s.model_surumu
    s.inceleme_karari = "onay"
    db.commit()
    s2 = eslestirici.kaydet(db, calisma, h, c)
    assert s2.id == s.id and s2.inceleme_karari == "onay"  # karar degismedi, inceleme korundu
    assert db.query(EslestirmeSonucu).count() == 1


def test_calisma_icin_tara(db, calisma, eslestirici):
    mid = calisma.merkezler[0].merkez_id
    db.add_all([_hasta(mid, kayit_no="A"), _hasta(mid, kayit_no="B", cinsiyet="E"),
                _hasta(mid, kayit_no="C", metinler=[{"tur": "epikriz", "metin": EPIKRIZ_HARIC}],
                       tanilar=[{"icd10": "I21.9", "ad": "MI", "tarih": str(date.today())}])])
    db.commit()
    sonuclar = eslestirici.calisma_icin_tara(db, calisma, golge_mod=True)
    # C hastasinin meme Ca tanisi yok: ICD on filtresi onu taramaya almaz
    assert len(sonuclar) == 2
    kararlar = {s.hasta.kayit_no: s.karar for s in sonuclar}
    assert kararlar["A"] == "uygun" and kararlar["B"] == "uygun_degil"
    assert all(s.golge_mod for s in sonuclar)
    # tekrar tarama kayit sayisini artirmaz
    eslestirici.calisma_icin_tara(db, calisma)
    assert db.query(EslestirmeSonucu).count() == 2


def test_merkezsiz_calisma(db, eslestirici):
    c = Calisma(kod="X", baslik="x", kisa_ad="x", tur=CalismaTuru.GOZLEMSEL, sponsor="s", terapotik_alan="t")
    db.add(c)
    db.commit()
    assert eslestirici.calisma_icin_tara(db, c) == []


def test_golge_mod_karsilastir():
    sonuclar = [{"hasta_id": 1, "karar": "uygun"}, {"hasta_id": 2, "karar": "uygun_degil"},
                {"hasta_id": 3, "karar": "belirsiz"}, {"hasta_id": 4, "karar": "olasi"}, {"hasta_id": 5, "karar": "uygun_degil"},
                {"hasta_id": 9, "karar": "uygun"}]
    m = golge_mod_karsilastir(sonuclar, {1: True, 2: False, 3: True, 4: False, 5: True})
    assert m["n"] == 5
    assert m["karisiklik"] == {"tp": 2, "fp": 1, "tn": 1, "fn": 1}
    assert m["duyarlilik"] == round(2 / 3, 3) and m["ozgulluk"] == 0.5
    assert golge_mod_karsilastir([], {})["duyarlilik"] is None
