"""Gonullu yasam dongusu: gecisler, tarama vizitleri, eCRF veri girisi, tekrarlayan form, AE guncelleme, erisim izi."""
import os
from datetime import date, timedelta

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    AdversOlay,
    Calisma,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    FormKaydi,
    Gonullu,
    GonulluDurumu,
    Kol,
    Kullanici,
    Merkez,
    Rol,
    Sorgu,
    Vizit,
)
from smartclinical.models import Form as CRF
from smartclinical.models._ortak import simdi
from smartclinical.scripts.onarim_tarama_vizitleri import onar
from smartclinical.services import ecrf, yetki
from smartclinical.services import gonullu as gsvc

PAROLA = "Test1234!xyz"
D = GonulluDurumu


@pytest.fixture(scope="module")
def istemci():
    sifirla()
    db = oturum_fabrikasi()()
    m = Merkez(kod="T-01", ad="Test Hastanesi", sehir="Ankara", kurum_tipi="universite")
    db.add(m)
    db.flush()
    db.add_all([
        Kullanici(kullanici_adi="admin", ad_soyad="Ayşe Yönetici", eposta="a@t.local",
                  parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.YONETICI),
        Kullanici(kullanici_adi="koord", ad_soyad="Kerem Koordinatör", eposta="k@t.local",
                  parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.KOORDINATOR),
    ])
    for kod, kol_sayisi in (("GON-001", 1), ("GON-002", 2)):
        c = Calisma(kod=kod, baslik="Gönüllü testi", kisa_ad="Gönüllü", tur=CalismaTuru.ILAC, sponsor="S",
                    terapotik_alan="Onkoloji", hedef_hasta=10)
        db.add(c)
        db.flush()
        db.add(CalismaMerkez(calisma_id=c.id, merkez_id=m.id, merkez_no="01", hedef_hasta=5, durum="aktif"))
        for i in range(kol_sayisi):
            db.add(Kol(calisma_id=c.id, ad=f"Kol {'AB'[i]}", oran=1))
        db.flush()
        ecrf.vizit_semasi_uygula(db, c, "kisa_takip")
        ecrf.standart_formlari_ekle(db, c, ["DM", "IE", "VS", "CM"])
        next(f for f in c.formlar if f.kod == "CM").tekrarlayan = True
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


def _giris(c, kadi="koord"):
    c.cookies.clear()
    r = c.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _calisma(kod="GON-001") -> int:
    db = oturum_fabrikasi()()
    cid = db.execute(select(Calisma.id).where(Calisma.kod == kod)).scalar_one()
    db.close()
    return cid


def _form_id(cid: int, kod: str) -> int:
    db = oturum_fabrikasi()()
    fid = db.execute(select(CRF.id).where(CRF.calisma_id == cid, CRF.kod == kod)).scalar_one()
    db.close()
    return fid


def _gonullu_olustur(istemci, cid: int, onam: str = "2024-03-01") -> int:
    db = oturum_fabrikasi()()
    cm_id = db.execute(select(CalismaMerkez.id).where(CalismaMerkez.calisma_id == cid)).scalar_one()
    db.close()
    veri = {"calisma_id": cid, "calisma_merkez_id": cm_id}
    if onam:
        veri["onam_tarihi"] = onam
    r = istemci.post("/gonulluler/yeni", data=veri, follow_redirects=False)
    assert r.status_code == 303
    return int(r.headers["location"].rsplit("/", 1)[1])


def _vizit(gid: int, ad: str) -> Vizit:
    db = oturum_fabrikasi()()
    v = db.execute(select(Vizit).where(Vizit.gonullu_id == gid, Vizit.ad == ad)).scalar_one()
    db.close()
    return v


def _durum(istemci, gid: int, durum: str, **ek):
    return istemci.post(f"/gonulluler/{gid}/durum", data={"durum": durum, **ek}, follow_redirects=False)


HAM_ROZETLER = (">planli<", ">gir<", ">sdv<", ">acik<", ">tamamlandi<", ">otomatik<", ">manuel<", ">taslak<")


# -- servis ---------------------------------------------------------------------

def test_gecis_sozlugu():
    assert gsvc.gecis_izinli("aday", "onam") and gsvc.gecis_izinli(D.TARAMA, D.RANDOMIZE)
    assert not gsvc.gecis_izinli("aday", "tamamladi") and not gsvc.gecis_izinli("randomize", "tarama")
    assert not gsvc.gecis_izinli("tamamladi", "takipte") and not gsvc.gecis_izinli("aday", "yok")
    assert gsvc.hedefler(D.TAMAMLADI) == []


def test_acik_gun_negatif_degil():
    s = Sorgu(form_kaydi_id=1, alan="X", soru="?", acilis=simdi() + timedelta(hours=3))
    assert s.acik_gun == 0
    s.acilis = simdi() - timedelta(days=5)
    assert s.acik_gun == 5


# -- web ------------------------------------------------------------------------

def test_tarama_formu_randomizasyon_sonrasi_matriste(istemci):
    _giris(istemci)
    cid = _calisma()
    gid = _gonullu_olustur(istemci, cid)
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert g.durum == D.ONAM and [v.ad for v in g.vizitler] == ["Tarama"]  # onamla tarama viziti olusur
    assert g.vizitler[0].durum == "planli" and g.vizitler[0].gerceklesen is None
    db.close()
    tarama = _vizit(gid, "Tarama")
    dm, ie, vs = _form_id(cid, "DM"), _form_id(cid, "IE"), _form_id(cid, "VS")
    r = istemci.get(f"/gonulluler/{gid}")
    assert f"/form/{dm}?vizit_id={tarama.id}" in r.text and "Veri gir" in r.text
    assert istemci.post(f"/gonulluler/{gid}/form/{dm}", data={"vizit_id": tarama.id, "islem": "tamamla", "BRTHYR": "1970",
                        "SEX": "Kadın", "HEIGHT": "165", "WEIGHT": "60"}, follow_redirects=False).status_code == 303
    assert istemci.post(f"/gonulluler/{gid}/form/{ie}", data={"vizit_id": tarama.id, "islem": "tamamla", "IEYN": "Evet",
                        "IEEXCL": "Hayır"}, follow_redirects=False).status_code == 303
    # eski surumden kalan bagsiz kayit (vizit_id bos) ve uzerinde acik sorgu
    db = oturum_fabrikasi()()
    fk = FormKaydi(gonullu_id=gid, form_id=vs, vizit_id=None, veriler={"SYSBP": "300"}, durum="tamamlandi")
    db.add(fk)
    db.flush()
    db.add(Sorgu(form_kaydi_id=fk.id, alan="SYSBP", soru="Değer aralık dışı", kaynak="otomatik"))
    db.commit()
    db.close()
    assert _durum(istemci, gid, "tarama", tarih="2024-03-02").status_code == 303
    assert _durum(istemci, gid, "randomize", tarih="2024-03-10").status_code == 303
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert g.durum == D.RANDOMIZE and len(g.vizitler) == 4 and g.kol_id is not None
    assert all(fk.vizit_id is not None for fk in g.form_kayitlari)  # bagsiz kayit tarama vizitine baglandi
    assert all(fk.form_versiyon == "1.0" for fk in g.form_kayitlari if fk.giren_id)
    db.close()
    r = istemci.get(f"/gonulluler/{gid}")
    assert r.status_code == 200
    satir = r.text.split("<b>Tarama</b>")[1].split("</tr>")[0]
    assert satir.count("Tamamlandı") == 3  # DM, IE ve baglanan VS kaydi
    assert "Değer aralık dışı" in r.text and "Açık sorgular (1)" in r.text
    assert not any(h in r.text for h in HAM_ROZETLER)
    assert "Kerem Koordinatör" in istemci.get(f"/gonulluler/{gid}/form/{dm}?vizit_id={tarama.id}").text


def test_izinsiz_gecis_400_ve_secici(istemci):
    _giris(istemci)
    gid = _gonullu_olustur(istemci, _calisma(), onam="")
    r = _durum(istemci, gid, "tamamladi")
    assert r.status_code == 400
    r = istemci.get(f"/gonulluler/{gid}")
    secici = r.text.split('id="durum-sec"')[1].split("</select>")[0]
    assert 'value="onam"' in secici and 'value="tarama_basarisiz"' in secici
    assert 'value="randomize"' not in secici and 'value="tamamladi"' not in secici
    assert "Durum: Aday" in r.text
    assert _durum(istemci, gid, "onam", tarih="2024-04-01").status_code == 303
    assert _durum(istemci, gid, "aday").status_code == 400  # geri yonlu gecis yok
    db = oturum_fabrikasi()()
    assert db.get(Gonullu, gid).durum == D.ONAM
    db.close()


def test_ie_hayir_iken_randomizasyon_reddi(istemci):
    _giris(istemci)
    cid = _calisma()
    gid = _gonullu_olustur(istemci, cid)
    tarama = _vizit(gid, "Tarama")
    assert _durum(istemci, gid, "tarama").status_code == 303
    # IE tamamlanmadan randomize edilemez
    assert _durum(istemci, gid, "randomize").status_code == 303
    db = oturum_fabrikasi()()
    assert db.get(Gonullu, gid).durum == D.TARAMA
    db.close()
    ie = _form_id(cid, "IE")
    istemci.post(f"/gonulluler/{gid}/form/{ie}", data={"vizit_id": tarama.id, "islem": "tamamla", "IEYN": "Hayır",
                 "IEEXCL": "Hayır"}, follow_redirects=False)
    r = _durum(istemci, gid, "randomize", tarih="2024-03-10")
    assert r.status_code == 303
    r = istemci.get(f"/gonulluler/{gid}")
    assert "uygun değil" in r.text and f"/calismalar/{cid}/izlem" in r.text
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert g.durum == D.TARAMA and g.randomizasyon_tarihi is None and len(g.vizitler) == 1
    db.close()


def test_tek_kollu_etiket_ve_takvim(istemci):
    _giris(istemci)
    cid = _calisma()
    gid = _gonullu_olustur(istemci, cid)
    tarama = _vizit(gid, "Tarama")
    ie = _form_id(cid, "IE")
    istemci.post(f"/gonulluler/{gid}/form/{ie}", data={"vizit_id": tarama.id, "islem": "tamamla", "IEYN": "Evet",
                 "IEEXCL": "Hayır"}, follow_redirects=False)
    assert _durum(istemci, gid, "tarama").status_code == 303
    r = istemci.get(f"/gonulluler/{gid}")
    assert 'name="kol_id"' not in r.text and "Çalışmaya alındı</option>" in r.text and "Randomize</option>" not in r.text
    gecmis = (date.today() - timedelta(days=200)).isoformat()
    assert _durum(istemci, gid, "randomize", tarih=gecmis).status_code == 303
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert g.durum == D.RANDOMIZE and g.durum_etiket == "Çalışmaya alındı" and g.kol.ad == "Kol A"
    durumlar = {v.ad: v.durum for v in g.vizitler}
    assert durumlar["V1 (Başlangıç)"] == "yapildi" and durumlar["V2"] == "planli" and durumlar["Çalışma Sonu"] == "planli"
    assert all(v.planlanan < date.today() for v in g.vizitler)  # gecmis tarihli ama otomatik 'yapildi' degil
    db.close()
    r = istemci.get(f"/gonulluler/{gid}")
    assert "Çalışmaya alındı" in r.text and "Çalışmaya alınma" in r.text
    r = istemci.get(f"/calismalar/{cid}/gonulluler")
    assert "Çalışmaya alındı" in r.text and 'value="randomize"' in r.text and "Randomize<" not in r.text


def test_cok_kollu_calismada_kol_zorunlu(istemci):
    _giris(istemci)
    cid = _calisma("GON-002")
    gid = _gonullu_olustur(istemci, cid)
    tarama = _vizit(gid, "Tarama")
    ie = _form_id(cid, "IE")
    istemci.post(f"/gonulluler/{gid}/form/{ie}", data={"vizit_id": tarama.id, "islem": "tamamla", "IEYN": "Evet",
                 "IEEXCL": "Hayır"}, follow_redirects=False)
    assert _durum(istemci, gid, "tarama").status_code == 303
    r = istemci.get(f"/gonulluler/{gid}")
    assert 'name="kol_id"' in r.text and "Randomize</option>" in r.text
    assert _durum(istemci, gid, "randomize").status_code == 303
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert g.durum == D.TARAMA and g.kol_id is None
    kol_id = g.calisma.kollar[1].id
    db.close()
    assert _durum(istemci, gid, "randomize", kol_id=str(kol_id)).status_code == 303
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert g.durum == D.RANDOMIZE and g.kol_id == kol_id and g.durum_etiket == "Randomize"
    db.close()


def test_kacirilan_vizit_gerekce(istemci):
    _giris(istemci)
    gid = _gonullu_olustur(istemci, _calisma())
    v = _vizit(gid, "Tarama")
    assert istemci.post(f"/gonulluler/{gid}/vizit/{v.id}", data={"durum": "kacirildi"}, follow_redirects=False).status_code == 400
    assert istemci.post(f"/gonulluler/{gid}/vizit/{v.id}", data={"durum": "yapildi"}, follow_redirects=False).status_code == 400
    r = istemci.post(f"/gonulluler/{gid}/vizit/{v.id}", data={"durum": "kacirildi", "neden": "Hasta ulaşılamadı"},
                     follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    v = db.get(Vizit, v.id)
    assert v.durum == "kacirildi" and v.kacirilma_nedeni == "Hasta ulaşılamadı" and v.gerceklesen is None
    db.close()
    r = istemci.get(f"/gonulluler/{gid}")
    assert "Kaçırıldı" in r.text and "Hasta ulaşılamadı" in r.text and ">kacirildi<" not in r.text


def test_tekrarlayan_form_ikinci_satir(istemci):
    _giris(istemci)
    cid = _calisma()
    gid = _gonullu_olustur(istemci, cid)
    v = _vizit(gid, "Tarama")
    cm = _form_id(cid, "CM")
    b = f"/gonulluler/{gid}/form/{cm}"
    assert istemci.post(b, data={"vizit_id": v.id, "yeni": "1", "islem": "tamamla", "CMTRT": "Metformin"},
                        follow_redirects=False).status_code == 303
    r = istemci.get(f"{b}?vizit_id={v.id}")
    assert "Yeni satır" in r.text and "1. Metformin" in r.text
    assert istemci.post(b, data={"vizit_id": v.id, "yeni": "1", "islem": "tamamla", "CMTRT": "Aspirin"},
                        follow_redirects=False).status_code == 303
    db = oturum_fabrikasi()()
    kayitlar = db.execute(select(FormKaydi).where(FormKaydi.gonullu_id == gid, FormKaydi.form_id == cm)
                          .order_by(FormKaydi.tekrar_no)).scalars().all()
    assert [(k.tekrar_no, k.veriler["CMTRT"]) for k in kayitlar] == [(1, "Metformin"), (2, "Aspirin")]
    db.close()
    r = istemci.get(f"/gonulluler/{gid}")
    assert "Tamamlandı (2)" in r.text
    r = istemci.get(f"{b}?vizit_id={v.id}&tekrar_no=2")
    assert 'value="Aspirin"' in r.text and "2. satır" in r.text


def test_sorgulu_tamamlamada_formda_kalma(istemci):
    _giris(istemci)
    cid = _calisma()
    gid = _gonullu_olustur(istemci, cid)
    v = _vizit(gid, "Tarama")
    vs = _form_id(cid, "VS")
    veri = {"vizit_id": v.id, "VSDAT": "2024-03-01", "SYSBP": "300", "DIABP": "80"}
    r = istemci.post(f"/gonulluler/{gid}/form/{vs}", data={**veri, "islem": "tamamla"}, follow_redirects=False)
    assert r.status_code == 200 and "1 alan sorgulu" in r.text and 'value="tamamla_onayla"' in r.text
    assert "beklenen aralığın üstünde" in r.text
    db = oturum_fabrikasi()()
    fk = db.execute(select(FormKaydi).where(FormKaydi.gonullu_id == gid, FormKaydi.form_id == vs)).scalar_one()
    assert fk.durum == "taslak" and fk.veriler["SYSBP"] == "300" and not fk.sorgular
    db.close()
    r = istemci.post(f"/gonulluler/{gid}/form/{vs}", data={**veri, "islem": "tamamla_onayla"}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    fk = db.execute(select(FormKaydi).where(FormKaydi.gonullu_id == gid, FormKaydi.form_id == vs)).scalar_one()
    assert fk.durum == "tamamlandi" and [s.alan for s in fk.sorgular] == ["SYSBP"] and fk.sorgular[0].kaynak == "otomatik"
    db.close()
    r = istemci.get(f"/gonulluler/{gid}/form/{vs}?vizit_id={v.id}")
    assert "Otomatik" in r.text and "Açık" in r.text and not any(h in r.text for h in HAM_ROZETLER)


def test_ae_duzenleme_denetim_izi(istemci):
    _giris(istemci)
    gid = _gonullu_olustur(istemci, _calisma())
    r = istemci.post(f"/gonulluler/{gid}/advers-olay", data={"terim": "Nötropeni", "baslangic": "2024-03-05", "siddet": "2",
                     "nedensellik": "olasi", "beklenen": "0", "ciddi": "0"}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    a = db.execute(select(AdversOlay).where(AdversOlay.gonullu_id == gid)).scalar_one()
    aid = a.id
    assert not a.ciddi and a.farkindalik_tarihi is None
    db.close()
    b = f"/gonulluler/{gid}/advers-olay/{aid}"
    r = istemci.get(b)
    assert r.status_code == 200 and "SAE'ye yükselt" in r.text and "SOC girilmedi" in r.text
    # gerekcesiz degisiklik yazilmaz
    r = istemci.post(b, data={"ciddi": "1", "sonuc": "Devam ediyor"}, follow_redirects=False)
    assert r.status_code == 200 and "gerekçe zorunlu" in r.text
    db = oturum_fabrikasi()()
    assert not db.get(AdversOlay, aid).ciddi
    db.close()
    r = istemci.post(b, data={"ciddi": "1", "ciddiyet_olcutu": "hastaneye_yatis", "sonuc": "Devam ediyor", "siddet": "3",
                     "nedensellik": "muhtemel", "bitis": "", "meddra_soc": "Kan ve lenf sistemi hastalıkları",
                     "meddra_pt": "Neutropenia", "takip_notu": "Hastaneye yatırıldı.",
                     "gerekce": "Hastaneye yatış ile SAE kriterine ulaştı"}, follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    a = db.get(AdversOlay, aid)
    assert a.ciddi and a.farkindalik_tarihi == date.today() and a.bildirim_suresi_gun == 15 and a.susar
    assert a.siddet == "3" and a.meddra_soc.startswith("Kan ve") and "Hastaneye yatırıldı" in a.takip_notu
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik == "advers_olay", DenetimKaydi.varlik_id == aid,
                                                  DenetimKaydi.islem == "guncelle")).scalars().all()
    assert len(kayit) == 1 and kayit[0].gerekce.startswith("Hastaneye") and kayit[0].eski["ciddi"] is False
    assert kayit[0].yeni["ciddi"] is True and kayit[0].yeni["siddet"] == "3" and "terim" not in kayit[0].yeni
    db.close()
    r = istemci.get(b)
    assert "geri alınamaz" in r.text and "Kan ve lenf" in r.text and "TİTCK bildirimi: 15 gün" in r.text
    # calisma guvenlik sayfasi SOC etiketi ve duzenleme baglantisi
    r = istemci.get(f"/calismalar/{_calisma()}/guvenlik")
    assert r.status_code == 200 and "Kodlanmamış" not in r.text and b in r.text and "Kan ve lenf" in r.text


def test_goruntuleme_olayi_oturumda_bir_kez(istemci):
    _giris(istemci)
    cid = _calisma()
    gid = _gonullu_olustur(istemci, cid)
    dm = _form_id(cid, "DM")

    def say(varlik, vid):
        db = oturum_fabrikasi()()
        n = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "goruntule", DenetimKaydi.varlik == varlik,
                                                  DenetimKaydi.varlik_id == vid)).scalars().all()
        db.close()
        return n

    assert say("gonullu", gid) == []
    istemci.get(f"/gonulluler/{gid}")
    istemci.get(f"/gonulluler/{gid}")
    k = say("gonullu", gid)
    assert len(k) == 1 and k[0].kullanici_adi == "koord"
    istemci.get(f"/gonulluler/{gid}/form/{dm}")
    istemci.get(f"/gonulluler/{gid}/form/{dm}")
    f = say("form", dm)
    assert len([x for x in f if x.yeni.get("gonullu_id") == gid]) == 1
    _giris(istemci, "admin")  # yeni oturum: yeniden yazilir
    istemci.get(f"/gonulluler/{gid}")
    assert len(say("gonullu", gid)) == 2


def test_onarim_scripti_bagsiz_kayitlari_baglar(istemci):
    cid = _calisma()
    dm = _form_id(cid, "DM")  # paylasilan baglanti: ikinci oturum acik islemi geri alir, once okunur
    db = oturum_fabrikasi()()
    cm = db.execute(select(CalismaMerkez).where(CalismaMerkez.calisma_id == cid)).scalar_one()
    g = Gonullu(calisma_id=cid, calisma_merkez_id=cm.id, gonullu_no="01-900", durum=D.ONAM, onam_tarihi=date(2024, 1, 5))
    db.add(g)
    db.flush()
    db.add(FormKaydi(gonullu_id=g.id, form_id=dm, vizit_id=None, veriler={"SEX": "Erkek"}, durum="tamamlandi"))
    db.commit()
    gid = g.id
    assert onar(db, kuru=True) == [("01-900", 1, 1)]
    db.rollback()
    db.close()
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert not g.vizitler and g.form_kayitlari[0].vizit_id is None  # kuru calisma yazmaz
    assert onar(db, kuru=False) == [("01-900", 1, 1)]
    db.commit()
    db.close()
    db = oturum_fabrikasi()()
    g = db.get(Gonullu, gid)
    assert [v.ad for v in g.vizitler] == ["Tarama"] and g.form_kayitlari[0].vizit_id == g.vizitler[0].id
    assert db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "onarim", DenetimKaydi.varlik_id == gid)).scalar_one()
    assert onar(db, kuru=False) == []
    db.close()


def test_aktif_merkez_yoksa_yonlendirme(istemci):
    _giris(istemci, "admin")
    db = oturum_fabrikasi()()
    c = Calisma(kod="GON-003", baslik="Boş", kisa_ad="Boş", tur=CalismaTuru.ILAC, sponsor="S", terapotik_alan="Onkoloji",
                hedef_hasta=5)
    db.add(c)
    db.flush()
    m = db.execute(select(Merkez)).scalars().first()
    cm = CalismaMerkez(calisma_id=c.id, merkez_id=m.id, merkez_no="01", hedef_hasta=5, durum="aday")
    db.add(cm)
    db.commit()
    cid, cm_id = c.id, cm.id
    db.close()
    r = istemci.get(f"/calismalar/{cid}/gonulluler")
    assert "bir merkezi Aktif yapın" in r.text and f"/calismalar/{cid}/merkezler" in r.text and "Gönüllü ekle (manuel)" not in r.text
    assert istemci.post("/gonulluler/yeni", data={"calisma_id": cid, "calisma_merkez_id": cm_id},
                        follow_redirects=False).status_code == 400
