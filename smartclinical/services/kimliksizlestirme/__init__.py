"""Turkce klinik serbest metin kimliksizlestirme.

Kullanim:
    >>> from smartclinical.services.kimliksizlestirme import kimliksizlestir
    >>> s = kimliksizlestir("Hasta Ayşe Yılmaz 12.03.2023 tarihinde ...")
    >>> s.metin
    'Hasta [AD] [TARIH] tarihinde ...'

Uc mod var:
    maske    -> [AD], [TCKN], [TARIH] gibi etiketler
    takma_ad -> deterministik sahte deger (ayni metinde ayni isim ayni takma ada gider)
    kaydir   -> tarihler sabit ofsetle kaydirilir, diger kimlik verisi maskelenir

HBYS'den gelen her serbest metin Hasta.metinler alanina yazilmadan once buradan gecmek zorunda.
Kural tabanli yaklasim; BDM tabanli NER katmani (ml/) hazir olunca ikinci gecis olarak eklenecek.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .kurallar import ETIKET_AD_RE, KELIME_RE, KURALLAR, UNVAN_AD_RE
from .sozluk import ADLAR, AYLAR, KLINIK_BEYAZ_LISTE, SOYADLAR

ETIKETLER = {
    "AD": "[AD]", "TCKN": "[TCKN]", "TELEFON": "[TELEFON]", "EPOSTA": "[EPOSTA]", "IBAN": "[IBAN]",
    "PLAKA": "[PLAKA]", "TARIH": "[TARIH]", "KAYIT_NO": "[KAYIT_NO]", "KURUM": "[KURUM]",
    "ADRES": "[ADRES]", "IL": "[IL]", "YAS": "[YAS>89]",
}


def tr_kucuk(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


_ADLAR_K = {tr_kucuk(a) for a in ADLAR}
_SOYADLAR_K = {tr_kucuk(a) for a in SOYADLAR}


@dataclass
class Bulgu:
    tur: str
    baslangic: int
    bitis: int
    orijinal_uzunluk: int
    degisim: str

    @property
    def orijinal(self) -> str:  # geriye donuk uyumluluk icin; metni tutmuyoruz
        return ""


@dataclass
class Sonuc:
    metin: str
    bulgular: list[Bulgu] = field(default_factory=list)
    istatistik: dict[str, int] = field(default_factory=dict)

    @property
    def toplam(self) -> int:
        return sum(self.istatistik.values())


def tckn_gecerli(s: str) -> bool:
    if len(s) != 11 or not s.isdigit() or s[0] == "0":
        return False
    d = [int(c) for c in s]
    tek = d[0] + d[2] + d[4] + d[6] + d[8]
    cift = d[1] + d[3] + d[5] + d[7]
    if (tek * 7 - cift) % 10 != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


def _kok(kelime: str) -> str:
    # kesme isaretli eki at: Ayşe'nin -> Ayşe
    return re.split(r"['’]", kelime)[0]


def _isim_mi(kelime: str) -> bool:
    k = tr_kucuk(_kok(kelime))
    if k in KLINIK_BEYAZ_LISTE:
        return False
    return k in _ADLAR_K or k in _SOYADLAR_K


def _beyaz_mi(kelime: str) -> bool:
    return tr_kucuk(_kok(kelime)) in KLINIK_BEYAZ_LISTE


# ----------------------------------------------------------------------------- tespit

def _adlari_bul(metin: str) -> list[tuple[int, int, str]]:
    bulunan: list[tuple[int, int, str]] = []

    for m in UNVAN_AD_RE.finditer(metin):
        kelimeler = [k for k in m.group(1).split() if not _beyaz_mi(k)]
        if kelimeler:
            bulunan.append((m.start(1), m.start(1) + len(" ".join(m.group(1).split()[: len(kelimeler)])), "AD"))
    for m in ETIKET_AD_RE.finditer(metin):
        bulunan.append((m.start(1), m.end(1), "AD"))

    # Sozluk + buyuk harf heuristigi: ardisik buyuk harfli kelimeler, en az biri sozlukte
    kelimeler = list(KELIME_RE.finditer(metin))
    i = 0
    while i < len(kelimeler):
        grup = [kelimeler[i]]
        j = i + 1
        while j < len(kelimeler):
            ara = metin[kelimeler[j - 1].end():kelimeler[j].start()]
            if ara != " " and ara != "  ":
                break
            grup.append(kelimeler[j])
            j += 1
        # grubu basindan ve sonundan beyaz listeyle kirp
        while grup and _beyaz_mi(grup[0].group()):
            grup.pop(0)
        while grup and _beyaz_mi(grup[-1].group()):
            grup.pop()
        if grup:
            sozlukte = sum(1 for g in grup if _isim_mi(g.group()))
            # tek kelimelik yakalama icin hem ad hem bilinen bir ad olmali; iki+ kelime icin biri yeterli
            if (len(grup) >= 2 and sozlukte >= 1) or (len(grup) == 1 and sozlukte == 1
                                                       and tr_kucuk(_kok(grup[0].group())) in _ADLAR_K
                                                       and _cumle_basi_degil(metin, grup[0].start())):
                bulunan.append((grup[0].start(), grup[-1].end(), "AD"))
        i = j
    return bulunan


def _cumle_basi_degil(metin: str, poz: int) -> bool:
    onceki = metin[:poz].rstrip()
    return bool(onceki) and onceki[-1] not in ".!?\n:"


def _kaliplari_bul(metin: str) -> list[tuple[int, int, str]]:
    bulunan = []
    for tur, kalip in KURALLAR:
        for m in kalip.finditer(metin):
            if tur == "TCKN" and not tckn_gecerli(m.group()):
                continue
            if tur == "KAYIT_NO":
                bulunan.append((m.start(2), m.end(2), tur))
                continue
            if tur == "TARIH" and not _tarih_mantikli(m):
                continue
            if tur == "ADRES":
                bas = m.start() + (len(m.group()) - len(m.group().lstrip()))
                bulunan.append((bas, m.end(), tur))
                continue
            bulunan.append((m.start(), m.end(), tur))
    return bulunan


def _tarih_mantikli(m: re.Match) -> bool:
    g = m.groups()
    try:
        gun = int(g[0])
    except (TypeError, ValueError):
        return True
    if not 1 <= gun <= 31:
        return False
    if g[1].isdigit():
        return 1 <= int(g[1]) <= 12
    return True


def _cakismalari_coz(spanlar: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    # uzun olan kazanir, esitlikte once gelen
    spanlar = sorted(set(spanlar), key=lambda s: (s[0], -(s[1] - s[0])))
    sonuc: list[tuple[int, int, str]] = []
    for s in spanlar:
        if sonuc and s[0] < sonuc[-1][1]:
            if s[1] - s[0] > sonuc[-1][1] - sonuc[-1][0]:
                sonuc[-1] = s
            continue
        sonuc.append(s)
    return sonuc


# ----------------------------------------------------------------------------- degistirme

def _hash_idx(tuz: str, deger: str, mod: int) -> int:
    h = hashlib.sha256(f"{tuz}|{deger}".encode("utf-8")).hexdigest()
    return int(h[:12], 16) % mod


def _takma_ad(tur: str, orijinal: str, tuz: str, hafiza: dict) -> str:
    anahtar = (tur, tr_kucuk(orijinal))
    if anahtar in hafiza:
        return hafiza[anahtar]
    if tur == "AD":
        parcalar = orijinal.split()
        ad = ADLAR[_hash_idx(tuz, orijinal + "a", len(ADLAR))]
        soyad = SOYADLAR[_hash_idx(tuz, orijinal + "s", len(SOYADLAR))]
        if tr_kucuk(ad) == tr_kucuk(parcalar[0]):
            ad = ADLAR[(_hash_idx(tuz, orijinal + "a", len(ADLAR)) + 1) % len(ADLAR)]
        deger = ad if len(parcalar) == 1 else f"{ad} {soyad}"
    elif tur == "TCKN":
        deger = "9" + str(_hash_idx(tuz, orijinal, 10**10)).zfill(10)
    elif tur == "TELEFON":
        deger = "05" + str(_hash_idx(tuz, orijinal, 10**9)).zfill(9)
    elif tur == "EPOSTA":
        deger = f"kisi{_hash_idx(tuz, orijinal, 9999):04d}@ornek.tld"
    elif tur == "KAYIT_NO":
        deger = "P" + str(_hash_idx(tuz, orijinal, 10**6)).zfill(6)
    elif tur == "IL":
        deger = "[IL]"
    else:
        deger = ETIKETLER.get(tur, f"[{tur}]")
    hafiza[anahtar] = deger
    return deger


_AY_IDX = {a: i + 1 for i, a in enumerate(AYLAR)}


def _tarih_kaydir(orijinal: str, ofset: int, yili_koru: bool) -> str:
    m = re.match(r"(\d{1,2})([./-])(\d{1,2})[./-](\d{4}|\d{2})$", orijinal)
    try:
        if m:
            gun, ayr, ay, yil = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
            tam_yil = int(yil) if len(yil) == 4 else 2000 + int(yil)
            d = date(tam_yil, ay, gun) + timedelta(days=ofset)
            if yili_koru:
                d = d.replace(year=tam_yil) if not (d.month == 2 and d.day == 29) else d.replace(year=tam_yil, day=28)
            yil_s = f"{d.year:04d}" if len(yil) == 4 else f"{d.year % 100:02d}"
            return f"{d.day:02d}{ayr}{d.month:02d}{ayr}{yil_s}"
        m = re.match(r"(\d{1,2})\s+([^\s\d]+)(?:\s+(\d{4}))?$", orijinal)
        if m:
            gun, ay_ad, yil = int(m.group(1)), m.group(2), m.group(3)
            ay = _AY_IDX[tr_kucuk(ay_ad)]
            tam_yil = int(yil) if yil else 2000
            d = date(tam_yil, ay, gun) + timedelta(days=ofset)
            if yili_koru:
                d = d.replace(year=tam_yil)
            ay_yeni = AYLAR[d.month - 1]
            ay_yeni = ay_yeni.capitalize() if ay_ad[0].isupper() else ay_yeni
            return f"{d.day} {ay_yeni}" + (f" {d.year}" if yil else "")
    except (ValueError, KeyError):
        pass
    return "[TARIH]"


# ----------------------------------------------------------------------------- disa acik API

def kimliksizlestir(metin: str, mod: str = "maske", ofset: int = 0, yili_koru: bool = False,
                    tuz: str = "ebm-sc") -> Sonuc:
    if mod not in ("maske", "takma_ad", "kaydir"):
        raise ValueError(f"bilinmeyen mod: {mod}")
    if not metin:
        return Sonuc(metin="")

    spanlar = _cakismalari_coz(_kaliplari_bul(metin) + _adlari_bul(metin))

    hafiza: dict = {}
    if mod == "takma_ad" and ofset == 0:
        # belge basina tutarli, tahmin edilemez ofset
        ofset = 30 + _hash_idx(tuz, metin[:200], 300)

    cikti: list[str] = []
    bulgular: list[Bulgu] = []
    istatistik: dict[str, int] = {}
    imlec = 0
    kayma = 0  # cikti metnindeki pozisyon farki
    for bas, bit, tur in spanlar:
        orijinal = metin[bas:bit]
        if mod == "maske":
            yeni = ETIKETLER.get(tur, f"[{tur}]")
        elif tur == "TARIH" and mod in ("kaydir", "takma_ad"):
            yeni = _tarih_kaydir(orijinal, ofset, yili_koru)
        elif mod == "takma_ad":
            yeni = _takma_ad(tur, _kok(orijinal), tuz, hafiza) + orijinal[len(_kok(orijinal)):]
        else:
            yeni = ETIKETLER.get(tur, f"[{tur}]")
        cikti.append(metin[imlec:bas])
        cikti.append(yeni)
        bulgular.append(Bulgu(tur=tur, baslangic=bas + kayma, bitis=bas + kayma + len(yeni),
                              orijinal_uzunluk=bit - bas, degisim=yeni))
        istatistik[tur] = istatistik.get(tur, 0) + 1
        kayma += len(yeni) - (bit - bas)
        imlec = bit
    cikti.append(metin[imlec:])
    return Sonuc(metin="".join(cikti), bulgular=bulgular, istatistik=istatistik)


_SUPHELI = [
    ("11 haneli sayı (TCKN olabilir)", re.compile(r"(?<!\d)\d{11}(?!\d)")),
    ("10 haneli sayı (telefon olabilir)", re.compile(r"(?<!\d)(?:5|0)\d{9}(?!\d)")),
    ("e-posta benzeri ifade", re.compile(r"\S+@\S+")),
    ("tarih benzeri ifade", re.compile(r"(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{2,4}(?!\d)")),
    ("'doğum' ifadesi yakınında sayı", re.compile(r"[Dd]oğ(?:um|umlu)[^.\n]{0,20}\d{4}")),
    ("sokak/mahalle ifadesi", re.compile(r"\b(?:Mah|Mahallesi|Sok|Sokak|Cad|Caddesi)\b", re.IGNORECASE)),
]


def metni_dogrula(metin: str) -> list[str]:
    """Ikinci gecis: kimliksizlestirilmis metinde kalmis olabilecek supheli kaliplari listeler.
    Bos liste donerse metin gozden gecirilmeden sisteme alinabilir demek degil; sadece otomatik kontrol."""
    uyarilar: list[str] = []
    for aciklama, kalip in _SUPHELI:
        for m in kalip.finditer(metin):
            uyarilar.append(f"{aciklama}: '{m.group()}' (konum {m.start()})")
    for m in KELIME_RE.finditer(metin):
        k = m.group()
        if _isim_mi(k) and tr_kucuk(_kok(k)) in _ADLAR_K and _cumle_basi_degil(metin, m.start()):
            uyarilar.append(f"sözlükte geçen kişi adı: '{k}' (konum {m.start()})")
    return uyarilar


def ozet_rapor(sonuc: Sonuc) -> str:
    if not sonuc.bulgular:
        return "Kimlik verisi tespit edilmedi."
    satirlar = [f"Toplam {sonuc.toplam} bulgu:"]
    for tur, adet in sorted(sonuc.istatistik.items(), key=lambda x: -x[1]):
        satirlar.append(f"  {tur:<10} {adet}")
    return "\n".join(satirlar)


__all__ = ["kimliksizlestir", "metni_dogrula", "ozet_rapor", "tckn_gecerli", "Sonuc", "Bulgu", "ETIKETLER"]
