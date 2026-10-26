import os
from types import SimpleNamespace

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest

from smartclinical.services.bdm import BDMErisimHatasi, BDMIstemci, korumalar, saglayici_olustur
from smartclinical.services.bdm.rag import (
    BM25Indeks,
    HibritArama,
    Parcalayici,
    cumlelere_bol,
    govde,
    tokenize,
)
from smartclinical.services.bdm.saglayicilar import KuralTabanliSaglayici, OllamaSaglayici, VLLMSaglayici

EPIKRIZ = (
    "Hasta 54 yaşında kadın. Sol meme üst dış kadranda kitle nedeniyle yapılan tru-cut biyopsi sonucu "
    "invaziv duktal karsinom olarak raporlandı. İmmünohistokimyasal incelemede ER pozitif, PR pozitif, HER2 negatif "
    "saptandı. Ki-67 %25. Hastanın bilinen hipertansiyonu mevcut, amlodipin kullanmakta. Diyabet öyküsü yok. "
    "Gebelik yok, emzirmiyor. ECOG performans durumu 1 olarak değerlendirildi. Daha önce kemoterapi almamış. "
    "Toraks BT'de metastaz lehine bulgu izlenmedi."
)


@pytest.fixture
def istemci():
    return BDMIstemci(KuralTabanliSaglayici())


# -- rag ---------------------------------------------------------------------

def test_cumle_bolme_kisaltma():
    c = cumlelere_bol("Prof. Dr. Ayşe tarafından değerlendirildi. İkinci cümle burada. Üçüncü!")
    assert len(c) == 3
    assert c[0].startswith("Prof. Dr.")


def test_parcalayici_pencere():
    p = Parcalayici(pencere=2, kaydirma=1).parcala(EPIKRIZ)
    assert len(p) > 3
    assert all(len(x) <= 900 for x in p)


def test_tokenize_turkce():
    t = tokenize("Hastanın İNVAZİV karsinomu ve metastazları")
    assert "hasta" in t and "invaziv" in t
    assert govde("metastazları") == "metastaz"


def test_bm25_arama():
    parcalar = cumlelere_bol(EPIKRIZ)
    idx = BM25Indeks(parcalar)
    hits = idx.ara("hipertansiyon amlodipin")
    assert hits and "amlodipin" in parcalar[hits[0][0]]


def test_hibrit_arama_gommesiz():
    arama = HibritArama(cumlelere_bol(EPIKRIZ))
    hits = arama.ara("metastaz", k=1)
    assert hits and "metastaz" in hits[0][2]
    assert HibritArama([]).ara("x") == []


# -- korumalar -----------------------------------------------------------------

def test_kanit_dogrula_birebir_ve_yakin():
    parcalar = ["Hastanın bilinen hipertansiyonu mevcut, amlodipin kullanmakta.", "Diyabet öyküsü yok."]
    assert korumalar.kanit_dogrula("hipertansiyonu mevcut, amlodipin kullanmakta", parcalar) == (True, 0)
    assert korumalar.kanit_dogrula("Hastanın bilinen hipertansiyonu mevcut amlodipin kullanıyor", parcalar)[0] is True
    assert korumalar.kanit_dogrula("Hasta metformin kullanmaktadır ve diyabetiktir", parcalar)[0] is False
    assert korumalar.kanit_dogrula("", parcalar)[0] is False


def test_json_ayikla():
    assert korumalar.json_ayikla('bla ```json\n{"a": 1}\n``` son') == {"a": 1}
    assert korumalar.json_ayikla('Cevap: {"sonuc": "saglandi", "guven": 0.9,} ') == {"sonuc": "saglandi", "guven": 0.9}
    assert korumalar.json_ayikla("json yok") is None


def test_belirsizlik_esigi():
    assert korumalar.belirsizlik_uygula("saglandi", 0.4) == ("belirsiz", 0.4)
    assert korumalar.belirsizlik_uygula("saglandi", 0.8) == ("saglandi", 0.8)
    assert korumalar.belirsizlik_uygula("sacma", 0.9)[0] == "belirsiz"


def test_cogunluk_oyu():
    assert korumalar.cogunluk_oyu([("saglandi", 0.9), ("saglandi", 0.7), ("belirsiz", 0.2)])[0] == "saglandi"
    assert korumalar.cogunluk_oyu([("saglandi", 0.9), ("saglanmadi", 0.9)])[0] == "belirsiz"


def test_phi_kontrol():
    korumalar.phi_kontrol("Hasta 54 yaşında, Hb 11.2 g/dL")
    with pytest.raises(korumalar.KorumaIhlali):
        korumalar.phi_kontrol("TC: 10000000146 hasta")
    with pytest.raises(korumalar.KorumaIhlali):
        korumalar.phi_kontrol("iletişim 0532 123 45 67")


# -- saglayicilar ----------------------------------------------------------------

def test_saglayici_fabrikasi():
    assert isinstance(saglayici_olustur("kural"), KuralTabanliSaglayici)
    assert isinstance(saglayici_olustur("ollama", "http://x", "m"), OllamaSaglayici)
    assert isinstance(saglayici_olustur("vllm", "http://x", "m"), VLLMSaglayici)
    assert isinstance(saglayici_olustur("yok"), KuralTabanliSaglayici)


def test_ag_hatasi_turkce_istisna():
    s = OllamaSaglayici("http://127.0.0.1:9", "m", zaman_asimi=1)
    with pytest.raises(BDMErisimHatasi):
        s.uret("merhaba")
    assert s.hazir() is False


def test_istemci_ag_hatasinda_kurala_duser():
    c = BDMIstemci(VLLMSaglayici("http://127.0.0.1:9", "m", zaman_asimi=1))
    r = c.kanit_cikar("Hipertansiyon", cumlelere_bol(EPIKRIZ))
    assert r.yontem == "kural" and r.sonuc == "saglandi"
    assert c.hazir() is False


# -- gorevler (kural modu) ----------------------------------------------------------

def test_durum(istemci):
    d = istemci.durum()
    assert d["saglayici"] == "kural" and d["hazir"] is True


def test_kriter_yapilandir_kural(istemci):
    y = istemci.kriter_yapilandir("Hemoglobin ≥ 9 g/dL")
    assert y.kategori == "lab" and y.yontem == "kural"


@pytest.mark.parametrize("kriter,beklenen", [
    ("Hipertansiyon", "saglandi"),
    ("Tip 2 diyabet", "saglanmadi"),
    ("Gebe veya emziren kadınlar", "saglanmadi"),
    ("Daha önce kemoterapi almış hastalar", "saglanmadi"),
    ("Uzak metastaz varlığı", "saglanmadi"),
    ("HER2-negatif meme kanseri", "saglandi"),
    ("Kronik böbrek hastalığı", "belirsiz"),
])
def test_kanit_cikar_kural(istemci, kriter, beklenen):
    r = istemci.kanit_cikar(kriter, Parcalayici().parcala(EPIKRIZ))
    assert r.sonuc == beklenen
    if beklenen != "belirsiz":
        assert r.kanit_cumlesi and r.kanit_cumlesi in EPIKRIZ


def test_kanit_cikar_bos_metin(istemci):
    assert istemci.kanit_cikar("Hipertansiyon", []).sonuc == "belirsiz"


def test_klinik_ozet_ve_soru_cevap(istemci):
    oz = istemci.klinik_ozet(EPIKRIZ)
    assert 1 <= len(oz) <= 5
    c = istemci.soru_cevap("Hasta hangi antihipertansif ilacı kullanıyor?", EPIKRIZ)
    assert "amlodipin" in c["cevap"].lower()


def test_protokol_taslagi_kural_modunda_none(istemci):
    assert istemci.protokol_taslagi("4.1 Dahil Etme Kriterleri\n1. 18 yaş ve üzeri") is None


def test_json_sema_ic_ice():
    sema = {"vizitler": [{"ad": str, "gun": (int, float)}], "formlar": [str], "guven": (int, float)}
    assert korumalar.json_sema({"vizitler": [{"ad": "V1", "gun": 0}], "formlar": ["VS"], "guven": 0.8}, sema)
    assert not korumalar.json_sema({"vizitler": [{"ad": "V1"}], "formlar": ["VS"], "guven": 0.8}, sema)
    assert not korumalar.json_sema({"vizitler": [], "formlar": [1], "guven": 0.8}, sema)
    assert not korumalar.json_sema(None, sema)


# -- dis URL'de kural moduna dusme, istem ozeti, sozluk adi korumasi ------------------

def _ayar(**ek):
    v = {"bdm_saglayici": "vllm", "bdm_url": "http://bdm.example.com", "bdm_model": "m", "bdm_zaman_asimi_sn": 1}
    v.update(ek)
    return SimpleNamespace(**v)


def _denetim(islem):
    from sqlalchemy import select

    from smartclinical.db import oturum_fabrikasi
    from smartclinical.models import DenetimKaydi

    db = oturum_fabrikasi()()
    try:
        return db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == islem).order_by(DenetimKaydi.id.desc())).scalars().all()
    finally:
        db.close()


def test_dis_url_kural_moduna_duser_ve_denetime_yazar(monkeypatch):
    from smartclinical.db import sifirla

    sifirla()
    monkeypatch.delenv("SC_BDM_DIS_IZIN", raising=False)
    c = BDMIstemci.olustur(_ayar())
    assert c.kural_modu and "özel ağ dışında" in (c.dusme_nedeni or "") and c.durum()["not"]
    kayitlar = _denetim("bdm_engel")
    assert kayitlar and kayitlar[0].yeni["url"] == "http://bdm.example.com" and kayitlar[0].yeni["neden"] == "ozel_ag_disi"
    monkeypatch.setenv("SC_BDM_DIS_IZIN", "1")
    assert not BDMIstemci.olustur(_ayar()).kural_modu
    assert not BDMIstemci.olustur(_ayar(bdm_url="http://10.0.0.5:8000")).kural_modu
    assert BDMIstemci.olustur(_ayar(bdm_saglayici="kural")).kural_modu and BDMIstemci.olustur(_ayar(bdm_saglayici="kural")).dusme_nedeni is None


class _SahteSaglayici(VLLMSaglayici):
    ad = "sahte"

    def hazir(self):
        return True

    def uret(self, istem, sistem=None, json_cikti=False, sicaklik=0.0, maks_token=512):
        from smartclinical.services.bdm.saglayicilar import Uretim
        return Uretim('{"kategori": "lab", "sorgu": {"alan": "lab", "ad": "hemoglobin", "op": ">=", "deger": 9}, "guven": 0.9}', 12, 5, "m")


def test_istem_ozeti_denetime_yazilir_metin_yazilmaz():
    from smartclinical.db import sifirla

    sifirla()
    c = BDMIstemci(_SahteSaglayici("http://10.0.0.5", "m"))
    y = c.kriter_yapilandir("Hemoglobin ≥ 9 g/dL")
    assert y.yontem == "bdm"
    kayitlar = _denetim("bdm_istem")
    assert kayitlar and kayitlar[0].yeni["gorev"] == "kriter_yapilandir" and kayitlar[0].yeni["sonuc"] == "ok"
    assert len(kayitlar[0].yeni["hash"]) == 64 and "Hemoglobin" not in str(kayitlar[0].yeni)
    # istemde sozluk adi varsa phi_kontrol engeller ve kayit 'phi_engel' olur
    with pytest.raises(korumalar.KorumaIhlali):
        c._uret_json("Hasta ayşe yılmaz 54 yaşında", {"a": str}, gorev="deneme")
    assert _denetim("bdm_istem")[0].yeni["sonuc"] == "phi_engel"


def test_phi_kontrol_sozluk_adi():
    with pytest.raises(korumalar.KorumaIhlali):
        korumalar.phi_kontrol("Dr. Mehmet Kaya tarafından değerlendirildi")
    korumalar.phi_kontrol("18 yaş ve üzeri kadın hastalar; ECOG 0-1")
