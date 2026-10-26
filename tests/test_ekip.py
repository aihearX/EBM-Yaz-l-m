"""Calisma bazli ekip atamasi: kisit yokken serbest erisim, ilk atamayla daralma, rol yollari, denetim izi,
sihirbazla kuran kullanicinin otomatik uyeligi."""
import os
import re

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import Calisma, CalismaMerkez, CalismaTuru, DenetimKaydi, Kullanici, Merkez, Rol
from smartclinical.models.ekip import CalismaUyesi
from smartclinical.services import yetki
from smartclinical.web import ekip

PAROLA = "Test1234!xyz"


@pytest.fixture(scope="module")
def istemci():
    sifirla()
    db = oturum_fabrikasi()()
    m1 = Merkez(kod="T-01", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
    m2 = Merkez(kod="T-02", ad="Diger Hastane", sehir="Izmir", kurum_tipi="sehir")
    db.add_all([m1, m2])
    db.flush()

    def kul(adi, rol, **ek):
        return Kullanici(kullanici_adi=adi, ad_soyad=adi.title(), eposta=f"{adi}@t.local",
                         parola_hash=yetki.parola_hashle(PAROLA), rol=rol, **ek)

    db.add_all([
        kul("admin", Rol.YONETICI), kul("denetci", Rol.DENETCI),
        kul("cra1", Rol.CRA), kul("cra2", Rol.CRA), kul("py", Rol.PROJE_YONETICISI),
        kul("arastirmaci", Rol.ARASTIRMACI, merkez_id=m1.id),
        kul("sponsor", Rol.SPONSOR, kurum="S1"),
    ])
    for kod, sponsor, merkez in (("S1-001", "S1", m1), ("DG-001", "Diger", m2)):
        c = Calisma(kod=kod, baslik=kod, kisa_ad=kod, tur=CalismaTuru.ILAC, sponsor=sponsor, terapotik_alan="Onkoloji")
        db.add(c)
        db.flush()
        db.add(CalismaMerkez(calisma_id=c.id, merkez_id=merkez.id, merkez_no="01"))
    db.commit()
    db.close()
    if not any(getattr(r, "path", "").startswith("/calismalar/{calisma_id}/ekip") for r in app.routes):
        app.include_router(ekip.router)  # entegrasyon web/__init__.py'de yapilir; testte elle
    with TestClient(app) as c:
        yield c


def _giris(c, kadi):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _id(kod):
    db = oturum_fabrikasi()()
    cid = db.scalar(select(Calisma.id).where(Calisma.kod == kod))
    db.close()
    return cid


def _kid(kadi):
    db = oturum_fabrikasi()()
    kid = db.scalar(select(Kullanici.id).where(Kullanici.kullanici_adi == kadi))
    db.close()
    return kid


def _uye_id(kod, kadi):
    db = oturum_fabrikasi()()
    uid = db.scalar(select(CalismaUyesi.id).where(CalismaUyesi.calisma_id == _id(kod), CalismaUyesi.kullanici_id == _kid(kadi)))
    db.close()
    return uid


def test_izin_haritasi():
    assert yetki.IZINLER["ekip.yonet"] == {Rol.YONETICI, Rol.PROJE_YONETICISI}
    assert Rol.ISTATISTIKCI in yetki.IZINLER["analiz.goruntule"] and Rol.CRA not in yetki.IZINLER["analiz.goruntule"]


def test_atama_yokken_herkes_gorur(istemci):
    s1, dg = _id("S1-001"), _id("DG-001")
    _giris(istemci, "cra1")
    assert istemci.get(f"/calismalar/{s1}").status_code == 200
    assert istemci.get(f"/calismalar/{dg}").status_code == 200
    assert {x["kod"] for x in istemci.get("/api/v1/calismalar").json()} == {"S1-001", "DG-001"}
    assert istemci.get(f"/calismalar/{s1}/ekip").status_code == 403  # ekip sekmesi yalnizca yonetici ve PY
    _giris(istemci, "admin")
    r = istemci.get(f"/calismalar/{s1}/ekip")
    assert r.status_code == 200 and "Henüz hiçbir çalışmada atama yok" in r.text


def test_ilk_atama_kisiti_baslatir(istemci):
    s1, dg = _id("S1-001"), _id("DG-001")
    _giris(istemci, "admin")
    r = istemci.post(f"/calismalar/{s1}/ekip/ekle", data={"kullanici_id": _kid("cra1")}, follow_redirects=False)
    assert r.status_code == 303
    r = istemci.get(f"/calismalar/{s1}/ekip")
    assert "Atama kısıtı etkin" in r.text and "Cra1" in r.text and "Çıkar" in r.text
    # ayni kullanici ikinci kez eklenmez
    istemci.post(f"/calismalar/{s1}/ekip/ekle", data={"kullanici_id": _kid("cra1")}, follow_redirects=False)
    db = oturum_fabrikasi()()
    assert db.scalar(select(CalismaUyesi.id).where(CalismaUyesi.kullanici_id == _kid("cra1"))) is not None
    assert len(db.execute(select(CalismaUyesi)).scalars().all()) == 1
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "calisma_uyesi", DenetimKaydi.islem == "olustur")).scalars().all()
    assert len(kayit) == 1 and kayit[0].yeni["kullanici"] == "cra1" and kayit[0].yeni["calisma"] == "S1-001"
    db.close()

    _giris(istemci, "cra1")  # atanmis: yalnizca S1-001
    assert istemci.get(f"/calismalar/{s1}").status_code == 200
    assert istemci.get(f"/calismalar/{s1}/rbm").status_code == 200
    assert istemci.get(f"/calismalar/{dg}").status_code == 403
    assert istemci.get(f"/calismalar/{dg}/rbm").status_code == 403
    assert istemci.get(f"/calismalar/{dg}/ekip").status_code == 403
    assert [x["kod"] for x in istemci.get("/api/v1/calismalar").json()] == ["S1-001"]
    assert istemci.get(f"/api/v1/calismalar/{s1}/kriterler").status_code == 200
    assert istemci.get(f"/api/v1/calismalar/{dg}/kriterler").status_code == 403

    _giris(istemci, "cra2")  # atanmamis: hicbiri
    assert istemci.get(f"/calismalar/{s1}").status_code == 403
    assert istemci.get(f"/calismalar/{dg}").status_code == 403
    assert istemci.get("/api/v1/calismalar").json() == []
    assert istemci.get(f"/api/v1/calismalar/{s1}/uyarilar").status_code == 403


def test_diger_roller_kendi_yolundan_erisir(istemci):
    s1, dg = _id("S1-001"), _id("DG-001")
    _giris(istemci, "arastirmaci")  # merkez uzerinden
    assert istemci.get(f"/calismalar/{s1}").status_code == 200
    assert istemci.get(f"/calismalar/{dg}").status_code == 403
    assert [x["kod"] for x in istemci.get("/api/v1/calismalar").json()] == ["S1-001"]
    _giris(istemci, "sponsor")  # kurum uzerinden
    assert istemci.get(f"/calismalar/{s1}").status_code == 200
    assert istemci.get(f"/calismalar/{dg}").status_code == 403
    for kadi in ("admin", "denetci"):
        _giris(istemci, kadi)
        assert istemci.get(f"/calismalar/{s1}").status_code == 200
        assert istemci.get(f"/calismalar/{dg}").status_code == 200
        assert len(istemci.get("/api/v1/calismalar").json()) == 2


def test_ekip_sayfasi_listeleri(istemci):
    s1 = _id("S1-001")
    _giris(istemci, "admin")
    r = istemci.get(f"/calismalar/{s1}/ekip")
    assert "merkez üzerinden erişir" in r.text and "Arastirmaci" in r.text
    assert "Cra2" in r.text and "Py" in r.text  # eklenebilirler
    r = istemci.get(f"/calismalar/{s1}/ekip?q=cra2")
    assert "Cra2" in r.text and ">Py<" not in r.text
    # arastirmaci ekibe eklenemez
    r = istemci.post(f"/calismalar/{s1}/ekip/ekle", data={"kullanici_id": _kid("arastirmaci")}, follow_redirects=False)
    assert r.status_code == 303 and _uye_id("S1-001", "arastirmaci") is None


def test_kendini_cikaramaz_ve_cikarma_denetimi(istemci):
    s1 = _id("S1-001")
    _giris(istemci, "admin")
    istemci.post(f"/calismalar/{s1}/ekip/ekle", data={"kullanici_id": _kid("py")}, follow_redirects=False)
    _giris(istemci, "py")
    kendi = _uye_id("S1-001", "py")
    r = istemci.post(f"/calismalar/{s1}/ekip/{kendi}/cikar", follow_redirects=False)
    assert r.status_code == 303 and _uye_id("S1-001", "py") == kendi
    r = istemci.get(f"/calismalar/{s1}/ekip")
    assert "Kendinizi ekipten çıkaramazsınız" in r.text
    # baskasini cikarabilir; denetim izine yazilir
    cra_uye = _uye_id("S1-001", "cra1")
    r = istemci.post(f"/calismalar/{s1}/ekip/{cra_uye}/cikar", follow_redirects=False)
    assert r.status_code == 303 and _uye_id("S1-001", "cra1") is None
    db = oturum_fabrikasi()()
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "calisma_uyesi", DenetimKaydi.islem == "sil")).scalar_one()
    assert kayit.eski["kullanici"] == "cra1" and kayit.kullanici_adi == "py"
    db.close()
    _giris(istemci, "cra1")
    assert istemci.get(f"/calismalar/{s1}").status_code == 403
    # ekip yonetme izni olmayan uye cikaramaz
    _giris(istemci, "cra2")
    assert istemci.post(f"/calismalar/{s1}/ekip/{kendi}/cikar", follow_redirects=False).status_code == 403


def test_calisma_filtresi_ve_erisim_fonksiyonlari():
    db = oturum_fabrikasi()()
    s1 = db.get(Calisma, _id("S1-001"))
    dg = db.get(Calisma, _id("DG-001"))
    py = db.get(Kullanici, _kid("py"))
    assert yetki.kisit_aktif(db)
    assert yetki.calisma_erisimi(db, py, s1) and not yetki.calisma_erisimi(db, py, dg)
    kodlar = [c.kod for c in db.execute(yetki.calisma_filtresi(db, py, select(Calisma))).scalars().unique()]
    assert kodlar == ["S1-001"]
    db.close()


def test_sihirbazla_kuran_py_otomatik_uye(istemci):
    """Kisit etkinken PY sihirbazla calisma kurar: CalismaUyesi kaydi olusur, yonlendirilen sayfa 200 doner."""
    _giris(istemci, "py")
    assert yetki.kisit_aktif(oturum_fabrikasi()())
    r = istemci.post("/sihirbaz/1", data={"kod": "PY-100", "kisa_ad": "Otomatik", "baslik": "Otomatik uyelik", "tur": "akademik",
                                         "terapotik_alan": "Kardiyoloji", "hedef_hasta": "5", "sponsor": "S1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/sihirbaz/2"
    istemci.post("/sihirbaz/2", data={"kol_ad": ["Tek kol"], "kol_oran": ["1"], "vizit_sablonu": "kisa_takip"})
    r = istemci.post("/sihirbaz/3", data={"merkez_id": "1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/sihirbaz/4"
    r = istemci.post("/sihirbaz/4", data={"form_kod": ["DM"], "basvuru": ["etik_kurul"]}, follow_redirects=False)
    assert r.status_code == 303 and re.match(r"/calismalar/\d+$", r.headers["location"])
    assert istemci.get(r.headers["location"]).status_code == 200
    assert _uye_id("PY-100", "py") is not None
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "PY-100")).scalar_one()
    assert c.olusturan_id == _kid("py")
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "calisma_uyesi", DenetimKaydi.varlik_id == _uye_id("PY-100", "py"))).scalar_one()
    assert kayit.yeni["kaynak"] == "sihirbaz"
    db.close()
    _giris(istemci, "cra2")  # uye degil
    assert istemci.get(f"/calismalar/{c.id}").status_code == 403
