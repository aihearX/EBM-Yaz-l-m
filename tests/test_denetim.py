import os
import threading

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from smartclinical.db import Taban, oturum_fabrikasi, sifirla
from smartclinical.models import DenetimKaydi, EImza, Kullanici, Rol
from smartclinical.models.denetim import DenetimZincir
from smartclinical.services import denetim, yetki


@pytest.fixture
def db():
    sifirla()
    s = oturum_fabrikasi()()
    k = Kullanici(kullanici_adi="u", ad_soyad="U", eposta="u@t", parola_hash=yetki.parola_hashle("Parola1234x"), rol=Rol.CRA)
    s.add(k)
    s.commit()
    yield s, k
    s.close()


def test_zincir_gecerli(db):
    s, k = db
    for i in range(5):
        denetim.kaydet(s, k, "guncelle", "calisma", i, eski={"a": i}, yeni={"a": i + 1})
    s.commit()
    assert denetim.zinciri_dogrula(s) == (True, None)


def test_zincir_bozulma_tespiti(db):
    s, k = db
    for i in range(4):
        denetim.kaydet(s, k, "guncelle", "calisma", i, yeni={"a": i})
    s.commit()
    kayit = s.get(DenetimKaydi, 2)
    kayit.yeni = {"a": 999}  # dogrudan veritabani mudahalesi
    s.commit()
    gecerli, bozuk = denetim.zinciri_dogrula(s)
    assert not gecerli and bozuk == 2


def test_eimza(db):
    s, k = db
    imza = denetim.imzala(s, k, "form_kaydi", 7, "Veri kilidi", {"HGB": 12.1})
    s.commit()
    assert len(imza.icerik_hash) == 64
    son = s.query(DenetimKaydi).order_by(DenetimKaydi.id.desc()).first()
    assert son.islem == "imza" and son.varlik_id == 7


def test_parola_hash_dogrulama():
    h = yetki.parola_hashle("Gizli12345")
    assert yetki.parola_dogrula("Gizli12345", h) and not yetki.parola_dogrula("Gizli12346", h)
    assert h.startswith("pbkdf2_sha256$")


def test_eszamanli_kayit_zinciri_bozmaz(tmp_path):
    """20 is parcacigi ayni anda kaydeder; dosya tabanli SQLite'ta her baglanti BEGIN IMMEDIATE ile sirali yazar."""
    # her is parcacigi kendi baglantisini acar (havuz siniri bariyeri kilitlemesin)
    motor = create_engine(f"sqlite:///{tmp_path / 'denetim.db'}", poolclass=NullPool,
                          connect_args={"check_same_thread": False, "timeout": 30})
    Taban.metadata.create_all(motor)
    Oturum = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    with Oturum() as s:
        s.add(Kullanici(kullanici_adi="u", ad_soyad="U", eposta="u@t", parola_hash="x", rol=Rol.CRA))
        s.commit()
    hatalar = []
    bariyer = threading.Barrier(20)

    def yaz(i):
        try:
            with Oturum() as s:
                k = s.get(Kullanici, 1)
                bariyer.wait()
                denetim.kaydet(s, k, "guncelle", "calisma", i, yeni={"i": i})
                s.commit()
        except Exception as e:  # pragma: no cover
            hatalar.append(e)

    isler = [threading.Thread(target=yaz, args=(i,)) for i in range(20)]
    for t in isler:
        t.start()
    for t in isler:
        t.join()
    assert not hatalar
    with Oturum() as s:
        kayitlar = s.execute(select(DenetimKaydi).order_by(DenetimKaydi.id)).scalars().all()
        assert len(kayitlar) == 20
        assert len({k.onceki_hash for k in kayitlar}) == 20  # iki kayit ayni onceki_hash'i tasimaz
        assert denetim.zinciri_dogrula(s) == (True, None)
        z = s.get(DenetimZincir, 1)
        assert z.son_hash == kayitlar[-1].hash and z.son_kayit_id == kayitlar[-1].id
    motor.dispose()


def test_anahtar_degisince_dogrulama_basarisiz(db, monkeypatch):
    s, k = db
    for i in range(3):
        denetim.kaydet(s, k, "guncelle", "calisma", i, yeni={"a": i})
    s.commit()
    assert denetim.zinciri_dogrula(s) == (True, None)
    monkeypatch.setenv("SC_SECRET_KEY", "baska-bir-anahtar-degeri")
    gecerli, bozuk = denetim.zinciri_dogrula(s)
    assert not gecerli and bozuk == 1
    monkeypatch.delenv("SC_SECRET_KEY")
    assert denetim.zinciri_dogrula(s) == (True, None)


def test_hash_hmac_anahtara_bagli():
    from datetime import datetime

    z = datetime(2024, 1, 1)
    a = denetim._ozet(None, z, "u", "olustur", "calisma", 1, None, {"x": 1})
    os.environ["SC_SECRET_KEY"] = "ikinci-anahtar"
    try:
        b = denetim._ozet(None, z, "u", "olustur", "calisma", 1, None, {"x": 1})
    finally:
        del os.environ["SC_SECRET_KEY"]
    assert a != b and len(a) == 64


def test_eimza_icerik_ozeti_anahtardan_bagimsiz(db, monkeypatch):
    s, k = db
    icerik = {"HGB": 12.1, "tarih": "2024-01-01"}
    imza1 = denetim.imzala(s, k, "form_kaydi", 1, "Veri kilidi", icerik)
    monkeypatch.setenv("SC_SECRET_KEY", "yeni-anahtar")
    imza2 = denetim.imzala(s, k, "form_kaydi", 1, "Veri kilidi", icerik)
    s.commit()
    assert imza1.icerik_hash == imza2.icerik_hash == denetim.icerik_ozeti(icerik)
    assert s.execute(select(EImza).where(EImza.varlik_id == 1)).scalars().all()
