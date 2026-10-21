"""Kalip tabanli tespit kurallari. Her kural (tur, regex) ikilisi; sira onemli, ilk eslesen kazanir."""

import re

from .sozluk import AYLAR, ILLER, UNVANLAR

_AY = "|".join(AYLAR + [a.capitalize() for a in AYLAR] + [a.upper() for a in AYLAR])

# Buyuk harfle baslayan Turkce kelime (ek olarak kesme isaretli ek: Ayşe'nin)
BUYUK_KELIME = r"[A-ZÇĞİÖŞÜ][a-zçğıöşüA-ZÇĞİÖŞÜ]+"
KESME_EK = r"(?:['’][a-zçğıöşü]+)?"

UNVAN_RE = "|".join(re.escape(u) for u in sorted(UNVANLAR, key=len, reverse=True))
IL_RE = "|".join(re.escape(i) for i in sorted(ILLER, key=len, reverse=True))

KURALLAR: list[tuple[str, re.Pattern]] = [
    ("EPOSTA", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("IBAN", re.compile(r"\bTR\d{2}(?:[ ]?\d{4}){5}[ ]?\d{2}\b")),
    # TCKN: 11 hane, 0 ile baslamaz. Algoritma dogrulamasi motor tarafinda yapiliyor.
    ("TCKN", re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")),
    ("TELEFON", re.compile(
        r"(?<!\d)(?:\+90[\s.-]?|0)?\(?(?:5\d{2}|2\d{2}|3\d{2}|4\d{2}|8\d{2})\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}(?!\d)"
    )),
    ("PLAKA", re.compile(r"\b(?:0[1-9]|[1-7]\d|8[01])\s?[A-Z]{1,3}\s?\d{2,4}\b")),
    # "Protokol No: 123456", "Dosya No. AB-1234", "Hasta Numarası: 44521"
    ("KAYIT_NO", re.compile(
        r"\b(Protokol|Dosya|Hasta|Kayıt|Barkod|Sigorta|SGK|Poliçe|Başvuru)\s*(?:No|Numarası|Nr|#)\s*[:.]?\s*"
        r"([A-Z0-9][A-Z0-9/-]{3,})",
        re.IGNORECASE,
    )),
    ("TARIH", re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)")),
    ("TARIH", re.compile(r"(?<!\d)(\d{1,2})\s+(" + _AY + r")(?:\s+(\d{4}))?(?![\wçğıöşü])")),
    ("KURUM", re.compile(
        r"(?:" + BUYUK_KELIME + r"\.?\s+){1,5}"
        r"(?:Eğitim\s+ve\s+Araştırma\s+Hastanesi|Üniversitesi\s+Tıp\s+Fakültesi(?:\s+Hastanesi)?|"
        r"Devlet\s+Hastanesi|Şehir\s+Hastanesi|Üniversite\s+Hastanesi|Onkoloji\s+Hastanesi|"
        r"Özel\s+Hastanesi|Hastanesi|Tıp\s+Merkezi|Üniversitesi)" + KESME_EK
    )),
    ("ADRES", re.compile(
        r"[^.\n:]{0,60}?\b(?:Mah\.|Mahallesi|Mahalle|Cad\.|Caddesi|Sok\.|Sokak|Sk\.|Bulv\.|Bulvarı|Apt\.|"
        r"Apartmanı|Sitesi|Blok)\b[^.\n]{0,80}"
    )),
    ("IL", re.compile(r"(?<![\wçğıöşü])(?:" + IL_RE + r")" + KESME_EK + r"(?![\wçğıöşü])")),
    ("YAS", re.compile(r"(?<!\d)(?:9\d|1[0-2]\d)\s*(?:yaşında|yaşındaki|yasinda|yaş|y\b)", re.IGNORECASE)),
]

# Unvan + ad soyad: "Prof. Dr. Ayşe Yılmaz", "Sn. Mehmet Kaya'nın"
UNVAN_AD_RE = re.compile(
    r"(?:" + UNVAN_RE + r")\s+((?:" + BUYUK_KELIME + r"\s+){0,2}" + BUYUK_KELIME + KESME_EK + r")"
)
# "Hasta: Ayşe Yılmaz", "Adı Soyadı: ..." gibi etiket tetikleyicileri
ETIKET_AD_RE = re.compile(
    r"(?:Hasta|Hastanın\s+Adı|Adı\s+Soyadı|Ad\s+Soyad|Adı|Yakını|Refakatçi|Eşi|Annesi|Babası|Kızı|Oğlu)\s*[:]\s*"
    r"((?:" + BUYUK_KELIME + r"\s+){0,2}" + BUYUK_KELIME + KESME_EK + r")"
)
KELIME_RE = re.compile(BUYUK_KELIME + KESME_EK)
