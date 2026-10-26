"""P4: eCRF tasarimcisi, protokol belgesinden taslak, kriter sayfasi cumleleri, analiz varsayilanlari (tek kollu),
merkez siniri, metin kalitesi (RBM / merkez zekasi), ayarlar ve hata sayfasi, arac yetkisi."""
import io
import os
from datetime import date

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
    FormKaydi,
    Gonullu,
    GonulluDurumu,
    Kol,
    Kriter,
    Kullanici,
    Merkez,
    Rol,
    Vizit,
)
from smartclinical.models import Form as CRF
from smartclinical.models.kurulum import MOD_ETIKET
from smartclinical.models.tasarim import VizitTanimi
from smartclinical.services import analiz, ecrf, protokol, yetki
from smartclinical.services.kriter import yapilandir
from smartclinical.services.kriter.okunur import kriter_cumlesi
from smartclinical.services.kurulum import ayar_yaz

PAROLA = "Test1234!xyz"

PROTOKOL = """Dahil Etme Kriterleri
1. 18 yaş ve üzeri kadın hastalar
2. Hemoglobin ≥ 9 g/dL
Hariç Tutma Kriterleri
a) Gebe veya emziren kadınlar
Çalışma Kolları
Kol A: Araştırma ürünü 200 mg günde iki kez; Kol B: Plasebo
Vizit Takvimi
Tarama (-14 gün ± 7)
Vizit 1 (Gün 0)
Vizit 2 (Gün 28 ± 3)
Hafta 12
Değerlendirmeler
- Her vizitte vital bulgular kaydedilir
- Haftalık telefon görüşmesi yapılır
"""


@pytest.fixture(scope="module")
def istemci():
    sifirla()
    db = oturum_fabrikasi()()
    m1 = Merkez(kod="P4-01", ad="Birinci Hastane", sehir="Ankara", kurum_tipi="universite")
    m2 = Merkez(kod="P4-02", ad="İkinci Hastane", sehir="İzmir", kurum_tipi="sehir")
    db.add_all([m1, m2])
    db.flush()

    def kul(adi, rol, **ek):
        return Kullanici(kullanici_adi=adi, ad_soyad=adi.title(), eposta=f"{adi}@t.local",
                         parola_hash=yetki.parola_hashle(PAROLA), rol=rol, **ek)

    db.add_all([kul("admin", Rol.YONETICI), kul("ar", Rol.ARASTIRMACI, merkez_id=m1.id), kul("cra", Rol.CRA),
                kul("py", Rol.PROJE_YONETICISI)])
    c = Calisma(kod="P4-001", baslik="P4 testi", kisa_ad="P4", tur=CalismaTuru.ILAC, sponsor="S", terapotik_alan="Onkoloji",
                hedef_hasta=10, baslangic=date(2024, 1, 1), planlanan_bitis=date(2025, 1, 1))
    db.add(c)
    db.flush()
    cm1 = CalismaMerkez(calisma_id=c.id, merkez_id=m1.id, merkez_no="01", hedef_hasta=5, durum="aktif", aktivasyon_tarihi=date(2024, 1, 1))
    cm2 = CalismaMerkez(calisma_id=c.id, merkez_id=m2.id, merkez_no="02", hedef_hasta=5, durum="aktif", aktivasyon_tarihi=date(2024, 1, 1))
    kol = Kol(calisma_id=c.id, ad="Tek kol")
    db.add_all([cm1, cm2, kol])
    db.flush()
    for i, (ad, gun, p) in enumerate([("Tarama", -14, 7), ("V1", 0, 0), ("V2", 28, 3)]):
        db.add(VizitTanimi(calisma_id=c.id, ad=ad, sira=i, gun=gun, pencere_gun=p))
    vs = CRF(calisma_id=c.id, kod="VS", ad="Vital Bulgular", vizitler=["V1", "V2"], sira=0, durum="yayinda",
             alanlar=[ecrf.alan_normalize({"kod": "SYSBP", "etiket": "Sistolik kan basıncı", "tip": "sayi", "birim": "mmHg"})])
    dm = CRF(calisma_id=c.id, kod="DM", ad="Demografi", vizitler=["Tarama"], sira=1, durum="yayinda",
             alanlar=[ecrf.alan_normalize(a) for a in ecrf.STANDART_FORMLAR["DM"]["alanlar"]])
    db.add_all([vs, dm])
    db.flush()
    for cm, n in ((cm1, 3), (cm2, 2)):
        for j in range(n):
            g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, gonullu_no=f"{cm.merkez_no}-{j + 1:03d}",
                        durum=GonulluDurumu.TEDAVIDE, kol_id=kol.id, randomizasyon_tarihi=date(2024, 3, 1))
            db.add(g)
            db.flush()
            vizitler = {}
            for i, ad in enumerate(("Tarama", "V1", "V2")):
                v = Vizit(gonullu_id=g.id, ad=ad, sira=i, planlanan=date(2024, 3, 1), gerceklesen=date(2024, 3, 1), durum="yapildi")
                db.add(v)
                db.flush()
                vizitler[ad] = v
            db.add(FormKaydi(gonullu_id=g.id, form_id=dm.id, vizit_id=vizitler["Tarama"].id, durum="tamamlandi",
                             veriler={"BRTHYR": str(1960 + j * 5), "SEX": "Kadın" if j % 2 else "Erkek", "HEIGHT": "170", "WEIGHT": "70"}))
            db.add(FormKaydi(gonullu_id=g.id, form_id=vs.id, vizit_id=vizitler["V1"].id, durum="tamamlandi", veriler={"SYSBP": str(130 + j)}))
            db.add(FormKaydi(gonullu_id=g.id, form_id=vs.id, vizit_id=vizitler["V2"].id, durum="tamamlandi", veriler={"SYSBP": str(120 + 2 * j)}))
    for sira, (metin, guven) in enumerate((("18 yaş ve üzeri kadın hastalar", 0.9), ("Hemoglobin ≥ 9 g/dL", 0.85), ("Yeterli organ fonksiyonu", 0.4)), 1):
        y = yapilandir(metin, "dahil")
        db.add(Kriter(calisma_id=c.id, tip="dahil", sira=sira, metin=metin, yapisal=y.to_dict(), guven=guven, onaylandi=False))
    from smartclinical.services.rbm import varsayilan_krileri_yukle

    varsayilan_krileri_yukle(db, c.id)
    db.commit()
    db.close()
    with TestClient(app) as cl:
        yield cl


def _giris(cl, kadi):
    cl.cookies.clear()
    r = cl.post("/giris", data={"kullanici_adi": kadi, "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
    assert r.status_code == 303


def _cid() -> int:
    db = oturum_fabrikasi()()
    cid = db.execute(select(Calisma.id).where(Calisma.kod == "P4-001")).scalar_one()
    db.close()
    return cid


# -- kriter cumlesi --------------------------------------------------------------

def test_kriter_cumlesi():
    assert kriter_cumlesi(yapilandir("18 yaş ve üzeri kadın hastalar").to_dict()) == "Yaş ≥ 18 VE Cinsiyet = Kadın"
    assert kriter_cumlesi(yapilandir("Hemoglobin ≥ 9 g/dL").to_dict()) == "Hemoglobin ≥ 9 g/dL"
    assert kriter_cumlesi(yapilandir("ECOG performans skoru 0-1").to_dict()) == "ECOG skoru 0–1 arası"
    assert kriter_cumlesi({"ve": [{"alan": "yas", "op": "<", "deger": 75}, {"degil": {"alan": "gebelik", "deger": True}}]}) \
        == "Yaş < 75 VE DEĞİL: Gebe ya da emziriyor"
    assert kriter_cumlesi(None) == "Hesaplanabilir sorgu yok" and kriter_cumlesi({"kategori": "serbest", "sorgu": None}).startswith("Hesaplanabilir")
    assert "ICD-10" in kriter_cumlesi(yapilandir("Tip 2 diyabet tanısı").to_dict())


def test_kriter_sayfasi_cumle_json_ve_toplu_onay(istemci):
    _giris(istemci, "admin")
    r = istemci.get(f"/calismalar/{_cid()}/protokol")
    assert r.status_code == 200
    assert "Yaş ≥ 18 VE Cinsiyet = Kadın" in r.text and "teknik ayrıntı (JSON)" in r.text
    assert "\\u00" not in r.text  # JSON kacissiz (ensure_ascii=False)
    assert "Güven eşiği üstündekileri toplu onayla (2)" in r.text and "Düşük güven:" in r.text
    assert "/protokol/kriter/toplu-onay" in r.text


# -- tasarimci ve protokol belgesi -------------------------------------------------

def test_tasarimci_sayfasi(istemci):
    _giris(istemci, "admin")
    cid = _cid()
    r = istemci.get(f"/calismalar/{cid}/tasarim")
    assert r.status_code == 200 and "Vizit × form matrisi" in r.text and "PHQ9 – PHQ-9 Depresyon Ölçeği" in r.text
    r = istemci.get(f"/calismalar/{cid}/tasarim/form/yeni")
    assert r.status_code == 200 and "<title>" not in r.text[:0] and "Yeni eCRF formu" in r.text
    for parca in ('class="tip"', "Seçenekler / Birim · Min · Max", 'id="alan-ayrinti"', 'data-p="cdash"', 'id="cdash-listesi"',
                  'data-hizli="tarih"', 'data-hizli="sayi"', 'id="onizleme"', 'name="tekrarlayan"', "/static/js/ecrf.js"):
        assert parca in r.text, parca
    r = istemci.get("/static/js/ecrf.js")
    assert r.status_code == 200 and "function kodUret" in r.text and "TR_HARF" in r.text
    # CRA tasarim sekmesini goremez (sekme_kontrol)
    _giris(istemci, "cra")
    assert istemci.get(f"/calismalar/{cid}/tasarim").status_code == 403
    assert istemci.get(f"/calismalar/{cid}/tasarim/protokol-taslak").status_code == 403


def _docx(metin: str) -> bytes:
    import docx

    d = docx.Document()
    for satir in metin.splitlines():
        d.add_paragraph(satir)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_protokol_belgesinden_taslak_dosya_saklanmaz(istemci, tmp_path):
    from smartclinical.config import ayarlar

    _giris(istemci, "admin")
    cid = _cid()
    b = f"/calismalar/{cid}/tasarim/protokol-taslak"
    dizin = ayarlar().dosya_dizini
    onceki = {p for p in dizin.rglob("*")} if dizin.exists() else set()
    r = istemci.post(f"{b}/dosya", files={"dosya": ("protokol.docx", _docx(PROTOKOL),
                                                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code == 200
    assert "Kol A: Araştırma ürünü 200 mg günde iki kez" in r.text and 'value="Kol B: Plasebo"' in r.text
    assert "şema kilitli" in r.text and 'name="vizitler"' not in r.text and "EX – Araştırma Ürünü" in r.text
    t = protokol.taslak_cikar(protokol.belge_metni(_docx(PROTOKOL), "protokol.docx"))
    assert ("Vizit 2", 28, 3) in t.vizitler and ("Hafta 12", 84, 3) in t.vizitler and ("Tarama", -14, 7) in t.vizitler
    assert "Tanınmayan satırlar" in r.text and "Haftalık telefon görüşmesi yapılır" in r.text and 'name="tn_tip_' in r.text
    assert "dosya saklanmadı" in r.text
    sonraki = {p for p in dizin.rglob("*")} if dizin.exists() else set()
    assert sonraki == onceki
    # metin dosyasi da okunur; pdfminer kurulu
    r = istemci.post(f"{b}/dosya", files={"dosya": ("protokol.txt", PROTOKOL.encode("utf-8"), "text/plain")})
    assert r.status_code == 200 and 'value="Kol B: Plasebo"' in r.text and "protokol.txt" in r.text
    import pdfminer  # noqa: F401
    assert protokol.belge_metni(_docx("Vizit 1 (Gün 0)"), "x.docx").strip() == "Vizit 1 (Gün 0)"
    with pytest.raises(ValueError):
        protokol.belge_metni(b"abc", "x.xlsx")
    db = oturum_fabrikasi()()
    kayit = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "protokol_belge")).scalars().all()
    assert kayit and kayit[0].yeni["saklandi"] is False and kayit[0].yeni["dosya"] == "protokol.docx"
    db.close()
    # metne don: textarea gonderilen metinle dolu gelir
    r = istemci.post(f"{b}/metin", data={"metin": "Dahil Etme Kriterleri\n1. deneme"})
    assert r.status_code == 200 and "1. deneme" in r.text


def test_taninmayan_satir_tek_tikla_eklenir_ve_kilitli_sema(istemci):
    _giris(istemci, "admin")
    cid = _cid()
    b = f"/calismalar/{cid}/tasarim/protokol-taslak"
    r = istemci.post(b, data={"metin": PROTOKOL})
    assert r.status_code == 200
    # gonullu vizitleri oldugundan sema kilitli: vizit onerileri listelenmez
    assert "şema kilitli" in r.text and 'name="vizitler"' not in r.text
    # zaten var olan kriter isaretsiz (normalize karsilastirma: nokta ve buyuk harf farki)
    assert "zaten var" in r.text
    r = istemci.post(f"{b}/uygula", data={"tn_metin_2": "Haftalık telefon görüşmesi yapılır", "tn_tip_2": "haric",
                                          "tn_metin_1": "Her vizitte vital bulgular kaydedilir", "tn_tip_1": "",
                                          "dahil": ["18 Yaş ve üzeri kadın hastalar."], "kollar": ["Kol B: Plasebo"]},
                     follow_redirects=False)
    assert r.status_code == 303
    db = oturum_fabrikasi()()
    c = db.get(Calisma, cid)
    assert [x.metin for x in c.kriterler if x.tip == "haric"] == ["Haftalık telefon görüşmesi yapılır"]
    assert len([x for x in c.kriterler if x.tip == "dahil"]) == 3  # normalize esleme: cift kayit yok
    assert [k.ad for k in c.kollar] == ["Tek kol", "Kol B: Plasebo"]
    db.delete(c.kollar[1])  # calisma tek kollu kalsin (analiz varsayilan gorunum testi)
    db.commit()
    db.close()


# -- analiz: tek kollu varsayilan, yas turetme, merkez siniri ------------------------

def test_tek_kollu_calismada_varsayilan_degisim_ve_yas(istemci):
    _giris(istemci, "admin")
    cid = _cid()
    db = oturum_fabrikasi()()
    c = db.get(Calisma, cid)
    assert analiz.varsayilan_vizit(c) == "V1"
    d = {x["kod"]: x for x in analiz.degiskenler(c)}
    assert "DM.YAS" in d and "DM.BRTHYR" not in d and d["DM.YAS"]["turetilmis"] == "yas"
    yas = analiz.kol_degerleri(c, "DM.YAS", "Tarama")["Tek kol"]
    assert sorted(yas) == [54.0, 59.0, 59.0, 64.0, 64.0]  # randomizasyon yili (2024) - dogum yili
    sutunlar, satirlar = analiz.veri_seti(c)
    assert "DM.YAS" in sutunlar and "DM.BRTHYR" not in sutunlar
    t = analiz.tablo1(c, "Tarama")
    assert any(s["etiket"].startswith("Yaş (doğum yılından türetilmiş)") for s in t["satirlar"])
    db.close()
    r = istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.SYSBP")
    assert r.status_code == 200 and "Tek kollu çalışmada varsayılan görünüm değişimdir" in r.text
    assert "V1 → V2" in r.text and ("Eşleştirilmiş t testi" in r.text or "Wilcoxon" in r.text)
    r = istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.SYSBP&mod=vizit")
    assert r.status_code == 200 and 'value="V1" selected' in r.text and "(başlangıç)" in r.text
    r = istemci.get(f"/calismalar/{cid}/analiz?degisken=VS.SYSBP&mod=vizit&vizit=tum")
    assert r.status_code == 200 and "kol testi yapılmaz" in r.text and "5 gönüllü" in r.text


def test_arastirmaci_merkez_siniri(istemci):
    _giris(istemci, "ar")
    cid = _cid()
    r = istemci.get(f"/calismalar/{cid}/analiz")
    assert r.status_code == 200 and "Yalnızca merkezinizin gönüllüleri" in r.text
    r = istemci.get(f"/calismalar/{cid}/analiz/veri-seti.csv")
    assert r.status_code == 200
    satirlar = r.text.splitlines()
    assert len(satirlar) == 10 and all(s.startswith("01-") for s in satirlar[1:])
    r = istemci.get(f"/calismalar/{cid}/analiz/tablo1?vizit=V1")
    assert r.status_code == 200 and "3 gönüllünün kaydı var" in r.text
    _giris(istemci, "admin")
    r = istemci.get(f"/calismalar/{cid}/analiz/tablo1?vizit=V1")
    assert "5 gönüllünün kaydı var" in r.text and "Yalnızca merkezinizin" not in r.text


# -- ayarlar, hata sayfasi, araclar ---------------------------------------------------

def test_hata_sayfasi_gercek_modu_gosterir_ve_sistem_sayfasi(istemci):
    db = oturum_fabrikasi()()
    ayar_yaz(db, "cro", "Test CRO")
    db.commit()
    db.close()
    _giris(istemci, "cra")
    r = istemci.get("/yonetim/sistem")
    assert r.status_code == 403 and MOD_ETIKET["cro"] in r.text and "Kullanım modu:" in r.text
    # hata metni flash kutusu olarak ikinci kez gosterilmez
    assert r.text.count("Bu işlem için yetkiniz yok") == 1
    _giris(istemci, "admin")
    r = istemci.get("/yonetim/sistem")
    assert r.status_code == 200
    for parca in ("<th>Sağlayıcı</th>", "<th>Model</th>", "<th>Durum</th>", "Kural tabanlı mod: sunucu tanımlı değil",
                  "<summary>Teknik bilgi</summary>", "Tablo kayıt sayıları"):
        assert parca in r.text, parca


def test_kimliksizlestirme_araci_yalnizca_yonetici(istemci):
    _giris(istemci, "ar")
    assert istemci.get("/araclar/kimliksizlestirme").status_code == 403
    _giris(istemci, "admin")
    r = istemci.get("/araclar/kimliksizlestirme")
    assert r.status_code == 200
    r = istemci.post("/araclar/kimliksizlestirme", data={"metin": "hasta ayşe yılmaz 12.03.2024 geldi", "mod": "maske"})
    assert r.status_code == 200 and "[AD]" in r.text and "şüpheli kalıp bulunmadı" in r.text


def test_merkez_zekasi_ve_rbm_sayfalari_metinler(istemci):
    _giris(istemci, "admin")
    cid = _cid()
    r = istemci.get(f"/calismalar/{cid}/merkez-zekasi")
    assert r.status_code == 200 and "henüz hesaplanmadı" in r.text
    assert istemci.post(f"/calismalar/{cid}/merkez-zekasi/guncelle", follow_redirects=False).status_code == 303
    r = istemci.get(f"/calismalar/{cid}/merkez-zekasi")
    assert r.status_code == 200 and "Zamanında bitirme olasılığı" in r.text and "100%" not in r.text
    assert "Monte Carlo yüzdelikleriyle" in r.text
    r = istemci.get(f"/calismalar/{cid}/rbm")
    assert r.status_code == 200 and "Kaçırılan vizit oranı" in r.text and "Önerilen izlem" in r.text
    assert "Merkez × KRI" in r.text and 'class="kri" title="KACIRILAN_VIZIT' in r.text
    r = istemci.get(f"/calismalar/{cid}/eslestirme")
    assert r.status_code == 200 and "Listeyi filtrele" in r.text and "Taramayı çalıştır" in r.text
    assert "Uygun değil" in r.text and ">uygun_degil<" not in r.text


def test_bitirme_olasiligi_yuz_yerine_99_ustu():
    # sayfa: olasilik 0.995 ve ustunde '>%99' ve varsayim notu; '%100' hic gosterilmez
    from smartclinical.web.sablon import sablonlar

    kaynak, _, _ = sablonlar.env.loader.get_source(sablonlar.env, "eslestirme/merkez_zekasi.html")
    assert "&gt;%99" in kaynak and "olasilik >= 0.995" in kaynak and "%100" not in kaynak
    assert "varsayımına dayanır" in kaynak and "henüz hesaplanmadı" in kaynak
