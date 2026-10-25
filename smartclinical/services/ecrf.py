"""eCRF ve vizit semasi servisi.

Standart form kutuphanesi, vizit sablonlari, alan sozlugu dogrulama ve edit-check burada.
Web katmani (web/ecrf.py, web/gonulluler.py) ve kurulum sihirbazi bu fonksiyonlari kullanir;
servis commit etmez, cagiran eder.
"""
import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from ..models.hasta import Gonullu, Vizit
from ..models.tasarim import VizitTanimi
from ..models.veri import Form, FormKaydi

# Alan sozlugu standardi (Form.alanlar icindeki her kayit)
ALAN_ANAHTARLARI = ("kod", "etiket", "tip", "zorunlu", "birim", "min", "max", "secenekler", "cdash", "bolum", "kosul")

ALAN_TIPLERI = {
    "metin": "Metin",
    "metin_uzun": "Uzun metin",
    "sayi": "Sayı",
    "tarih": "Tarih",
    "secim": "Seçim (tek)",
    "coklu_secim": "Seçim (çoklu)",
    "evet_hayir": "Evet / Hayır",
}
EVET_HAYIR = ["Evet", "Hayır"]
FORM_DURUMLARI = {"taslak": "Taslak", "yayinda": "Yayında"}

_KOD = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")
FORM_KOD = re.compile(r"^[A-Z][A-Z0-9_]{0,15}$")

# ---------------------------------------------------------------------------
# Standart formlar (CDASH). demo_veri ve kurulum sihirbazi buradan okur.
# ---------------------------------------------------------------------------
STANDART_FORMLAR: dict[str, dict] = {
    "DM": {"ad": "Demografi", "vizitler": ["Tarama"], "alanlar": [
        {"kod": "BRTHYR", "etiket": "Doğum yılı", "tip": "sayi", "zorunlu": True, "min": 1930, "max": 2008, "cdash": "DM.BRTHDTC"},
        {"kod": "SEX", "etiket": "Cinsiyet", "tip": "secim", "secenekler": ["Kadın", "Erkek"], "zorunlu": True, "cdash": "DM.SEX"},
        {"kod": "HEIGHT", "etiket": "Boy", "tip": "sayi", "birim": "cm", "min": 130, "max": 210, "cdash": "VS.VSORRES"},
        {"kod": "WEIGHT", "etiket": "Kilo", "tip": "sayi", "birim": "kg", "min": 35, "max": 200, "cdash": "VS.VSORRES"},
    ]},
    "IE": {"ad": "Uygunluk Kontrolü", "vizitler": ["Tarama"], "alanlar": [
        {"kod": "IEYN", "etiket": "Tüm dahil etme kriterleri karşılandı mı?", "tip": "secim", "secenekler": ["Evet", "Hayır"], "zorunlu": True, "cdash": "IE.IEORRES"},
        {"kod": "IEEXCL", "etiket": "Herhangi bir hariç tutma kriteri var mı?", "tip": "secim", "secenekler": ["Evet", "Hayır"], "zorunlu": True, "cdash": "IE.IEORRES"},
        {"kod": "IECOM", "etiket": "Açıklama", "tip": "metin_uzun"},
    ]},
    "VS": {"ad": "Vital Bulgular", "vizitler": [], "alanlar": [
        {"kod": "VSDAT", "etiket": "Ölçüm tarihi", "tip": "tarih", "zorunlu": True, "cdash": "VS.VSDTC"},
        {"kod": "SYSBP", "etiket": "Sistolik kan basıncı", "tip": "sayi", "birim": "mmHg", "min": 70, "max": 220, "zorunlu": True, "cdash": "VS.VSORRES"},
        {"kod": "DIABP", "etiket": "Diyastolik kan basıncı", "tip": "sayi", "birim": "mmHg", "min": 40, "max": 130, "zorunlu": True, "cdash": "VS.VSORRES"},
        {"kod": "PULSE", "etiket": "Nabız", "tip": "sayi", "birim": "/dk", "min": 35, "max": 160, "cdash": "VS.VSORRES"},
        {"kod": "TEMP", "etiket": "Vücut sıcaklığı", "tip": "sayi", "birim": "°C", "min": 35, "max": 41, "cdash": "VS.VSORRES"},
    ]},
    "LB": {"ad": "Laboratuvar", "vizitler": [], "alanlar": [
        {"kod": "LBDAT", "etiket": "Örnek tarihi", "tip": "tarih", "zorunlu": True, "cdash": "LB.LBDTC"},
        {"kod": "HGB", "etiket": "Hemoglobin", "tip": "sayi", "birim": "g/dL", "min": 5, "max": 20, "cdash": "LB.LBORRES"},
        {"kod": "ANC", "etiket": "Mutlak nötrofil", "tip": "sayi", "birim": "x10⁹/L", "min": 0.1, "max": 30, "cdash": "LB.LBORRES"},
        {"kod": "PLT", "etiket": "Trombosit", "tip": "sayi", "birim": "x10⁹/L", "min": 10, "max": 900, "cdash": "LB.LBORRES"},
        {"kod": "CREAT", "etiket": "Kreatinin", "tip": "sayi", "birim": "mg/dL", "min": 0.2, "max": 10, "cdash": "LB.LBORRES"},
        {"kod": "ALT", "etiket": "ALT", "tip": "sayi", "birim": "U/L", "min": 2, "max": 1000, "cdash": "LB.LBORRES"},
        {"kod": "HBA1C", "etiket": "HbA1c", "tip": "sayi", "birim": "%", "min": 4, "max": 15, "cdash": "LB.LBORRES"},
    ]},
    "EX": {"ad": "Araştırma Ürünü Uygulaması", "vizitler": [], "alanlar": [
        {"kod": "EXDAT", "etiket": "Uygulama tarihi", "tip": "tarih", "zorunlu": True, "cdash": "EX.EXSTDTC"},
        {"kod": "EXDOSE", "etiket": "Doz", "tip": "sayi", "zorunlu": True, "cdash": "EX.EXDOSE"},
        {"kod": "EXDOSU", "etiket": "Doz birimi", "tip": "secim", "secenekler": ["mg", "U", "mL"], "cdash": "EX.EXDOSU"},
        {"kod": "EXADJ", "etiket": "Doz değişikliği nedeni", "tip": "metin"},
    ]},
    "CM": {"ad": "Eşlik Eden İlaçlar", "vizitler": [], "alanlar": [
        {"kod": "CMTRT", "etiket": "İlaç adı", "tip": "metin", "zorunlu": True, "cdash": "CM.CMTRT"},
        {"kod": "CMINDC", "etiket": "Endikasyon", "tip": "metin", "cdash": "CM.CMINDC"},
        {"kod": "CMSTDAT", "etiket": "Başlangıç", "tip": "tarih", "cdash": "CM.CMSTDTC"},
        {"kod": "CMONGO", "etiket": "Devam ediyor", "tip": "secim", "secenekler": ["Evet", "Hayır"]},
    ]},
    "QS": {"ad": "ECOG Performans", "vizitler": [], "alanlar": [
        {"kod": "ECOG", "etiket": "ECOG skoru", "tip": "secim", "secenekler": ["0", "1", "2", "3", "4"], "zorunlu": True, "cdash": "QS.QSORRES"},
    ]},
    "ANKET": {"ad": "Anket", "vizitler": [], "alanlar": []},
}

# ---------------------------------------------------------------------------
# Vizit sablonlari: (ad, gun, pencere_gun)
# ---------------------------------------------------------------------------
VIZIT_SABLONLARI: dict[str, list[tuple[str, int, int]]] = {
    "tek_vizit": [("Vizit", 0, 0)],
    "kisa_takip": [("Tarama", -14, 7), ("V1 (Başlangıç)", 0, 0), ("V2", 28, 3), ("Çalışma Sonu", 84, 7)],
    "standart": [("Tarama", -14, 7), ("V1 (Başlangıç)", 0, 0), ("V2", 28, 3), ("V3", 56, 3), ("V4", 84, 5),
                 ("V5", 112, 5), ("Çalışma Sonu", 168, 7)],
    "uzun_takip": [("Tarama", -28, 14), ("V1 (Başlangıç)", 0, 0), ("Ay 3", 90, 7), ("Ay 6", 180, 7),
                   ("Ay 9", 270, 7), ("Ay 12 (Çalışma Sonu)", 360, 14)],
}
VIZIT_SABLON_ETIKET = {
    "tek_vizit": "Tek vizit (kesitsel)",
    "kisa_takip": "Kısa takip (tarama, başlangıç, 1 ay, 3 ay)",
    "standart": "Standart (tarama + 6 vizit, 24 hafta)",
    "uzun_takip": "Uzun takip (12 ay, 3 ayda bir)",
}


# ---------------------------------------------------------------------------
# Vizit semasi
# ---------------------------------------------------------------------------
def vizit_semasi_degistirilebilir(calisma) -> bool:
    """Vizit kaydi uretilmis gonullusu olan calismada sema degistirilemez."""
    return not any(g.vizitler for g in calisma.gonulluler)


def vizit_semasi_uygula(db: Session, calisma, sablon: str | list[tuple]) -> list[VizitTanimi]:
    """Mevcut tanimlari siler, sablondaki (ad, gun, pencere) listesini yazar. Commit etmez."""
    if isinstance(sablon, str):
        if sablon not in VIZIT_SABLONLARI:
            raise ValueError(f"Bilinmeyen vizit şablonu: {sablon}")
        satirlar = VIZIT_SABLONLARI[sablon]
    else:
        satirlar = list(sablon)
    if not vizit_semasi_degistirilebilir(calisma):
        raise ValueError("Vizit kaydı oluşturulmuş gönüllüsü olan çalışmada vizit şeması değiştirilemez.")
    for t in list(calisma.vizit_tanimlari):
        db.delete(t)
    calisma.vizit_tanimlari.clear()
    yeni = []
    for i, (ad, gun, pencere) in enumerate(sorted(satirlar, key=lambda s: s[1])):
        t = VizitTanimi(calisma_id=calisma.id, ad=str(ad)[:40], sira=i, gun=int(gun), pencere_gun=int(pencere))
        db.add(t)
        calisma.vizit_tanimlari.append(t)
        yeni.append(t)
    db.flush()
    return yeni


def vizit_ekle(db: Session, calisma, ad: str, gun: int, pencere_gun: int = 3) -> VizitTanimi:
    """Semaya tek vizit ekler; sira gun'e gore yeniden hesaplanir. Commit etmez."""
    t = VizitTanimi(calisma_id=calisma.id, ad=ad.strip()[:40], gun=int(gun), pencere_gun=max(0, int(pencere_gun)))
    db.add(t)
    calisma.vizit_tanimlari.append(t)
    _vizit_sirala(calisma)
    db.flush()
    return t


def _vizit_sirala(calisma) -> None:
    for i, t in enumerate(sorted(calisma.vizit_tanimlari, key=lambda x: (x.gun, x.id or 0))):
        t.sira = i


def gonullu_vizitleri_olustur(db: Session, gonullu: Gonullu, baslangic: date) -> list[Vizit]:
    """Calismanin vizit semasindan gonullu vizitlerini uretir; sema yoksa 'standart' sablon. Commit etmez."""
    tanimlar = list(gonullu.calisma.vizit_tanimlari)
    if tanimlar:
        satirlar = [(t.ad, t.gun, t.pencere_gun, t.id) for t in sorted(tanimlar, key=lambda x: x.sira)]
    else:
        satirlar = [(ad, gun, pencere, None) for ad, gun, pencere in VIZIT_SABLONLARI["standart"]]
    vizitler = []
    for i, (ad, gun, pencere, tanim_id) in enumerate(satirlar):
        v = Vizit(gonullu_id=gonullu.id, vizit_tanimi_id=tanim_id, ad=ad, sira=i,
                  planlanan=baslangic + timedelta(days=gun), pencere_gun=pencere,
                  durum="yapildi" if gun <= 0 else "planli", gerceklesen=baslangic if gun == 0 else None)
        db.add(v)
        gonullu.vizitler.append(v)
        vizitler.append(v)
    return vizitler


# ---------------------------------------------------------------------------
# Formlar
# ---------------------------------------------------------------------------
def standart_formlari_ekle(db: Session, calisma, kodlar: list[str]) -> list[Form]:
    """Standart kutuphaneden formlari calismaya kopyalar; var olan kodlari atlar. Commit etmez."""
    mevcut = {f.kod for f in calisma.formlar}
    sira = max((f.sira for f in calisma.formlar), default=-1) + 1
    eklenen = []
    for kod in kodlar:
        kod = (kod or "").strip().upper()
        if kod not in STANDART_FORMLAR or kod in mevcut:
            continue
        s = STANDART_FORMLAR[kod]
        f = Form(calisma_id=calisma.id, kod=kod, ad=s["ad"], vizitler=list(s["vizitler"]), sira=sira,
                 alanlar=[dict(a) for a in s["alanlar"]], versiyon="1.0", durum="yayinda")
        db.add(f)
        calisma.formlar.append(f)
        eklenen.append(f)
        mevcut.add(kod)
        sira += 1
    db.flush()
    return eklenen


def alan_normalize(a: dict) -> dict:
    """Tasarimcidan gelen alani standart sozluge indirger (bos degerler atilir)."""
    y = {"kod": str(a.get("kod", "")).strip().upper(), "etiket": str(a.get("etiket", "")).strip(),
         "tip": str(a.get("tip", "metin")).strip() or "metin", "zorunlu": bool(a.get("zorunlu"))}
    for k in ("birim", "cdash", "bolum"):
        v = str(a.get(k) or "").strip()
        if v:
            y[k] = v
    for k in ("min", "max"):
        v = a.get(k)
        if v not in (None, ""):
            try:
                v = float(str(v).replace(",", "."))
                y[k] = int(v) if v == int(v) else v
            except ValueError:
                y[k] = v  # form_dogrula hata verir
    sec = a.get("secenekler")
    if isinstance(sec, str):
        sec = [s.strip() for s in re.split(r"[;|\n]", sec) if s.strip()]
    if y["tip"] == "evet_hayir":
        sec = list(EVET_HAYIR)
    if sec:
        y["secenekler"] = [str(s) for s in sec]
    kosul = a.get("kosul")
    if isinstance(kosul, dict) and str(kosul.get("alan") or "").strip():
        y["kosul"] = {"alan": str(kosul["alan"]).strip().upper(), "deger": str(kosul.get("deger") or "").strip()}
    return y


def form_dogrula(alanlar: list) -> list[str]:
    """Alan sozlugu listesini dogrular; hata mesajlari (bos liste = gecerli)."""
    hatalar: list[str] = []
    if not isinstance(alanlar, list):
        return ["Alan listesi okunamadı."]
    kodlar: set[str] = set()
    for i, a in enumerate(alanlar, 1):
        if not isinstance(a, dict):
            hatalar.append(f"{i}. satır geçerli bir alan değil.")
            continue
        kod = str(a.get("kod") or "").strip()
        if not _KOD.match(kod):
            hatalar.append(f"{i}. satır: alan kodu büyük harf, rakam ve alt çizgiden oluşmalı, harfle başlamalı ('{kod or 'boş'}').")
        elif kod in kodlar:
            hatalar.append(f"'{kod}' kodu formda birden fazla kez kullanılmış.")
        kodlar.add(kod)
        if not str(a.get("etiket") or "").strip():
            hatalar.append(f"'{kod or i}': etiket boş olamaz.")
        tip = a.get("tip")
        if tip not in ALAN_TIPLERI:
            hatalar.append(f"'{kod or i}': bilinmeyen alan tipi '{tip}'.")
        if tip in ("secim", "coklu_secim") and not a.get("secenekler"):
            hatalar.append(f"'{kod or i}': seçim alanı için en az bir seçenek girilmeli.")
        mn, mx = a.get("min"), a.get("max")
        for ad, v in (("min", mn), ("max", mx)):
            if v not in (None, "") and not isinstance(v, (int, float)):
                hatalar.append(f"'{kod or i}': {ad} sayısal olmalı.")
        if isinstance(mn, (int, float)) and isinstance(mx, (int, float)) and mn > mx:
            hatalar.append(f"'{kod or i}': min, max değerinden büyük olamaz.")
    for a in alanlar:
        if not isinstance(a, dict):
            continue
        kosul = a.get("kosul")
        if not kosul:
            continue
        if not isinstance(kosul, dict) or not kosul.get("alan"):
            hatalar.append(f"'{a.get('kod')}': koşul {{'alan', 'deger'}} biçiminde olmalı.")
        elif kosul["alan"] not in kodlar:
            hatalar.append(f"'{a.get('kod')}': koşul alanı '{kosul['alan']}' formda yok.")
        elif kosul["alan"] == a.get("kod"):
            hatalar.append(f"'{a.get('kod')}': alan kendi değerine koşullanamaz.")
    return hatalar


def form_degistirilebilir(form: Form) -> bool:
    """Form kaydi yoksa alan silme / tip degistirme serbesttir."""
    db = object_session(form)
    if db is None or form.id is None:
        return True
    return db.scalar(select(FormKaydi.id).where(FormKaydi.form_id == form.id).limit(1)) is None


def alan_degisikligi_kontrol(eski: list, yeni: list) -> list[str]:
    """Kaydi olan formda yasak degisiklikler: alan silme, tip degistirme."""
    eski_h = {a["kod"]: a for a in eski if isinstance(a, dict) and a.get("kod")}
    yeni_h = {a["kod"]: a for a in yeni if isinstance(a, dict) and a.get("kod")}
    hatalar = []
    for kod, a in eski_h.items():
        if kod not in yeni_h:
            hatalar.append(f"'{kod}' alanı silinemez; bu formda veri kaydı var.")
        elif yeni_h[kod].get("tip") != a.get("tip"):
            hatalar.append(f"'{kod}' alanının tipi değiştirilemez; bu formda veri kaydı var.")
    return hatalar


def versiyon_artir(v: str | None) -> str:
    try:
        buyuk, kucuk = (v or "1.0").split(".", 1)
        return f"{buyuk}.{int(kucuk) + 1}"
    except ValueError:
        return "1.1"


# ---------------------------------------------------------------------------
# Edit-check
# ---------------------------------------------------------------------------
def kosul_saglandi(alan: dict, veriler: dict) -> bool:
    kosul = alan.get("kosul")
    if not kosul or not kosul.get("alan"):
        return True
    v = veriler.get(kosul["alan"])
    deger = str(kosul.get("deger", ""))
    if isinstance(v, (list, tuple)):
        return deger in [str(x) for x in v]
    return str(v if v is not None else "") == deger


def _bos(v) -> bool:
    return v is None or v == "" or (isinstance(v, (list, tuple)) and len(v) == 0)


def edit_check(form: Form, veriler: dict) -> list[tuple[str, str]]:
    """Otomatik edit-check'ler. Donus: (alan kodu, soru) listesi; kaydi engellemez, sorgu acar."""
    sorunlar: list[tuple[str, str]] = []
    for alan in form.alanlar:
        kod, etiket, tip = alan["kod"], alan.get("etiket", alan["kod"]), alan.get("tip")
        if not kosul_saglandi(alan, veriler):
            continue  # kosulu saglanmayan alan ne zorunlu ne de gorunur
        v = veriler.get(kod, "")
        if _bos(v):
            if alan.get("zorunlu"):
                sorunlar.append((kod, f"'{etiket}' zorunlu alan boş bırakılmış."))
            continue
        if tip == "sayi":
            try:
                f = float(str(v).replace(",", "."))
            except ValueError:
                sorunlar.append((kod, f"'{etiket}' sayısal değer bekleniyor, girilen: {v}"))
                continue
            if alan.get("min") is not None and f < alan["min"]:
                sorunlar.append((kod, f"'{etiket}' = {v} {alan.get('birim', '')} beklenen aralığın altında (min {alan['min']}). Lütfen doğrulayın."))
            if alan.get("max") is not None and f > alan["max"]:
                sorunlar.append((kod, f"'{etiket}' = {v} {alan.get('birim', '')} beklenen aralığın üstünde (maks {alan['max']}). Lütfen doğrulayın."))
        elif tip == "tarih":
            try:
                t = date.fromisoformat(str(v))
                if t > date.today():
                    sorunlar.append((kod, f"'{etiket}' gelecek tarihli olamaz."))
            except ValueError:
                sorunlar.append((kod, f"'{etiket}' geçerli tarih değil."))
        elif tip == "secim":
            sec = alan.get("secenekler") or []
            if sec and str(v) not in [str(s) for s in sec]:
                sorunlar.append((kod, f"'{etiket}' için '{v}' seçenekler arasında değil."))
        elif tip == "coklu_secim":
            sec = [str(s) for s in alan.get("secenekler") or []]
            secilen = v if isinstance(v, (list, tuple)) else [v]
            yabanci = [str(x) for x in secilen if sec and str(x) not in sec]
            if yabanci:
                sorunlar.append((kod, f"'{etiket}' için '{', '.join(yabanci)}' seçenekler arasında değil."))
        elif tip == "evet_hayir":
            if str(v) not in EVET_HAYIR:
                sorunlar.append((kod, f"'{etiket}' yalnızca Evet veya Hayır olabilir."))
    return sorunlar


def veri_oku(form: Form, gelen) -> dict:
    """HTML formundan gelen degerleri alan sozlugune gore okur (coklu secim -> liste)."""
    veriler = {}
    for a in form.alanlar:
        kod = a["kod"]
        if a.get("tip") == "coklu_secim":
            veriler[kod] = [x for x in gelen.getlist(kod)] if hasattr(gelen, "getlist") else list(gelen.get(kod, []) or [])
        else:
            veriler[kod] = gelen.get(kod, "")
    return veriler
