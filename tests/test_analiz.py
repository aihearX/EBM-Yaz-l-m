"""On analiz: test secimi, veri seti, gonullu akisi, AE ozeti ve web ucu yetkileri."""
import os

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    AdversOlay,
    Calisma,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    FormKaydi,
    Gonullu,
    GonulluDurumu,
    Kol,
    Kullanici,
    Merkez,
    Rol,
    Vizit,
)
from smartclinical.models import Form as CRF
from smartclinical.services import analiz, yetki
from smartclinical.web import analiz as analiz_web

PAROLA = "Test1234!xyz"
R = np.random.default_rng(7)


# -- servis: test secimi ------------------------------------------------------

def test_normal_veride_welch_t():
    a = list(R.normal(120, 10, 25))
    b = list(R.normal(128, 10, 25))
    s = analiz.kol_karsilastir({"A": a, "B": b}, analiz.SAYISAL)
    assert s["test"] == "Welch t testi" and 0 <= s["p"] <= 1 and "Shapiro" in s["gerekce"]


def test_carpik_veride_mann_whitney():
    a = list(R.exponential(2.0, 30))
    b = list(R.exponential(3.0, 30))
    s = analiz.kol_karsilastir({"A": a, "B": b}, analiz.SAYISAL)
    assert s["test"] == "Mann-Whitney U testi" and "sağlanmadı" in s["gerekce"]


def test_uc_kolda_anova_veya_kruskal():
    normal = {k: list(R.normal(50, 5, 20)) for k in "ABC"}
    assert analiz.kol_karsilastir(normal, analiz.SAYISAL)["test"] == "Tek yönlü ANOVA"
    carpik = {k: list(R.exponential(2.0, 20)) for k in "ABC"}
    assert analiz.kol_karsilastir(carpik, analiz.SAYISAL)["test"] == "Kruskal-Wallis testi"


def test_kucuk_beklenen_degerde_fisher():
    a = ["Evet"] * 2 + ["Hayır"] * 8
    b = ["Evet"] * 7 + ["Hayır"] * 3
    s = analiz.kol_karsilastir({"A": a, "B": b}, analiz.KATEGORIK)
    assert s["test"] == "Fisher kesin testi" and s["p"] is not None and s["tablo"] == [[2, 8], [7, 3]]
    buyuk = {"A": ["Evet"] * 30 + ["Hayır"] * 30, "B": ["Evet"] * 20 + ["Hayır"] * 40}
    assert analiz.kol_karsilastir(buyuk, analiz.KATEGORIK)["test"] == "Ki-kare testi"


def test_n_kucukse_test_yok():
    s = analiz.kol_karsilastir({"A": [1.0, 2.0], "B": [3.0, 4.0, 5.0, 6.0]}, analiz.SAYISAL)
    assert s["test"] is None and s["p"] is None and "n < 3" in s["gerekce"]
    s = analiz.kol_karsilastir({"A": [1.0, 2.0, 3.0]}, analiz.SAYISAL)
    assert s["test"] is None and "iki kol" in s["gerekce"]


def test_betimle_ve_kutu():
    o = analiz.betimle([1, 2, 3, 4, None, "5", "6,5", "yok"], analiz.SAYISAL)
    assert o["n"] == 6 and o["eksik"] == 2 and o["medyan"] == 3.5 and o["min"] == 1 and o["maks"] == 6.5
    assert analiz.sayiya("6,5") == 6.5 and analiz.sayiya("1.250,5") == 1250.5 and analiz.sayiya("x") is None
    k = analiz.betimle(["Evet", "Hayır", "Evet", None], analiz.KATEGORIK, ["Evet", "Hayır"])
    assert k["n"] == 3 and k["eksik"] == 1 and k["duzeyler"][0] == {"deger": "Evet", "n": 2, "yuzde": 66.7}
    kutu = analiz.kutu_verisi([10, 11, 12, 13, 14, 40])
    assert kutu["aykiri"] == [40.0] and kutu["maks"] == 14.0 and kutu["medyan"] == 12.5


# -- web ve veri seti ------------------------------------------------------------

ALANLAR = [
    {"kod": "VSDAT", "etiket": "Ölçüm tarihi", "tip": "tarih", "zorunlu": True},
    {"kod": "SYSBP", "etiket": "Sistolik kan basıncı", "tip": "sayi", "birim": "mmHg", "zorunlu": True},
    {"kod": "ATES", "etiket": "Ateş var mı?", "tip": "secim", "secenekler": ["Evet", "Hayır"]},
    {"kod": "NOT", "etiket": "Not", "tip": "metin"},
]


@pytest.fixture(scope="module")
def istemci():
    if not any(getattr(r, "path", "").startswith("/calismalar/{calisma_id}/analiz") for r in app.routes):
        app.include_router(analiz_web.router)
    sifirla()
    db = oturum_fabrikasi()()
    m = Merkez(kod="T-01", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
    db.add(m)
    db.flush()
    for kadi, rol in (("admin", Rol.YONETICI), ("istat", Rol.ISTATISTIKCI), ("sponsor", Rol.SPONSOR), ("cra", Rol.CRA)):
        db.add(Kullanici(kullanici_adi=kadi, ad_soyad=kadi, eposta=f"{kadi}@t.local", parola_hash=yetki.parola_hashle(PAROLA),
                         rol=rol, kurum="S" if rol == Rol.SPONSOR else None))
    c = Calisma(kod="ANZ-001", baslik="Analiz testi", kisa_ad="Analiz", tur=CalismaTuru.ILAC, sponsor="S",
                terapotik_alan="Kardiyoloji", hedef_hasta=20)
    db.add(c)
    db.flush()
    cm = CalismaMerkez(calisma_id=c.id, merkez_id=m.id, merkez_no="01", hedef_hasta=20, durum="aktif")
    kol_a, kol_b = Kol(calisma_id=c.id, ad="Kol A"), Kol(calisma_id=c.id, ad="Kol B")
    form = CRF(calisma_id=c.id, kod="VS", ad="Vital Bulgular", vizitler=[], sira=0, alanlar=ALANLAR, durum="yayinda")
    db.add_all([cm, kol_a, kol_b, form])
    db.flush()
    r = np.random.default_rng(3)
    # 8 randomize gonullu (4+4), 2 tarama basarisiz, 1 aday
    for i in range(11):
        if i < 8:
            kol = kol_a if i % 2 == 0 else kol_b
            durum = GonulluDurumu.TAMAMLADI if i == 0 else (GonulluDurumu.AYRILDI if i == 1 else GonulluDurumu.TEDAVIDE)
            g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, gonullu_no=f"01-{i + 1:03d}", durum=durum, kol_id=kol.id,
                        randomizasyon_tarihi=date(2024, 1, 1), ayrilma_nedeni="Hasta kararı" if i == 1 else None)
        elif i < 10:
            g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, gonullu_no=f"01-{i + 1:03d}", durum=GonulluDurumu.TARAMA_BASARISIZ,
                        tarama_basarisizlik_nedeni="Hb < 9 g/dL")
        else:
            g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, gonullu_no=f"01-{i + 1:03d}", durum=GonulluDurumu.ADAY)
        db.add(g)
        db.flush()
        if i >= 8:
            continue
        for sira, vad in enumerate(("V1", "V2")):
            v = Vizit(gonullu_id=g.id, ad=vad, sira=sira, planlanan=date(2024, 1, 1), gerceklesen=date(2024, 1, 1), durum="yapildi")
            db.add(v)
            db.flush()
            taban = 120 if kol.ad == "Kol A" else 135
            veriler = {"VSDAT": "2024-01-01", "SYSBP": str(round(taban + r.normal(0, 6), 1)).replace(".", ","),
                       "ATES": "Evet" if i % 3 == 0 else "Hayır", "NOT": "x"}
            durum = "taslak" if (i == 7 and vad == "V2") else ("kilitli" if i < 3 else "tamamlandi")
            db.add(FormKaydi(gonullu_id=g.id, form_id=form.id, vizit_id=v.id, veriler=veriler, durum=durum))
        if i < 3:
            db.add(AdversOlay(gonullu_id=g.id, terim="Bulantı", meddra_soc="Gastrointestinal hastalıklar" if i else None,
                              baslangic=date(2024, 1, 5), siddet="3" if i == 0 else "1", ciddi=i == 0))
    db.commit()
    db.close()
    with TestClient(app) as cl:
        yield cl


def _giris(cl, kadi):
    cl.cookies.clear()
    r = cl.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _calisma():
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "ANZ-001")).scalar_one()
    return db, c


def test_veri_seti_taslaklari_dislar(istemci):
    db, c = _calisma()
    sutunlar, satirlar = analiz.veri_seti(c)
    assert sutunlar[:3] == ["gonullu_no", "kol", "vizit"] and "VS.SYSBP" in sutunlar and "VS.NOT" in sutunlar
    assert len(satirlar) == 15  # 16 kayit, 1 taslak
    assert all(isinstance(s["VS.SYSBP"], float) for s in satirlar) and satirlar[0]["kol"] == "Kol A"
    d = analiz.degiskenler(c)
    assert [x["kod"] for x in d] == ["VS.SYSBP", "VS.ATES"] and d[0]["vizitler"] == ["V1", "V2"]
    assert analiz.veri_durumu(c) == {"toplam": 16, "analiz": 15, "taslak": 1, "kilitli": 6, "kilitli_oran": 40.0, "on_analiz": True}
    db.close()


def test_degisken_analizi(istemci):
    db, c = _calisma()
    # tum vizitler: gonullu basina son deger, kol testi yok
    a = analiz.degisken_analizi(c, "VS.SYSBP")
    assert [k["ad"] for k in a["kollar"]] == ["Kol A", "Kol B"] and a["kollar"][0]["ozet"]["n"] == 4
    assert a["test"]["test"] is None and "kol testi yapılmaz" in a["test"]["gerekce"] and a["gorunum"] == "tum"
    assert len(a["grafik"]) == 2 and {"min", "c1", "medyan", "c3", "maks", "aykiri"} <= set(a["grafik"][0])
    a = analiz.degisken_analizi(c, "VS.SYSBP", "V1")
    assert a["kollar"][0]["ozet"]["n"] == 4
    assert a["test"]["test"] in ("Welch t testi", "Mann-Whitney U testi") and 0 <= a["test"]["p"] <= 1
    a = analiz.degisken_analizi(c, "VS.SYSBP", "V2")
    assert a["kollar"][1]["ozet"]["n"] == 3  # kol B'de V2 taslagi disarida
    a = analiz.degisken_analizi(c, "VS.ATES")
    assert a["toplam"]["duzeyler"][0]["deger"] == "Evet" and a["grafik"]["etiketler"] == ["Kol A", "Kol B"]
    assert analiz.degisken_analizi(c, "VS.YOK") is None
    db.close()


def test_gonullu_akisi_toplamlari(istemci):
    db, c = _calisma()
    ak = analiz.gonullu_akisi(c)
    s = {x["anahtar"]: x for x in ak["satirlar"]}
    assert ak["kollar"] == ["Kol A", "Kol B", analiz.KOL_YOK] and ak["toplam_gonullu"] == 11
    assert s["tarandi"]["toplam"] + s["tarama_oncesi"]["toplam"] == 11
    assert s["tarama_basarisiz"]["toplam"] == 2 and s["tarama_basarisiz"]["nedenler"] == [("Hb < 9 g/dL", 2)]
    assert s["randomize"]["kollar"] == {"Kol A": 4, "Kol B": 4, analiz.KOL_YOK: 0}
    assert s["tamamladi"]["toplam"] == 1 and s["ayrildi"]["nedenler"] == [("Hasta kararı", 1)]
    assert s["randomize"]["toplam"] == s["tedavide"]["toplam"] + s["tamamladi"]["toplam"] + s["ayrildi"]["toplam"]
    assert all(sum(x["kollar"].values()) == x["toplam"] for x in ak["satirlar"])
    db.close()


def test_advers_olay_ozeti(istemci):
    db, c = _calisma()
    ae = analiz.advers_olay_ozeti(c)
    assert ae["toplam_olay"] == 3 and ae["ozet"]["Kol A"] == {"gonullu_toplam": 4, "olay": 2, "olayli_gonullu": 2, "ciddi": 1,
                                                              "ciddi_gonullu": 1, "derece3": 1, "derece3_gonullu": 1}
    assert {s["soc"] for s in ae["satirlar"]} == {"Gastrointestinal hastalıklar", "Kodlanmamış"}
    db.close()


def test_sayfalar_ve_csv(istemci):
    db, c = _calisma()
    cid = c.id
    db.close()
    _giris(istemci, "istat")
    r = istemci.get(f"/calismalar/{cid}/analiz")
    assert r.status_code == 200 and "Ön analiz: kilitlenmemiş veri içerir" in r.text and "ön analiz içindir" in r.text
    assert "VS.SYSBP" in r.text and "Tarama başarısız" in r.text
    r = istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.SYSBP&vizit=V2")
    assert r.status_code == 200 and "Gerekçe:" in r.text and "SCGrafik.kutu" in r.text and "Medyan" in r.text
    r = istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.ATES")
    assert r.status_code == 200 and "yigili: true" in r.text
    assert istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.YOK").status_code == 404
    r = istemci.get(f"/calismalar/{cid}/analiz/advers-olaylar")
    assert r.status_code == 200 and "Kodlanmamış" in r.text and "ön analiz içindir" in r.text
    r = istemci.get(f"/calismalar/{cid}/analiz/veri-seti.csv")
    assert r.status_code == 200 and r.text.startswith("﻿gonullu_no;kol;vizit;")
    satirlar = r.text.splitlines()
    assert len(satirlar) == 16 and "taslak" not in r.text  # baslik + 15 kayit
    db = oturum_fabrikasi()()
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "disa_aktar", DenetimKaydi.varlik_id == cid)).scalars().all()
    assert kayit and kayit[-1].kullanici_adi == "istat" and kayit[-1].yeni["bicim"] == "analiz_csv"
    db.close()


def test_sponsor_ve_cra_403(istemci):
    db, c = _calisma()
    cid = c.id
    db.close()
    for kadi in ("sponsor", "cra"):
        _giris(istemci, kadi)
        for yol in ("", "/advers-olaylar", "/veri-seti.csv"):
            assert istemci.get(f"/calismalar/{cid}/analiz{yol}").status_code == 403, (kadi, yol)
    _giris(istemci, "admin")
    assert istemci.get(f"/calismalar/{cid}/analiz").status_code == 200


# -- P4: vizitler arasi degisim, Tablo 1, merkez siniri -----------------------------

def test_vizitler_arasi_degisim_eslestirilmis_test(istemci):
    db, c = _calisma()
    d = analiz.vizit_degisimi(c, "VS.SYSBP", "V1", "V2")
    assert d["gorunum"] == "degisim" and d["test"]["test"] in ("Eşleştirilmiş t testi", "Wilcoxon işaretli sıra testi")
    assert d["test"]["n_cift"] == 7  # kol B'de bir V2 taslak
    assert sum(k["n"] for k in d["kollar"]) == 7 and d["toplam"]["n"] == 7
    assert analiz.vizit_degisimi(c, "VS.ATES", "V1", "V2")["test"]["test"] is None
    kucuk = analiz.eslestirilmis_karsilastir([1.0, 2.0])
    assert kucuk["test"] is None and "en az 3" in kucuk["gerekce"]
    db.close()


def test_tablo1_sutunlari_ve_csv(istemci):
    db, c = _calisma()
    t = analiz.tablo1(c, "V1")
    assert t["kollar"] == ["Kol A", "Kol B"] and t["gonullu"] == 8
    etiketler = [s["etiket"] for s in t["satirlar"]]
    assert any(e.startswith("Sistolik kan basıncı (mmHg), ") for e in etiketler)
    assert "Ateş var mı?, n (%)" in etiketler and "Evet" in etiketler
    satir = next(s for s in t["satirlar"] if s["etiket"].startswith("Sistolik"))
    assert set(satir["hucreler"]) == {"Kol A", "Kol B"} and "(n=4)" in satir["hucreler"]["Kol A"]
    csv_satirlar = analiz.tablo1_csv_satirlari(t)
    assert csv_satirlar[0] == ["Değişken", "Kol A", "Kol B", "Toplam"]
    cid = c.id
    db.close()
    _giris(istemci, "istat")
    r = istemci.get(f"/calismalar/{cid}/analiz/tablo1")
    assert r.status_code == 200 and "Başlangıç özeti (Tablo 1)" in r.text and "Sistolik kan basıncı" in r.text
    r = istemci.get(f"/calismalar/{cid}/analiz/tablo1.csv?vizit=V1")
    assert r.status_code == 200 and r.text.startswith("﻿Değişken;Kol A;Kol B;Toplam")
    db = oturum_fabrikasi()()
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "disa_aktar").order_by(DenetimKaydi.id.desc())).scalars().first()
    assert kayit.yeni["bicim"] == "tablo1_csv" and kayit.yeni["vizit"] == "V1"
    db.close()
    # sema olmadiginda varsayilan vizit yok, tum vizitler gorunumu; mod secimi calisir
    r = istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.SYSBP&mod=degisim&vizit1=V1&vizit2=V2")
    assert r.status_code == 200 and "Vizitler arası değişim" in r.text and "eşleştirilmiş gönüllü" in r.text
    r = istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.SYSBP&mod=vizit")
    assert r.status_code == 200 and 'value="V1" selected' in r.text  # sema yok: gozlenen ilk vizit varsayilan
    r = istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.SYSBP&mod=vizit&vizit=tum")
    assert r.status_code == 200 and "kol testi yapılmaz" in r.text


def test_arastirmaci_yalnizca_kendi_merkezini_gorur(istemci):
    db, c = _calisma()
    cid = c.id
    m2 = Merkez(kod="T-02", ad="İkinci Hastane", sehir="İzmir", kurum_tipi="sehir")
    db.add(m2)
    db.flush()
    cm2 = CalismaMerkez(calisma_id=cid, merkez_id=m2.id, merkez_no="02", hedef_hasta=5, durum="aktif")
    db.add(cm2)
    db.flush()
    form = next(f for f in c.formlar if f.kod == "VS")
    g = Gonullu(calisma_id=cid, calisma_merkez_id=cm2.id, gonullu_no="02-001", durum=GonulluDurumu.TEDAVIDE, kol_id=c.kollar[0].id)
    db.add(g)
    db.flush()
    v = Vizit(gonullu_id=g.id, ad="V1", sira=0, planlanan=date(2024, 1, 1), gerceklesen=date(2024, 1, 1), durum="yapildi")
    db.add(v)
    db.flush()
    db.add(FormKaydi(gonullu_id=g.id, form_id=form.id, vizit_id=v.id, veriler={"SYSBP": "150", "ATES": "Evet"}, durum="tamamlandi"))
    db.add(Kullanici(kullanici_adi="ar2", ad_soyad="Araştırmacı", eposta="ar2@t.local", parola_hash=yetki.parola_hashle(PAROLA),
                     rol=Rol.ARASTIRMACI, merkez_id=m2.id))
    db.commit()
    assert analiz.veri_seti(c, m2.id)[1][0]["gonullu_no"] == "02-001" and len(analiz.veri_seti(c, m2.id)[1]) == 1
    assert analiz.gonullu_akisi(c, m2.id)["toplam_gonullu"] == 1
    db.close()
    _giris(istemci, "ar2")
    r = istemci.get(f"/calismalar/{cid}/analiz")
    assert r.status_code == 200 and "Yalnızca merkezinizin gönüllüleri" in r.text
    r = istemci.get(f"/calismalar/{cid}/analiz/veri-seti.csv")
    assert r.status_code == 200 and len(r.text.splitlines()) == 2 and "01-001" not in r.text
