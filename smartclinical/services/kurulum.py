"""Kurulum modu ve moda bagli varsayilanlar.

Mod yalnizca menuyu, varsayilanlari ve sihirbazi sadelestirir; yetki kurallarina dokunmaz.
Form ve vizit kodlari services/ecrf.py sozlesmesine (STANDART_FORMLAR, VIZIT_SABLONLARI) dayanir.
"""
import re
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Calisma, Kullanici, Rol
from ..models.calisma import CalismaTuru
from ..models.kurulum import MOD_ETIKET, MODLAR, KurulumAyari  # noqa: F401

# Faz alani yalnizca bu turlerde anlamli; TITCK basvurusu da bunlarda gerekir
FAZ_TURLERI = {CalismaTuru.ILAC, CalismaTuru.BIYOBENZER, CalismaTuru.TIBBI_CIHAZ, CalismaTuru.IVD,
               CalismaTuru.BIYOESDEGERLIK, CalismaTuru.ILERI_TEDAVI}

# Modda sik kullanilan calisma turleri (sihirbazda ustte listelenir)
SIK_TURLER = {
    "tekil": [CalismaTuru.AKADEMIK, CalismaTuru.GOZLEMSEL, CalismaTuru.KAYIT],
    "universite": [CalismaTuru.AKADEMIK, CalismaTuru.GOZLEMSEL, CalismaTuru.KAYIT],
    "cro": [CalismaTuru.ILAC, CalismaTuru.BIYOBENZER, CalismaTuru.TIBBI_CIHAZ],
}

# Kullanici ekleme formunda sunulan roller
MOD_ROLLERI = {
    "tekil": [Rol.ARASTIRMACI, Rol.KOORDINATOR, Rol.VERI_YONETICISI, Rol.ISTATISTIKCI, Rol.YONETICI],
    "universite": [Rol.ARASTIRMACI, Rol.KOORDINATOR, Rol.VERI_YONETICISI, Rol.ISTATISTIKCI, Rol.YONETICI, Rol.DENETCI],
    "cro": list(Rol),
}

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def ayar_getir(db: Session) -> KurulumAyari:
    """Kayit yoksa mod='tekil' ile gecici nesne doner; veritabanina yazmaz."""
    a = db.get(KurulumAyari, 1)
    return a if a else KurulumAyari(id=1, mod="tekil", kurum_adi="")


def ayar_yaz(db: Session, mod: str, kurum_adi: str, varsayilan_merkez_id: int | None = None,
             varsayilan_sponsor: str | None = None) -> KurulumAyari:
    """Tek satiri olusturur ya da gunceller. Commit etmez."""
    if mod not in MOD_ETIKET:
        raise ValueError(f"Bilinmeyen kurulum modu: {mod}")
    a = db.get(KurulumAyari, 1)
    if not a:
        a = KurulumAyari(id=1)
        db.add(a)
    a.mod = mod
    a.kurum_adi = (kurum_adi or "").strip()[:160]
    a.varsayilan_merkez_id = varsayilan_merkez_id
    a.varsayilan_sponsor = (varsayilan_sponsor or "").strip()[:160] or None
    db.flush()
    return a


def mod_varsayilanlari(mod: str, tur: str | CalismaTuru | None = None) -> dict:
    """Sihirbazin moda ve calisma turune gore on secimleri."""
    if isinstance(tur, str):
        try:
            tur = CalismaTuru(tur)
        except ValueError:
            tur = None
    if mod == "cro":
        return {"vizit_sablonu": "standart", "form_kodlari": ["DM", "IE", "VS", "LB", "EX", "CM"],
                "basvuru_kurumlari": ["etik_kurul", "titck", "kvkk"], "hedef_merkez": None}
    if mod == "universite":
        kurumlar = ["etik_kurul", "kurum_izni"]
        if tur in FAZ_TURLERI:
            kurumlar.append("titck")
        return {"vizit_sablonu": "kisa_takip", "form_kodlari": ["DM", "IE", "VS", "LB", "ANKET"],
                "basvuru_kurumlari": kurumlar, "hedef_merkez": 1}
    return {"vizit_sablonu": "kisa_takip", "form_kodlari": ["DM", "IE", "VS", "LB"],
            "basvuru_kurumlari": ["etik_kurul"], "hedef_merkez": 1}


def mod_rolleri(mod: str) -> list[Rol]:
    return list(MOD_ROLLERI.get(mod, MOD_ROLLERI["cro"]))


def kullanici_sayisi_sifir(db: Session) -> bool:
    return (db.scalar(select(func.count(Kullanici.id))) or 0) == 0


def kurum_kisaltmasi(kurum_adi: str) -> str:
    """'Mustafa Kemal Üniversitesi' -> 'MKU'. Bos ad icin 'SC'."""
    kelimeler = [k for k in re.split(r"[\s\-/.,]+", (kurum_adi or "").translate(_TR)) if k]
    kelimeler = [k for k in kelimeler if k.lower() not in ("ve", "ile", "of", "and")]
    harfler = "".join(k[0] for k in kelimeler if k[0].isalpha()).upper()
    if len(harfler) < 2 and kelimeler:
        harfler = re.sub(r"[^A-Z0-9]", "", kelimeler[0].upper())[:4]
    return (harfler or "SC")[:6]


def protokol_kodu_oner(db: Session, kurum_adi: str, yil: int | None = None) -> str:
    """kurum kisaltmasi-yil-sira; mevcut kodlarla cakismayan ilk sira secilir."""
    yil = yil or date.today().year
    onek = f"{kurum_kisaltmasi(kurum_adi)}-{yil}-"
    mevcut = {k for (k,) in db.execute(select(Calisma.kod).where(Calisma.kod.like(f"{onek}%"))).all()}
    sira = len(mevcut) + 1
    while f"{onek}{sira:03d}" in mevcut:
        sira += 1
    return f"{onek}{sira:03d}"


def kod_kullanimda(db: Session, kod: str) -> bool:
    return db.execute(select(Calisma.id).where(Calisma.kod == (kod or "").strip().upper())).first() is not None
