"""Rol bazli ekranlar: rol x rota matrisi, sekme gorunurlugu, sponsor kurum filtresi, bos durumlar, kontrol listesi.

Rol x sekme ve rol x izin tablolari docs/roller.md ile ayni kaynaktan dogrulanir.
"""
import os
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    Calisma,
    CalismaDurumu,
    CalismaMerkez,
    Gonullu,
    GonulluDurumu,
    IzlemZiyareti,
    Kullanici,
    Merkez,
    Rol,
)
from smartclinical.models.ekip import CalismaUyesi
from smartclinical.services import ecrf as ecrf_svc
from smartclinical.services import yetki
from smartclinical.web import ekip as ekip_web
from smartclinical.web.calismalar import SEKME_ETIKET, kontrol_listesi, sekme_gorunur

PAROLA = "Test1234!xyz"
SABLONLAR = Path("smartclinical/web/templates")
DOKUMAN = Path("docs/roller.md")

ROL_SUTUN = {
    "Yönetici": Rol.YONETICI, "Proje Yöneticisi": Rol.PROJE_YONETICISI, "CRA": Rol.CRA,
    "Veri Yöneticisi": Rol.VERI_YONETICISI, "Sponsor": Rol.SPONSOR, "Araştırmacı": Rol.ARASTIRMACI,
    "Koordinatör": Rol.KOORDINATOR, "Denetçi": Rol.DENETCI, "Biyoistatistikçi": Rol.ISTATISTIKCI,
    "Farmakovijilans": Rol.FARMAKOVIJILANS,
}
# matris kullanicilari (kullanici adi -> rol); arastirmaci ve koordinator T-01 merkezine bagli
ROLLER = ("admin", "py", "cra", "vy", "sponsor", "arastirmaci", "koordinator", "denetci")
_ids: dict[str, int] = {}


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
        kul("admin", Rol.YONETICI),
        kul("py", Rol.PROJE_YONETICISI),
        kul("cra", Rol.CRA),
        kul("vy", Rol.VERI_YONETICISI),
        kul("arastirmaci", Rol.ARASTIRMACI, merkez_id=m1.id),
        kul("koordinator", Rol.KOORDINATOR, merkez_id=m1.id),
        kul("sponsor", Rol.SPONSOR, kurum=" s1 "),  # bosluk ve kucuk harf: normalize edilir
        kul("sponsor_bos", Rol.SPONSOR),
        kul("denetci", Rol.DENETCI),
    ])
    db.commit()
    _ids["m1"], _ids["m2"] = m1.id, m2.id
    db.close()
    if not any(getattr(r, "path", "").startswith("/calismalar/{calisma_id}/ekip") for r in app.routes):
        app.include_router(ekip_web.router)
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


def _kid(kadi):
    db = oturum_fabrikasi()()
    kid = db.scalar(select(Kullanici.id).where(Kullanici.kullanici_adi == kadi))
    db.close()
    return kid


def _sekmeler(html: str) -> list[str]:
    blok = re.search(r'<div class="sekmeler">(.*?)</div>', html, re.S).group(1)
    return [re.sub(r"<span.*?</span>", "", t).strip() for t in re.findall(r"<a [^>]*>(.*?)</a>", blok, re.S)]


def _tablo(baslik: str) -> dict[str, dict[str, str]]:
    """docs/roller.md icindeki '## baslik' tablosunu {satir: {sutun: sembol}} olarak okur."""
    metin = DOKUMAN.read_text(encoding="utf-8")
    bolum = metin.split(f"## {baslik}", 1)[1].split("\n## ", 1)[0]
    satirlar = [s for s in bolum.splitlines() if s.startswith("|")]
    sutunlar = [h.strip() for h in satirlar[0].strip("|").split("|")]
    tablo = {}
    for s in satirlar[2:]:
        hucreler = [h.strip() for h in s.strip("|").split("|")]
        tablo[hucreler[0]] = dict(zip(sutunlar[1:], hucreler[1:]))
    return tablo


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
    assert c.olusturan_id == _kid("admin")
    r = istemci.post(f"/calismalar/{c.id}/merkezler/ekle", data={"merkez_id": str(_ids["m1"]), "hedef_hasta": "5"}, follow_redirects=False)
    assert r.status_code == 303


def test_arastirmaci_sekmeleri(istemci):
    _giris(istemci, "arastirmaci")
    c = _calisma("S1-001")
    r = istemci.get(f"/calismalar/{c.id}")
    assert r.status_code == 200
    sekmeler = _sekmeler(r.text)
    assert "Merkez Zekâsı" not in sekmeler and "Denetim İzi" not in sekmeler and "Tasarım" not in sekmeler
    assert "Gönüllüler" in sekmeler and "Veri (eCRF)" in sekmeler and "Analiz" in sekmeler
    assert "Ziyaret ve Sapmalar" in sekmeler and "TMF" in sekmeler
    assert len(sekmeler) <= 12
    assert istemci.get(f"/calismalar/{c.id}/merkez-zekasi").status_code == 403
    assert istemci.get(f"/calismalar/{c.id}/rbm").status_code == 403
    # calisma listesi sade: sponsor ve tur sutunu yok, acik sorgu ve uyari var
    r = istemci.get("/calismalar")
    assert "<th>Sponsor</th>" not in r.text and "<th>Tür</th>" not in r.text
    assert "Açık sorgu" in r.text and "Uyarı" in r.text


def test_sekme_gruplari_ve_sarma(istemci):
    _giris(istemci, "admin")
    c = _calisma("S1-001")
    r = istemci.get(f"/calismalar/{c.id}")
    assert re.search(r'<span class="sekme-grup">Kurulum</span>', r.text) and "Yürütme" in r.text and "Kapanış" in r.text
    assert len(_sekmeler(r.text)) == len(SEKME_ETIKET)
    css = Path("smartclinical/static/css/uygulama.css").read_text(encoding="utf-8")
    assert re.search(r"\.sekmeler \{[^}]*flex-wrap: wrap", css) and ".tablo-kaydir" in css and ".sayfalama" in css


def test_sponsor_kurum_filtresi_ve_sekmeler(istemci):
    _giris(istemci, "sponsor")
    r = istemci.get("/")
    assert r.status_code == 200 and "S1-001" in r.text and "DG-001" not in r.text
    assert "Fizibilite raporu" in r.text and "Hastane içi" not in r.text
    assert 'href="/sihirbaz"' not in r.text  # yeni calisma dugmesi yok
    r = istemci.get("/calismalar")
    assert "S1-001" in r.text and "DG-001" not in r.text and 'href="/sihirbaz"' not in r.text
    assert istemci.get("/sihirbaz", follow_redirects=False).status_code == 403
    c = _calisma("S1-001")
    r = istemci.get(f"/calismalar/{c.id}")
    sekmeler = _sekmeler(r.text)
    assert len(sekmeler) <= 7 and "Gönüllüler" not in sekmeler and "Veri (eCRF)" not in sekmeler and "Tasarım" not in sekmeler
    assert "Son işlemler" not in r.text
    assert istemci.get(f"/calismalar/{c.id}/gonulluler").status_code == 403
    assert istemci.get(f"/calismalar/{c.id}/veri").status_code == 403
    assert istemci.get(f"/calismalar/{c.id}/eslestirme").status_code == 403
    assert istemci.get(f"/calismalar/{c.id}/ekip").status_code == 403
    # sponsor yazamaz: asama degisimi ve basvuru kaydi 403
    assert istemci.post(f"/calismalar/{c.id}/durum", data={"durum": "fizibilite", "gerekce": "x"}, follow_redirects=False).status_code == 403
    assert istemci.post(f"/calismalar/{c.id}/basvurular", data={"kurum": "etik_kurul"}, follow_redirects=False).status_code == 403
    r = istemci.get(f"/calismalar/{c.id}/guvenlik")
    assert r.status_code == 200 and "Sponsor görünümü" in r.text
    # kurumu bos sponsor hicbir calisma gormez
    _giris(istemci, "sponsor_bos")
    r = istemci.get("/")
    assert "S1-001" not in r.text and "Henüz size atanmış çalışma yok" in r.text
    assert istemci.get(f"/calismalar/{c.id}").status_code == 403


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
    assert "kimliksizleştirilmiş hasta kaydı yok" in r.text and f"/merkezler/{_ids['m1']}/hasta-yukle" in r.text
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
    assert "Proje ekibi atandı" not in tasarim  # atama kisiti yokken madde yok
    basvuru = [m["etiket"] for m in kontrol_listesi(db, c)[CalismaDurumu.BASVURU]]
    assert "TİTCK başvurusu kayıtlı" in basvuru  # ilac calismasi
    fizibilite = {m["etiket"]: m["tamam"] for m in kontrol_listesi(db, c)[CalismaDurumu.FIZIBILITE]}
    assert fizibilite["En az bir aday merkez eklendi"] is True
    aktivasyon = {m["etiket"]: m["tamam"] for m in kontrol_listesi(db, c)[CalismaDurumu.AKTIVASYON]}
    assert aktivasyon["Başlatma ziyareti (SIV) yapıldı"] is False
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
    assert "protokol sürümü oluşturuldu" in r.text  # son islemler cumle halinde


def test_izlem_gorunumu(istemci):
    _giris(istemci, "cra")
    r = istemci.get("/")
    assert r.status_code == 200 and "SDV bekleyen" in r.text and "14 günü geçen" in r.text
    assert "Bana atanan ziyaretler" in r.text and "diğer ziyaretler" in r.text


def test_arayuz_metinleri_temiz():
    for yol in SABLONLAR.rglob("*.html"):
        metin = yol.read_text(encoding="utf-8")
        assert "PQ-001" not in metin and "IP5" not in metin, yol
    for yol in (SABLONLAR / "eslestirme").glob("*.html"):
        assert "pilot" not in yol.read_text(encoding="utf-8").lower(), yol


# --- rol x rota matrisi -------------------------------------------------------

def test_matris_hazirlik(istemci):
    """S1-001: T-01 ve T-02 aktif, T-02'de bir gonullu, DM formu, ekip (py, cra, vy) atanmis -> kisit etkin.
    DG-001: yalnizca T-02 (sponsor ve T-01 rolleri gormez). Izlem ziyaretleri: cra'ya atanan ve atanmamis."""
    db = oturum_fabrikasi()()
    c = db.execute(select(Calisma).where(Calisma.kod == "S1-001")).scalar_one()
    dg = db.execute(select(Calisma).where(Calisma.kod == "DG-001")).scalar_one()
    cm1 = c.merkezler[0]
    cm1.durum, cm1.aktivasyon_tarihi = "aktif", date.today()
    cm2 = CalismaMerkez(calisma_id=c.id, merkez_id=_ids["m2"], merkez_no="02", durum="aktif", aktivasyon_tarihi=date.today())
    cm_dg = CalismaMerkez(calisma_id=dg.id, merkez_id=_ids["m2"], merkez_no="01", durum="aktif", aktivasyon_tarihi=date.today())
    db.add_all([cm2, cm_dg])
    db.flush()
    g1 = Gonullu(calisma_id=c.id, calisma_merkez_id=cm1.id, gonullu_no="01-001", durum=GonulluDurumu.RANDOMIZE,
                 randomizasyon_tarihi=date.today())
    g2 = Gonullu(calisma_id=c.id, calisma_merkez_id=cm2.id, gonullu_no="02-001", durum=GonulluDurumu.ONAM)
    db.add_all([g1, g2])
    formlar = ecrf_svc.standart_formlari_ekle(db, c, ["DM"])
    cra_id = db.scalar(select(Kullanici.id).where(Kullanici.kullanici_adi == "cra"))
    for kadi in ("py", "cra", "vy"):
        db.add(CalismaUyesi(calisma_id=c.id, kullanici_id=db.scalar(select(Kullanici.id).where(Kullanici.kullanici_adi == kadi))))
    db.add_all([IzlemZiyareti(calisma_merkez_id=cm1.id, tip="IMV", planlanan=date.today(), cra_id=cra_id),
                IzlemZiyareti(calisma_merkez_id=cm2.id, tip="SIV", planlanan=date.today()),
                IzlemZiyareti(calisma_merkez_id=cm_dg.id, tip="IMV", planlanan=date.today(), cra_id=cra_id)])
    db.commit()
    _ids.update(c=c.id, dg=dg.id, g_m1=g1.id, g_m2=g2.id, form=formlar[0].id)
    db.close()
    assert yetki.kisit_aktif(oturum_fabrikasi()())


def _rota(ad: str) -> str:
    c = _ids["c"]
    return {
        "ozet": f"/calismalar/{c}", "tasarim": f"/calismalar/{c}/tasarim", "ekip": f"/calismalar/{c}/ekip",
        "gonulluler": f"/calismalar/{c}/gonulluler", "veri": f"/calismalar/{c}/veri", "izlem": f"/calismalar/{c}/izlem",
        "belgeler": f"/calismalar/{c}/belgeler", "basvurular": f"/calismalar/{c}/basvurular",
        "analiz": f"/calismalar/{c}/analiz", "gonullu_detay": f"/gonulluler/{_ids['g_m2']}",
        "gonullu_form": f"/gonulluler/{_ids['g_m2']}/form/{_ids['form']}",
    }[ad]


def _beklenen(yasak: tuple[str, ...]) -> dict[str, int]:
    return {kadi: (403 if kadi in yasak else 200) for kadi in ROLLER}


# gonullu T-02'de: T-01'e bagli arastirmaci ve koordinator goremez; sponsor hicbir gonulluyu goremez
MATRIS = {
    "ozet": _beklenen(()),
    "tasarim": _beklenen(("cra", "vy", "sponsor", "arastirmaci", "koordinator", "denetci")),
    "ekip": _beklenen(("cra", "vy", "sponsor", "arastirmaci", "koordinator", "denetci")),
    "gonulluler": _beklenen(("sponsor",)),
    "veri": _beklenen(("sponsor",)),
    "izlem": _beklenen(("vy", "sponsor")),
    "belgeler": _beklenen(()),
    "basvurular": _beklenen(("vy", "koordinator")),
    "analiz": _beklenen(("cra", "sponsor", "koordinator", "denetci")),
    "gonullu_detay": _beklenen(("sponsor", "arastirmaci", "koordinator")),
    "gonullu_form": _beklenen(("sponsor", "arastirmaci", "koordinator")),
}
# P2 (tasarim rotasinda calisma_duzenleyebilir) ve P4 (gonullu rotalarinda yetki.gonullu_erisimi) entegre olana dek
_BEKLEYEN = {("tasarim", k) for k in ("cra", "vy", "sponsor", "arastirmaci", "koordinator", "denetci")} | {
    (r, k) for r in ("gonullu_detay", "gonullu_form") for k in ("sponsor", "arastirmaci", "koordinator")}


def _parametreler():
    for rota, satir in MATRIS.items():
        for kadi, kod in satir.items():
            marks = [pytest.mark.xfail(strict=True, reason="P2/P4 entegrasyonu bekleniyor")] if (rota, kadi) in _BEKLEYEN else []
            yield pytest.param(rota, kadi, kod, id=f"{rota}-{kadi}", marks=marks)


@pytest.mark.parametrize("rota,kadi,kod", list(_parametreler()))
def test_rol_rota_matrisi(istemci, rota, kadi, kod):
    _giris(istemci, kadi)
    r = istemci.get(_rota(rota), follow_redirects=False)
    assert r.status_code == kod, f"{kadi} -> {rota}: {r.status_code}, beklenen {kod}"


def test_matris_dokumanla_uyumlu():
    """docs/roller.md rol x sekme tablosu sekme_gorunur ile, rol x izin tablosu IZINLER ile birebir ayni."""
    sekme_tablo = _tablo("Rol x sekme")
    assert set(sekme_tablo) == set(SEKME_ETIKET)
    for sekme, satir in sekme_tablo.items():
        for sutun, sembol in satir.items():
            rol = ROL_SUTUN[sutun]
            gorunur = sekme_gorunur(SimpleNamespace(rol=rol), sekme)
            if sembol == "○":
                assert sekme == "tasarim" and rol == Rol.ARASTIRMACI and gorunur, (sekme, sutun)
            else:
                assert gorunur is (sembol == "●"), (sekme, sutun, sembol)
    izin_tablo = _tablo("Rol x izin")
    assert set(izin_tablo) == set(yetki.IZINLER)
    for izin, satir in izin_tablo.items():
        roller = {ROL_SUTUN[sutun] for sutun, sembol in satir.items() if sembol == "●"}
        assert roller == yetki.IZINLER[izin], izin
        assert Rol.SPONSOR not in roller or izin == "rbm.goruntule"  # sponsor salt okunur


def test_merkez_rolleri_kendi_merkezini_gorur(istemci):
    _giris(istemci, "arastirmaci")
    c = _ids["c"]
    r = istemci.get(f"/calismalar/{c}/gonulluler")
    assert r.status_code == 200 and "01-001" in r.text and "02-001" not in r.text
    r = istemci.get(f"/calismalar/{c}/izlem")
    assert "IMV" in r.text and "SIV" not in r.text
    # DG-001 yalnizca T-02'de: T-01 arastirmacisi goremez
    assert istemci.get(f"/calismalar/{_ids['dg']}").status_code == 403
    _giris(istemci, "admin")
    r = istemci.get(f"/calismalar/{c}/gonulluler")
    assert "01-001" in r.text and "02-001" in r.text


def test_sponsor_merkez_detayi_kendi_calismalari(istemci):
    _giris(istemci, "sponsor")
    r = istemci.get(f"/merkezler/{_ids['m2']}")
    assert r.status_code == 200 and "S1-001" in r.text and "DG-001" not in r.text
    assert "hasta-yukle" not in r.text  # hasta havuzu yukleme sponsora kapali
    assert istemci.get(f"/merkezler/{_ids['m2']}/hasta-yukle").status_code == 403
    _giris(istemci, "admin")
    r = istemci.get(f"/merkezler/{_ids['m2']}")
    assert "S1-001" in r.text and "DG-001" in r.text


def test_cra_panosu_yalnizca_atandigi_calismalar(istemci):
    """CRA yalnizca S1-001 uyesi: pano sayilari ve listeler DG-001 icermez, hicbir baglanti 403 vermez."""
    _giris(istemci, "cra")
    r = istemci.get("/")
    assert r.status_code == 200 and "S1-001" in r.text and "DG-001" not in r.text
    assert re.search(r"Bana atanan ziyaretler <small[^>]*>1</small>", r.text)
    assert re.search(r"diğer ziyaretler <small[^>]*>1</small>", r.text)
    baglantilar = set(re.findall(r'href="(/(?:calismalar|gonulluler)/[^"#]+)"', r.text))
    assert baglantilar
    for b in baglantilar:
        assert istemci.get(b, follow_redirects=False).status_code != 403, b
    # kontrol listesinde proje ekibi maddesi (kisit etkin)
    db = oturum_fabrikasi()()
    c = db.get(Calisma, _ids["c"])
    tasarim = {m["etiket"]: m["tamam"] for m in kontrol_listesi(db, c)[CalismaDurumu.TASARIM]}
    assert tasarim["Proje ekibi atandı"] is True
    dg = db.get(Calisma, _ids["dg"])
    assert {m["etiket"]: m["tamam"] for m in kontrol_listesi(db, dg)[CalismaDurumu.TASARIM]}["Proje ekibi atandı"] is False
    db.close()


def test_genel_bakis_ve_liste_ayni_sayilari_gosterir(istemci):
    _giris(istemci, "admin")
    pano = istemci.get("/").text
    liste = istemci.get("/calismalar").text
    assert re.search(r"1 / 20", pano) and re.search(r">1/20<", liste)
