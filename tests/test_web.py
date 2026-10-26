"""Web katmani duman testleri: giris, sureli kilit, parola degisimi, IP siniri, yetki, temel akislar, denetim izi,
HMAC takma ad ve yeniden anahtarlama."""
import os
from datetime import timedelta

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import Calisma, CalismaMerkez, DenetimKaydi, Gonullu, GonulluDurumu, Hasta, Kullanici, Merkez, Rol
from smartclinical.models._ortak import simdi
from smartclinical.scripts.yeniden_anahtarla import eslem_hesapla, yeniden_anahtarla
from smartclinical.services import denetim, yetki
from smartclinical.services.fhir import takma_kayit_no
from smartclinical.web import giris as giris_web
from smartclinical.web import hesap as hesap_web

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
    if not any(getattr(r, "path", "").startswith("/hesap") for r in app.routes):
        app.include_router(hesap_web.router)  # entegrasyon web/__init__.py'de yapilir; testte elle
    giris_web._ip_denemeleri.clear()
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


def test_hatali_giris_ve_sureli_kilit(istemci):
    istemci.cookies.clear()
    giris_web._ip_denemeleri.clear()
    for _ in range(5):
        r = istemci.post("/giris", data={"kullanici_adi": "cra", "parola": "yanlis", "sonraki": "/"})
        assert "hatalı" in r.text and "15 dakika" in r.text
    r = istemci.post("/giris", data={"kullanici_adi": "cra", "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 200  # kilitli: dogru parolayla da giremez
    db = oturum_fabrikasi()()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "cra")).scalar_one()
    assert k.hatali_giris == 5 and k.kilitli and (k.kilit_bitis - simdi()) <= timedelta(minutes=15)
    kilit = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "kilit", DenetimKaydi.varlik_id == k.id)).scalars().all()
    assert len(kilit) == 1 and kilit[0].yeni["dakika"] == 15
    # sure dolunca dogru parola kabul edilir, sayac sifirlanir
    k.kilit_bitis = simdi() - timedelta(seconds=1)
    db.commit()
    r = istemci.post("/giris", data={"kullanici_adi": "cra", "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "cra")).scalar_one()
    assert k.hatali_giris == 0 and k.kilit_bitis is None
    db.close()
    assert yetki.kilit_suresi(5) == timedelta(minutes=15) and yetki.kilit_suresi(10) == timedelta(minutes=30)
    assert yetki.kilit_suresi(15) == timedelta(minutes=60)
    giris_web._ip_denemeleri.clear()


def test_ip_basina_deneme_siniri(istemci):
    istemci.cookies.clear()
    giris_web._ip_denemeleri.clear()
    for _ in range(giris_web.IP_SINIR):
        assert istemci.post("/giris", data={"kullanici_adi": "yok", "parola": "x", "sonraki": "/"}).status_code == 200
    r = istemci.post("/giris", data={"kullanici_adi": "yok", "parola": "x", "sonraki": "/"})
    assert r.status_code == 429 and "çok sayıda hatalı deneme" in r.text
    r = istemci.post("/giris", data={"kullanici_adi": "admin", "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 429  # sinir dogru parolayi da bekletir
    db = oturum_fabrikasi()()
    assert db.scalar(select(DenetimKaydi.id).where(DenetimKaydi.islem == "giris_engellendi").limit(1))
    db.close()
    giris_web._ip_denemeleri.clear()
    _giris(istemci, "admin")


def test_parola_degistir_ve_gecmis(istemci):
    _giris(istemci, "denetci")
    assert istemci.get("/hesap/parola").status_code == 200
    r = istemci.post("/hesap/parola", data={"eski": "yanlis", "yeni": "Yeni12345!abc", "yeni_tekrar": "Yeni12345!abc"})
    assert r.status_code == 200 and "Mevcut parola doğrulanamadı" in r.text
    r = istemci.post("/hesap/parola", data={"eski": PAROLA, "yeni": "kisa1", "yeni_tekrar": "kisa1"})
    assert "en az 12 karakter" in r.text
    r = istemci.post("/hesap/parola", data={"eski": PAROLA, "yeni": "Yeni12345!abc", "yeni_tekrar": "farkli12345!x"})
    assert "uyuşmuyor" in r.text
    r = istemci.post("/hesap/parola", data={"eski": PAROLA, "yeni": "Yeni12345!abc", "yeni_tekrar": "Yeni12345!abc"}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "denetci")).scalar_one()
    assert yetki.parola_dogrula("Yeni12345!abc", k.parola_hash) and len(k.parola_gecmisi) == 1
    assert db.scalar(select(DenetimKaydi.id).where(DenetimKaydi.islem == "parola_degistir", DenetimKaydi.varlik_id == k.id))
    db.close()
    # eski parola yeniden kullanilamaz; son 5 tutulur
    r = istemci.post("/hesap/parola", data={"eski": "Yeni12345!abc", "yeni": PAROLA, "yeni_tekrar": PAROLA})
    assert "yeniden kullanılamaz" in r.text
    su_an = "Yeni12345!abc"
    for i in range(5):
        yeni = f"Parola{i}2345!xyz"
        r = istemci.post("/hesap/parola", data={"eski": su_an, "yeni": yeni, "yeni_tekrar": yeni}, follow_redirects=False)
        assert r.status_code == 303, r.text
        su_an = yeni
    db = oturum_fabrikasi()()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "denetci")).scalar_one()
    assert len(k.parola_gecmisi) == 5
    k.parola_hash = yetki.parola_hashle(PAROLA)  # diger testler icin geri al
    db.commit()
    db.close()


def test_ilk_giriste_parola_degisimi_zorunlu(istemci):
    db = oturum_fabrikasi()()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "denetci")).scalar_one()
    k.ilk_giris_degisim = True
    db.commit()
    db.close()
    istemci.cookies.clear()
    r = istemci.post("/giris", data={"kullanici_adi": "denetci", "parola": PAROLA, "sonraki": "/yonetim/denetim"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/hesap/parola"
    r = istemci.get("/yonetim/denetim", follow_redirects=True)
    assert r.url.path == "/hesap/parola" and "parolanızı değiştirmeniz gerekiyor" in r.text
    assert istemci.get("/api/v1/saglik").status_code == 200  # API etkilenmez
    r = istemci.post("/hesap/parola", data={"eski": PAROLA, "yeni": "Zorunlu12345!x", "yeni_tekrar": "Zorunlu12345!x"}, follow_redirects=False)
    assert r.status_code == 303
    assert istemci.get("/yonetim/denetim").status_code == 200
    db = oturum_fabrikasi()()
    k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == "denetci")).scalar_one()
    assert k.ilk_giris_degisim is False
    k.parola_hash, k.parola_gecmisi = yetki.parola_hashle(PAROLA), []
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


def test_parola_politikasi(istemci, monkeypatch):
    assert yetki.parola_politikasi("kisa") is not None
    assert yetki.parola_politikasi("sadeceharflerxx") is not None
    assert yetki.parola_politikasi("Uzun12345x") is not None  # 10 karakter: varsayilan 12'nin altinda
    assert yetki.parola_politikasi("Uzun12345xyz") is None
    monkeypatch.setenv("SC_PAROLA_MIN", "8")
    assert yetki.parola_min() == 8 and yetki.parola_politikasi("Kisa1234") is None
    monkeypatch.setenv("SC_PAROLA_GUN", "1")
    k = Kullanici(parola_degisim=simdi() - timedelta(days=2))
    assert yetki.parola_suresi_doldu(k) and yetki.parola_degisimi_gerekli(k)
    assert not yetki.parola_suresi_doldu(Kullanici(parola_degisim=None))


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


def test_takma_ad_hmac_ve_yeniden_anahtarla(istemci):
    ident = [{"system": "hbys", "value": "123"}]
    eski = takma_kayit_no(ident, None, 1, anahtar="eski-anahtar")
    yeni = takma_kayit_no(ident, None, 1, anahtar="yeni-anahtar")
    assert eski.startswith("P-") and eski == takma_kayit_no(ident, None, 1, anahtar="eski-anahtar")
    assert eski != yeni and eski != takma_kayit_no(ident, None, 2, anahtar="eski-anahtar")
    assert takma_kayit_no(ident, None, 1) == takma_kayit_no(ident, None, 1)  # varsayilan anahtar deterministik
    assert takma_kayit_no(ident, None, 1) != eski
    # mevcut kayit eski takma adla; yeniden anahtarlama kayit_no'yu yeniler, Gonullu.hasta_id korunur
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "TST-001")).scalar_one()
    cm = CalismaMerkez(calisma_id=c.id, merkez_id=1, merkez_no="01", durum="aktif")
    db.add(cm)
    db.flush()
    h = Hasta(merkez_id=1, kayit_no=eski, dogum_yili=1960)
    db.add(h)
    db.flush()
    g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, hasta_id=h.id, gonullu_no="01-009", durum=GonulluDurumu.ONAM)
    db.add(g)
    db.commit()
    hid, gid = h.id, g.id
    eslem = eslem_hesapla([(1, "hbys", "123"), (1, "hbys", "yok")], "eski-anahtar", "yeni-anahtar")
    sonuc = yeniden_anahtarla(db, eslem)
    db.commit()
    assert sonuc == {"eslem": 2, "guncellenen": 1, "bulunamayan": 1, "cakisan": 0}
    db.expire_all()
    h = db.get(Hasta, hid)
    g = db.get(Gonullu, gid)
    assert h.kayit_no == yeni and g.hasta_id == hid and g.hasta.kayit_no == yeni
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "yeniden_anahtarla")).scalars().all()
    assert kayit and kayit[-1].yeni["guncellenen"] == 1 and denetim.zinciri_dogrula(db) == (True, None)
    db.close()
