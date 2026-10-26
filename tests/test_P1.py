"""P1: erisim denetimi birimleri, merkez siniri (API ve CSV), denetim izi filtre/CSV, sponsor kurum zorunlulugu."""
import os
from datetime import date
from types import SimpleNamespace

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import Taban, oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    Calisma,
    CalismaDurumu,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    Gonullu,
    GonulluDurumu,
    Hasta,
    Kullanici,
    Merkez,
    Rol,
)
from smartclinical.models.merkez import Arastirmaci
from smartclinical.services import yetki
from smartclinical.web.pano import _portfoy_satiri

PAROLA = "Test1234!xyz"
_ids: dict[str, int] = {}


@pytest.fixture(scope="module")
def istemci():
    sifirla()
    db = oturum_fabrikasi()()
    ank = Merkez(kod="ANK-01", ad="Ankara Hastanesi", sehir="Ankara", kurum_tipi="universite")
    izm = Merkez(kod="IZM-01", ad="Izmir Hastanesi", sehir="Izmir", kurum_tipi="sehir")
    db.add_all([ank, izm])
    db.flush()

    def kul(adi, rol, **ek):
        return Kullanici(kullanici_adi=adi, ad_soyad=adi.title(), eposta=f"{adi}@t.local",
                         parola_hash=yetki.parola_hashle(PAROLA), rol=rol, **ek)

    db.add_all([kul("admin", Rol.YONETICI), kul("ank", Rol.ARASTIRMACI, merkez_id=ank.id),
                kul("koord", Rol.KOORDINATOR, merkez_id=izm.id), kul("py", Rol.PROJE_YONETICISI),
                kul("sponsor", Rol.SPONSOR, kurum="Ilac AS")])
    c = Calisma(kod="MRK-001", baslik="Merkez siniri", kisa_ad="MRK", tur=CalismaTuru.ILAC, sponsor="ILAC AS",
                terapotik_alan="Onkoloji", hedef_hasta=10)
    db.add(c)
    db.flush()
    cm_ank = CalismaMerkez(calisma_id=c.id, merkez_id=ank.id, merkez_no="01", durum="aktif", aktivasyon_tarihi=date.today())
    cm_izm = CalismaMerkez(calisma_id=c.id, merkez_id=izm.id, merkez_no="02", durum="aktif", aktivasyon_tarihi=date.today())
    db.add_all([cm_ank, cm_izm])
    db.flush()
    h_izm = Hasta(merkez_id=izm.id, kayit_no="P-IZM1", dogum_yili=1970, cinsiyet="K")
    h_ank = Hasta(merkez_id=ank.id, kayit_no="P-ANK1", dogum_yili=1965, cinsiyet="E")
    db.add_all([h_izm, h_ank])
    db.flush()
    db.add_all([Gonullu(calisma_id=c.id, calisma_merkez_id=cm_ank.id, hasta_id=h_ank.id, gonullu_no="01-001", durum=GonulluDurumu.ONAM),
                Gonullu(calisma_id=c.id, calisma_merkez_id=cm_izm.id, hasta_id=h_izm.id, gonullu_no="02-001", durum=GonulluDurumu.ONAM)])
    db.commit()
    _ids.update(ank=ank.id, izm=izm.id, c=c.id, h_izm=h_izm.id, h_ank=h_ank.id)
    db.close()
    with TestClient(app) as cl:
        yield cl


def _giris(c, kadi):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _kullanici(kadi):
    db = oturum_fabrikasi()()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == kadi)).scalar_one()
    db.close()
    return k


def test_izin_haritasi_sponsor_salt_okunur():
    assert Rol.SPONSOR not in yetki.IZINLER["calisma.olustur"] and Rol.SPONSOR not in yetki.IZINLER["calisma.duzenle"]
    assert Rol.ARASTIRMACI in yetki.IZINLER["calisma.olustur"] and Rol.ARASTIRMACI in yetki.IZINLER["calisma.duzenle"]
    yazma = {izin for izin, roller in yetki.IZINLER.items() if Rol.SPONSOR in roller}
    assert yazma == {"rbm.goruntule"}


def test_kilometre_tasi_kaldirildi():
    assert "kilometre_tasi" not in Taban.metadata.tables
    assert "calisma_taslagi" in Taban.metadata.tables
    assert not hasattr(CalismaMerkez, "kilometre_taslari")


def test_merkez_ve_gonullu_erisimi(istemci):
    db = oturum_fabrikasi()()
    admin, ank, koord, py, sponsor = (_kullanici(x) for x in ("admin", "ank", "koord", "py", "sponsor"))
    assert yetki.merkez_erisimi(admin, _ids["izm"]) and yetki.merkez_erisimi(ank, _ids["ank"])
    assert not yetki.merkez_erisimi(ank, _ids["izm"]) and not yetki.merkez_erisimi(py, _ids["ank"])
    assert not yetki.merkez_erisimi(sponsor, _ids["ank"])
    assert not yetki.merkez_erisimi(SimpleNamespace(rol=Rol.ARASTIRMACI, merkez_id=None), _ids["ank"])
    c = db.get(Calisma, _ids["c"])
    g_ank = next(g for g in c.gonulluler if g.gonullu_no == "01-001")
    g_izm = next(g for g in c.gonulluler if g.gonullu_no == "02-001")
    assert yetki.gonullu_erisimi(db, ank, g_ank) and not yetki.gonullu_erisimi(db, ank, g_izm)
    assert yetki.gonullu_erisimi(db, koord, g_izm) and not yetki.gonullu_erisimi(db, koord, g_ank)
    assert yetki.gonullu_erisimi(db, admin, g_izm) and yetki.gonullu_erisimi(db, py, g_izm)
    assert not yetki.gonullu_erisimi(db, sponsor, g_izm)  # sponsor gonullu goremez
    # sponsor kurum karsilastirmasi normalize: 'Ilac AS' == 'ILAC AS'
    assert yetki.calisma_erisimi(db, sponsor, c)
    assert [x.kod for x in db.execute(yetki.calisma_filtresi(db, sponsor, select(Calisma))).scalars().unique()] == ["MRK-001"]
    db.close()


def test_calisma_duzenleyebilir(istemci):
    db = oturum_fabrikasi()()
    c = db.get(Calisma, _ids["c"])
    admin, ank, koord, py = (_kullanici(x) for x in ("admin", "ank", "koord", "py"))
    assert yetki.calisma_duzenleyebilir(db, admin, c) and yetki.calisma_duzenleyebilir(db, py, c)
    assert not yetki.calisma_duzenleyebilir(db, ank, c) and not yetki.calisma_duzenleyebilir(db, koord, c)
    # bas arastirmacisi kendi merkezinden olan calisma
    a = Arastirmaci(merkez_id=_ids["ank"], ad_soyad="Dr. Ank")
    db.add(a)
    db.flush()
    c.merkezler[0].bas_arastirmaci_id = a.id
    db.commit()
    db.expire_all()
    c = db.get(Calisma, _ids["c"])
    assert yetki.calisma_duzenleyebilir(db, ank, c)
    c.merkezler[0].bas_arastirmaci_id = None
    db.commit()
    # kendi kurdugu calisma
    c.olusturan_id = ank.id
    db.commit()
    assert yetki.calisma_duzenleyebilir(db, ank, c)
    c.olusturan_id = None
    db.commit()
    db.close()


def test_arastirmaci_baska_merkezin_hastasina_erisemez(istemci):
    _giris(istemci, "ank")
    assert istemci.get(f"/api/v1/hastalar/{_ids['h_izm']}").status_code == 403
    assert istemci.get(f"/api/v1/hastalar/{_ids['h_ank']}").status_code == 200
    bundle = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient", "id": "p1", "gender": "female",
                                                                 "birthDate": "1970-01-01"}}]}
    assert istemci.post(f"/api/v1/fhir/Bundle?merkez_id={_ids['izm']}", json=bundle).status_code == 403
    assert istemci.post(f"/api/v1/fhir/Bundle?merkez_id={_ids['ank']}", json=bundle).status_code == 200
    assert istemci.post(f"/api/v1/hbys/senkron?merkez_id={_ids['izm']}", json=["E11"]).status_code == 403
    assert istemci.post("/api/v1/hastalar", json={"merkez_id": _ids["izm"], "kayit_no": "P-X", "dogum_yili": 1980}).status_code == 403
    # CSV yukleme: baska merkez 403, kendi merkezi acik
    assert istemci.get(f"/merkezler/{_ids['izm']}/hasta-yukle").status_code == 403
    csv = "kayit_no;dogum_yili;cinsiyet;icd10;metin\nHBYS-9;1960;K;C50.9;\n"
    assert istemci.post(f"/merkezler/{_ids['izm']}/hasta-yukle", files={"dosya": ("h.csv", csv.encode(), "text/csv")}).status_code == 403
    r = istemci.post(f"/merkezler/{_ids['ank']}/hasta-yukle", files={"dosya": ("h.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200 and "1 yeni" in r.text
    # gonullu listesi ve eslestirme havuzu yalnizca kendi merkezi
    r = istemci.get(f"/calismalar/{_ids['c']}/gonulluler")
    assert "01-001" in r.text and "02-001" not in r.text
    r = istemci.get(f"/calismalar/{_ids['c']}/eslestirme")
    assert r.status_code == 200
    # proje yoneticisi hasta havuzuna dokunamaz
    _giris(istemci, "py")
    assert istemci.get(f"/merkezler/{_ids['ank']}/hasta-yukle").status_code == 403


def test_sponsor_kullanicisina_kurum_zorunlu(istemci):
    _giris(istemci, "admin")
    db = oturum_fabrikasi()()
    from smartclinical.services import kurulum as kurulum_svc
    kurulum_svc.ayar_yaz(db, "cro", "EBM CRO", None, None)
    db.commit()
    db.close()
    r = istemci.get("/yonetim/kullanicilar")
    assert r.status_code == 200 and 'name="kurum"' in r.text and '<option value="ILAC AS">' in r.text
    r = istemci.post("/yonetim/kullanicilar", data={"kullanici_adi": "spons2", "ad_soyad": "S", "eposta": "s2@t.local",
                                                   "parola": PAROLA, "rol": "sponsor", "merkez_id": ""}, follow_redirects=True)
    assert "kurum adı zorunludur" in r.text
    r = istemci.post("/yonetim/kullanicilar", data={"kullanici_adi": "spons2", "ad_soyad": "S", "eposta": "s2@t.local",
                                                   "parola": PAROLA, "rol": "sponsor", "merkez_id": "", "kurum": "ILAC AS"},
                     follow_redirects=True)
    assert "ilk girişte değiştirmesi istenir" in r.text
    k = _kullanici("spons2")
    assert k.kurum == "ILAC AS" and k.ilk_giris_degisim is True
    # yeni sponsor ilk giriste parola sayfasina duser, sonra calismasini gorur
    istemci.cookies.clear()
    r = istemci.post("/giris", data={"kullanici_adi": "spons2", "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/hesap/parola"
    r = istemci.get("/calismalar", follow_redirects=True)
    assert r.url.path == "/hesap/parola" and "Parola değiştir" in r.text
    r = istemci.post("/hesap/parola", data={"eski": PAROLA, "yeni": "Yeni12345!abc", "yeni_tekrar": "Yeni12345!abc"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "MRK-001" in istemci.get("/calismalar").text


def test_denetim_izi_filtre_ve_csv(istemci):
    _giris(istemci, "admin")
    bugun = date.today().isoformat()
    r = istemci.get(f"/yonetim/denetim?varlik=kullanici&islem=olustur&baslangic={bugun}&bitis={bugun}")
    assert r.status_code == 200 and "kullanıcı oluşturuldu" in r.text and "CSV indir" in r.text
    r = istemci.get("/yonetim/denetim?varlik=kullanici&baslangic=2000-01-01&bitis=2000-01-02")
    assert "Kayıt yok" in r.text
    r = istemci.get(f"/yonetim/denetim?bicim=csv&varlik=kullanici&islem=olustur&baslangic={bugun}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    satirlar = r.text.lstrip("﻿").splitlines()
    assert satirlar[0].startswith("id;zaman_utc;kullanici;islem;varlik") and len(satirlar) >= 2
    assert "kullanıcı oluşturuldu" in satirlar[1]
    db = oturum_fabrikasi()()
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "disa_aktar", DenetimKaydi.varlik == "denetim_kaydi")).scalars().all()
    assert kayit and kayit[-1].yeni["bicim"] == "csv"
    db.close()


def test_arsiv_calismada_takvim_bos(istemci):
    db = oturum_fabrikasi()()
    c = db.get(Calisma, _ids["c"])
    c.durum = CalismaDurumu.ARSIV
    c.planlanan_bitis = date(2030, 1, 1)
    db.commit()
    satir = _portfoy_satiri(db, c, date.today())
    assert satir["takvim"] == "arsiv" and satir["tahmini_ay"] is None and satir["plan_ay"] is None
    c.durum = CalismaDurumu.KAYIT
    db.commit()
    db.close()
    _giris(istemci, "admin")
    assert istemci.get("/").status_code == 200
