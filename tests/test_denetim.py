import os

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.models import DenetimKaydi, Kullanici, Rol
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
