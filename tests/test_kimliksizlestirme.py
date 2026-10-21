from smartclinical.services.kimliksizlestirme import (
    Sonuc,
    kimliksizlestir,
    metni_dogrula,
    ozet_rapor,
    tckn_gecerli,
)

ORNEK = (
    "EPİKRİZ\n"
    "Hasta: Ayşe Yılmaz, TC: 10000000146, Tel: 0532 123 45 67, e-posta: ayse.yilmaz@gmail.com\n"
    "Dosya No: 2023-44521. Doğum tarihi 12.03.1951. 72 yaşında kadın hasta.\n"
    "İstanbul Üniversitesi Tıp Fakültesi Hastanesi Tıbbi Onkoloji Kliniği'ne 5 Mart 2023 tarihinde başvurdu.\n"
    "Sol meme Ca tanısı mevcut. Metastaz saptanmadı. Prof. Dr. Mehmet Kaya tarafından değerlendirildi.\n"
    "Tamoksifen 20 mg günde 1 tablet başlandı. Hemoglobin 11.2 g/dL. Kontrol 15/04/23.\n"
    "Adres: Bağdat Caddesi No: 12 Kadıköy. Yakını: Fatma Demir'in refakatinde. 34 AB 1234 plakalı araçla geldi.\n"
    "92 yaşında annesi var. IBAN TR33 0006 1005 1978 6457 8413 26"
)


def test_tckn_algoritmasi():
    assert tckn_gecerli("10000000146")
    assert not tckn_gecerli("10000000147")
    assert not tckn_gecerli("01234567890")
    assert not tckn_gecerli("1234")


def test_maske_modu_tum_turleri_yakalar():
    s = kimliksizlestir(ORNEK)
    assert isinstance(s, Sonuc)
    for tur in ("AD", "TCKN", "TELEFON", "EPOSTA", "KAYIT_NO", "TARIH", "KURUM", "ADRES", "PLAKA", "YAS", "IBAN"):
        assert tur in s.istatistik, tur
    m = s.metin
    assert "Ayşe" not in m and "Yılmaz" not in m and "Mehmet Kaya" not in m and "Fatma" not in m
    assert "10000000146" not in m and "0532" not in m and "gmail" not in m
    assert "12.03.1951" not in m and "5 Mart 2023" not in m and "15/04/23" not in m
    assert "Bağdat" not in m and "TR33" not in m
    assert "[TCKN]" in m and "[AD]" in m and "[YAS>89]" in m


def test_klinik_terimler_korunur():
    s = kimliksizlestir(ORNEK)
    for terim in ("Sol meme Ca", "Metastaz", "Tamoksifen 20 mg", "Hemoglobin 11.2", "72 yaşında", "Tıbbi Onkoloji"):
        assert terim in s.metin, terim


def test_bulgu_konumlari_cikti_metniyle_uyumlu():
    s = kimliksizlestir(ORNEK)
    for b in s.bulgular:
        assert s.metin[b.baslangic:b.bitis] == b.degisim
    assert s.toplam == len(s.bulgular) == sum(s.istatistik.values())


def test_takma_ad_tutarli_ve_deterministik():
    metin = "Ayşe Yılmaz geldi. Daha sonra Ayşe Yılmaz taburcu edildi. Mehmet Kaya muayene etti."
    a = kimliksizlestir(metin, mod="takma_ad")
    b = kimliksizlestir(metin, mod="takma_ad")
    assert a.metin == b.metin
    assert "Ayşe Yılmaz" not in a.metin and "Mehmet Kaya" not in a.metin
    takma = [x.degisim for x in a.bulgular if x.tur == "AD"]
    assert takma[0] == takma[1]            # ayni kisi -> ayni takma ad
    assert takma[0] != takma[2]            # farkli kisi -> farkli takma ad
    farkli_tuz = kimliksizlestir(metin, mod="takma_ad", tuz="baska")
    assert farkli_tuz.metin != a.metin


def test_takma_ad_ek_korur():
    s = kimliksizlestir("Yakını: Fatma Demir'in refakatinde.", mod="takma_ad")
    assert s.metin.endswith("'in refakatinde.")
    assert "Fatma" not in s.metin


def test_tarih_kaydirma():
    s = kimliksizlestir("Yatış 12.03.2023, kontrol 5 Mart 2023 ve 28/02/23.", mod="kaydir", ofset=10)
    assert "22.03.2023" in s.metin and "15 Mart 2023" in s.metin and "10/03/23" in s.metin
    s2 = kimliksizlestir("Yatış 25.12.2023.", mod="kaydir", ofset=10, yili_koru=True)
    assert "04.01.2023" in s2.metin  # yil korunur, gun/ay kayar


def test_kaydir_modu_diger_kimlikleri_maskeler():
    s = kimliksizlestir("Ayşe Yılmaz 12.03.2023 tarihinde TC 10000000146 ile başvurdu.", mod="kaydir", ofset=1)
    assert "[AD]" in s.metin and "[TCKN]" in s.metin and "13.03.2023" in s.metin


def test_gecersiz_tckn_benzeri_sayi_dokunulmaz():
    s = kimliksizlestir("Barkod 12345678901 okutuldu.")
    assert "TCKN" not in s.istatistik


def test_bos_metin():
    assert kimliksizlestir("").metin == ""
    assert kimliksizlestir("").toplam == 0


def test_gecersiz_mod():
    import pytest
    with pytest.raises(ValueError):
        kimliksizlestir("x", mod="yok")


def test_dogrulama_ikinci_gecis():
    temiz = kimliksizlestir(ORNEK).metin
    assert metni_dogrula(temiz) == []
    kirli = "Hastanın TC numarası 98765432109 ve tel 5321234567, Ahmet gelecek."
    uyarilar = metni_dogrula(kirli)
    assert any("11 haneli" in u for u in uyarilar)
    assert any("Ahmet" in u for u in uyarilar)


def test_ozet_rapor():
    s = kimliksizlestir(ORNEK)
    r = ozet_rapor(s)
    assert r.startswith("Toplam") and "AD" in r
    assert ozet_rapor(kimliksizlestir("Hemoglobin 11.2 g/dL.")) == "Kimlik verisi tespit edilmedi."
