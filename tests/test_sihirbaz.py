"""Kullanim modu, ilk kurulum ve 4 adimli calisma sihirbazi."""
import os
import re

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import Arastirmaci, Basvuru, Calisma, CalismaMerkez, Kol, Kullanici, Merkez, Rol
from smartclinical.models import Form as CRF
from smartclinical.models.kurulum import KurulumAyari
from smartclinical.models.tasarim import VizitTanimi
from smartclinical.services import denetim, kurulum
from smartclinical.web import sihirbaz as sihirbaz_web

PAROLA = "Test1234!xyz"


@pytest.fixture(scope="module")
def istemci():
    if not any(getattr(r, "path", "").startswith("/sihirbaz") for r in app.routes):
        app.include_router(sihirbaz_web.router)
    sifirla()
    with TestClient(app) as c:
        c.cookies.clear()
        yield c


def _db():
    return oturum_fabrikasi()()


def _giris(c, kadi="admin"):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _mod_ayarla(mod, merkez_id=1):
    db = _db()
    kurulum.ayar_yaz(db, mod, "EBM Klinik Araştırma" if mod == "cro" else "Mustafa Kemal Üniversitesi",
                     merkez_id if mod != "cro" else None, "EBM CRO" if mod == "cro" else None)
    db.commit()
    db.close()


def _alanlar(html: str) -> list[str]:
    """Formdaki gorunur alan adlari: hidden girdiler ve hidden kapsayici icindekiler sayilmaz."""
    form = re.search(r'<form method="post" action="/sihirbaz/1".*?</form>', html, re.S).group(0)
    form = re.sub(r'<div class="alan" id="faz-alani" hidden>.*?</select></div>', "", form, flags=re.S)
    adlar = re.findall(r'<(?:input|select|textarea)[^>]*?name="([a-z_]+)"', form)
    gizli = re.findall(r'<input type="hidden" name="([a-z_]+)"', form)
    return [a for a in adlar if a not in gizli]


# --- ilk kurulum ---------------------------------------------------------------

def test_bos_veritabaninda_kuruluma_yonlendirir(istemci):
    r = istemci.get("/giris", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/kurulum"
    r = istemci.get("/", follow_redirects=True)
    assert r.status_code == 200 and "ilk kurulum" in r.text and 'name="mod"' in r.text


def test_kurulum_tekil_mod_yoneticiyi_merkeze_baglar(istemci):
    r = istemci.post("/kurulum", data={
        "mod": "tekil", "kurum_adi": "Mustafa Kemal Üniversitesi", "kullanici_adi": "Admin", "ad_soyad": "Ayşe Demir",
        "eposta": "a@t.local", "parola": PAROLA, "merkez_adi": "MKÜ Tıp Fakültesi Hastanesi", "merkez_sehir": "Hatay"},
        follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    db = _db()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "admin")).scalar_one()
    assert k.rol == Rol.YONETICI and k.merkez_id is not None
    ayar = db.get(KurulumAyari, 1)
    assert ayar.mod == "tekil" and ayar.varsayilan_merkez_id == k.merkez_id and ayar.kurum_adi.startswith("Mustafa")
    assert db.get(Merkez, k.merkez_id).sehir == "Hatay"
    assert denetim.zinciri_dogrula(db) == (True, None)
    db.close()
    # kullanici varken kurulum ekrani kapali, giris acik
    istemci.cookies.clear()
    assert istemci.get("/kurulum").status_code == 404
    assert istemci.get("/giris", follow_redirects=False).status_code == 200


def test_servis_varsayilanlari():
    assert kurulum.mod_varsayilanlari("tekil", "akademik")["form_kodlari"] == ["DM", "IE", "VS", "LB"]
    assert kurulum.mod_varsayilanlari("universite", "ilac")["basvuru_kurumlari"] == ["etik_kurul", "kurum_izni", "titck"]
    assert kurulum.mod_varsayilanlari("universite", "gozlemsel")["basvuru_kurumlari"] == ["etik_kurul", "kurum_izni"]
    cro = kurulum.mod_varsayilanlari("cro")
    assert cro["vizit_sablonu"] == "standart" and cro["hedef_merkez"] is None and "kvkk" in cro["basvuru_kurumlari"]
    assert Rol.DENETCI not in kurulum.mod_rolleri("tekil") and Rol.DENETCI in kurulum.mod_rolleri("universite")
    assert len(kurulum.mod_rolleri("cro")) == len(list(Rol))


# --- sihirbaz ----------------------------------------------------------------

def test_tekil_adim1_sade_ve_kod_onerisi(istemci):
    _giris(istemci)
    r = istemci.get("/sihirbaz", follow_redirects=True)
    assert r.status_code == 200 and "1. adım" in r.text
    alanlar = _alanlar(r.text)
    assert "sponsor" not in alanlar and "faz" not in alanlar
    assert len(alanlar) <= 7, alanlar
    assert 'value="MKU-' in r.text and re.search(r'value="MKU-\d{4}-001"', r.text)


def test_sihirbaz_dort_adim_tek_islemde_olusturur(istemci):
    _giris(istemci)
    kod = re.search(r'name="kod" value="([^"]+)"', istemci.get("/sihirbaz/1").text).group(1)
    r = istemci.post("/sihirbaz/1", data={"kod": kod, "kisa_ad": "Diyabet kayıt", "baslik": "Tip 2 diyabette izlem",
                                         "tur": "akademik", "terapotik_alan": "Endokrinoloji", "hedef_hasta": "40",
                                         "baslangic": "2026-01-15"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/sihirbaz/2"
    r = istemci.get("/sihirbaz/2")
    assert 'value="kisa_takip" checked' in r.text and "Tek kol" in r.text
    r = istemci.post("/sihirbaz/2", data={"kol_ad": ["Tek kol"], "kol_oran": ["1"], "vizit_sablonu": "kisa_takip",
                                         "dahil": "18 yaş ve üzeri\nHbA1c ≥ 7", "haric": ""}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/sihirbaz/3"
    r = istemci.get("/sihirbaz/3")
    assert "Ayşe Demir" in r.text and "koord_kullanici_adi" in r.text
    r = istemci.post("/sihirbaz/3", data={"koord_kullanici_adi": "koord1", "koord_ad_soyad": "Koordinatör Bir",
                                         "koord_eposta": "k1@t.local", "koord_parola": PAROLA}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/sihirbaz/4"
    r = istemci.get("/sihirbaz/4")
    assert 'value="DM" checked' in r.text and 'value="LB" checked' in r.text and 'value="EX" checked' not in r.text
    assert 'value="etik_kurul" checked' in r.text and 'value="titck" checked' not in r.text
    # geri: taslak korunur
    assert kod in istemci.get("/sihirbaz/1").text
    db = _db()
    assert db.execute(select(Calisma.id).where(Calisma.kod == kod)).first() is None  # henuz yazilmadi
    db.close()
    r = istemci.post("/sihirbaz/4", data={"form_kod": ["DM", "IE", "VS", "LB"], "basvuru": ["etik_kurul"]}, follow_redirects=False)
    assert r.status_code == 303 and re.match(r"/calismalar/\d+$", r.headers["location"])
    r2 = istemci.get(r.headers["location"])
    assert "Çalışma hazır. Eksikler aşama kontrol listesinde." in r2.text

    db = _db()
    c = db.execute(select(Calisma).where(Calisma.kod == kod)).scalar_one()
    assert c.sponsor == "Mustafa Kemal Üniversitesi" and c.hedef_hasta == 40 and c.hedef_merkez == 1
    assert len(db.execute(select(Kol).where(Kol.calisma_id == c.id)).scalars().all()) == 1
    assert len(db.execute(select(VizitTanimi).where(VizitTanimi.calisma_id == c.id)).scalars().all()) == 4
    assert sorted(f.kod for f in db.execute(select(CRF).where(CRF.calisma_id == c.id)).scalars()) == ["DM", "IE", "LB", "VS"]
    basvurular = db.execute(select(Basvuru).where(Basvuru.calisma_id == c.id)).scalars().all()
    assert len(basvurular) == 1 and basvurular[0].kurum == "etik_kurul" and basvurular[0].karar == "beklemede"
    assert len(c.kriterler) == 2 and not any(x.onaylandi for x in c.kriterler) and all(x.yapisal for x in c.kriterler)
    cm = db.execute(select(CalismaMerkez).where(CalismaMerkez.calisma_id == c.id)).scalar_one()
    assert cm.merkez_no == "01" and cm.bas_arastirmaci.ad_soyad == "Ayşe Demir"
    koord = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "koord1")).scalar_one()
    assert koord.rol == Rol.KOORDINATOR and koord.merkez_id == cm.merkez_id
    assert denetim.zinciri_dogrula(db) == (True, None)
    db.close()
    assert "sihirbaz" not in istemci.cookies.get("sc_oturum", "")  # taslak temizlendi (cerez imzali; kaba kontrol)
    assert istemci.get("/sihirbaz/4", follow_redirects=False).headers["location"] == "/sihirbaz/1"


def test_protokol_kodu_benzersiz(istemci):
    _giris(istemci)
    db = _db()
    kod = kurulum.protokol_kodu_oner(db, "Mustafa Kemal Üniversitesi")
    assert kod.endswith("-002") and not kurulum.kod_kullanimda(db, kod)
    mevcut = db.execute(select(Calisma.kod)).scalars().first()
    db.close()
    r = istemci.post("/sihirbaz/1", data={"kod": mevcut, "kisa_ad": "x", "baslik": "y", "tur": "akademik",
                                         "terapotik_alan": "z"}, follow_redirects=False)
    assert r.status_code == 200 and "zaten kayıtlı" in r.text


def test_cro_modu_faz_ve_sponsor(istemci):
    _mod_ayarla("cro")
    _giris(istemci)
    istemci.get("/sihirbaz/iptal")
    r = istemci.get("/sihirbaz/1")
    alanlar = _alanlar(r.text)
    assert "faz" in alanlar and "sponsor" in alanlar and 'value="ilac" selected' in r.text
    assert 'value="EKA-' in r.text  # kisaltma kurum adindan
    r = istemci.get("/yonetim/kullanicilar")
    assert 'value="denetci"' in r.text and 'value="farmakovijilans"' in r.text


def test_universite_modu_bolum_gruplama(istemci):
    _mod_ayarla("universite")
    db = _db()
    m = db.get(Merkez, 1)
    db.add_all([Arastirmaci(merkez_id=m.id, ad_soyad="Dr. Kardiyo", bolum="Kardiyoloji"),
                Arastirmaci(merkez_id=m.id, ad_soyad="Dr. Nefro", bolum="Nefroloji")])
    db.commit()
    db.close()
    _giris(istemci)
    r = istemci.get("/merkezler")
    assert "Bölümler ve araştırmacılar" in r.text and "Kardiyoloji" in r.text and "Nefroloji" in r.text
    r = istemci.get("/merkezler?bolum=Kardiyoloji")
    assert "Dr. Kardiyo" in r.text and "Dr. Nefro" not in r.text
    r = istemci.get("/yonetim/kullanicilar")
    assert 'value="denetci"' in r.text and 'value="farmakovijilans"' not in r.text
    # sihirbaz 3. adim: bolum ve bas arastirmaci secimi
    istemci.get("/sihirbaz/iptal")
    r = istemci.post("/sihirbaz/1", data={"kod": "MKU-2030-001", "kisa_ad": "x", "baslik": "y", "tur": "ilac", "faz": "II",
                                         "sponsor": "MKÜ", "terapotik_alan": "z"}, follow_redirects=False)
    assert r.status_code == 303
    assert 'value="standart"' in istemci.get("/sihirbaz/2").text
    istemci.post("/sihirbaz/2", data={"kol_ad": ["Kol A", "Kol B"], "kol_oran": ["1", "1"], "vizit_sablonu": "uzun_takip"})
    r = istemci.get("/sihirbaz/3")
    assert 'name="bolum"' in r.text and "Dr. Kardiyo" in r.text
    r = istemci.post("/sihirbaz/3", data={"merkez_id": "1", "bolum": "Nefroloji", "bas_arastirmaci_id": "",
                                         "bas_arastirmaci_ad": "Prof. Dr. Yeni"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/sihirbaz/4"
    r = istemci.get("/sihirbaz/4")
    assert 'value="kurum_izni" checked' in r.text and 'value="titck" checked' in r.text and 'value="ANKET"' not in r.text
    assert "Prof. Dr. Yeni" in r.text and "Nefroloji" in r.text
    r = istemci.post("/sihirbaz/4", data={"form_kod": ["DM", "VS"], "anket": "1", "basvuru": ["etik_kurul", "kurum_izni", "titck"]},
                     follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    c = db.execute(select(Calisma).where(Calisma.kod == "MKU-2030-001")).scalar_one()
    assert len(c.kollar) == 2 and len(c.vizit_tanimlari) == 6 and sorted(f.kod for f in c.formlar) == ["ANKET", "DM", "VS"]
    assert sorted(b.kurum for b in c.basvurular) == ["etik_kurul", "kurum_izni", "titck"]
    a = db.execute(select(Arastirmaci).where(Arastirmaci.ad_soyad == "Prof. Dr. Yeni")).scalar_one()
    assert a.bolum == "Nefroloji" and c.merkezler[0].bas_arastirmaci_id == a.id
    assert denetim.zinciri_dogrula(db) == (True, None)
    db.close()


def test_tekil_modda_tek_merkez_karti_ve_ayarlar(istemci):
    _mod_ayarla("tekil")
    _giris(istemci)
    r = istemci.get("/merkezler")
    assert "Merkezim" in r.text and "Merkez bilgilerini düzenle" in r.text and "Merkez kayıt defteri" not in r.text
    r = istemci.get("/yonetim/sistem")
    assert "Kullanım modu" in r.text and "Sistem bilgileri" in r.text
    r = istemci.post("/yonetim/ayarlar", data={"mod": "cro", "kurum_adi": "EBM CRO", "varsayilan_sponsor": "EBM",
                                              "varsayilan_merkez_id": ""}, follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    assert db.get(KurulumAyari, 1).mod == "cro"
    db.close()
    assert "Merkez kayıt defteri" in istemci.get("/merkezler").text
    _mod_ayarla("tekil")
