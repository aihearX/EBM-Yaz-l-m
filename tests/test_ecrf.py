"""Calisma tasarimi: kollar, vizit semasi, eCRF tasarimcisi, protokolden taslak ve veri girisi baglantisi."""
import json
import os

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    Calisma,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    FormKaydi,
    Gonullu,
    Kriter,
    Kullanici,
    Merkez,
    Rol,
)
from smartclinical.models import Form as CRF
from smartclinical.models.tasarim import VizitTanimi
from smartclinical.services import ecrf, protokol, yetki
from smartclinical.web import ecrf as ecrf_web

PAROLA = "Test1234!xyz"

PROTOKOL = """
4. ÇALIŞMA POPÜLASYONU
4.1 Dahil Etme Kriterleri
1. 18 yaş ve üzeri kadın hastalar
2. Histolojik olarak doğrulanmış HER2-negatif meme kanseri
3. ECOG performans skoru 0-1
4. Hemoglobin ≥ 9 g/dL
4.2 Hariç Tutma Kriterleri
a) Uzak metastaz varlığı
b) Gebe veya emziren kadınlar
c) Son 6 ay içinde miyokard enfarktüsü
5. ÇALIŞMA KOLLARI
- Kol A: Kemoterapi + CDK4/6 inhibitörü
- Kol B: Kemoterapi
6. VİZİT TAKVİMİ
Tarama (-14 gün ± 7), Vizit 1 (Gün 0), Vizit 2 (Gün 28 ± 3), Hafta 12, Çalışma Sonu (Gün 168 ± 7)
7. DEĞERLENDİRMELER
Her vizitte vital bulgular ve eşlik eden ilaçlar kaydedilir; taramada hemogram ve biyokimya alınır.
Yaşam kalitesi ölçeği 12. haftada uygulanır.
"""

ALANLAR = [
    {"kod": "VSDAT", "etiket": "Ölçüm tarihi", "tip": "tarih", "zorunlu": True, "bolum": "Ölçüm"},
    {"kod": "SYSBP", "etiket": "Sistolik", "tip": "sayi", "zorunlu": True, "birim": "mmHg", "min": 70, "max": 220},
    {"kod": "ATES", "etiket": "Ateş var mı?", "tip": "evet_hayir", "zorunlu": True},
    {"kod": "ATESDER", "etiket": "Ateş derecesi", "tip": "sayi", "zorunlu": True, "min": 35, "max": 42,
     "kosul": {"alan": "ATES", "deger": "Evet"}},
    {"kod": "BELIRTI", "etiket": "Belirtiler", "tip": "coklu_secim", "secenekler": "Öksürük; Baş ağrısı; Bulantı"},
]


@pytest.fixture(scope="module")
def istemci():
    if not any(getattr(r, "path", "").startswith("/calismalar/{calisma_id}/tasarim") for r in app.routes):
        app.include_router(ecrf_web.router)
    sifirla()
    db = oturum_fabrikasi()()
    m = Merkez(kod="T-01", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
    db.add(m)
    db.flush()
    db.add_all([
        Kullanici(kullanici_adi="admin", ad_soyad="Admin", eposta="a@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.YONETICI),
        Kullanici(kullanici_adi="cra", ad_soyad="CRA", eposta="c@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.CRA),
    ])
    for kod in ("ECRF-001", "ECRF-002"):
        c = Calisma(kod=kod, baslik="Tasarım testi", kisa_ad="Tasarım", tur=CalismaTuru.ILAC, sponsor="S",
                    terapotik_alan="Onkoloji", hedef_hasta=10)
        db.add(c)
        db.flush()
        db.add(CalismaMerkez(calisma_id=c.id, merkez_id=m.id, merkez_no="01", hedef_hasta=5, durum="aktif"))
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


def _giris(c, kadi="admin"):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _calisma(kod="ECRF-001") -> int:
    db = oturum_fabrikasi()()
    cid = db.execute(select(Calisma.id).where(Calisma.kod == kod)).scalar_one()
    db.close()
    return cid


def _form_id(cid: int, kod: str) -> int:
    db = oturum_fabrikasi()()
    fid = db.execute(select(CRF.id).where(CRF.calisma_id == cid, CRF.kod == kod)).scalar_one()
    db.close()
    return fid


# -- servis -----------------------------------------------------------------

def test_sozlesme_fonksiyonlari_mevcut():
    for ad in ("STANDART_FORMLAR", "VIZIT_SABLONLARI", "vizit_semasi_uygula", "standart_formlari_ekle", "edit_check",
               "gonullu_vizitleri_olustur", "form_dogrula", "form_degistirilebilir"):
        assert hasattr(ecrf, ad), ad
    assert set(ecrf.STANDART_FORMLAR) >= {"DM", "IE", "VS", "LB", "EX", "CM", "QS", "ANKET"}
    assert set(ecrf.VIZIT_SABLONLARI) == {"tek_vizit", "kisa_takip", "standart", "uzun_takip"}
    assert len(ecrf.VIZIT_SABLONLARI["standart"]) == 7


def test_form_dogrula():
    assert ecrf.form_dogrula([ecrf.alan_normalize(a) for a in ALANLAR]) == []
    hatalar = ecrf.form_dogrula([{"kod": "küçük", "etiket": "", "tip": "yok"},
                                 {"kod": "A", "etiket": "a", "tip": "secim"},
                                 {"kod": "A", "etiket": "b", "tip": "metin", "kosul": {"alan": "YOK", "deger": "1"}}])
    metin = " ".join(hatalar)
    assert "büyük harf" in metin and "birden fazla" in metin and "seçenek" in metin and "formda yok" in metin


def test_edit_check_kosul_ve_yeni_tipler():
    f = CRF(kod="T", ad="T", alanlar=[ecrf.alan_normalize(a) for a in ALANLAR])
    # kosul saglanmiyor: ATESDER zorunlu sayilmaz
    s = ecrf.edit_check(f, {"VSDAT": "2024-01-01", "SYSBP": "120", "ATES": "Hayır", "ATESDER": "", "BELIRTI": []})
    assert s == []
    # kosul saglaniyor: ATESDER zorunlu
    s = ecrf.edit_check(f, {"VSDAT": "2024-01-01", "SYSBP": "120", "ATES": "Evet", "ATESDER": "", "BELIRTI": ["Öksürük"]})
    assert [a for a, _ in s] == ["ATESDER"]
    # evet_hayir ve coklu_secim degerleri dogrulanir
    s = ecrf.edit_check(f, {"VSDAT": "2024-01-01", "SYSBP": "300", "ATES": "Belki", "BELIRTI": ["Uykusuzluk"]})
    assert {a for a, _ in s} == {"SYSBP", "ATES", "BELIRTI"}


def test_protokol_taslak_kural_tabanli():
    t = protokol.taslak_cikar(PROTOKOL)
    assert t.yontem == "kural"
    assert len(t.dahil) >= 3 and "18 yaş ve üzeri kadın hastalar" in t.dahil
    assert len(t.haric) >= 2 and "Uzak metastaz varlığı" in t.haric
    assert len(t.vizitler) >= 3
    assert ("Tarama", -14, 7) in t.vizitler and ("Vizit 2", 28, 3) in t.vizitler and ("Hafta 12", 84, 3) in t.vizitler
    assert len(t.formlar) >= 2 and {"VS", "LB", "CM", "ANKET"} <= set(t.formlar)
    assert t.kollar == ["Kol A: Kemoterapi + CDK4/6 inhibitörü", "Kol B: Kemoterapi"]
    bos = protokol.taslak_cikar("Bu metinde hiçbir başlık yok.")
    assert bos.bos and bos.notlar


# -- web: kol / vizit / form ---------------------------------------------------

def test_kol_vizit_form_ekle(istemci):
    _giris(istemci)
    cid = _calisma()
    b = f"/calismalar/{cid}/tasarim"
    assert istemci.get(b).status_code == 200
    assert istemci.get(f"{b}/form/yeni").status_code == 200
    assert istemci.post(f"{b}/kol", data={"ad": "Kol A", "aciklama": "Test ürünü", "oran": "1"}, follow_redirects=False).status_code == 303
    assert istemci.post(f"{b}/vizit/sablon", data={"sablon": "kisa_takip"}, follow_redirects=False).status_code == 303
    assert istemci.post(f"{b}/vizit", data={"ad": "V3", "gun": "56", "pencere_gun": "3"}, follow_redirects=False).status_code == 303
    r = istemci.post(f"{b}/form/yeni", data={"kod": "vs", "ad": "Vital Bulgular", "durum": "yayinda",
                                            "vizitler": ["V1 (Başlangıç)", "V2", "V3"],
                                            "alanlar_json": json.dumps(ALANLAR)}, follow_redirects=False)
    assert r.status_code == 303 and "/form/" in r.headers["location"]
    db = oturum_fabrikasi()()
    c = db.get(Calisma, cid)
    assert [k.ad for k in c.kollar] == ["Kol A"]
    assert [(t.ad, t.gun) for t in c.vizit_tanimlari] == [("Tarama", -14), ("V1 (Başlangıç)", 0), ("V2", 28), ("V3", 56), ("Çalışma Sonu", 84)]
    f = c.formlar[0]
    assert f.kod == "VS" and f.durum == "yayinda" and f.vizit_listesi == ["V1 (Başlangıç)", "V2", "V3"]
    assert f.alanlar[3]["kosul"] == {"alan": "ATES", "deger": "Evet"} and f.alanlar[4]["secenekler"] == ["Öksürük", "Baş ağrısı", "Bulantı"]
    assert f.alanlar[2]["secenekler"] == ["Evet", "Hayır"]
    fid = f.id
    db.close()
    assert istemci.get(f"{b}/form/{fid}").status_code == 200
    r = istemci.get(f"{b}/form/{fid}/onizle")
    assert r.status_code == 200 and 'data-kosul-alan="ATES"' in r.text and "VS.VSORRES" not in r.text
    # gecersiz alan listesi reddedilir
    r = istemci.post(f"{b}/form/yeni", data={"kod": "LB", "ad": "Lab", "alanlar_json": json.dumps([{"kod": "x y", "etiket": "", "tip": "sayi"}])})
    assert r.status_code == 200 and "büyük harf" in r.text
    # standart form ekleme
    assert istemci.post(f"{b}/form/standart", data={"kodlar": ["DM", "QS", "YOK"]}, follow_redirects=False).status_code == 303
    db = oturum_fabrikasi()()
    assert {f.kod for f in db.get(Calisma, cid).formlar} == {"VS", "DM", "QS"}
    db.close()


def test_yetkisiz_kullanici_duzenleyemez(istemci):
    _giris(istemci, "cra")
    cid = _calisma()
    # tasarim sekmesi yalnizca calismayi duzenleyebilenlere acik (sekme_kontrol)
    assert istemci.get(f"/calismalar/{cid}/tasarim").status_code == 403
    assert istemci.get(f"/calismalar/{cid}/tasarim/form/yeni").status_code == 403
    assert istemci.post(f"/calismalar/{cid}/tasarim/kol", data={"ad": "X"}).status_code == 403


def test_randomizasyonda_vizitler_tanimdan_uretilir(istemci):
    _giris(istemci)
    cid = _calisma()
    db = oturum_fabrikasi()()
    cm_id = db.execute(select(CalismaMerkez.id).where(CalismaMerkez.calisma_id == cid)).scalar_one()
    kol_id = db.get(Calisma, cid).kollar[0].id
    db.close()
    r = istemci.post("/gonulluler/yeni", data={"calisma_id": cid, "calisma_merkez_id": cm_id, "onam_tarihi": "2024-03-01"},
                     follow_redirects=False)
    assert r.status_code == 303
    gid = int(r.headers["location"].rsplit("/", 1)[1])
    # onam -> tarama -> randomize (gecis sozlugu: services/gonullu.GECISLER)
    assert istemci.post(f"/gonulluler/{gid}/durum", data={"durum": "tarama", "tarih": "2024-03-02"},
                        follow_redirects=False).status_code == 303
    assert istemci.post(f"/gonulluler/{gid}/durum", data={"durum": "randomize", "tarih": "2024-03-10", "kol_id": kol_id},
                        follow_redirects=False).status_code == 303
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    tanimlar = {t.id: t for t in g.calisma.vizit_tanimlari}
    assert len(g.vizitler) == 5 and all(v.vizit_tanimi_id in tanimlar for v in g.vizitler)
    v3 = next(v for v in g.vizitler if v.ad == "V3")
    assert v3.planlanan.isoformat() == "2024-05-05" and v3.pencere_gun == 3
    db.close()
    r = istemci.get(f"/gonulluler/{gid}")
    assert r.status_code == 200 and "Çalışmaya alındı" in r.text and "Vizit şeması tanımlı değil" not in r.text
    # form matrisi: VS yalnizca V1/V2/V3'te, DM yalnizca Taramada
    fid = _form_id(cid, "VS")
    assert r.text.count(f"/form/{fid}?vizit_id=") == 3
    # form doldurulabilir; kosul saglanmayan zorunlu alan sorgu acmaz
    r = istemci.post(f"/gonulluler/{gid}/form/{fid}", data={"vizit_id": v3.id, "islem": "tamamla", "VSDAT": "2024-05-05",
                                                            "SYSBP": "118", "ATES": "Hayır", "BELIRTI": ["Öksürük", "Bulantı"]},
                     follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    fk = db.execute(select(FormKaydi).where(FormKaydi.form_id == fid)).scalar_one()
    assert fk.durum == "tamamlandi" and fk.veriler["BELIRTI"] == ["Öksürük", "Bulantı"] and not fk.sorgular
    db.close()
    r = istemci.get(f"/gonulluler/{gid}/form/{fid}?vizit_id={v3.id}")
    assert r.status_code == 200 and r.text.count("checked") == 3  # 2 belirti + ATES=Hayır


def test_kayitli_formda_alan_silme_reddi_ve_versiyon(istemci):
    _giris(istemci)
    cid = _calisma()
    fid = _form_id(cid, "VS")
    b = f"/calismalar/{cid}/tasarim/form/{fid}"
    db = oturum_fabrikasi()()
    f = db.get(CRF, fid)
    assert ecrf.form_degistirilebilir(f) is False
    eski_alanlar = list(f.alanlar)
    db.close()
    ortak = {"kod": "VS", "ad": "Vital Bulgular", "durum": "yayinda", "vizitler": ["V1 (Başlangıç)", "V2", "V3"]}
    # alan silme reddedilir
    r = istemci.post(b, data={**ortak, "alanlar_json": json.dumps(eski_alanlar[1:])}, follow_redirects=False)
    assert r.status_code == 200 and "silinemez" in r.text
    # tip degistirme reddedilir
    degisik = [dict(a) for a in eski_alanlar]
    degisik[1]["tip"] = "metin"
    r = istemci.post(b, data={**ortak, "alanlar_json": json.dumps(degisik)}, follow_redirects=False)
    assert r.status_code == 200 and "tipi değiştirilemez" in r.text
    db = oturum_fabrikasi()()
    assert db.get(CRF, fid).versiyon == "1.0"
    db.close()
    # etiket degisikligi + yeni alan serbest, versiyon artar, denetim izinde eski/yeni alan listesi
    yeni = [dict(a) for a in eski_alanlar]
    yeni[1]["etiket"] = "Sistolik kan basıncı"
    yeni.append({"kod": "PULSE", "etiket": "Nabız", "tip": "sayi", "min": 30, "max": 200})
    r = istemci.post(b, data={**ortak, "alanlar_json": json.dumps(yeni)}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    f = db.get(CRF, fid)
    assert f.versiyon == "1.1" and f.alanlar[1]["etiket"] == "Sistolik kan basıncı" and f.alanlar[-1]["kod"] == "PULSE"
    k = db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "form", DenetimKaydi.varlik_id == fid,
                                              DenetimKaydi.islem == "guncelle").order_by(DenetimKaydi.id.desc())).scalars().first()
    assert k.eski["versiyon"] == "1.0" and k.yeni["versiyon"] == "1.1"
    assert [a["kod"] for a in k.eski["alanlar"]] == [a["kod"] for a in eski_alanlar]
    assert k.yeni["alanlar"][-1]["kod"] == "PULSE"
    # kaydi olan form silinemez, vizit semasi degistirilemez
    assert istemci.post(f"{b}/sil", follow_redirects=False).status_code == 303
    assert db.get(CRF, fid) is not None
    db.close()
    r = istemci.post(f"/calismalar/{cid}/tasarim/vizit/sablon", data={"sablon": "tek_vizit"}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    assert len(db.get(Calisma, cid).vizit_tanimlari) == 5
    db.close()


# -- protokolden taslak --------------------------------------------------------

def test_protokol_taslak_onaysiz_yazmaz_ve_uygulanir(istemci):
    _giris(istemci)
    cid = _calisma("ECRF-002")
    b = f"/calismalar/{cid}/tasarim/protokol-taslak"
    assert istemci.get(b).status_code == 200
    r = istemci.post(b, data={"metin": PROTOKOL})
    assert r.status_code == 200 and "Hemoglobin ≥ 9 g/dL" in r.text and 'value="Vizit 2|28|3"' in r.text
    db = oturum_fabrikasi()()
    c = db.get(Calisma, cid)
    assert not c.kriterler and not c.kollar and not c.vizit_tanimlari and not c.formlar  # yalnizca oneri
    cm_id = c.merkezler[0].id
    db.close()
    # semasiz calismada gonullu sayfasi uyari ve tasarim baglantisi gosterir
    r = istemci.post("/gonulluler/yeni", data={"calisma_id": cid, "calisma_merkez_id": cm_id}, follow_redirects=False)
    r = istemci.get(r.headers["location"])
    assert r.status_code == 200 and "Vizit şeması tanımlı değil" in r.text and f"/calismalar/{cid}/tasarim" in r.text
    r = istemci.post(f"{b}/uygula", data={
        "dahil": ["18 yaş ve üzeri kadın hastalar", "Hemoglobin ≥ 9 g/dL"],
        "haric": ["Gebe veya emziren kadınlar"],
        "kollar": ["Kol A: Kemoterapi + CDK4/6 inhibitörü", "Kol B: Kemoterapi"],
        "vizitler": ["Tarama|-14|7", "Vizit 1|0|0", "Vizit 2|28|3"],
        "formlar": ["VS", "LB"]}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    c = db.get(Calisma, cid)
    kr = db.execute(select(Kriter).where(Kriter.calisma_id == cid).order_by(Kriter.id)).scalars().all()
    assert [(x.tip, x.metin) for x in kr] == [("dahil", "18 yaş ve üzeri kadın hastalar"), ("dahil", "Hemoglobin ≥ 9 g/dL"),
                                             ("haric", "Gebe veya emziren kadınlar")]
    assert kr[1].yapisal["kategori"] == "lab" and not kr[1].onaylandi
    assert [k.ad for k in c.kollar] == ["Kol A: Kemoterapi + CDK4/6 inhibitörü", "Kol B: Kemoterapi"]
    assert [(t.ad, t.gun, t.pencere_gun) for t in c.vizit_tanimlari] == [("Tarama", -14, 7), ("Vizit 1", 0, 0), ("Vizit 2", 28, 3)]
    assert sorted(f.kod for f in c.formlar) == ["LB", "VS"] and all(f.durum == "yayinda" for f in c.formlar)
    assert db.execute(select(VizitTanimi).where(VizitTanimi.calisma_id == cid)).scalars().all()
    db.close()
    # ayni taslak ikinci kez uygulanirsa cift kayit olusmaz
    istemci.post(f"{b}/uygula", data={"dahil": ["Hemoglobin ≥ 9 g/dL"], "formlar": ["VS"], "vizitler": ["Vizit 2|28|3"]})
    db = oturum_fabrikasi()()
    c = db.get(Calisma, cid)
    assert len(c.kriterler) == 3 and len(c.formlar) == 2 and len(c.vizit_tanimlari) == 3
    db.close()
