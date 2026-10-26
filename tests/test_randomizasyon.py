"""Dahili blok randomizasyon: blok dengesi, strata, tek kullanim, e-imza ve gizli tahsis."""
import os
from collections import Counter

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    Calisma,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    EImza,
    Gonullu,
    GonulluDurumu,
    Kol,
    Kullanici,
    Merkez,
    Rol,
)
from smartclinical.models.randomizasyon import RandomizasyonAyari, RandomizasyonKaydi
from smartclinical.services import ecrf, yetki
from smartclinical.services import randomizasyon as rnd
from smartclinical.web import randomizasyon as rnd_web

PAROLA = "Test1234!xyz"


@pytest.fixture(scope="module")
def istemci():
    if not any(getattr(r, "path", "").startswith("/calismalar/{calisma_id}/randomizasyon") for r in app.routes):
        app.include_router(rnd_web.router)
    sifirla()
    db = oturum_fabrikasi()()
    m1 = Merkez(kod="T-01", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
    m2 = Merkez(kod="T-02", ad="İkinci Hastane", sehir="İzmir", kurum_tipi="devlet")
    db.add_all([m1, m2])
    db.flush()
    db.add_all([
        Kullanici(kullanici_adi="admin", ad_soyad="Admin", eposta="a@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.YONETICI),
        Kullanici(kullanici_adi="pm", ad_soyad="Proje Yöneticisi", eposta="p@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.PROJE_YONETICISI),
        Kullanici(kullanici_adi="koord", ad_soyad="Koordinatör", eposta="k@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.KOORDINATOR),
    ])
    for kod in ("RND-001", "RND-002"):
        c = Calisma(kod=kod, baslik="Randomizasyon testi", kisa_ad="Rnd", tur=CalismaTuru.ILAC, sponsor="S",
                    terapotik_alan="Kardiyoloji", hedef_hasta=12)
        db.add(c)
        db.flush()
        db.add_all([CalismaMerkez(calisma_id=c.id, merkez_id=m1.id, merkez_no="01", hedef_hasta=6, durum="aktif"),
                    CalismaMerkez(calisma_id=c.id, merkez_id=m2.id, merkez_no="02", hedef_hasta=6, durum="aktif"),
                    Kol(calisma_id=c.id, ad="Kol A", oran=2), Kol(calisma_id=c.id, ad="Kol B", oran=1)])
        db.flush()
        ecrf.vizit_semasi_uygula(db, c, "kisa_takip")
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


def _giris(c, kadi="pm"):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _calisma(db, kod="RND-001") -> Calisma:
    return db.execute(select(Calisma).where(Calisma.kod == kod)).scalar_one()


def _gonullu(db, c: Calisma, merkez_no: str, no: int) -> Gonullu:
    cm = next(x for x in c.merkezler if x.merkez_no == merkez_no)
    g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, gonullu_no=f"{merkez_no}-{no:03d}", durum=GonulluDurumu.TARAMA)
    db.add(g)
    db.flush()
    return g


def test_blok_dengesi_oranlara_uyar(istemci):
    db = oturum_fabrikasi()()
    c = _calisma(db)
    assert rnd.blok_boyutu_dogrula(c, 4) and rnd.blok_boyutu_dogrula(c, 6) is None
    with pytest.raises(ValueError):
        rnd.liste_uret(db, c, 4, "yok", tohum=1)
    kayitlar = rnd.liste_uret(db, c, 6, "yok", tohum=1)
    db.commit()
    a, b = sorted(c.kollar, key=lambda k: k.id)
    assert len(kayitlar) >= int(12 * 1.2) + 6 and len(kayitlar) % 6 == 0
    assert [k.sira for k in kayitlar] == list(range(1, len(kayitlar) + 1))
    for i in range(0, len(kayitlar), 6):
        blok = Counter(k.kol_id for k in kayitlar[i:i + 6])
        assert blok[a.id] == 4 and blok[b.id] == 2
    # ayni tohum ayni diziyi, farkli tohum farkli diziyi verir (yeniden uretilebilirlik)
    dizi = [k.kol_id for k in kayitlar]
    rnd.liste_uret(db, c, 6, "yok", tohum=1)
    assert [k.kol_id for k in db.execute(select(RandomizasyonKaydi).where(RandomizasyonKaydi.calisma_id == c.id)
                                          .order_by(RandomizasyonKaydi.sira)).scalars()] == dizi
    rnd.liste_uret(db, c, 6, "yok", tohum=2)
    assert [k.kol_id for k in db.execute(select(RandomizasyonKaydi).where(RandomizasyonKaydi.calisma_id == c.id)
                                          .order_by(RandomizasyonKaydi.sira)).scalars()] != dizi
    db.rollback()
    db.close()


def test_strata_ayrimi_ve_tek_kullanim(istemci):
    db = oturum_fabrikasi()()
    c = _calisma(db)
    kayitlar = rnd.liste_uret(db, c, 3, "merkez", tohum=7, kayit_sayisi=6)
    db.add(RandomizasyonAyari(calisma_id=c.id, blok_boyutu=3, strata="merkez", imza_zamani=rnd.simdi()))
    db.commit()
    stratalar = Counter(k.strata_anahtari for k in kayitlar)
    assert set(stratalar) == {"01", "02"} and stratalar["01"] == stratalar["02"] == 3
    assert sorted(k.sira for k in kayitlar if k.strata_anahtari == "02") == [1, 2, 3]
    g1, g2, g3, g4 = (_gonullu(db, c, "01", 1), _gonullu(db, c, "01", 2), _gonullu(db, c, "02", 1), _gonullu(db, c, "01", 3))
    k1 = rnd.siradaki_tahsis(db, g1)
    k2 = rnd.siradaki_tahsis(db, g2)
    k3 = rnd.siradaki_tahsis(db, g3)
    db.commit()
    assert k1.id != k2.id and k1.strata_anahtari == k2.strata_anahtari == "01" and k3.strata_anahtari == "02"
    assert (k1.sira, k2.sira, k3.sira) == (1, 2, 1)
    assert g1.kol_id == k1.kol_id and g2.kol_id == k2.kol_id and all(k.gonullu_id for k in (k1, k2, k3))
    assert all(k.kullanim_zamani for k in (k1, k2, k3))
    # 01 stratasinda 3 kayit var: ucuncu tahsis sonuncuyu alir, dorduncu tukenir
    k4 = rnd.siradaki_tahsis(db, g4)
    assert k4.sira == 3 and len({k1.id, k2.id, k4.id}) == 3
    with pytest.raises(ValueError, match="kalmadı"):
        rnd.siradaki_tahsis(db, _gonullu(db, c, "01", 4))
    # tahsis yapilmis liste yeniden uretilemez
    with pytest.raises(ValueError, match="yeniden"):
        rnd.liste_uret(db, c, 3, "merkez", tohum=7)
    ozet = {o["strata"]: o for o in rnd.ozet(db, c)}
    assert ozet["01"]["kullanilan"] == 3 and ozet["01"]["kalan"] == 0 and ozet["02"]["kalan"] == 2
    db.rollback()
    db.close()


def test_eimza_olmadan_liste_uretilmez(istemci):
    _giris(istemci, "pm")
    db = oturum_fabrikasi()()
    c = _calisma(db, "RND-002")
    cid = c.id
    db.close()
    b = f"/calismalar/{cid}/randomizasyon"
    r = istemci.get(b)
    assert r.status_code == 200 and "Liste yok" in r.text
    r = istemci.post(f"{b}/uret", data={"blok_boyutu": "6", "strata": "yok", "parola": "yanlis"}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    assert not db.execute(select(RandomizasyonKaydi).where(RandomizasyonKaydi.calisma_id == cid)).scalars().all()
    assert rnd.ayar_getir(db, _calisma(db, "RND-002")) is None
    db.close()
    r = istemci.post(f"{b}/uret", data={"blok_boyutu": "6", "strata": "yok", "parola": PAROLA}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    c = _calisma(db, "RND-002")
    kayitlar = db.execute(select(RandomizasyonKaydi).where(RandomizasyonKaydi.calisma_id == cid)).scalars().all()
    ayar = rnd.ayar_getir(db, c)
    assert kayitlar and ayar.imza_zamani and ayar.olusturan.kullanici_adi == "pm"
    olay = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "randomizasyon_listesi",
                                                 DenetimKaydi.varlik_id == cid)).scalar_one()
    assert olay.yeni["kayit"] == len(kayitlar) and "kol_id" not in str(olay.yeni)
    assert db.execute(select(EImza).where(EImza.varlik == "randomizasyon_ayari", EImza.varlik_id == ayar.id)).scalar_one()
    db.close()
    # ozet yalnizca sayilar: sira/kol sutunu yok, kol adlari yalnizca basliktaki tanimda
    r = istemci.get(b)
    assert "Liste hazır" in r.text and "<th>Sıra</th>" not in r.text and "<th>Kol</th>" not in r.text
    assert r.text.count("Kol A") == 1 and "tahsis yapıldı" not in r.text
    # koordinator sayfayi acamaz
    _giris(istemci, "koord")
    assert istemci.get(b).status_code == 403


def test_web_randomizasyonda_kol_listeden_atanir(istemci):
    _giris(istemci, "koord")
    db = oturum_fabrikasi()()
    c = _calisma(db, "RND-002")
    cm_id = c.merkezler[0].id
    cid = c.id
    ilk = db.execute(select(RandomizasyonKaydi).where(RandomizasyonKaydi.calisma_id == cid)
                     .order_by(RandomizasyonKaydi.sira)).scalars().first()
    beklenen_kol = ilk.kol_id
    db.close()
    r = istemci.post("/gonulluler/yeni", data={"calisma_id": cid, "calisma_merkez_id": cm_id, "onam_tarihi": "2024-05-01"},
                     follow_redirects=False)
    gid = int(r.headers["location"].rsplit("/", 1)[1])
    assert istemci.post(f"/gonulluler/{gid}/durum", data={"durum": "tarama"}, follow_redirects=False).status_code == 303
    r = istemci.get(f"/gonulluler/{gid}")
    assert 'name="kol_id"' not in r.text and "listesinden otomatik" in r.text
    # kol_id gonderilse bile liste kazanir
    assert istemci.post(f"/gonulluler/{gid}/durum", data={"durum": "randomize", "kol_id": "999"},
                        follow_redirects=False).status_code == 303
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert g.durum == GonulluDurumu.RANDOMIZE and g.kol_id == beklenen_kol
    kayit = db.execute(select(RandomizasyonKaydi).where(RandomizasyonKaydi.gonullu_id == gid)).scalar_one()
    assert kayit.sira == 1 and kayit.kullanim_zamani is not None
    db.close()
    r = istemci.get(f"/gonulluler/{gid}")
    assert "Randomize" in r.text and "Kol: " in r.text
