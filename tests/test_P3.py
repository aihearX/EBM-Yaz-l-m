"""P3 paketi: rota baglama yardimcisi, API belgeleri oturum kosulu, /saglik anonim yaniti, gece isleri,
hasta saklama betigi ve dokumantasyon izlenebilirligi (TM-001 satirlari kodla eslesir)."""
import os
import re
from datetime import date, timedelta
from pathlib import Path

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    AdversOlay,
    Calisma,
    CalismaDurumu,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    EslestirmeSonucu,
    Gonullu,
    Hasta,
    Kullanici,
    Merkez,
    Rol,
)
from smartclinical.models._ortak import simdi
from smartclinical.scripts import gece_isleri, hasta_saklama
from smartclinical.services import yetki
from smartclinical.web import belgeler as belgeler_web
from smartclinical.web import izlem as izlem_web
from smartclinical.web import veri_islem as veri_web

PAROLA = "Test1234!xyz"
KOK = Path(__file__).resolve().parent.parent

# calismalar.py'de kalan eski rotalar; entegrasyonda silinecek (bkz. entegrasyon notu). Testte yeni modullerin
# ayni yollari devralmasi icin kaldirilir.
ESKI_ROTALAR = {
    ("/calismalar/{calisma_id}/izlem", "GET"), ("/calismalar/{calisma_id}/izlem/sapma", "POST"),
    ("/calismalar/{calisma_id}/izlem/ziyaret", "POST"), ("/calismalar/{calisma_id}/belgeler", "GET"),
    ("/calismalar/{calisma_id}/belgeler", "POST"), ("/calismalar/{calisma_id}/belgeler/{belge_id}/onayla", "POST"),
}


def _eski_rotalari_sil(router) -> None:
    """Ic ice router'larda calismalar modulunun eski kopyalarini kaldirir (FastAPI include_router referansla tutar)."""
    kalan, degisti = [], False
    for r in router.routes:
        if hasattr(r, "original_router"):
            _eski_rotalari_sil(r.original_router)
            kalan.append(r)
        elif (getattr(r, "endpoint", None) is not None and r.endpoint.__module__ == "smartclinical.web.calismalar"
              and any((r.path, m) in ESKI_ROTALAR for m in r.methods)):
            degisti = True
        else:
            kalan.append(r)
    if degisti:
        router.routes[:] = kalan
        if hasattr(router, "_mark_routes_changed"):
            router._mark_routes_changed()


def tum_rotalar(router=None, onek: str = "") -> list:
    """Ic ice router'lardaki tum rotalar: (tam yol, rota) listesi; include prefix'i yola eklenir."""
    sonuc = []
    for r in (router or app.router).routes:
        if hasattr(r, "original_router"):
            sonuc.extend(tum_rotalar(r.original_router, onek + (getattr(r.include_context, "prefix", "") or "")))
        else:
            sonuc.append((onek + getattr(r, "path", ""), r))
    return sonuc


def rotalari_bagla():
    """izlem, belgeler ve veri_islem router'larini uygulamaya ekler; calismalar'daki eski kopyalari kaldirir."""
    _eski_rotalari_sil(app.router)
    moduller = {getattr(getattr(r, "endpoint", None), "__module__", "") for _, r in tum_rotalar()}
    for mod in (izlem_web, belgeler_web, veri_web):
        if mod.__name__ not in moduller:
            app.include_router(mod.router)


@pytest.fixture(scope="module")
def istemci():
    rotalari_bagla()
    sifirla()
    db = oturum_fabrikasi()()
    m1 = Merkez(kod="P3-M1", ad="Test Üniversitesi", sehir="Ankara", kurum_tipi="universite")
    m2 = Merkez(kod="P3-M2", ad="Boş Merkez", sehir="İzmir", kurum_tipi="sehir")
    db.add_all([m1, m2])
    db.flush()
    db.add_all([
        Kullanici(kullanici_adi="admin", ad_soyad="Admin", eposta="a@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.YONETICI),
        Kullanici(kullanici_adi="pi", ad_soyad="Araştırmacı", eposta="p@t.local", parola_hash=yetki.parola_hashle(PAROLA),
                  rol=Rol.ARASTIRMACI, merkez_id=m1.id),
    ])
    c = Calisma(kod="P3-GECE", baslik="Gece işleri", kisa_ad="Gece", tur=CalismaTuru.ILAC, sponsor="S", terapotik_alan="Onkoloji",
                hedef_hasta=10, durum=CalismaDurumu.KAYIT, baslangic=date.today() - timedelta(days=120))
    kapali = Calisma(kod="P3-ARSIV", baslik="Kapalı", kisa_ad="Kapalı", tur=CalismaTuru.ILAC, sponsor="S", terapotik_alan="Onkoloji",
                     hedef_hasta=10, durum=CalismaDurumu.ARSIV)
    db.add_all([c, kapali])
    db.flush()
    cm = CalismaMerkez(calisma_id=c.id, merkez_id=m1.id, merkez_no="01", durum="aktif", hedef_hasta=5,
                       aktivasyon_tarihi=date.today() - timedelta(days=90))
    cm2 = CalismaMerkez(calisma_id=kapali.id, merkez_id=m2.id, merkez_no="01", durum="kapali", hedef_hasta=5)
    db.add_all([cm, cm2])
    db.flush()
    cm2.guncelleme = simdi() - timedelta(days=400)
    h_bagli = Hasta(merkez_id=m1.id, kayit_no="BAGLI0001", dogum_yili=1970, cinsiyet="K", kaynak="manuel")
    h_acik = Hasta(merkez_id=m1.id, kayit_no="ACIK00001", dogum_yili=1975, cinsiyet="E", kaynak="manuel")
    h_eski = Hasta(merkez_id=m2.id, kayit_no="ESKI00001", dogum_yili=1960, cinsiyet="E", kaynak="manuel",
                   metinler=[{"tur": "epikriz", "metin": "kimliksiz metin"}])
    db.add_all([h_bagli, h_acik, h_eski])
    db.flush()
    db.add(EslestirmeSonucu(calisma_id=kapali.id, hasta_id=h_eski.id, skor=0.5, karar="olasi", kriter_sonuclari=[], model_surumu="kural"))
    g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, hasta_id=h_bagli.id, gonullu_no="01-001", onam_tarihi=date.today() - timedelta(days=60),
                randomizasyon_tarihi=date.today() - timedelta(days=55))
    db.add(g)
    db.flush()
    db.add(AdversOlay(gonullu_id=g.id, terim="Ateş", baslangic=date.today() - timedelta(days=20), siddet="3", nedensellik="olasi", ciddi=True,
                      ciddiyet_olcutu="hastaneye_yatis", farkindalik_tarihi=date.today() - timedelta(days=20)))
    db.commit()
    db.close()
    with TestClient(app) as tc:
        yield tc


def _giris(c, kadi):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def test_api_belgeleri_oturum_ister(istemci):
    istemci.cookies.clear()
    r = istemci.get("/api/belgeler", follow_redirects=False)
    assert r.status_code in (303, 401)
    r = istemci.get("/api/openapi.json", follow_redirects=False)
    assert r.status_code in (303, 401)
    assert istemci.get("/docs").status_code == 404
    _giris(istemci, "admin")
    r = istemci.get("/api/belgeler")
    assert r.status_code == 200 and "/api/v1/calismalar" in r.text
    assert "paths" in istemci.get("/api/openapi.json").json()


def test_saglik_anonim_surum_vermez(istemci):
    istemci.cookies.clear()
    for yol in ("/saglik", "/api/v1/saglik"):
        veri = istemci.get(yol).json()
        assert veri == {"durum": "ok"}, yol
    assert istemci.get("/api/v1/surum", follow_redirects=False).status_code == 401
    _giris(istemci, "admin")
    assert "surum" in istemci.get("/api/v1/surum").json()


def test_gece_isleri_aktif_calismalar(istemci):
    db = oturum_fabrikasi()()
    sonuclar = gece_isleri.calistir(db)
    kodlar = {s["calisma"] for s in sonuclar}
    assert "P3-GECE" in kodlar and "P3-ARSIV" not in kodlar
    s = next(x for x in sonuclar if x["calisma"] == "P3-GECE")
    assert s["sae_bekleyen"] == 1 and s["sae_gecikmis"] == 1 and s["tahmin_merkez"] == 1
    cm = db.execute(select(CalismaMerkez).join(Calisma).where(Calisma.kod == "P3-GECE")).scalar_one()
    assert cm.tahmini_kazanim is not None and cm.risk_puani is not None
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "zamanlanmis")).scalars().all()
    assert kayit and kayit[-1].yeni["is_"] == "gece_isleri"
    # kuru calisma yazmaz
    onceki = db.scalar(select(DenetimKaydi.id).order_by(DenetimKaydi.id.desc()).limit(1))
    gece_isleri.calistir(db, kuru=True)
    assert db.scalar(select(DenetimKaydi.id).order_by(DenetimKaydi.id.desc()).limit(1)) == onceki
    db.close()


def test_hasta_saklama(istemci):
    db = oturum_fabrikasi()()
    # kuru calisma: aday belirlenir ama silinmez
    s = hasta_saklama.calistir(db, ay=6, kuru=True)
    assert s["silinen"] == 1
    assert db.scalar(select(Hasta.id).where(Hasta.kayit_no == "ESKI00001")) is not None
    s = hasta_saklama.calistir(db, ay=6)
    assert s["silinen"] == 1
    assert db.scalar(select(Hasta.id).where(Hasta.kayit_no == "ESKI00001")) is None
    assert db.scalar(select(EslestirmeSonucu.id)) is None
    # acik calismanin merkezindeki kayit ve gonulluye bagli kayit kalir
    assert db.scalar(select(Hasta.id).where(Hasta.kayit_no == "ACIK00001")) is not None
    # veri sahibi talebi: bagli kayit silinmez, kisitlanir; bagsiz kayit silinir
    s = hasta_saklama.calistir(db, kayit_no="BAGLI0001")
    assert s == {"silinen": 0, "kisitlanan": 1, "atlanan": 0}
    h = db.execute(select(Hasta).where(Hasta.kayit_no == "BAGLI0001")).scalar_one()
    assert h.kaynak == "kisitli" and h.metinler is None
    s = hasta_saklama.calistir(db, kayit_no="ACIK00001")
    assert s["silinen"] == 1
    islemler = [d.islem for d in db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "hasta")).scalars()]
    assert "sil" in islemler and "kisitla" in islemler
    # denetim kaydinda takma ad yok
    for d in db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "hasta")).scalars():
        assert "kayit_no" not in (d.yeni or {})
    db.close()


def _test_fonksiyonlari(dosya: Path) -> set[str]:
    return set(re.findall(r"^def (test_\w+)", dosya.read_text(encoding="utf-8"), re.M))


def test_izlenebilirlik_matrisi_kodla_eslesir():
    """TM-001'deki her test ve rota referansi depoda bulunmali; belgelerde surum/tarih damgasi olmamali."""
    rotalari_bagla()
    metin = (KOK / "docs/validasyon/TM-001_izlenebilirlik_matrisi.md").read_text(encoding="utf-8")
    uygulama_rotalari = {yol for yol, _ in tum_rotalar()}
    for ref in re.findall(r"`(tests/test_\w+\.py)(?:::(test_\w+))?`", metin):
        dosya, fonk = ref
        assert (KOK / dosya).exists(), dosya
        if fonk:
            assert fonk in _test_fonksiyonlari(KOK / dosya), f"{dosya}::{fonk}"
    for betik in re.findall(r"`(smartclinical/[\w/]+\.py)`", metin):
        assert (KOK / betik).exists(), betik
    for rota in re.findall(r"`((?:GET|POST) /[^`]+)`", metin):
        yol = rota.split(" ", 1)[1]
        assert yol in uygulama_rotalari, rota
    damga = re.compile(r"\bv\d+\.\d+\.\d+\b|Sürüm \d|\b20\d\d-\d\d(-\d\d)?\b")
    for d in list((KOK / "docs/validasyon").glob("*.md")) + [KOK / "docs/gelistirme.md", KOK / "docs/api.md", KOK / "deploy/KURULUM.md"]:
        icerik = d.read_text(encoding="utf-8")
        assert not damga.search(icerik), f"{d.name}: surum/tarih damgasi"
        for yok in ("csv_sablonu.xlsx", "TOTP", "Yönetim → Entegrasyon", "03:00", "otomatik uygulanır", "SMTP"):
            assert yok not in icerik, f"{d.name}: {yok}"
