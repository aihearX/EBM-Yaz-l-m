"""Izlem dongusu, sapma kapatma, TMF belge indirme/surum zinciri, toplu kilit ve arastirmaci imzasi."""
import os
from datetime import date, timedelta

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    Belge,
    Calisma,
    CalismaDurumu,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    EImza,
    FormKaydi,
    Gonullu,
    GonulluDurumu,
    IzlemZiyareti,
    Kullanici,
    Merkez,
    ProtokolSapmasi,
    RiskUyarisi,
    Rol,
    Sorgu,
    Vizit,
)
from smartclinical.models import Form as CRF
from smartclinical.models.belge import MAKS_BELGE_BOYUTU
from smartclinical.models.tasarim import VizitTanimi
from smartclinical.services import yetki
from smartclinical.web import veri_islem
from smartclinical.web.belgeler import dosya_kontrol
from smartclinical.web.calismalar import kontrol_listesi
from tests.test_isletim import rotalari_bagla

PAROLA = "Test1234!xyz"


@pytest.fixture(scope="module")
def ortam(tmp_path_factory):
    rotalari_bagla()
    os.environ["SC_DOSYA_DIZINI"] = str(tmp_path_factory.mktemp("tmf"))
    from smartclinical.config import ayarlar

    ayarlar.cache_clear()
    sifirla()
    db = oturum_fabrikasi()()
    m1 = Merkez(kod="IZ-M1", ad="Ankara Üniversitesi", sehir="Ankara", kurum_tipi="universite")
    m2 = Merkez(kod="IZ-M2", ad="İzmir Şehir", sehir="İzmir", kurum_tipi="sehir")
    db.add_all([m1, m2])
    db.flush()
    kullanicilar = {
        "admin": (Rol.YONETICI, None, None), "py": (Rol.PROJE_YONETICISI, None, None), "cra": (Rol.CRA, None, None),
        "pi": (Rol.ARASTIRMACI, m1.id, None), "koor": (Rol.KOORDINATOR, m1.id, None), "veri": (Rol.VERI_YONETICISI, None, None),
        "sponsor": (Rol.SPONSOR, None, "Sponsor A"), "sponsor2": (Rol.SPONSOR, None, "Başka Kurum"),
    }
    for ad, (rol, mid, kurum) in kullanicilar.items():
        db.add(Kullanici(kullanici_adi=ad, ad_soyad=ad.title(), eposta=f"{ad}@t.local", parola_hash=yetki.parola_hashle(PAROLA),
                         rol=rol, merkez_id=mid, kurum=kurum))
    c = Calisma(kod="IZ-001", baslik="İzlem testi", kisa_ad="İzlem", tur=CalismaTuru.ILAC, sponsor="Sponsor A", terapotik_alan="Onkoloji",
                hedef_hasta=10, durum=CalismaDurumu.AKTIVASYON)
    db.add(c)
    db.flush()
    cm1 = CalismaMerkez(calisma_id=c.id, merkez_id=m1.id, merkez_no="01", durum="aktif", hedef_hasta=5, aktivasyon_tarihi=date.today() - timedelta(days=60))
    cm2 = CalismaMerkez(calisma_id=c.id, merkez_id=m2.id, merkez_no="02", durum="aktif", hedef_hasta=5, aktivasyon_tarihi=date.today() - timedelta(days=60))
    db.add_all([cm1, cm2])
    db.add_all([VizitTanimi(calisma_id=c.id, ad="Tarama", sira=0, gun=-14), VizitTanimi(calisma_id=c.id, ad="V1", sira=1, gun=0)])
    vs = CRF(calisma_id=c.id, kod="VS", ad="Vital bulgular", sira=1, durum="yayinda",
             alanlar=[{"kod": "SYSBP", "etiket": "Sistolik", "tip": "sayi", "cdash": "VS.VSORRES"}, {"kod": "VSDAT", "etiket": "Tarih", "tip": "tarih"}])
    olc = CRF(calisma_id=c.id, kod="ÖLÇÜM", ad="Ölçüm", sira=2, durum="yayinda", tekrarlayan=True,
              alanlar=[{"kod": "AĞIRLIK", "etiket": "Ağırlık", "tip": "sayi"}, {"kod": "AGIRLIK", "etiket": "Ağırlık (ASCII)", "tip": "sayi"}])
    db.add_all([vs, olc])
    db.flush()
    g1 = Gonullu(calisma_id=c.id, calisma_merkez_id=cm1.id, gonullu_no="01-001", durum=GonulluDurumu.RANDOMIZE,
                 onam_tarihi=date.today() - timedelta(days=30), randomizasyon_tarihi=date.today() - timedelta(days=20))
    g2 = Gonullu(calisma_id=c.id, calisma_merkez_id=cm2.id, gonullu_no="02-001", durum=GonulluDurumu.TEDAVIDE,
                 onam_tarihi=date.today() - timedelta(days=30))
    db.add_all([g1, g2])
    db.flush()
    v1 = Vizit(gonullu_id=g1.id, ad="V1", sira=1, planlanan=date.today() - timedelta(days=20), gerceklesen=date.today() - timedelta(days=20), durum="yapildi")
    db.add(v1)
    db.flush()
    fk1 = FormKaydi(gonullu_id=g1.id, form_id=vs.id, vizit_id=v1.id, veriler={"SYSBP": 120, "VSDAT": "2024-01-01"}, durum="sdv")
    fk2 = FormKaydi(gonullu_id=g1.id, form_id=olc.id, vizit_id=v1.id, tekrar_no=1, veriler={"AĞIRLIK": 70}, durum="tamamlandi")
    fk3 = FormKaydi(gonullu_id=g2.id, form_id=vs.id, veriler={"SYSBP": 130}, durum="sdv")
    db.add_all([fk1, fk2, fk3])
    db.flush()
    db.add(Sorgu(form_kaydi_id=fk3.id, alan="SYSBP", soru="Kaynakla uyuşmuyor", kaynak="manuel"))
    db.add(RiskUyarisi(calisma_id=c.id, calisma_merkez_id=cm1.id, kri_kod="SORGU_ORANI", deger=0.4, esik=0.3, seviye="aksiyon",
                       mesaj="Sorgu oranı yüksek", durum="acik"))
    db.commit()
    kimlik = {"c": c.id, "cm1": cm1.id, "cm2": cm2.id, "g1": g1.id, "g2": g2.id, "fk1": fk1.id, "fk2": fk2.id, "fk3": fk3.id, "m1": m1.id, "m2": m2.id}
    db.close()
    with TestClient(app) as tc:
        yield tc, kimlik


def _giris(c, kadi):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"


def _db():
    return oturum_fabrikasi()()


# --- Izlem ------------------------------------------------------------------

def test_ziyaret_raporu_ve_py_onayi(ortam):
    tc, k = ortam
    cid = k["c"]
    _giris(tc, "cra")
    r = tc.post(f"/calismalar/{cid}/izlem/ziyaret", data={"calisma_merkez_id": k["cm1"], "tip": "SIV", "planlanan": date.today().isoformat()},
                follow_redirects=False)
    assert r.status_code == 303 and "/izlem/ziyaret/" in r.headers["location"]
    zid = int(r.headers["location"].rsplit("/", 1)[1])
    assert tc.get(r.headers["location"]).status_code == 200
    db = _db()
    c = db.get(Calisma, cid)
    assert not next(m for m in kontrol_listesi(db, c)[CalismaDurumu.AKTIVASYON] if "SIV" in m["etiket"])["tamam"]
    db.close()
    r = tc.post(f"/calismalar/{cid}/izlem/ziyaret/{zid}", data={"gerceklesen": date.today().isoformat(), "katilimcilar": "PI, koordinatör",
                "sdv_orani": "50", "rapor": "ISF ve onamlar incelendi.", "kontrol": ["onam", "isf"]}, follow_redirects=False)
    assert r.status_code == 303
    r = tc.post(f"/calismalar/{cid}/izlem/ziyaret/{zid}/bulgu", data={"konu": "Onam formunda tarih eksik", "onem": "major",
                "aksiyon": "Düzeltme notu", "sorumlu": "Koordinatör", "hedef_tarih": (date.today() + timedelta(days=14)).isoformat()},
                follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    z = db.get(IzlemZiyareti, zid)
    assert z.gerceklesen == date.today() and z.sdv_orani == 50 and z.kontrol_listesi == {"onam": True, "isf": True, "ilac": False, "sapma": False}
    assert z.bulgular and z.bulgular[0]["onem"] == "major" and not z.bulgular[0]["kapali"] and z.durum == "raporlandi"
    c = db.get(Calisma, cid)
    assert next(m for m in kontrol_listesi(db, c)[CalismaDurumu.AKTIVASYON] if "SIV" in m["etiket"])["tamam"]
    db.close()
    # CRA onaylayamaz, PY yanlis parolayla onaylayamaz, dogru parolayla onaylar
    assert tc.post(f"/calismalar/{cid}/izlem/ziyaret/{zid}/onay", data={"parola": PAROLA}, follow_redirects=False).status_code == 403
    _giris(tc, "py")
    tc.post(f"/calismalar/{cid}/izlem/ziyaret/{zid}/onay", data={"parola": "yanlis"}, follow_redirects=False)
    db = _db()
    assert db.get(IzlemZiyareti, zid).rapor_onay is None
    db.close()
    r = tc.post(f"/calismalar/{cid}/izlem/ziyaret/{zid}/onay", data={"parola": PAROLA}, follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    z = db.get(IzlemZiyareti, zid)
    assert z.rapor_onay and z.onaylayan.kullanici_adi == "py" and z.durum == "onaylandi"
    imza = db.execute(select(EImza).where(EImza.varlik == "izlem_ziyareti", EImza.varlik_id == zid)).scalar_one()
    assert imza.anlam == "Ziyaret raporu onaylandı" and len(imza.icerik_hash) == 64
    db.close()
    # onaylanmis rapor degismez
    tc.post(f"/calismalar/{cid}/izlem/ziyaret/{zid}", data={"gerceklesen": "", "rapor": "değişti"}, follow_redirects=False)
    db = _db()
    assert db.get(IzlemZiyareti, zid).rapor == "ISF ve onamlar incelendi."
    db.close()
    sayfa = tc.get(f"/calismalar/{cid}/izlem/ziyaret/{zid}").text
    assert "Rapor onaylı" in sayfa and "window.print()" in sayfa


def test_acik_bulgu_sonraki_ziyarete_tasinir(ortam):
    tc, k = ortam
    cid = k["c"]
    _giris(tc, "cra")
    r = tc.post(f"/calismalar/{cid}/izlem/ziyaret", data={"calisma_merkez_id": k["cm1"], "tip": "IMV", "planlanan": date.today().isoformat()},
                follow_redirects=False)
    zid = int(r.headers["location"].rsplit("/", 1)[1])
    db = _db()
    z = db.get(IzlemZiyareti, zid)
    assert len(z.bulgular) == 1 and z.bulgular[0]["konu"] == "Onam formunda tarih eksik" and z.bulgular[0]["tasindi_ziyaret_id"]
    db.close()
    # baska merkezin ziyaretine tasinmaz
    r = tc.post(f"/calismalar/{cid}/izlem/ziyaret", data={"calisma_merkez_id": k["cm2"], "tip": "IMV", "planlanan": date.today().isoformat()},
                follow_redirects=False)
    db = _db()
    assert not db.get(IzlemZiyareti, int(r.headers["location"].rsplit("/", 1)[1])).bulgular
    db.close()
    # bulgu kapatilinca bir sonraki ziyarete tasinmaz
    assert tc.post(f"/calismalar/{cid}/izlem/ziyaret/{zid}/bulgu/0/kapat", data={"not": "Düzeltildi"}, follow_redirects=False).status_code == 303
    r = tc.post(f"/calismalar/{cid}/izlem/ziyaret", data={"calisma_merkez_id": k["cm1"], "tip": "IMV", "planlanan": date.today().isoformat()},
                follow_redirects=False)
    db = _db()
    assert not db.get(IzlemZiyareti, int(r.headers["location"].rsplit("/", 1)[1])).bulgular
    db.close()


def test_aksiyon_uyarisindan_tetiklenmis_ziyaret(ortam):
    tc, k = ortam
    cid = k["c"]
    _giris(tc, "cra")
    db = _db()
    u = db.execute(select(RiskUyarisi).where(RiskUyarisi.calisma_id == cid)).scalar_one()
    uid = u.id
    db.close()
    sayfa = tc.get(f"/calismalar/{cid}/izlem").text
    assert f"/izlem/tetikle/{uid}" in sayfa
    r = tc.post(f"/calismalar/{cid}/izlem/tetikle/{uid}", follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    z = db.execute(select(IzlemZiyareti).where(IzlemZiyareti.tetikleyen_uyari_id == uid)).scalar_one()
    assert z.tip == "tetiklenmis" and z.calisma_merkez_id == k["cm1"] and db.get(RiskUyarisi, uid).durum == "inceleniyor"
    db.close()
    # ikinci tiklama yeni ziyaret acmaz
    tc.post(f"/calismalar/{cid}/izlem/tetikle/{uid}", follow_redirects=False)
    db = _db()
    assert db.scalar(select(IzlemZiyareti.id).where(IzlemZiyareti.tetikleyen_uyari_id == uid).limit(2).offset(1)) is None
    db.close()
    assert "ziyaret planlandı" in tc.get(f"/calismalar/{cid}/izlem").text


def test_sapma_kapatma_majorde_etik_bildirim_zorunlu(ortam):
    tc, k = ortam
    cid = k["c"]
    _giris(tc, "cra")
    r = tc.post(f"/calismalar/{cid}/izlem/sapma", data={"calisma_merkez_id": k["cm1"], "gonullu_id": k["g1"], "tarih": date.today().isoformat(),
                "kategori": "onam", "onem": "major", "aciklama": "Yeni onam sürümü imzalatılmadı"}, follow_redirects=False)
    assert r.status_code == 303 and "/izlem/sapma/" in r.headers["location"]
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    assert tc.get(f"/calismalar/{cid}/izlem/sapma/{sid}").status_code == 200
    veri = {"kok_neden": "Sürüm takibi yapılmadı", "duzeltici_faaliyet": "Onam takip listesi", "hedef_tarih": date.today().isoformat(), "kapat": "1"}
    tc.post(f"/calismalar/{cid}/izlem/sapma/{sid}", data=veri, follow_redirects=False)
    db = _db()
    s = db.get(ProtokolSapmasi, sid)
    assert not s.kapali and s.kapanis_tarihi is None
    db.close()
    assert "etik kurul bildirim tarihi" in tc.get(f"/calismalar/{cid}/izlem/sapma/{sid}").text
    db = _db()
    py_id = db.execute(select(Kullanici.id).where(Kullanici.kullanici_adi == "py")).scalar_one()
    db.close()
    tc.post(f"/calismalar/{cid}/izlem/sapma/{sid}", data=dict(veri, etik_bildirim=date.today().isoformat(), sorumlu_id=py_id), follow_redirects=False)
    db = _db()
    s = db.get(ProtokolSapmasi, sid)
    assert s.kapali and s.kapanis_tarihi == date.today() and s.sorumlu_id == py_id and s.etik_bildirim == date.today()
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "protokol_sapmasi", DenetimKaydi.varlik_id == sid)
                       .order_by(DenetimKaydi.id.desc())).scalars().first()
    assert kayit.eski["kapali"] is False and kayit.yeni["kapali"] is True
    db.close()
    # minor sapma etik bildirim olmadan kapanir
    r = tc.post(f"/calismalar/{cid}/izlem/sapma", data={"calisma_merkez_id": k["cm2"], "tarih": date.today().isoformat(),
                "kategori": "vizit", "onem": "minor", "aciklama": "Pencere dışı"}, follow_redirects=False)
    sid2 = int(r.headers["location"].rsplit("/", 1)[1])
    tc.post(f"/calismalar/{cid}/izlem/sapma/{sid2}", data={"kok_neden": "Hasta gecikti", "duzeltici_faaliyet": "Hatırlatma", "kapat": "1"}, follow_redirects=False)
    db = _db()
    assert db.get(ProtokolSapmasi, sid2).kapali
    db.close()


def test_merkez_rolu_yalnizca_kendi_merkezini_gorur(ortam):
    tc, k = ortam
    cid = k["c"]
    _giris(tc, "pi")
    sayfa = tc.get(f"/calismalar/{cid}/izlem")
    assert sayfa.status_code == 200 and "02 – İzmir" not in sayfa.text
    db = _db()
    z2 = db.execute(select(IzlemZiyareti).where(IzlemZiyareti.calisma_merkez_id == k["cm2"])).scalars().first()
    s2 = db.execute(select(ProtokolSapmasi).where(ProtokolSapmasi.calisma_merkez_id == k["cm2"])).scalars().first()
    db.close()
    assert tc.get(f"/calismalar/{cid}/izlem/ziyaret/{z2.id}").status_code == 403
    assert tc.get(f"/calismalar/{cid}/izlem/sapma/{s2.id}").status_code == 403
    # merkez rolu ziyaret planlayamaz (rbm.yonet yok)
    assert tc.post(f"/calismalar/{cid}/izlem/ziyaret", data={"calisma_merkez_id": k["cm1"], "tip": "IMV", "planlanan": "2030-01-01"},
                   follow_redirects=False).status_code == 403


# --- TMF --------------------------------------------------------------------

def _pdf(n: int = 2000) -> bytes:
    return b"%PDF-1.4\n" + b"0" * n + b"\n%%EOF"


def test_belge_yukleme_kontrolleri():
    assert dosya_kontrol("a.exe", "application/octet-stream", b"MZ") is not None
    assert dosya_kontrol("a.pdf", "application/pdf", b"MZ....") is not None  # icerik uyusmuyor
    assert dosya_kontrol("a.pdf", "text/plain", _pdf()) is not None  # bildirilen tur uyusmuyor
    assert dosya_kontrol("a.pdf", "application/pdf", b"%PDF" + b"0" * MAKS_BELGE_BOYUTU) is not None  # 25 MB ustu
    assert dosya_kontrol("a.pdf", "application/pdf", _pdf()) is None
    assert dosya_kontrol("rapor.docx", "application/octet-stream", b"PK\x03\x04...") is None
    assert dosya_kontrol("a.png", "image/png", b"\x89PNG\r\n") is None


def test_belge_indirme_surum_zinciri_ve_yetki(ortam):
    tc, k = ortam
    cid = k["c"]
    _giris(tc, "cra")
    r = tc.post(f"/calismalar/{cid}/belgeler", data={"tmf_bolge": "04", "ad": "Etik kurul onayı", "versiyon": "1.0"},
                files={"dosya": ("onay.pdf", _pdf(), "application/pdf")}, follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    b1 = db.execute(select(Belge).where(Belge.calisma_id == cid, Belge.ad == "Etik kurul onayı")).scalar_one()
    assert b1.sha256 and b1.durum == "taslak" and b1.dosya_yolu
    db.close()
    # izin disi uzanti ve icerik reddedilir
    tc.post(f"/calismalar/{cid}/belgeler", data={"tmf_bolge": "04", "ad": "Zararlı"}, files={"dosya": ("x.exe", b"MZ", "application/octet-stream")},
            follow_redirects=False)
    tc.post(f"/calismalar/{cid}/belgeler", data={"tmf_bolge": "04", "ad": "Sahte"}, files={"dosya": ("x.pdf", b"hello", "application/pdf")},
            follow_redirects=False)
    db = _db()
    assert db.scalar(select(Belge.id).where(Belge.ad.in_(("Zararlı", "Sahte")))) is None
    db.close()
    # indirme: yetkili 200 + denetim 'goruntule'
    r = tc.get(f"/calismalar/{cid}/belgeler/{b1.id}/indir")
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment") and r.content.startswith(b"%PDF")
    db = _db()
    assert db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "goruntule", DenetimKaydi.varlik == "belge",
                                                 DenetimKaydi.varlik_id == b1.id)).scalars().first()
    db.close()
    # sponsor (ayni kurum) indirir, baska kurumun sponsoru 403
    _giris(tc, "sponsor")
    assert tc.get(f"/calismalar/{cid}/belgeler/{b1.id}/indir").status_code == 200
    _giris(tc, "sponsor2")
    assert tc.get(f"/calismalar/{cid}/belgeler/{b1.id}/indir").status_code == 403
    assert tc.get(f"/calismalar/{cid}/belgeler").status_code == 403
    # merkez belgesi: baska merkezin arastirmacisi 403
    _giris(tc, "cra")
    tc.post(f"/calismalar/{cid}/belgeler", data={"tmf_bolge": "05", "ad": "Merkez sözleşmesi", "merkez_id": k["m2"]},
            files={"dosya": ("sozlesme.pdf", _pdf(), "application/pdf")}, follow_redirects=False)
    db = _db()
    b_m2 = db.execute(select(Belge).where(Belge.ad == "Merkez sözleşmesi")).scalar_one()
    db.close()
    _giris(tc, "pi")
    assert tc.get(f"/calismalar/{cid}/belgeler/{b_m2.id}/indir").status_code == 403
    assert tc.get(f"/calismalar/{cid}/belgeler/{b1.id}/indir").status_code == 200
    sayfa = tc.get(f"/calismalar/{cid}/belgeler").text
    assert "Merkez sözleşmesi" not in sayfa and "Etik kurul onayı" in sayfa
    # yeni surum: onceki eskir, zincir kurulur, eskimis belgeler katlanir
    _giris(tc, "cra")
    tc.post(f"/calismalar/{cid}/belgeler/{b1.id}/onayla", data={"parola": PAROLA}, follow_redirects=False)
    tc.post(f"/calismalar/{cid}/belgeler", data={"tmf_bolge": "04", "ad": "Etik kurul onayı", "versiyon": "2.0"},
            files={"dosya": ("onay_v2.pdf", _pdf(3000), "application/pdf")}, follow_redirects=False)
    db = _db()
    surumler = db.execute(select(Belge).where(Belge.ad == "Etik kurul onayı").order_by(Belge.id)).scalars().all()
    assert len(surumler) == 2 and surumler[0].durum == "eskimis" and surumler[1].onceki_id == surumler[0].id and surumler[1].durum == "taslak"
    db.close()
    sayfa = tc.get(f"/calismalar/{cid}/belgeler").text
    assert "Eskimiş sürümler (1)" in sayfa and "TMF tamlığı" in sayfa
    # merkez bazli ISF gorunumu
    sayfa = tc.get(f"/calismalar/{cid}/belgeler?merkez_id={k['m1']}").text
    assert "Merkez sözleşmesi" not in sayfa and "Merkez dosyası (ISF)" in sayfa


# --- Veri yonetimi kapanisi -------------------------------------------------

def test_arastirmaci_imzasi_ve_toplu_kilit(ortam):
    tc, k = ortam
    cid = k["c"]
    _giris(tc, "veri")
    assert tc.get(f"/calismalar/{cid}/veri/kilit").status_code == 200
    assert tc.get(f"/calismalar/{cid}/veri/imza").status_code == 200
    # PI imzasi yokken hicbir kayit kilitlenmez
    tc.post(f"/calismalar/{cid}/veri/kilit", data={"kapsam": "calisma", "parola": PAROLA}, follow_redirects=False)
    db = _db()
    assert db.get(FormKaydi, k["fk1"]).durum == "sdv"
    db.close()
    # veri yoneticisi imza atamaz; arastirmaci kendi merkezinin gonullusunu imzalar
    assert tc.post(f"/calismalar/{cid}/veri/imza/{k['g1']}", data={"parola": PAROLA}, follow_redirects=False).status_code == 403
    _giris(tc, "pi")
    assert tc.post(f"/calismalar/{cid}/veri/imza/{k['g2']}", data={"parola": PAROLA}, follow_redirects=False).status_code == 403
    r = tc.post(f"/calismalar/{cid}/veri/imza/{k['g1']}", data={"parola": PAROLA}, follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    g1 = db.get(Gonullu, k["g1"])
    assert veri_islem.imza_durumu(db, g1)[0] == "imzali"
    imza = db.execute(select(EImza).where(EImza.varlik == "gonullu", EImza.varlik_id == g1.id)).scalar_one()
    assert imza.anlam == veri_islem.PI_IMZA_ANLAMI
    db.close()
    assert "İmzalı" in tc.get(f"/calismalar/{cid}/veri/imza").text
    # toplu kilit: fk1 (sdv + imzali) kilitlenir; fk2 (sdv yok) ve fk3 (acik sorgu, imza yok) raporlanir
    _giris(tc, "veri")
    sayfa = tc.get(f"/calismalar/{cid}/veri/kilit").text
    assert "SDV yapılmadı" in sayfa and "Açık sorgu" in sayfa
    r = tc.post(f"/calismalar/{cid}/veri/kilit", data={"kapsam": "calisma", "parola": PAROLA}, follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    assert db.get(FormKaydi, k["fk1"]).durum == "kilitli" and db.get(FormKaydi, k["fk2"]).durum == "tamamlandi" and db.get(FormKaydi, k["fk3"]).durum == "sdv"
    kilit_imza = db.execute(select(EImza).where(EImza.anlam == "Toplu veri kilidi")).scalar_one()
    assert kilit_imza.varlik == "calisma" and kilit_imza.varlik_id == cid
    db.close()
    assert "1 form kaydı kilitlendi" in tc.get(f"/calismalar/{cid}/veri/kilit").text
    # merkez kapsami: yanlis parola kilitlemez
    tc.post(f"/calismalar/{cid}/veri/kilit", data={"kapsam": "merkez", "kapsam_id": k["cm2"], "parola": "yanlis"}, follow_redirects=False)
    db = _db()
    assert db.get(FormKaydi, k["fk3"]).durum == "sdv"
    db.close()
    # kilit acma: gerekcesiz olmaz, gerekceli olur ve denetim izinde eski/yeni + gerekce
    tc.post(f"/calismalar/{cid}/veri/kilit-ac/{k['fk1']}", data={"gerekce": "  "}, follow_redirects=False)
    db = _db()
    assert db.get(FormKaydi, k["fk1"]).durum == "kilitli"
    db.close()
    tc.post(f"/calismalar/{cid}/veri/kilit-ac/{k['fk1']}", data={"gerekce": "Kaynak belge düzeltmesi"}, follow_redirects=False)
    db = _db()
    fk1 = db.get(FormKaydi, k["fk1"])
    assert fk1.durum == "tamamlandi" and fk1.kilit_zamani is None
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "kilit_ac")).scalar_one()
    assert kayit.eski == {"durum": "kilitli"} and kayit.yeni == {"durum": "tamamlandi"} and kayit.gerekce == "Kaynak belge düzeltmesi"
    db.close()
    # CRA kilit acamaz
    _giris(tc, "cra")
    assert tc.post(f"/calismalar/{cid}/veri/kilit-ac/{k['fk1']}", data={"gerekce": "x"}, follow_redirects=False).status_code == 403


def test_imzadan_sonra_degisen_kayit_yenilenmeli(ortam):
    tc, k = ortam
    cid = k["c"]
    db = _db()
    fk1 = db.get(FormKaydi, k["fk1"])
    fk1.veriler = dict(fk1.veriler, SYSBP=125)
    db.commit()
    assert veri_islem.imza_durumu(db, db.get(Gonullu, k["g1"]))[0] == "yenilenmeli"
    db.close()
    _giris(tc, "pi")
    assert "İmza yenilenmeli" in tc.get(f"/calismalar/{cid}/veri/imza").text
    tc.post(f"/calismalar/{cid}/veri/imza/{k['g1']}", data={"parola": PAROLA}, follow_redirects=False)
    db = _db()
    assert veri_islem.imza_durumu(db, db.get(Gonullu, k["g1"]))[0] == "imzali"
    db.close()


def test_sorgu_toplu_kapatma_ve_csv(ortam):
    tc, k = ortam
    cid = k["c"]
    _giris(tc, "cra")
    sayfa = tc.get(f"/calismalar/{cid}/veri").text
    assert "Seçilenleri kapat" in sayfa and "sorgular.csv" in sayfa and "Toplu kilit" not in sayfa  # CRA kilitleyemez
    r = tc.get(f"/calismalar/{cid}/veri/sorgular.csv?durum=acik")
    assert r.status_code == 200 and r.content.startswith("﻿".encode("utf-8")) and b"GONULLU;MERKEZ;FORM" in r.content
    assert "02-001;02;VS" in r.text
    db = _db()
    sid = db.scalar(select(Sorgu.id).where(Sorgu.durum == "acik"))
    db.close()
    r = tc.post(f"/calismalar/{cid}/veri/sorgu-toplu", data={"sorgu_id": [sid], "islem": "kapat"}, follow_redirects=False)
    assert r.status_code == 303
    db = _db()
    s = db.get(Sorgu, sid)
    assert s.durum == "kapali" and s.kapanis is not None
    db.close()
    assert "02-001" not in tc.get(f"/calismalar/{cid}/veri/sorgular.csv?durum=acik").text
    for yol, baslik in (("/gonulluler.csv", "GONULLU;MERKEZ;DURUM"), ("/izlem/ziyaretler.csv", "MERKEZ;TIP;PLANLANAN"),
                        ("/izlem/sapmalar.csv", "TARIH;MERKEZ;GONULLU")):
        r = tc.get(f"/calismalar/{cid}{yol}")
        assert r.status_code == 200 and baslik in r.text and r.headers["content-disposition"].startswith("attachment"), yol
    assert "Başlatma ziyareti" in tc.get(f"/calismalar/{cid}/izlem/ziyaretler.csv").text
    db = _db()
    listeler = {d.yeni.get("liste") for d in db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "disa_aktar")).scalars()}
    assert {"sorgular", "gonulluler", "ziyaretler", "sapmalar"} <= listeler
    db.close()
    # sponsor liste CSV'lerini alamaz (veri sekmesi kapali)
    _giris(tc, "sponsor")
    assert tc.get(f"/calismalar/{cid}/veri/sorgular.csv").status_code == 403
