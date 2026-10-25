"""Web katmani duman testleri: giris, yetki, temel akislar ve denetim izi."""
import os

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import Calisma, DenetimKaydi, Kullanici, Merkez, Rol
from smartclinical.services import denetim, yetki

PAROLA = "Test1234!xyz"


@pytest.fixture(scope="module")
def istemci():
    sifirla()
    db = oturum_fabrikasi()()
    m = Merkez(kod="T-01", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
    db.add(m)
    db.flush()
    db.add_all([
        Kullanici(kullanici_adi="admin", ad_soyad="Admin", eposta="a@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.YONETICI),
        Kullanici(kullanici_adi="cra", ad_soyad="CRA", eposta="c@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.CRA),
        Kullanici(kullanici_adi="denetci", ad_soyad="Denetci", eposta="d@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.DENETCI),
    ])
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


def _giris(c, kadi):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"


def test_oturumsuz_yonlendirme(istemci):
    istemci.cookies.clear()
    r = istemci.get("/calismalar", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/giris")


def test_hatali_giris_ve_kilit(istemci):
    istemci.cookies.clear()
    for _ in range(5):
        r = istemci.post("/giris", data={"kullanici_adi": "cra", "parola": "yanlis", "sonraki": "/"})
        assert "hatalı" in r.text
    r = istemci.post("/giris", data={"kullanici_adi": "cra", "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 200  # kilitli: dogru parolayla da giremez
    db = oturum_fabrikasi()()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "cra")).scalar_one()
    assert k.hatali_giris >= 5
    k.hatali_giris = 0
    db.commit()
    db.close()


def test_calisma_olustur_ve_denetim(istemci):
    _giris(istemci, "admin")
    r = istemci.post("/calismalar/yeni", data={
        "kod": "tst-001", "baslik": "Test calismasi", "kisa_ad": "Test", "tur": "ilac", "faz": "II", "sponsor": "S",
        "terapotik_alan": "Onkoloji", "hedef_hasta": "10", "hedef_merkez": "1"}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "TST-001")).scalar_one()
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "calisma", DenetimKaydi.varlik_id == c.id)).scalars().all()
    assert kayit and kayit[0].kullanici_adi == "admin" and kayit[0].hash
    assert denetim.zinciri_dogrula(db) == (True, None)
    db.close()
    for yol in ("", "/protokol", "/merkezler", "/basvurular", "/gonulluler", "/veri", "/guvenlik", "/izlem",
                "/belgeler", "/eslestirme", "/merkez-zekasi", "/rbm", "/denetim"):
        assert istemci.get(f"/calismalar/{c.id}{yol}").status_code == 200, yol


def test_kriter_ekle_yapilandirilir(istemci):
    _giris(istemci, "admin")
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "TST-001")).scalar_one()
    db.close()
    r = istemci.post(f"/calismalar/{c.id}/protokol/kriter", data={"tip": "dahil", "metin": "18 yaş ve üzeri\nHemoglobin ≥ 9 g/dL"}, follow_redirects=False)
    assert r.status_code == 303
    r = istemci.get(f"/api/v1/calismalar/{c.id}/kriterler")
    veri = r.json()
    assert len(veri) == 2 and veri[1]["yapisal"]["kategori"] == "lab" and veri[1]["guven"] > 0.7


def test_rol_kisiti(istemci):
    _giris(istemci, "denetci")
    assert istemci.get("/yonetim/denetim").status_code == 200
    assert istemci.get("/calismalar/yeni").status_code == 403
    assert istemci.get("/yonetim/kullanicilar").status_code == 403


def test_parola_politikasi(istemci):
    assert yetki.parola_politikasi("kisa") is not None
    assert yetki.parola_politikasi("sadeceharfler") is not None
    assert yetki.parola_politikasi("Uzun12345x") is None


def test_api_saglik_ve_kimliksizlestir(istemci):
    assert istemci.get("/api/v1/saglik").json()["durum"] == "ok"
    _giris(istemci, "admin")
    r = istemci.post("/api/v1/yz/kimliksizlestir", json={"metin": "Hasta Ayşe Yılmaz, TC 10000000146, tel 0532 111 22 33", "mod": "maske"})
    assert r.status_code == 200 and "[TCKN]" in r.json()["metin"] and "[TELEFON]" in r.json()["metin"]


def test_guvenlik_basliklari(istemci):
    r = istemci.get("/giris")
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["Cache-Control"] == "no-store"


def test_disa_aktar(istemci):
    _giris(istemci, "admin")
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "TST-001")).scalar_one()
    db.close()
    r = istemci.get(f"/calismalar/{c.id}/veri/disa-aktar?bicim=odm")
    assert r.status_code == 200 and b"<ODM" in r.content and b'StudyOID="TST-001"' in r.content
    r = istemci.get(f"/calismalar/{c.id}/veri/disa-aktar?bicim=csv")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert istemci.get(f"/calismalar/{c.id}/merkez-zekasi/rapor").status_code == 200
    r = istemci.post("/api/v1/yz/icd-kodla", json={"metin": "KOAH ve hipertansiyon"})
    assert r.status_code == 200 and any(b["icd10"] == ["J44"] for b in r.json()["bulgular"])


def test_api_anahtari_ve_sponsor(istemci):
    _giris(istemci, "admin")
    r = istemci.post("/yonetim/api-anahtarlari", data={"ad": "test", "kullanici_id": "1", "gecerlilik_gun": "30"}, follow_redirects=True)
    assert r.status_code == 200 and "sc_" in r.text
    import re
    ham = re.search(r"<code>(sc_[0-9a-f]+)</code>", r.text).group(1)
    istemci.cookies.clear()
    assert istemci.get("/api/v1/calismalar", headers={"X-SC-Anahtar": ham}).status_code == 200
    assert istemci.get("/api/v1/calismalar", headers={"X-SC-Anahtar": "sc_yanlis"}).status_code == 401
    _giris(istemci, "admin")
    assert istemci.get("/merkezler/endeks").status_code == 200


def test_csv_hasta_yukleme(istemci):
    _giris(istemci, "admin")
    csv = ("kayit_no;dogum_yili;cinsiyet;icd10;metin\n"
           "HBYS-1;1960;K;C50.9;\"60 yaşında kadın hasta Ayşe Yılmaz, HER2 negatif.\"\n"
           "HBYS-2;1970;E;E11.9;\"Telefon 0532 111 22 33 olan hasta\"\n")
    r = istemci.post("/merkezler/1/hasta-yukle", files={"dosya": ("h.csv", csv.encode("utf-8"), "text/csv")})
    assert r.status_code == 200 and "2 yeni" in r.text
    from smartclinical.models import Hasta
    db = oturum_fabrikasi()()
    h = db.execute(select(Hasta).where(Hasta.merkez_id == 1)).scalars().all()
    assert len(h) == 2 and all(x.kayit_no.startswith("P-") for x in h)
    assert "Ayşe" not in h[0].metinler[0]["metin"] and "[AD]" in h[0].metinler[0]["metin"]
    db.close()
