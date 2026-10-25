"""Protokol metninden calisma tasarimi taslagi.

Kural tabanli yol basliklari ve madde satirlarini ayirir; BDM varsa onun ciktisi semaya gore
dogrulanip tercih edilir. Her iki yolda da cikti yalnizca oneridir: hicbir sey veritabanina
yazilmaz, uygulama kullanici onayiyla web/ecrf.py uzerinden yapilir.
"""
import re
from dataclasses import dataclass, field

from .ecrf import STANDART_FORMLAR

_TR = str.maketrans("İI", "iı")


def _kucuk(s: str) -> str:
    return (s or "").translate(_TR).lower()


@dataclass
class ProtokolTaslagi:
    dahil: list[str] = field(default_factory=list)
    haric: list[str] = field(default_factory=list)
    vizitler: list[tuple[str, int, int]] = field(default_factory=list)  # (ad, gun, pencere)
    formlar: list[str] = field(default_factory=list)
    kollar: list[str] = field(default_factory=list)
    yontem: str = "kural"  # kural | bdm
    notlar: list[str] = field(default_factory=list)

    @property
    def bos(self) -> bool:
        return not (self.dahil or self.haric or self.vizitler or self.formlar or self.kollar)


# Bolum basliklari (kucuk harf, Turkce karakterli ve karaktersiz)
BASLIKLAR = {
    "dahil": ("dahil etme kriter", "dahil olma kriter", "dahil edilme kriter", "dahil etme ölçüt", "dahil etme olcut",
              "inclusion criteria"),
    "haric": ("hariç tutma kriter", "haric tutma kriter", "dışlama kriter", "dislama kriter", "hariç tutulma kriter",
              "hariç tutma ölçüt", "exclusion criteria"),
    "kollar": ("çalışma kolları", "calisma kollari", "tedavi grupları", "tedavi gruplari", "çalışma grupları",
               "tedavi kolları", "tedavi kollari", "study arms"),
    "vizitler": ("vizit takvimi", "vizit çizelgesi", "vizit cizelgesi", "değerlendirme çizelgesi",
                 "degerlendirme cizelgesi", "vizit planı", "vizit plani", "ziyaret takvimi", "schedule of assessments"),
}

_MADDE = re.compile(r"^\s*(?:\(?\d{1,2}[\.\)]|\(?[a-zA-Z][\.\)]|[-•*–—]|[ivx]{1,4}[\.\)])\s+(.*\S)\s*$")
_BASLIK_GIBI = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?[A-ZÇĞİÖŞÜ][^.!?]{2,70}$")

# Form onerileri: anahtar sozcuk -> standart form kodu
FORM_ANAHTARLARI = (
    (("vital",), "VS"),
    (("hemogram", "biyokimya", "laboratuvar", "laboratuar", "hemoglobin", "kreatinin", "hba1c"), "LB"),
    (("ecog", "performans skoru", "performans durumu", "karnofsky"), "QS"),
    (("eşlik eden ilaç", "eslik eden ilac", "eş zamanlı ilaç", "es zamanli ilac", "birlikte kullanılan ilaç"), "CM"),
    (("demografi", "demografik"), "DM"),
    (("anket", "ölçek", "olcek", "yaşam kalitesi", "yasam kalitesi"), "ANKET"),
    (("araştırma ürünü", "arastirma urunu", "doz uygulama", "ilaç uygulama", "ilac uygulama", "çalışma ilacı"), "EX"),
)

# Vizit kaliplari
_VIZIT_PAREN = re.compile(r"(?i)(.*?)\(\s*(?:gün|gun|g)\s*(-?\d+)\s*(?:gün|gun)?\s*(?:±|\+/-|\+-)?\s*(\d+)?\s*(?:gün|gun)?\s*\)")
_GUN = re.compile(r"(?i)\b(?:gün|gun)\s*(-?\d+)\b")
_HAFTA = re.compile(r"(?i)\bhafta\s*(-?\d+)\b")
_AY = re.compile(r"(?i)\bay\s*(\d+)\b")
_PENCERE = re.compile(r"(?:±|\+/-|\+-)\s*(\d+)")
_VIZIT_NO = re.compile(r"(?i)\b(vizit|ziyaret|v)\s*(\d+)\b")
_TARAMA = re.compile(r"(?i)\btarama\b")


def _baslik_tipi(satir: str) -> str | None:
    k = _kucuk(satir).strip(" :.-\t")
    if len(k) > 90:
        return None
    for tip, anahtarlar in BASLIKLAR.items():
        if any(a in k for a in anahtarlar):
            # madde satirinda gecen "dahil etme kriterleri karsilandi" gibi cumleler baslik degil
            if _MADDE.match(satir) and len(k) > 45:
                return None
            return tip
    return None


def bolumleri_ayir(metin: str) -> dict[str, list[str]]:
    """Basliklara gore bolumler; her bolum madde satirlari listesi."""
    bolumler: dict[str, list[str]] = {}
    aktif: str | None = None
    for ham in (metin or "").splitlines():
        satir = ham.strip()
        if not satir:
            continue
        tip = _baslik_tipi(satir)
        if tip:
            aktif = tip
            bolumler.setdefault(aktif, [])
            continue
        if aktif is None:
            continue
        m = _MADDE.match(satir)
        if m:
            bolumler[aktif].append(m.group(1).strip())
        elif _BASLIK_GIBI.match(satir) and bolumler[aktif]:
            aktif = None  # yeni, taninmayan bir baslik: bolum bitti
        elif len(satir) > 12 and aktif in ("dahil", "haric", "kollar") and not bolumler[aktif]:
            # madde isareti olmayan tek satirlik kriterler
            bolumler[aktif].append(satir)
        elif len(satir) > 12 and aktif == "vizitler":
            bolumler[aktif].append(satir)
    return bolumler


def _vizit_cikar(satirlar: list[str]) -> list[tuple[str, int, int]]:
    bulunan: dict[int, tuple[str, int, int]] = {}
    for s in satirlar:
        for parca in re.split(r"[;,]\s+(?=[A-ZÇĞİÖŞÜ])", s):
            v = _vizit_satiri(parca.strip())
            if v and v[1] not in bulunan:
                bulunan[v[1]] = v
    return [bulunan[g] for g in sorted(bulunan)]


def _vizit_satiri(s: str) -> tuple[str, int, int] | None:
    if not s:
        return None
    pencere_m = _PENCERE.search(s)
    pencere = int(pencere_m.group(1)) if pencere_m else None
    gun = None
    ad = None
    m = _VIZIT_PAREN.match(s)
    if m:
        ad, gun = m.group(1).strip(" :-"), int(m.group(2))
        if m.group(3):
            pencere = int(m.group(3))
    if gun is None:
        if (m2 := _HAFTA.search(s)):
            gun = 7 * int(m2.group(1))
        elif (m2 := _AY.search(s)):
            gun = 30 * int(m2.group(1))
        elif (m2 := _GUN.search(s)):
            gun = int(m2.group(1))
        elif _TARAMA.search(s):
            gun = -14
    if gun is None:
        return None
    if not ad:
        if (m3 := _VIZIT_NO.search(s)):
            ad = f"Vizit {m3.group(2)}"
        elif _TARAMA.search(s):
            ad = "Tarama"
        elif _HAFTA.search(s):
            ad = f"Hafta {_HAFTA.search(s).group(1)}"
        elif _AY.search(s):
            ad = f"Ay {_AY.search(s).group(1)}"
        else:
            ad = s.split("(")[0].strip(" :-")[:40] or f"Gün {gun}"
    if gun < -6 and _TARAMA.search(s) and gun <= -7 and "tarama" not in _kucuk(ad):
        ad = "Tarama"
    if pencere is None:
        pencere = 0 if gun == 0 else (7 if gun < 0 else 3)
    return (ad[:40], gun, pencere)


def _form_oner(metin: str, kriter_var: bool) -> list[str]:
    k = _kucuk(metin)
    kodlar: list[str] = []
    for anahtarlar, kod in FORM_ANAHTARLARI:
        if any(a in k for a in anahtarlar) and kod not in kodlar:
            kodlar.append(kod)
    if kriter_var and "IE" not in kodlar:
        kodlar.append("IE")
    if kriter_var and "DM" not in kodlar:
        kodlar.append("DM")
    return [kod for kod in STANDART_FORMLAR if kod in kodlar]


def _kollar_tara(metin: str) -> list[str]:
    bulunan = []
    for satir in (metin or "").splitlines():
        s = satir.strip(" -•*\t")
        if re.match(r"(?i)^(kol|grup)\s*[A-Z0-9]{1,2}\s*[:\-–]", s) and s not in bulunan:
            bulunan.append(s[:120])
    return bulunan


def taslak_kural(metin: str) -> ProtokolTaslagi:
    t = ProtokolTaslagi(yontem="kural")
    bolumler = bolumleri_ayir(metin)
    t.dahil = [s[:400] for s in bolumler.get("dahil", [])]
    t.haric = [s[:400] for s in bolumler.get("haric", [])]
    t.kollar = [s[:120] for s in bolumler.get("kollar", [])] or _kollar_tara(metin)
    if "vizitler" in bolumler:
        t.vizitler = _vizit_cikar(bolumler["vizitler"])
    if not t.vizitler:
        # bolum yoksa yalnizca vizit/hafta/tarama gecen satirlara bakilir
        adaylar = [s for s in metin.splitlines() if re.search(r"(?i)\b(vizit|ziyaret|hafta|tarama)\b", s)]
        t.vizitler = _vizit_cikar(adaylar)
        if t.vizitler:
            t.notlar.append("Vizit takvimi başlığı bulunamadı; vizitler metin içindeki kalıplardan çıkarıldı.")
    t.formlar = _form_oner(metin, bool(t.dahil or t.haric))
    for tip, ad in (("dahil", "Dahil etme kriterleri"), ("haric", "Hariç tutma kriterleri")):
        if tip not in bolumler:
            t.notlar.append(f"'{ad}' başlığı bulunamadı.")
    if t.bos:
        t.notlar.append("Metinden tanınabilir bir bölüm çıkarılamadı; başlıkları ve madde işaretlerini kontrol edin.")
    return t


def taslak_cikar(metin: str, istemci=None) -> ProtokolTaslagi:
    """Protokol metninden taslak. BDM istemcisi verildiyse ve kural modunda degilse once o denenir."""
    metin = (metin or "").strip()
    kural = taslak_kural(metin)
    if istemci is None or getattr(istemci, "kural_modu", True):
        return kural
    try:
        v = istemci.protokol_taslagi(metin)
    except Exception as e:  # koruma ihlali (PHI) dahil; kural yoluna duser
        kural.notlar.append(f"BDM kullanılamadı: {e}")
        return kural
    if not v:
        kural.notlar.append("BDM geçerli bir taslak üretmedi; kural tabanlı sonuç gösteriliyor.")
        return kural
    t = ProtokolTaslagi(yontem="bdm")
    t.dahil = [str(x).strip()[:400] for x in v["dahil"] if str(x).strip()] or kural.dahil
    t.haric = [str(x).strip()[:400] for x in v["haric"] if str(x).strip()] or kural.haric
    t.kollar = [str(x).strip()[:120] for x in v["kollar"] if str(x).strip()] or kural.kollar
    gorulen: set[int] = set()
    for x in v["vizitler"]:
        if x["gun"] in gorulen:
            continue
        gorulen.add(x["gun"])
        t.vizitler.append((x["ad"], x["gun"], max(0, x["pencere"])))
    t.vizitler.sort(key=lambda x: x[1])
    t.vizitler = t.vizitler or kural.vizitler
    bdm_formlar = [str(k).upper() for k in v["formlar"] if str(k).upper() in STANDART_FORMLAR]
    t.formlar = [k for k in STANDART_FORMLAR if k in bdm_formlar or k in kural.formlar]
    if len(metin) > 12000:
        t.notlar.append("Metin uzun olduğundan modele yalnızca başlık çevresindeki bölümler gönderildi.")
    t.notlar.append(f"BDM güveni: %{round(100 * v['guven'])}. Öneriler onaylanmadan kaydedilmez.")
    return t
