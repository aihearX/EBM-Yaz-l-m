import os
from datetime import date, datetime, timedelta

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import numpy as np
import pytest

from smartclinical.db import db_oturumu, sifirla
from smartclinical.models import (
    AdversOlay,
    Calisma,
    CalismaMerkez,
    CalismaTuru,
    Form,
    FormKaydi,
    Gonullu,
    GonulluDurumu,
    Merkez,
    ProtokolSapmasi,
    RiskGostergesi,
    RiskUyarisi,
    Sorgu,
    Vizit,
)
from smartclinical.services import rbm
from smartclinical.services.rbm.anomali import anomali_tespit, cusum
from smartclinical.services.rbm.gostergeler import kri_hesapla
from smartclinical.services.rbm.uyari import bilesik_risk_puani, izlem_onerisi

BUGUN = date.today()


def _calisma_kur(db, n_merkez=5):
    c = Calisma(kod="RBM-1", baslik="RBM test", kisa_ad="rbm", tur=CalismaTuru.ILAC, sponsor="s",
                terapotik_alan="Kardiyoloji", baslangic=BUGUN - timedelta(days=200),
                planlanan_bitis=BUGUN + timedelta(days=300))
    db.add(c)
    db.flush()
    form = Form(calisma_id=c.id, kod="VS", ad="Vital", alanlar=[])
    db.add(form)
    db.flush()
    cmler = []
    for i in range(n_merkez):
        m = Merkez(kod=f"M{i}", ad=f"Hastane {i}", sehir="Ankara", kurum_tipi="universite")
        db.add(m)
        db.flush()
        cm = CalismaMerkez(calisma_id=c.id, merkez_id=m.id, merkez_no=f"{i + 1:02d}", durum="aktif",
                           hedef_hasta=10, secim_tarihi=BUGUN - timedelta(days=250),
                           aktivasyon_tarihi=BUGUN - timedelta(days=180))
        db.add(cm)
        db.flush()
        cmler.append(cm)
    return c, form, cmler


def _gonullu_ekle(db, cm, no, durum=GonulluDurumu.TEDAVIDE, rand=True):
    g = Gonullu(calisma_id=cm.calisma_id, calisma_merkez_id=cm.id, gonullu_no=f"{cm.merkez_no}-{no:03d}",
                durum=durum, randomizasyon_tarihi=BUGUN - timedelta(days=120) if rand else None)
    db.add(g)
    db.flush()
    return g


def _normal_merkez(db, cm, form, n=6):
    """Sorunsuz merkez: her gonullude 1 form, sorgu yok, 1 AE, vizitler pencerede."""
    for i in range(n):
        g = _gonullu_ekle(db, cm, i + 1)
        v = Vizit(gonullu_id=g.id, ad="V1", sira=1, planlanan=BUGUN - timedelta(days=60),
                  gerceklesen=BUGUN - timedelta(days=60), durum="yapildi")
        db.add(v)
        db.flush()
        fk = FormKaydi(gonullu_id=g.id, form_id=form.id, vizit_id=v.id, durum="sdv",
                       sdv_zamani=datetime.now())
        fk.olusturma = datetime.combine(BUGUN - timedelta(days=58), datetime.min.time())
        db.add(fk)
        db.add(AdversOlay(gonullu_id=g.id, terim="Bas agrisi", baslangic=BUGUN - timedelta(days=30)))
    db.flush()


def _sorunlu_merkez(db, cm, form, n=6):
    """Cok sorgu, major sapma, AE yok, gec SAE, pencere disi vizit, erken ayrilma."""
    for i in range(n):
        durum = GonulluDurumu.AYRILDI if i < 2 else GonulluDurumu.TEDAVIDE
        g = _gonullu_ekle(db, cm, i + 1, durum)
        v = Vizit(gonullu_id=g.id, ad="V1", sira=1, planlanan=BUGUN - timedelta(days=60),
                  gerceklesen=BUGUN - timedelta(days=50), durum="yapildi", pencere_gun=3)
        db.add(v)
        db.flush()
        fk = FormKaydi(gonullu_id=g.id, form_id=form.id, vizit_id=v.id, durum="tamamlandi")
        fk.olusturma = datetime.combine(BUGUN - timedelta(days=30), datetime.min.time())
        db.add(fk)
        db.flush()
        for j in range(2):
            s = Sorgu(form_kaydi_id=fk.id, alan="SYSBP", soru="Deger kontrol")
            s.acilis = datetime.now() - timedelta(days=40)
            db.add(s)
        db.add(ProtokolSapmasi(calisma_merkez_id=cm.id, gonullu_id=g.id, tarih=BUGUN - timedelta(days=20),
                               kategori="onam" if i == 0 else "vizit", onem="major" if i < 3 else "minor",
                               aciklama="test"))
    g0 = cm.gonulluler[0]
    db.add(AdversOlay(gonullu_id=g0.id, terim="MI", baslangic=BUGUN - timedelta(days=10), ciddi=True,
                      ciddiyet_olcutu="yasam_tehdidi", farkindalik_tarihi=BUGUN - timedelta(days=10),
                      sponsor_bildirim=BUGUN - timedelta(days=5)))
    # tarama basarisiz 3 kisi
    for i in range(3):
        _gonullu_ekle(db, cm, 50 + i, GonulluDurumu.TARAMA_BASARISIZ, rand=False)
    db.flush()


@pytest.fixture
def veri():
    sifirla()
    with db_oturumu() as db:
        c, form, cmler = _calisma_kur(db)
        for cm in cmler[:4]:
            _normal_merkez(db, cm, form)
        _sorunlu_merkez(db, cmler[4], form)
        db.commit()
        db.refresh(c)
        for cm in cmler:
            db.refresh(cm)
        yield db, c, cmler


def test_varsayilan_kri_listesi():
    assert len(rbm.VARSAYILAN_KRILER) >= 12
    kodlar = {k["kod"] for k in rbm.VARSAYILAN_KRILER}
    assert {"SORGU_ORANI", "AE_ORANI", "SAE_GEC_BILDIRIM", "ONAM_HATASI", "KAZANIM_HEDEF_SAPMA"} <= kodlar
    for k in rbm.VARSAYILAN_KRILER:
        assert k["hesaplama"] in rbm.HESAPLAYICILAR
        assert k["yon"] in ("yuksek", "dusuk")


def test_kri_hesapla_normal_merkez(veri):
    db, c, cmler = veri
    d = kri_hesapla(db, c)
    n = d[cmler[0].id]
    assert n["SORGU_ORANI"] == 0
    assert n["SAPMA_ORANI"] == 0
    assert n["AE_ORANI"] == 1.0
    assert n["SAE_GEC_BILDIRIM"] == 0
    assert n["PENCERE_DISI_VIZIT"] == 0
    assert n["SDV_ORANI"] == 100.0
    assert n["FORM_TAMAMLAMA"] == 100.0
    assert n["VERI_GIRIS_GECIKME_GUN"] == 2
    assert n["ERKEN_AYRILMA"] == 0


def test_kri_hesapla_sorunlu_merkez(veri):
    db, c, cmler = veri
    d = kri_hesapla(db, c)[cmler[4].id]
    assert d["SORGU_ORANI"] == 2.0
    assert d["SORGU_KAPANIS_GUN"] == 40
    assert d["MAJOR_SAPMA"] == 3
    assert d["ONAM_HATASI"] == 1
    assert d["AE_ORANI"] == pytest.approx(1 / 6, abs=0.01)
    assert d["SAE_GEC_BILDIRIM"] == 1
    assert d["PENCERE_DISI_VIZIT"] == 100.0
    assert d["TARAMA_BASARISIZ"] == pytest.approx(33.3, abs=0.1)
    assert d["ERKEN_AYRILMA"] == pytest.approx(33.3, abs=0.1)
    assert d["VERI_GIRIS_GECIKME_GUN"] == 20
    assert d["SDV_ORANI"] == 0


def test_kri_hesapla_aday_merkez_atlanir(veri):
    db, c, cmler = veri
    cmler[0].durum = "aday"
    db.flush()
    db.refresh(c)
    assert cmler[0].id not in kri_hesapla(db, c)


def test_kazanim_hedef_sapma(veri):
    db, c, cmler = veri
    # 480 gunluk surenin 180'i gecti -> beklenen 3.75, gercek 6 -> geri degil
    assert rbm.HESAPLAYICILAR["kazanim_hedef_sapma"](db, cmler[0]) == 0
    cmler[0].hedef_hasta = 40  # beklenen 15, gercek 6
    assert rbm.HESAPLAYICILAR["kazanim_hedef_sapma"](db, cmler[0]) == pytest.approx(60.0, abs=0.2)


def test_kacirilan_vizit(veri):
    db, c, cmler = veri
    g = cmler[0].gonulluler[0]
    db.add(Vizit(gonullu_id=g.id, ad="V2", sira=2, planlanan=BUGUN - timedelta(days=20), durum="planli"))
    db.add(Vizit(gonullu_id=g.id, ad="V3", sira=3, planlanan=BUGUN + timedelta(days=20), durum="planli"))
    db.flush()
    # 6 gecmis yapilan + 1 kacirilan; gelecekteki sayilmaz
    assert rbm.HESAPLAYICILAR["kacirilan_vizit"](db, cmler[0]) == pytest.approx(14.3, abs=0.1)


def test_erken_uyari_uretimi(veri):
    db, c, cmler = veri
    uyarilar = rbm.erken_uyari_calistir(db, c, kullanici_id=None)
    db.commit()
    sorunlu = [u for u in uyarilar if u.calisma_merkez_id == cmler[4].id]
    normal = [u for u in uyarilar if u.calisma_merkez_id == cmler[0].id]
    kodlar = {u.kri_kod for u in sorunlu}
    assert {"SORGU_ORANI", "MAJOR_SAPMA", "SAE_GEC_BILDIRIM", "ONAM_HATASI", "ERKEN_AYRILMA", "AE_ORANI"} <= kodlar
    assert not normal
    sae = next(u for u in sorunlu if u.kri_kod == "SAE_GEC_BILDIRIM")
    assert sae.seviye == "uyari" and sae.esik == 1
    major = next(u for u in sorunlu if u.kri_kod == "MAJOR_SAPMA")
    assert major.seviye == "aksiyon"
    assert "eşik" in major.aciklama.lower() and "medyan" in major.aciklama
    assert "Hastane 4 (05)" in major.mesaj
    assert cmler[4].risk_puani > 50
    assert cmler[0].risk_puani is not None and cmler[0].risk_puani < 15
    # AE_ORANI dusuk yonlu: normal merkezlerde (1.0) tetiklenmemeli
    assert not any(u.kri_kod == "AE_ORANI" and u.calisma_merkez_id == cmler[0].id for u in uyarilar)


def test_erken_uyari_tekrar_calisma_cogaltmaz(veri):
    db, c, cmler = veri
    ilk = rbm.erken_uyari_calistir(db, c)
    db.commit()
    ikinci = rbm.erken_uyari_calistir(db, c)
    db.commit()
    assert len(ilk) == len(ikinci)
    toplam = db.query(RiskUyarisi).count()
    assert toplam == len(ilk)


def test_erken_uyari_otomatik_kapanis(veri):
    db, c, cmler = veri
    rbm.erken_uyari_calistir(db, c)
    db.commit()
    # SAE'yi zamaninda bildirilmis yap -> uyari kapanmali
    sae = db.query(AdversOlay).filter_by(ciddi=True).one()
    sae.sponsor_bildirim = sae.farkindalik_tarihi
    db.commit()
    db.refresh(c)
    rbm.erken_uyari_calistir(db, c)
    db.commit()
    u = db.query(RiskUyarisi).filter_by(kri_kod="SAE_GEC_BILDIRIM").one()
    assert u.durum == "kapandi" and u.kapanis is not None


def test_calismaya_ozel_kri_tanimi(veri):
    db, c, cmler = veri
    db.add(RiskGostergesi(calisma_id=c.id, kod="SORGU_ORANI", ad="Sorgu", hesaplama="sorgu_orani",
                          yon="yuksek", esik_uyari=5, esik_aksiyon=10, agirlik=1))
    db.commit()
    kriler = rbm.calisma_krileri(db, c)
    assert len(kriler) == 1
    uyarilar = rbm.erken_uyari_calistir(db, c)
    assert not [u for u in uyarilar if u.kri_kod == "SORGU_ORANI" and u.seviye == "aksiyon"]


def test_varsayilan_krileri_yukle(veri):
    db, c, _ = veri
    eklenen = rbm.varsayilan_krileri_yukle(db, None)
    db.commit()
    assert len(eklenen) == len(rbm.VARSAYILAN_KRILER)
    assert rbm.varsayilan_krileri_yukle(db, None) == []
    assert len(rbm.calisma_krileri(db, c)) == len(rbm.VARSAYILAN_KRILER)


def test_qtl(veri):
    db, c, _ = veri
    eklenen = rbm.varsayilan_qtlleri_yukle(db, c)
    db.commit()
    assert len(eklenen) == 3
    qtller = rbm.qtl_guncelle(db, c)
    db.commit()
    d = {q.hesaplama: q for q in qtller}
    # 30 kayitli, 2 ayrildi -> %6.7 ; major 3/30 = %10 -> limit 10 asilmadi (>) ; ikincil asildi
    assert d["erken_ayrilma"].mevcut_deger == pytest.approx(6.7, abs=0.1)
    assert d["major_sapma"].mevcut_deger == 10.0
    assert not d["major_sapma"].asildi
    assert d["uygunluk_ihlali"].mevcut_deger == 0
    assert all(q.son_hesaplama is not None for q in qtller)


def test_bilesik_puan_ve_oneri():
    kriler = rbm.VARSAYILAN_KRILER
    dusuk = bilesik_risk_puani({"SORGU_ORANI": 0.0, "SAPMA_ORANI": 0.0, "AE_ORANI": 1.0}, kriler)
    yuksek = bilesik_risk_puani({"SORGU_ORANI": 0.9, "SAPMA_ORANI": 0.9, "AE_ORANI": 0.05}, kriler)
    assert dusuk == 0
    assert yuksek >= 90
    assert bilesik_risk_puani({}, kriler) is None

    class CM:
        risk_puani = None
    cm = CM()
    assert "yeterli veri" in izlem_onerisi(cm)
    cm.risk_puani = 70
    assert "tetiklenmiş" in izlem_onerisi(cm)
    cm.risk_puani = 5
    assert "uzaktan" in izlem_onerisi(cm).lower()


# --- anomali ----------------------------------------------------------

def test_anomali_aykiri_tespit():
    d = {1: 0.10, 2: 0.12, 3: 0.09, 4: 0.11, 5: 0.10, 6: 0.55}
    s = anomali_tespit(d, "yuksek")
    assert s[6].aykiri and s[6].sira == 1 and s[6].z > 2.5
    assert not s[1].aykiri
    assert "medyan" in s[6].aciklama


def test_anomali_dusuk_yon():
    d = {1: 1.0, 2: 1.1, 3: 0.9, 4: 1.0, 5: 0.1}
    s = anomali_tespit(d, "dusuk")
    assert s[5].aykiri and s[5].sira == 1
    assert not s[1].aykiri


def test_anomali_az_merkez_ve_none():
    s = anomali_tespit({1: 5.0, 2: 1.0, 3: None}, "yuksek")
    assert not s[1].aykiri and "karşılaştırma yapılamadı" in s[1].aciklama
    assert s[3].z is None and s[3].aciklama == "Veri yok"
    assert anomali_tespit({}, "yuksek") == {}


def test_anomali_sabit_degerler():
    s = anomali_tespit({i: 2.0 for i in range(6)}, "yuksek")
    assert not any(v.aykiri for v in s.values())


def test_cusum():
    rng = np.random.default_rng(0)
    seri = list(rng.normal(0, 1, 30)) + list(rng.normal(2.5, 1, 15))
    S, alarm = cusum(seri, k=0.5, h=4.0)
    assert len(S) == 45
    assert alarm and alarm[0] >= 30
    assert not cusum([0.0] * 20, 0.5, 4.0)[1]


# -- P4: Turkce metinler, kacirilan vizit (durum), kapali sapmalar ---------------------

_ASCII_TUZAK = ("esik", "ustunde", "altinda", "gonullu", "yuksek", "dusuk", "gun ", "sure", "karsilastirma", "dagilim",
                "siklik", "sapmasi", "agirlik", "medyani", "degeri", "calisma", "oncul", "gecmis")


def _turkce_mi(metin: str) -> bool:
    k = metin.lower()
    return not any(f" {t}" in f" {k}" or k.startswith(t) for t in _ASCII_TUZAK)


def test_kri_ve_uyari_metinleri_turkce(veri):
    db, c, cmler = veri
    for k in rbm.VARSAYILAN_KRILER:
        assert _turkce_mi(k["ad"]) and _turkce_mi(k["aciklama"]), k["kod"]
        assert k["birim"] in ("%", "gün", "adet", "sorgu/form", "sapma/gönüllü", "AE/gönüllü")
    for q in rbm.VARSAYILAN_QTLLER:
        assert _turkce_mi(q["parametre"]) and _turkce_mi(q["gerekce"])
    uyarilar = rbm.erken_uyari_calistir(db, c)
    db.commit()
    assert uyarilar
    for u in uyarilar:
        assert _turkce_mi(u.mesaj) and _turkce_mi(u.aciklama), (u.mesaj, u.aciklama)
    major = next(u for u in uyarilar if u.kri_kod == "MAJOR_SAPMA")
    assert "Major sapma sayısı 3 adet" in major.mesaj and "eşiğinin üstünde" in major.aciklama

    class CM:
        risk_puani = 70
    assert _turkce_mi(izlem_onerisi(CM()))
    from smartclinical.services.rbm.gostergeler import deger_metni
    assert deger_metni(38, "%") == "%38" and deger_metni(12.5, "gün") == "12,5 gün"


def test_anomali_sonsuz_z_metni():
    s = anomali_tespit({1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 3.0}, "yuksek")
    assert s[5].aykiri and s[5].z is None and "diğer merkezlerde gözlenmedi" in s[5].aciklama
    assert not s[1].aykiri and s[1].z == 0.0


def test_kacirilan_vizit_durum_ve_kapali_sapma(veri):
    db, c, cmler = veri
    g = cmler[0].gonulluler[0]
    # gelecekte planli ama 'kacirildi' isaretlenmis vizit de sayilir (P2 durum alani)
    db.add(Vizit(gonullu_id=g.id, ad="V2", sira=2, planlanan=BUGUN + timedelta(days=10), durum="kacirildi"))
    db.flush()
    assert rbm.HESAPLAYICILAR["kacirilan_vizit"](db, cmler[0]) == pytest.approx(14.3, abs=0.1)
    # kapatilan sapmalar acik sapma oranina girmez; major sayisi degismez
    once = rbm.HESAPLAYICILAR["sapma_orani"](db, cmler[4])
    for s in db.query(ProtokolSapmasi).filter_by(calisma_merkez_id=cmler[4].id).all()[:3]:
        s.kapanis_tarihi = BUGUN
    db.flush()
    assert rbm.HESAPLAYICILAR["sapma_orani"](db, cmler[4]) < once
    assert rbm.HESAPLAYICILAR["major_sapma"](db, cmler[4]) == 3
