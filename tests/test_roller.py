"""Rol bazli ekranlar: sekme gorunurlugu, sponsor kurum filtresi, bos durumlar, hesaplanan kontrol listesi."""
import os
import re
from pathlib import Path

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import Calisma, CalismaDurumu, Kullanici, Merkez, Rol
from smartclinical.services import yetki
from smartclinical.web.calismalar import kontrol_listesi

PAROLA = "Test1234!xyz"
SABLONLAR = Path("smartclinical/web/templates")


@pytest.fixture(scope="module")
def istemci():
    sifirla()
    db = oturum_fabrikasi()()
    m = Merkez(kod="T-01", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
    db.add(m)
    db.flush()

    def kul(adi, rol, **ek):
        return Kullanici(kullanici_adi=adi, ad_soyad=adi.title(), eposta=f"{adi}@t.local",
                         parola_hash=yetki.parola_hashle(PAROLA), rol=rol, **ek)

    db.add_all([
        kul("admin", Rol.YONETICI),
        kul("arastirmaci", Rol.ARASTIRMACI, merkez_id=m.id),
        kul("sponsor", Rol.SPONSOR, kurum="S1"),
        kul("sponsor_bos", Rol.SPONSOR),
        kul("cra", Rol.CRA),
    ])
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


def _giris(c, kadi):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _calisma(kod):
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == kod)).scalar_one()
    db.close()
    return c


def _sekmeler(html: str) -> list[str]:
    blok = re.search(r'<div class="sekmeler">(.*?)</div>', html, re.S).group(1)
    return [re.sub(r"<span.*?</span>", "", t).strip() for t in re.findall(r"<a [^>]*>(.*?)</a>", blok, re.S)]


def test_bos_kurulumda_pano_yonlendirir(istemci):
    _giris(istemci, "admin")
    r = istemci.get("/")
    assert r.status_code == 200 and 'href="/sihirbaz"' in r.text and "İlk çalışmanızı oluşturun" in r.text
    _giris(istemci, "arastirmaci")
    r = istemci.get("/")
    assert "Henüz size atanmış çalışma yok" in r.text and "/sihirbaz" not in r.text


def test_calismalar_olustur(istemci):
    _giris(istemci, "admin")
    for kod, sponsor in (("S1-001", "S1"), ("DG-001", "Diger Sponsor")):
        r = istemci.post("/calismalar/yeni", data={
            "kod": kod, "baslik": "Test", "kisa_ad": kod, "tur": "ilac", "faz": "II", "sponsor": sponsor,
            "terapotik_alan": "Onkoloji", "hedef_hasta": "20", "hedef_merkez": "1"}, follow_redirects=False)
        assert r.status_code == 303
    c = _calisma("S1-001")
    r = istemci.post(f"/calismalar/{c.id}/merkezler/ekle", data={"merkez_id": "1", "hedef_hasta": "5"}, follow_redirects=False)
    assert r.status_code == 303


def test_arastirmaci_sekmeleri(istemci):
    _giris(istemci, "arastirmaci")
    c = _calisma("S1-001")
    r = istemci.get(f"/calismalar/{c.id}")
    assert r.status_code == 200
    sekmeler = _sekmeler(r.text)
    assert "Merkez Zekâsı" not in sekmeler and "Denetim İzi" not in sekmeler and "Tasarım" not in sekmeler
    assert "Gönüllüler" in sekmeler and "Veri (eCRF)" in sekmeler and "Analiz" in sekmeler
    assert len(sekmeler) <= 9
    assert istemci.get(f"/calismalar/{c.id}/merkez-zekasi").status_code == 403
    assert istemci.get(f"/calismalar/{c.id}/rbm").status_code == 403
    # calisma listesi sade: sponsor ve tur sutunu yok, acik sorgu ve uyari var
    r = istemci.get("/calismalar")
    assert "<th>Sponsor</th>" not in r.text and "<th>Tür</th>" not in r.text
    assert "Açık sorgu" in r.text and "Uyarı" in r.text


def test_sponsor_kurum_filtresi_ve_sekmeler(istemci):
    _giris(istemci, "sponsor")
    r = istemci.get("/")
    assert r.status_code == 200 and "S1-001" in r.text and "DG-001" not in r.text
    assert "Fizibilite raporu" in r.text and "Hastane içi" not in r.text
    r = istemci.get("/calismalar")
    assert "S1-001" in r.text and "DG-001" not in r.text
    c = _calisma("S1-001")
    r = istemci.get(f"/calismalar/{c.id}")
    sekmeler = _sekmeler(r.text)
    assert len(sekmeler) <= 7 and "Gönüllüler" not in sekmeler and "Veri (eCRF)" not in sekmeler
    assert istemci.get(f"/calismalar/{c.id}/gonulluler").status_code == 403
    assert istemci.get(f"/calismalar/{c.id}/veri").status_code == 403
    assert istemci.get(f"/calismalar/{c.id}/eslestirme").status_code == 403
    r = istemci.get(f"/calismalar/{c.id}/guvenlik")
    assert r.status_code == 200 and "Sponsor görünümü" in r.text
    # kurumu bos sponsor hicbir calisma gormez
    _giris(istemci, "sponsor_bos")
    r = istemci.get("/")
    assert "S1-001" not in r.text and "Henüz size atanmış çalışma yok" in r.text


def test_sponsor_rotasi_kaldirildi(istemci):
    _giris(istemci, "admin")
    assert istemci.get("/sponsor").status_code == 404
    assert istemci.get("/arge").status_code == 404
    assert istemci.get("/araclar/bdm").status_code == 404
    assert istemci.post("/api/v1/yz/soru-cevap", json={"soru": "?", "baglam": "x"}).status_code == 404
    assert istemci.get("/merkezler/endeks").status_code == 200


def test_kimliksizlestirme_izni(istemci):
    _giris(istemci, "arastirmaci")
    assert istemci.get("/araclar/kimliksizlestirme").status_code == 200
    _giris(istemci, "sponsor")
    assert istemci.get("/araclar/kimliksizlestirme").status_code == 403


def test_bos_calisma_bos_durumlari(istemci):
    _giris(istemci, "admin")
    c = _calisma("DG-001")
    r = istemci.get(f"/calismalar/{c.id}/veri")
    assert r.status_code == 200 and f"/calismalar/{c.id}/tasarim" in r.text and "eCRF formu tanımlı değil" in r.text
    r = istemci.get(f"/calismalar/{c.id}/gonulluler")
    assert "Henüz gönüllü yok" in r.text and "Önce merkez ekleyin" in r.text
    r = istemci.get(f"/calismalar/{c.id}/merkezler")
    assert "henüz merkez eklenmedi" in r.text and 'href="#merkez-ekle"' in r.text
    r = istemci.get(f"/calismalar/{c.id}/eslestirme")
    assert "henüz merkez yok" in r.text and f"/calismalar/{c.id}/merkezler" in r.text
    r = istemci.get(f"/calismalar/{c.id}/rbm")
    assert "henüz merkez yok" in r.text and f"/calismalar/{c.id}/merkezler" in r.text
    r = istemci.get(f"/calismalar/{c.id}/merkez-zekasi")
    assert "henüz merkez eklenmedi" in r.text
    # merkezi olan ama hasta havuzu bos calisma: CSV yukleme baglantisi
    c2 = _calisma("S1-001")
    r = istemci.get(f"/calismalar/{c2.id}/eslestirme")
    assert "kimliksizleştirilmiş hasta kaydı yok" in r.text and "/merkezler/1/hasta-yukle" in r.text
    for yol in ("/basvurular", "/izlem", "/belgeler", "/guvenlik"):
        assert istemci.get(f"/calismalar/{c.id}{yol}").status_code == 200, yol


def test_asama_degisimi_gerekce_zorunlu(istemci):
    _giris(istemci, "admin")
    c = _calisma("DG-001")
    r = istemci.post(f"/calismalar/{c.id}/durum", data={"durum": "fizibilite", "gerekce": "  "}, follow_redirects=True)
    assert "gerekçe zorunludur" in r.text
    assert _calisma("DG-001").durum == CalismaDurumu.TASARIM
    r = istemci.post(f"/calismalar/{c.id}/durum", data={"durum": "fizibilite", "gerekce": "Tasarım tamamlandı"}, follow_redirects=True)
    assert r.status_code == 200 and _calisma("DG-001").durum == CalismaDurumu.FIZIBILITE


def test_kontrol_listesi_veriden_hesaplanir(istemci):
    _giris(istemci, "admin")
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "S1-001")).scalar_one()
    tasarim = {m["etiket"]: m for m in kontrol_listesi(db, c)[CalismaDurumu.TASARIM]}
    assert tasarim["Protokol sürümü kayıtlı"]["tamam"] is False
    assert tasarim["Protokol sürümü kayıtlı"]["url"].endswith("/protokol")
    basvuru = [m["etiket"] for m in kontrol_listesi(db, c)[CalismaDurumu.BASVURU]]
    assert "TİTCK başvurusu kayıtlı" in basvuru  # ilac calismasi
    fizibilite = {m["etiket"]: m["tamam"] for m in kontrol_listesi(db, c)[CalismaDurumu.FIZIBILITE]}
    assert fizibilite["En az bir aday merkez eklendi"] is True
    db.close()
    r = istemci.get(f"/calismalar/{c.id}")
    assert "eksik" in r.text and "Protokol sürümü kayıtlı" in r.text
    r = istemci.post(f"/calismalar/{c.id}/protokol/versiyon", data={"versiyon": "1.0", "tarih": "2024-01-01"}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "S1-001")).scalar_one()
    tasarim = {m["etiket"]: m["tamam"] for m in kontrol_listesi(db, c)[CalismaDurumu.TASARIM]}
    assert tasarim["Protokol sürümü kayıtlı"] is True
    db.close()
    r = istemci.get(f"/calismalar/{c.id}")
    assert re.search(r"tamam</span> Protokol sürümü kayıtlı", r.text)


def test_izlem_gorunumu(istemci):
    _giris(istemci, "cra")
    r = istemci.get("/")
    assert r.status_code == 200 and "SDV bekleyen" in r.text and "14 günü geçen" in r.text


def test_arayuz_metinleri_temiz():
    for yol in SABLONLAR.rglob("*.html"):
        metin = yol.read_text(encoding="utf-8")
        assert "PQ-001" not in metin and "IP5" not in metin, yol
    for yol in (SABLONLAR / "eslestirme").glob("*.html"):
        assert "pilot" not in yol.read_text(encoding="utf-8").lower(), yol
