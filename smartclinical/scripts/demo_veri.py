"""Demo / egitim ortami verisi.

    python -m smartclinical.scripts.demo_veri --sifirla

Tum hasta kayitlari ve metinler sentetiktir; gercek kisi veya kurum verisi icermez.
Merkez adlari kurgusaldir. Uretim ortaminda CALISTIRMAYIN.
"""
import argparse
import random
from datetime import date, datetime, timedelta

from sqlalchemy import select

from ..db import db_oturumu, sifirla, tablolari_olustur
from ..models import (
    AdversOlay,
    Arastirmaci,
    Basvuru,
    Belge,
    Calisma,
    CalismaDurumu,
    CalismaMerkez,
    CalismaTuru,
    CalismaUyesi,
    FormKaydi,
    Gonullu,
    GonulluDurumu,
    Hasta,
    IzlemZiyareti,
    KilometreTasi,
    Kol,
    Kriter,
    Kullanici,
    Merkez,
    ProtokolSapmasi,
    ProtokolVersiyon,
    Rol,
    Sorgu,
    Vizit,
)
from ..models._ortak import simdi
from ..services import denetim, ecrf, yetki
from ..services import kurulum as kurulum_svc

R = random.Random(20260421)
BUGUN = date.today()


def g(gun: int) -> date:
    return BUGUN - timedelta(days=gun)


# ---------------------------------------------------------------------------
# Kullanicilar
# ---------------------------------------------------------------------------
KULLANICILAR = [
    ("admin", "Sistem Yöneticisi", "admin@ebm-cro.com", Rol.YONETICI, None),
    ("pelin.aydin", "Pelin Aydın", "pelin.aydin@ebm-cro.com", Rol.PROJE_YONETICISI, None),
    ("burak.sen", "Burak Şen", "burak.sen@ebm-cro.com", Rol.CRA, None),
    ("elif.kara", "Elif Kara", "elif.kara@ebm-cro.com", Rol.CRA, None),
    ("dr.ozturk", "Dr. Cem Öztürk", "cozturk@hastane.example", Rol.ARASTIRMACI, "ANK-01"),
    ("hemsire.demir", "Seda Demir", "sdemir@hastane.example", Rol.KOORDINATOR, "ANK-01"),
    ("dr.yildiz", "Dr. Nalan Yıldız", "nyildiz@hastane.example", Rol.ARASTIRMACI, "IST-02"),
    ("veri.ekibi", "Murat Koç", "murat.koc@ebm-cro.com", Rol.VERI_YONETICISI, None),
    ("fv.ekibi", "Ayça Tuncer", "ayca.tuncer@ebm-cro.com", Rol.FARMAKOVIJILANS, None),
    ("sponsor.gorunum", "Sponsor Temsilcisi", "sponsor@firma.example", Rol.SPONSOR, None),
    ("denetci", "Kalite Denetçisi", "qa@ebm-cro.com", Rol.DENETCI, None),
]
DEMO_PAROLA = "Demo2026!sc"

# ---------------------------------------------------------------------------
# Merkezler (kurgusal)
# ---------------------------------------------------------------------------
MERKEZLER = [
    ("ANK-01", "Başkent Onkoloji Eğitim ve Araştırma Hastanesi", "Ankara", "egitim_arastirma", 620, "Nucleus", ["Onkoloji", "Hematoloji"]),
    ("IST-02", "Marmara Kuzey Üniversitesi Tıp Fakültesi Hastanesi", "İstanbul", "universite", 1100, "Probel", ["Onkoloji", "Kardiyoloji", "Endokrinoloji", "Romatoloji"]),
    ("IZM-03", "Ege Sahil Şehir Hastanesi", "İzmir", "sehir", 1800, "Sisoft", ["Onkoloji", "Kardiyoloji", "Göğüs Hastalıkları"]),
    ("ADA-04", "Çukurova Bölge Eğitim ve Araştırma Hastanesi", "Adana", "egitim_arastirma", 750, "Nucleus", ["Onkoloji", "Endokrinoloji"]),
    ("BUR-05", "Uludağ Vadisi Üniversitesi Hastanesi", "Bursa", "universite", 900, "Probel", ["Kardiyoloji", "Nöroloji", "Romatoloji"]),
    ("KON-06", "Selçuklu Şehir Hastanesi", "Konya", "sehir", 1250, "Sisoft", ["Onkoloji", "Endokrinoloji", "Göğüs Hastalıkları"]),
    ("ANT-07", "Akdeniz Yıldızı Özel Hastanesi", "Antalya", "ozel", 220, "Medisoft", ["Kardiyoloji", "Onkoloji"]),
    ("GAZ-08", "Gaziantep Fırat Eğitim ve Araştırma Hastanesi", "Gaziantep", "egitim_arastirma", 680, "Nucleus", ["Onkoloji", "Endokrinoloji", "Nefroloji"]),
    ("SAM-09", "Karadeniz Ondokuz Üniversitesi Hastanesi", "Samsun", "universite", 850, "Probel", ["Onkoloji", "Göğüs Hastalıkları"]),
    ("ERZ-10", "Doğu Anadolu Şehir Hastanesi", "Erzurum", "sehir", 1000, "Sisoft", ["Kardiyoloji", "Endokrinoloji"]),
]

ARASTIRMACI_ADLARI = [
    ("Prof. Dr.", "Cem Öztürk", "Tıbbi Onkoloji"), ("Doç. Dr.", "Nalan Yıldız", "Tıbbi Onkoloji"),
    ("Prof. Dr.", "Hakan Erdem", "Kardiyoloji"), ("Doç. Dr.", "Zeynep Arslan", "Endokrinoloji"),
    ("Prof. Dr.", "Tolga Kılıç", "Göğüs Hastalıkları"), ("Dr. Öğr. Üyesi", "Merve Çelik", "Romatoloji"),
    ("Prof. Dr.", "Okan Doğan", "Tıbbi Onkoloji"), ("Doç. Dr.", "Gamze Polat", "Nöroloji"),
    ("Prof. Dr.", "Serkan Aksoy", "Kardiyoloji"), ("Doç. Dr.", "Derya Şahin", "Tıbbi Onkoloji"),
    ("Uzm. Dr.", "Barış Yalçın", "Endokrinoloji"), ("Prof. Dr.", "Leyla Kurt", "Hematoloji"),
]

# ---------------------------------------------------------------------------
# Calismalar
# ---------------------------------------------------------------------------
CALISMALAR = [
    dict(kod="EBM-ONK-2025-003", kisa_ad="HER2- HR+ lokal ileri meme Ca, neoadjuvan", tur=CalismaTuru.ILAC, faz="III",
         baslik="HER2-negatif, hormon reseptörü pozitif lokal ileri meme kanserinde neoadjuvan kemoterapiye eklenen "
                "CDK4/6 inhibitörünün patolojik tam yanıt üzerine etkisini değerlendiren randomize, açık etiketli, çok merkezli faz III çalışma",
         tasarim="Randomize (1:1), açık etiketli, çok merkezli", sponsor="Anadolu Biyofarma A.Ş.", terapotik_alan="Onkoloji",
         endikasyon="Meme kanseri (HER2-, HR+)", durum=CalismaDurumu.KAYIT, hedef_hasta=120, hedef_merkez=6,
         baslangic=g(300), bitis=BUGUN + timedelta(days=420), risk="yuksek", ct="NCT0XXXX412",
         merkezler=["ANK-01", "IST-02", "IZM-03", "ADA-04", "KON-06", "SAM-09"],
         kollar=[("Kol A: Kemoterapi + CDK4/6i", "Standart neoadjuvan kemoterapi + ribosiklib 400 mg"), ("Kol B: Kemoterapi", "Standart neoadjuvan kemoterapi")],
         dahil=["18 yaş ve üzeri kadın hastalar", "Histolojik olarak doğrulanmış invaziv meme kanseri, HER2-negatif (IHC 0-1+ veya ISH negatif)",
                "Hormon reseptörü pozitif (ER ve/veya PR ≥ %1)", "Klinik evre II-III (T2-T4, N0-N2, M0)",
                "ECOG performans skoru 0-1", "Hemoglobin ≥ 9 g/dL", "Mutlak nötrofil sayısı ≥ 1,5 x10⁹/L", "Trombosit ≥ 100 x10⁹/L",
                "Kreatinin klerensi ≥ 50 mL/dk", "AST ve ALT ≤ 2,5 × ULN"],
         haric=["Uzak metastaz varlığı", "Daha önce meme kanseri için sistemik tedavi almış olmak",
                "Son 6 ay içinde miyokard enfarktüsü veya kararsız angina", "Gebe veya emziren kadınlar",
                "QTc > 450 ms", "Aktif ikinci malignite (son 3 yıl)"],
         indikasyon="meme"),
    dict(kod="EBM-END-2026-001", kisa_ad="İnsülin glargin biyobenzer, T2DM", tur=CalismaTuru.BIYOBENZER, faz="III",
         baslik="Tip 2 diabetes mellitus hastalarında yerli insülin glargin biyobenzerinin referans ürüne karşı etkililik ve güvenliliğinin "
                "karşılaştırıldığı randomize, açık etiketli, paralel gruplu çalışma",
         tasarim="Randomize (1:1), açık etiketli, paralel grup, non-inferiorite", sponsor="Yerli İlaç Sanayi A.Ş.", terapotik_alan="Endokrinoloji",
         endikasyon="Tip 2 diabetes mellitus", durum=CalismaDurumu.IZLEM, hedef_hasta=260, hedef_merkez=8,
         baslangic=g(520), bitis=BUGUN + timedelta(days=200), risk="orta",
         merkezler=["IST-02", "ADA-04", "KON-06", "GAZ-08", "ERZ-10", "BUR-05"],
         kollar=[("Test: Glargin-EBM", "Yerli insülin glargin 100 U/mL"), ("Referans", "Referans insülin glargin 100 U/mL")],
         dahil=["18-75 yaş arası hastalar", "En az 1 yıldır tip 2 diabetes mellitus tanısı", "HbA1c %7,5 ile %10 arası",
                "Vücut kitle indeksi 20-40 kg/m²", "Metformin tedavisi altında (stabil doz, en az 3 ay)"],
         haric=["Tip 1 diabetes mellitus", "Son 6 ay içinde ciddi hipoglisemi öyküsü", "eGFR < 30 mL/dk/1,73 m²",
                "Gebe veya emziren kadınlar", "Son 3 ay içinde sistemik kortikosteroid kullanımı"],
         indikasyon="diyabet"),
    dict(kod="EBM-KRD-2026-004", kisa_ad="Yerli ilaç salınımlı stent, pivotal", tur=CalismaTuru.TIBBI_CIHAZ, faz="pivotal",
         baslik="De novo koroner lezyonlarda yerli üretim sirolimus salınımlı koroner stentin 12 aylık hedef lezyon başarısızlığı açısından "
                "değerlendirildiği prospektif, çok merkezli, tek kollu pivotal çalışma",
         tasarim="Prospektif, tek kollu, çok merkezli; tarihsel kontrol", sponsor="MedTek Kardiyovasküler Ltd.", terapotik_alan="Kardiyoloji",
         endikasyon="Koroner arter hastalığı", durum=CalismaDurumu.AKTIVASYON, hedef_hasta=180, hedef_merkez=5,
         baslangic=g(90), bitis=BUGUN + timedelta(days=600), risk="yuksek",
         merkezler=["IST-02", "IZM-03", "BUR-05", "ANT-07", "ERZ-10"],
         kollar=[("Tek kol", "Sirolimus salınımlı stent")],
         dahil=["18 yaş ve üzeri", "Stabil veya kararsız angina ya da belgelenmiş sessiz iskemi", "Referans damar çapı 2,5-4,0 mm olan de novo lezyon",
                "Lezyon uzunluğu ≤ 32 mm", "Sol ventrikül ejeksiyon fraksiyonu ≥ %30"],
         haric=["Son 72 saat içinde STEMI", "Sol ana koroner lezyonu", "Kronik total oklüzyon", "Bilinen sirolimus veya kobalt-krom alerjisi",
                "eGFR < 30 mL/dk/1,73 m²"],
         indikasyon="kah"),
    dict(kod="EBM-IVD-2026-002", kisa_ad="HPV genotipleme kiti, klinik performans", tur=CalismaTuru.IVD, faz="performans",
         baslik="Yerli üretim HPV genotipleme kitinin servikal örneklerde klinik performansının referans yöntemle karşılaştırıldığı çalışma",
         tasarim="Prospektif, kesitsel, karşılaştırmalı", sponsor="GenTanı Biyoteknoloji A.Ş.", terapotik_alan="Kadın Hastalıkları",
         endikasyon="Servikal kanser taraması", durum=CalismaDurumu.BASVURU, hedef_hasta=800, hedef_merkez=3,
         baslangic=BUGUN + timedelta(days=45), bitis=BUGUN + timedelta(days=400), risk="dusuk",
         merkezler=["IST-02", "ANK-01", "GAZ-08"], kollar=[],
         dahil=["25-65 yaş arası kadınlar", "Rutin servikal tarama için başvuran"], haric=["Histerektomi öyküsü", "Gebelik"],
         indikasyon=None),
    dict(kod="EBM-GOZ-2025-007", kisa_ad="KOAH gerçek yaşam kayıt çalışması", tur=CalismaTuru.KAYIT, faz=None,
         baslik="Türkiye'de KOAH hastalarında üçlü inhaler tedavinin gerçek yaşam etkililiği: prospektif, gözlemsel kayıt çalışması",
         tasarim="Prospektif, gözlemsel, girişimsel olmayan", sponsor="Araştırmacı başlatımlı / dernek destekli", terapotik_alan="Göğüs Hastalıkları",
         endikasyon="KOAH", durum=CalismaDurumu.KAYIT, hedef_hasta=500, hedef_merkez=4,
         baslangic=g(240), bitis=BUGUN + timedelta(days=500), risk="dusuk",
         merkezler=["IZM-03", "KON-06", "SAM-09", "ANK-01"], kollar=[],
         dahil=["40 yaş ve üzeri", "Spirometrik olarak doğrulanmış KOAH (FEV1/FVC < 0,70)", "Son 12 ay içinde en az 1 orta/ağır alevlenme"],
         haric=["Astım tanısı", "Aktif akciğer kanseri"], indikasyon="koah"),
    dict(kod="EBM-ROM-2026-005", kisa_ad="RA'da JAK inhibitörü, akademik faz IV", tur=CalismaTuru.AKADEMIK, faz="IV",
         baslik="Romatoid artritte JAK inhibitörü tedavisinin kardiyovasküler güvenliliği: araştırmacı başlatımlı prospektif çalışma",
         tasarim="Prospektif, tek merkezli, kontrollü", sponsor="Uludağ Vadisi Üniversitesi (araştırmacı başlatımlı)", terapotik_alan="Romatoloji",
         endikasyon="Romatoid artrit", durum=CalismaDurumu.TASARIM, hedef_hasta=90, hedef_merkez=1,
         baslangic=BUGUN + timedelta(days=120), bitis=BUGUN + timedelta(days=850), risk="orta",
         merkezler=["BUR-05"], kollar=[],
         dahil=["18 yaş ve üzeri", "ACR/EULAR 2010 kriterlerine göre romatoid artrit", "En az bir csDMARD'a yetersiz yanıt"],
         haric=["Aktif enfeksiyon", "Son 6 ay içinde venöz tromboemboli"], indikasyon=None),
    # gecmis (kapanmis) calismalar - merkez zekasi icin tarihsel veri
    dict(kod="EBM-ONK-2023-011", kisa_ad="KHDAK 2. basamak, faz III (tamamlandı)", tur=CalismaTuru.ILAC, faz="III",
         baslik="Platin sonrası ilerlemiş küçük hücreli dışı akciğer kanserinde ikinci basamak tedavi çalışması",
         tasarim="Randomize, çift kör", sponsor="Uluslararası sponsor (CRO: EBM)", terapotik_alan="Onkoloji", endikasyon="KHDAK",
         durum=CalismaDurumu.ARSIV, hedef_hasta=96, hedef_merkez=6, baslangic=g(1100), bitis=g(380), risk="yuksek",
         merkezler=["ANK-01", "IST-02", "IZM-03", "KON-06", "SAM-09", "GAZ-08"], kollar=[], dahil=[], haric=[], indikasyon="khdak",
         gecmis=True),
    dict(kod="EBM-END-2023-006", kisa_ad="T2DM SGLT2 biyoeşdeğerlik ve faz III (tamamlandı)", tur=CalismaTuru.ILAC, faz="III",
         baslik="Tip 2 diyabette yerli SGLT2 inhibitörü faz III çalışması", tasarim="Randomize, çift kör",
         sponsor="Yerli İlaç Sanayi A.Ş.", terapotik_alan="Endokrinoloji", endikasyon="T2DM", durum=CalismaDurumu.ARSIV,
         hedef_hasta=210, hedef_merkez=7, baslangic=g(1000), bitis=g(300), risk="orta",
         merkezler=["IST-02", "ADA-04", "KON-06", "GAZ-08", "ERZ-10", "BUR-05", "ANT-07"], kollar=[], dahil=[], haric=[],
         indikasyon="diyabet", gecmis=True),
    dict(kod="EBM-KRD-2024-002", kisa_ad="Kalp yetmezliği faz III (tamamlandı)", tur=CalismaTuru.ILAC, faz="III",
         baslik="Düşük EF'li kalp yetmezliğinde faz III çalışması", tasarim="Randomize, çift kör",
         sponsor="Uluslararası sponsor (CRO: EBM)", terapotik_alan="Kardiyoloji", endikasyon="HFrEF", durum=CalismaDurumu.ARSIV,
         hedef_hasta=140, hedef_merkez=5, baslangic=g(820), bitis=g(120), risk="orta",
         merkezler=["IST-02", "IZM-03", "BUR-05", "ANT-07", "ERZ-10"], kollar=[], dahil=[], haric=[], indikasyon="ky", gecmis=True),
]

# ---------------------------------------------------------------------------
# Sentetik hasta metinleri
# ---------------------------------------------------------------------------
def _meme(h, r):
    er = r.choice([70, 80, 90, 95, 60])
    her2 = r.choice(["HER2 negatif (IHC 0)", "HER2 negatif (IHC 1+)", "HER2 pozitif (IHC 3+)", "HER2 2+ ISH negatif"])
    evre = r.choice(["T2N0M0", "T2N1M0", "T3N1M0", "T1N0M0", "T4N2M0", "T3N2M1"])
    ecog = r.choice([0, 0, 1, 1, 2])
    "metastaz" in evre or evre.endswith("M1")
    hb = round(r.uniform(8.2, 13.5), 1)
    onceki = r.random() < 0.25
    metastaz_cumle = "PET-BT'de kemik ve karaciğer metastazı saptandı." if evre.endswith("M1") else "PET-BT'de uzak metastaz saptanmadı."
    metin = (f"{h['yas']} yaşında kadın hasta, {r.choice(['sol', 'sağ'])} memede ele gelen kitle şikayetiyle başvurdu. "
             f"Tru-cut biyopsi: invaziv duktal karsinom, ER (+) %{er}, PR (+) %{max(0, er - 30)}, {her2}, Ki-67 %{r.choice([15, 25, 35, 45])}. "
             f"Klinik evre {evre}. {metastaz_cumle} "
             f"ECOG performans skoru {ecog}. "
             f"Laboratuvar: Hb {hb} g/dL, nötrofil {round(r.uniform(1.2, 5.5), 1)} x10³/µL, trombosit {r.randint(95, 320)} x10³/µL, "
             f"kreatinin {round(r.uniform(0.6, 1.3), 1)} mg/dL, AST {r.randint(15, 60)} U/L, ALT {r.randint(12, 70)} U/L. "
             f"{'Daha önce adjuvan AC-T kemoterapisi almış.' if onceki else 'Daha önce sistemik tedavi almamış.'} "
             f"{'Postmenopozal.' if h['yas'] > 52 else 'Premenopozal, gebe değil, kontrasepsiyon kullanıyor.'} "
             f"{r.choice(['Ek hastalık yok.', 'Hipertansiyon, amlodipin kullanıyor.', '8 yıldır tip 2 diyabet, metformin kullanıyor.', '2022 yılında miyokard enfarktüsü geçirmiş, stentli.'])} "
             f"EKG: sinüs ritmi, QTc {r.choice([410, 425, 438, 462])} ms. Neoadjuvan tedavi için tümör konseyinde değerlendirildi.")
    tanilar = [{"icd10": "C50.9", "ad": "Meme malign neoplazmı", "tarih": str(g(r.randint(10, 60)))}]
    if evre.endswith("M1"):
        tanilar.append({"icd10": "C79.5", "ad": "Kemik metastazı", "tarih": str(g(r.randint(5, 30)))})
    lab = [{"loinc": "718-7", "ad": "Hemoglobin", "deger": hb, "birim": "g/dL", "tarih": str(g(r.randint(3, 25)))},
           {"loinc": "751-8", "ad": "Nötrofil", "deger": round(r.uniform(1.2, 5.5), 1), "birim": "x10^9/L", "tarih": str(g(r.randint(3, 25)))},
           {"loinc": "777-3", "ad": "Trombosit", "deger": r.randint(95, 320), "birim": "x10^9/L", "tarih": str(g(r.randint(3, 25)))},
           {"loinc": "2160-0", "ad": "Kreatinin", "deger": round(r.uniform(0.6, 1.3), 1), "birim": "mg/dL", "tarih": str(g(r.randint(3, 25)))}]
    ilaclar = [{"atc": "L01XE", "ad": "Trastuzumab", "aktif": False}] if "pozitif" in her2 and r.random() < 0.3 else []
    return metin, tanilar, lab, ilaclar, {"ecog": ecog}


def _diyabet(h, r):
    hba1c = round(r.uniform(6.8, 11.2), 1)
    egfr = r.choice([95, 82, 70, 55, 41, 27])
    bmi = round(r.uniform(22, 43), 1)
    metin = (f"{h['yas']} yaşında {'kadın' if h['cinsiyet']=='K' else 'erkek'} hasta, {r.randint(2, 15)} yıldır tip 2 diabetes mellitus tanısıyla izleniyor. "
             f"Metformin 2x1000 mg {r.choice(['ve gliklazid', 've sitagliptin', ''])} kullanıyor; son {r.choice([3, 6, 12])} aydır doz değişikliği yok. "
             f"HbA1c %{hba1c}, açlık glukozu {r.randint(120, 260)} mg/dL. VKİ {bmi} kg/m². eGFR {egfr} mL/dk/1,73 m². "
             f"{'Son 6 ay içinde bir kez hastane başvurusu gerektiren ciddi hipoglisemi atağı geçirmiş.' if r.random() < 0.15 else 'Hipoglisemi öyküsü yok.'} "
             f"{'Diyabetik retinopati nedeniyle göz takibinde.' if r.random() < 0.3 else ''} "
             f"{'Astım alevlenmesi için 2 ay önce 10 gün oral prednizolon kullanmış.' if r.random() < 0.12 else ''} "
             f"Kan basıncı {r.randint(118, 165)}/{r.randint(70, 98)} mmHg. İnsülin tedavisine geçiş planlanıyor.")
    tanilar = [{"icd10": "E11.9", "ad": "Tip 2 diabetes mellitus", "tarih": str(g(r.randint(700, 5000)))}]
    if egfr < 60:
        tanilar.append({"icd10": "N18.3", "ad": "Kronik böbrek hastalığı, evre 3", "tarih": str(g(r.randint(100, 900)))})
    lab = [{"loinc": "4548-4", "ad": "HbA1c", "deger": hba1c, "birim": "%", "tarih": str(g(r.randint(3, 40)))},
           {"loinc": "62238-1", "ad": "eGFR", "deger": egfr, "birim": "mL/min/1.73m2", "tarih": str(g(r.randint(3, 40)))},
           {"loinc": "39156-5", "ad": "VKİ", "deger": bmi, "birim": "kg/m2", "tarih": str(g(r.randint(3, 40)))}]
    ilaclar = [{"atc": "A10BA02", "ad": "Metformin", "aktif": True}]
    return metin, tanilar, lab, ilaclar, None


def _kah(h, r):
    ef = r.choice([25, 35, 45, 55, 60])
    metin = (f"{h['yas']} yaşında {'kadın' if h['cinsiyet']=='K' else 'erkek'} hasta, eforla gelen göğüs ağrısı nedeniyle değerlendirildi. "
             f"Koroner anjiyografi: LAD proksimalinde %{r.randint(70, 95)} darlık, de novo lezyon, referans damar çapı {r.choice([2.5, 2.75, 3.0, 3.5, 4.0])} mm, "
             f"lezyon uzunluğu {r.randint(12, 38)} mm. {'Sol ana koronerde %60 darlık mevcut.' if r.random() < 0.12 else ''} "
             f"Ekokardiyografi: LVEF %{ef}. {'3 gün önce STEMI tanısıyla primer PKG uygulanmış.' if r.random() < 0.1 else 'Akut koroner sendrom bulgusu yok, kararlı angina (CCS II).'} "
             f"eGFR {r.choice([88, 72, 58, 45, 28])} mL/dk/1,73 m². Asetilsalisilik asit ve atorvastatin kullanıyor. Bilinen ilaç alerjisi yok.")
    tanilar = [{"icd10": "I25.1", "ad": "Aterosklerotik kalp hastalığı", "tarih": str(g(r.randint(5, 100)))}]
    lab = [{"loinc": "62238-1", "ad": "eGFR", "deger": r.choice([88, 72, 58, 45, 28]), "birim": "mL/min/1.73m2", "tarih": str(g(r.randint(2, 20)))}]
    ilaclar = [{"atc": "B01AC06", "ad": "Asetilsalisilik asit", "aktif": True}, {"atc": "C10AA05", "ad": "Atorvastatin", "aktif": True}]
    return metin, tanilar, lab, ilaclar, {"lvef": ef}


def _koah(h, r):
    fev = r.randint(32, 68)
    metin = (f"{h['yas']} yaşında {'kadın' if h['cinsiyet']=='K' else 'erkek'} hasta, {r.randint(20, 50)} paket-yıl sigara öyküsü. "
             f"Spirometri: FEV1 %{fev}, FEV1/FVC 0,{r.randint(48, 68)}. GOLD evre {r.choice(['B', 'C', 'D', 'E'])}. "
             f"Son 12 ayda {r.randint(0, 3)} orta şiddette alevlenme, {r.randint(0, 1)} hastane yatışı. "
             f"{'Çocukluktan beri astım tanısı mevcut.' if r.random() < 0.1 else ''} LAMA/LABA kombinasyonu kullanıyor; üçlü tedaviye geçiş değerlendirildi. "
             f"Toraks BT'de amfizem bulguları, {'sağ üst lobda 9 mm nodül, takip önerildi.' if r.random() < 0.15 else 'kitle lezyonu yok.'}")
    tanilar = [{"icd10": "J44.1", "ad": "KOAH, akut alevlenme ile", "tarih": str(g(r.randint(30, 400)))}]
    return metin, tanilar, [{"loinc": "20150-9", "ad": "FEV1 %", "deger": fev, "birim": "%", "tarih": str(g(r.randint(5, 60)))}], \
        [{"atc": "R03AL", "ad": "LAMA/LABA inhaler", "aktif": True}], None


URETICILER = {"meme": _meme, "diyabet": _diyabet, "kah": _kah, "koah": _koah}


def hasta_uret(merkez_id, indikasyon, n, r, baslangic_no):
    hastalar = []
    for i in range(n):
        if indikasyon == "meme":
            cins, yas = "K", r.randint(29, 78)
        else:
            cins, yas = r.choice(["K", "E"]), r.randint(38, 82)
        h = {"yas": yas, "cinsiyet": cins}
        metin, tanilar, lab, ilaclar, perf = URETICILER[indikasyon](h, r)
        hastalar.append(Hasta(
            merkez_id=merkez_id, kayit_no=f"P-{merkez_id:02d}{baslangic_no + i:05d}", dogum_yili=BUGUN.year - yas,
            cinsiyet=cins, tanilar=tanilar, laboratuvar=lab, ilaclar=ilaclar, performans=perf,
            metinler=[{"tur": "epikriz", "tarih": str(g(r.randint(2, 45))), "metin": metin}],
            kaynak="hbys-fhir", son_senkron=simdi() - timedelta(hours=r.randint(1, 72))))
    return hastalar


# ---------------------------------------------------------------------------
AE_TERIMLER = [
    ("Nötropeni", "Neutropenia", "Kan ve lenf sistemi hastalıkları", "3", "muhtemel", True, False),
    ("Bulantı", "Nausea", "Gastrointestinal hastalıklar", "1", "olasi", True, False),
    ("Yorgunluk", "Fatigue", "Genel bozukluklar", "2", "olasi", True, False),
    ("Hipoglisemi", "Hypoglycaemia", "Metabolizma ve beslenme hastalıkları", "2", "muhtemel", True, False),
    ("Enjeksiyon yeri reaksiyonu", "Injection site reaction", "Genel bozukluklar", "1", "kesin", True, False),
    ("Febril nötropeni", "Febrile neutropenia", "Kan ve lenf sistemi hastalıkları", "3", "muhtemel", True, True),
    ("Pnömoni", "Pneumonia", "Enfeksiyonlar", "3", "olasi_degil", True, True),
    ("QT uzaması", "Electrocardiogram QT prolonged", "Araştırmalar", "2", "olasi", True, False),
    ("Alanin aminotransferaz artışı", "ALT increased", "Araştırmalar", "2", "olasi", True, False),
    ("Ciddi hipoglisemi", "Hypoglycaemia", "Metabolizma ve beslenme hastalıkları", "3", "muhtemel", True, True),
    ("Stent trombozu", "Stent thrombosis", "Kardiyak hastalıklar", "4", "muhtemel", False, True),
    ("Diyare", "Diarrhoea", "Gastrointestinal hastalıklar", "1", "olasi", True, False),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sifirla", action="store_true", help="Mevcut veritabanini siler")
    a = p.parse_args()
    if a.sifirla:
        sifirla()
    else:
        tablolari_olustur()
    with db_oturumu() as db:
        if db.scalar(select(Kullanici.id).limit(1)):
            print("Veritabani bos degil; --sifirla ile calistirin.")
            return
        yukle(db)
    print("Demo verisi yuklendi. Giris: admin / " + DEMO_PAROLA)


def yukle(db):
    r = R
    # merkezler
    merkezler = {}
    for kod, ad, sehir, tip, yatak, hbys, alanlar in MERKEZLER:
        m = Merkez(kod=kod, ad=ad, sehir=sehir, kurum_tipi=tip, yatak_sayisi=yatak, hbys=hbys, terapotik_alanlar=alanlar,
                   fhir_uc_noktasi=f"https://fhir.{kod.lower().replace('-', '')}.hastane.local/r4")
        db.add(m)
        merkezler[kod] = m
    db.flush()
    arastirmacilar = []
    for i, (unvan, ad, uzm) in enumerate(ARASTIRMACI_ADLARI):
        m = list(merkezler.values())[i % len(merkezler)]
        ar = Arastirmaci(merkez_id=m.id, ad_soyad=ad, unvan=unvan, uzmanlik=uzm, gcp_egitim_tarihi=g(r.randint(60, 900)),
                         cv_tarihi=g(r.randint(30, 400)), tamamlanan_calisma=r.randint(2, 14))
        db.add(ar)
        arastirmacilar.append(ar)
    # ikinci tur: her merkezde en az iki arastirmaci olsun
    for m in merkezler.values():
        for unvan, ad, uzm in r.sample(ARASTIRMACI_ADLARI, 2):
            db.add(Arastirmaci(merkez_id=m.id, ad_soyad=ad, unvan=unvan, uzmanlik=uzm, gcp_egitim_tarihi=g(r.randint(60, 900)),
                               tamamlanan_calisma=r.randint(1, 9)))
    db.flush()

    # kullanicilar
    kullanicilar = {}
    for kadi, ad, eposta, rol, mkod in KULLANICILAR:
        k = Kullanici(kullanici_adi=kadi, ad_soyad=ad, eposta=eposta, parola_hash=yetki.parola_hashle(DEMO_PAROLA), rol=rol,
                      merkez_id=merkezler[mkod].id if mkod else None, parola_degisim=simdi(),
                      son_giris=simdi() - timedelta(hours=r.randint(1, 200)))
        db.add(k)
        kullanicilar[kadi] = k
    kullanicilar["sponsor.gorunum"].kurum = "Anadolu Biyofarma A.Ş."
    db.flush()
    kurulum_svc.ayar_yaz(db, "cro", "EBM Klinik Araştırma", None, "EBM CRO")
    admin, py, cra1, cra2 = kullanicilar["admin"], kullanicilar["pelin.aydin"], kullanicilar["burak.sen"], kullanicilar["elif.kara"]
    from ..models import ApiAnahtari

    db.add(ApiAnahtari(kullanici_id=kullanicilar["veri.ekibi"].id, ad="HBYS FHIR senkron – demo", onek="sc_demo0000",
                       hash=yetki.api_anahtari_hashle("sc_demo-anahtari-uretimde-kullanmayin"), aktif=True))
    ara1, _koord = kullanicilar["dr.ozturk"], kullanicilar["hemsire.demir"]
    denetim.kaydet(db, admin, "olustur", "sistem", None, yeni={"not": "demo verisi yuklendi"})

    from ..services.bdm import BDMIstemci
    from ..services.rbm import varsayilan_krileri_yukle, varsayilan_qtlleri_yukle

    istemci = BDMIstemci.olustur()
    varsayilan_krileri_yukle(db, None)

    # hastalar (merkez x indikasyon)
    hasta_havuzu = {}
    for kod, m in merkezler.items():
        for ind, n in (("meme", 9), ("diyabet", 8), ("kah", 6), ("koah", 6)):
            if ind == "meme" and "Onkoloji" not in (m.terapotik_alanlar or []):
                continue
            if ind == "kah" and "Kardiyoloji" not in (m.terapotik_alanlar or []):
                continue
            hs = hasta_uret(m.id, ind, n, r, len(hasta_havuzu.get(m.id, [])) + 1)
            for h in hs:
                db.add(h)
            hasta_havuzu.setdefault(m.id, []).extend(hs)
    db.flush()

    calismalar = {}
    for cdef in CALISMALAR:
        c = Calisma(kod=cdef["kod"], baslik=cdef["baslik"], kisa_ad=cdef["kisa_ad"], tur=cdef["tur"], faz=cdef["faz"],
                    tasarim=cdef["tasarim"], sponsor=cdef["sponsor"], terapotik_alan=cdef["terapotik_alan"],
                    endikasyon=cdef["endikasyon"], durum=cdef["durum"], hedef_hasta=cdef["hedef_hasta"],
                    hedef_merkez=cdef["hedef_merkez"], baslangic=cdef["baslangic"], planlanan_bitis=cdef["bitis"],
                    risk_sinifi=cdef["risk"], ct_gov_no=cdef.get("ct"))
        db.add(c)
        db.flush()
        calismalar[c.kod] = c
        gecmis = cdef.get("gecmis", False)
        denetim.kaydet(db, py, "olustur", "calisma", c.id, yeni={"kod": c.kod})
        varsayilan_qtlleri_yukle(db, c)

        if not gecmis:
            db.add(ProtokolVersiyon(calisma_id=c.id, versiyon="1.0", tarih=c.baslangic - timedelta(days=90), ozet="İlk sürüm"))
            if c.durum.value in ("kayit", "izlem"):
                db.add(ProtokolVersiyon(calisma_id=c.id, versiyon="2.0", tarih=c.baslangic + timedelta(days=60),
                                        degisiklik_notu="Dahil etme kriteri 6 (Hb eşiği) ve vizit penceresi güncellendi; etik kurul onayı alındı."))
        for ad, acik in cdef["kollar"]:
            db.add(Kol(calisma_id=c.id, ad=ad, aciklama=acik))
        sira = 0
        for tip, liste in (("dahil", cdef["dahil"]), ("haric", cdef["haric"])):
            for i, metin in enumerate(liste, 1):
                y = istemci.kriter_yapilandir(metin, tip)
                db.add(Kriter(calisma_id=c.id, tip=tip, sira=i, metin=metin, yapisal=y.to_dict(), guven=y.guven,
                              onaylandi=(y.guven or 0) >= 0.6 or c.durum.value in ("kayit", "izlem"),
                              onaylayan_id=ara1.id if (y.guven or 0) >= 0.6 else None))
                sira += 1
        # eCRF formlari standart kutuphaneden (durum="yayinda"); vizit semasi calisma bazli
        kodlar = [kod for kod in ecrf.STANDART_FORMLAR if kod != "ANKET"
                  and not (c.tur == CalismaTuru.KAYIT and kod in ("EX", "IE"))
                  and not (c.tur != CalismaTuru.ILAC and kod == "QS")]
        for f in ecrf.standart_formlari_ekle(db, c, kodlar):
            f.versiyon = "1.1" if c.durum.value in ("kayit", "izlem") else "1.0"
        ecrf.vizit_semasi_uygula(db, c, "standart")
        # calisma ekibi: CRO senaryosunda proje ekibi calismaya atanir (gorunurluk kisiti etkin)
        cra = cra1 if c.terapotik_alan in ("Onkoloji", "Endokrinoloji") else cra2
        for uye in (py, cra, kullanicilar["veri.ekibi"], kullanicilar["fv.ekibi"]):
            db.add(CalismaUyesi(calisma_id=c.id, kullanici_id=uye.id, ekleyen_id=admin.id))
        db.flush()

        # merkezler ve kilometre taslari
        (BUGUN - c.baslangic).days
        for j, mkod in enumerate(cdef["merkezler"], 1):
            m = merkezler[mkod]
            bas = next((x for x in m.arastirmacilar if x.uzmanlik and (x.uzmanlik.split()[0] in c.terapotik_alan or c.terapotik_alan.split()[0] in x.uzmanlik)), m.arastirmacilar[0])
            secim = c.baslangic - timedelta(days=r.randint(60, 150))
            akt_sure = int(r.gauss({"universite": 150, "egitim_arastirma": 120, "sehir": 100, "ozel": 70}[m.kurum_tipi], 30))
            akt = secim + timedelta(days=max(40, akt_sure))
            durum = "aktif"
            if gecmis:
                durum = "kapali"
            elif c.durum == CalismaDurumu.TASARIM:
                durum, akt = "aday", None
            elif c.durum == CalismaDurumu.BASVURU:
                durum, akt = r.choice(["fizibilite", "secildi", "etik"]), None
            elif c.durum == CalismaDurumu.AKTIVASYON:
                durum = r.choice(["etik", "sozlesme", "siv", "aktif", "aktif"])
                akt = akt if durum == "aktif" else None
            elif akt > BUGUN:
                durum, akt = "sozlesme", None
            cm = CalismaMerkez(calisma_id=c.id, merkez_id=m.id, bas_arastirmaci_id=bas.id, merkez_no=f"{j:02d}", durum=durum,
                               hedef_hasta=max(5, c.hedef_hasta // max(1, len(cdef["merkezler"]))), secim_tarihi=secim,
                               aktivasyon_tarihi=akt)
            db.add(cm)
            db.flush()
            for tip, gun in (("fizibilite", 20), ("etik_onay", 75), ("sozlesme", 95), ("siv", 110), ("ilk_hasta", 140)):
                plan = secim + timedelta(days=gun)
                gerc = None
                if akt and tip in ("fizibilite", "etik_onay", "sozlesme", "siv"):
                    gerc = plan + timedelta(days=int(r.gauss(8, 15)))
                db.add(KilometreTasi(calisma_merkez_id=cm.id, tip=tip, planlanan=plan, gerceklesen=gerc))

            # gonulluler
            if akt and durum in ("aktif", "kapali"):
                son_gun = min(BUGUN, c.planlanan_bitis if gecmis else BUGUN)
                ay = max(1, (son_gun - akt).days / 30.4)
                hiz = {"universite": 1.4, "egitim_arastirma": 1.1, "sehir": 1.7, "ozel": 0.6}[m.kurum_tipi] * r.uniform(0.5, 1.4)
                if c.tur == CalismaTuru.KAYIT:
                    hiz *= 3
                n_rand = min(int(hiz * ay), cm.hedef_hasta + 4)
                n_toplam = int(n_rand * r.uniform(1.25, 1.6)) + 1
                cm.ilk_hasta_tarihi = akt + timedelta(days=r.randint(5, 40)) if n_rand else None
                havuz = [h for h in hasta_havuzu.get(m.id, []) if cdef["indikasyon"] and any(t["icd10"].startswith({"meme": "C50", "diyabet": "E11", "kah": "I25", "koah": "J44", "khdak": "C34", "ky": "I50"}[cdef["indikasyon"]]) for t in t_list(h))]
                for i in range(1, n_toplam + 1):
                    onam = akt + timedelta(days=int(r.uniform(5, max(6, (son_gun - akt).days))))
                    if onam > son_gun:
                        onam = son_gun - timedelta(days=r.randint(0, 5))
                    gn = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, gonullu_no=f"{cm.merkez_no}-{i:03d}",
                                 onam_tarihi=onam, onam_versiyonu="2.0" if onam > c.baslangic + timedelta(days=60) else "1.0",
                                 tarama_tarihi=onam + timedelta(days=r.randint(0, 3)))
                    if i <= n_rand:
                        gn.randomizasyon_tarihi = gn.tarama_tarihi + timedelta(days=r.randint(3, 14))
                        if gn.randomizasyon_tarihi > son_gun:
                            gn.randomizasyon_tarihi = son_gun
                        gecen = (son_gun - gn.randomizasyon_tarihi).days
                        if gecmis or gecen > 175:
                            gn.durum = GonulluDurumu.TAMAMLADI if r.random() > 0.12 else GonulluDurumu.AYRILDI
                            gn.bitis_tarihi = gn.randomizasyon_tarihi + timedelta(days=170 if gn.durum == GonulluDurumu.TAMAMLADI else r.randint(20, 150))
                            if gn.durum == GonulluDurumu.AYRILDI:
                                gn.ayrilma_nedeni = r.choice(["Advers olay", "Hasta kararı", "Takipten çıktı", "Araştırmacı kararı"])
                        elif gecen > 90:
                            gn.durum = r.choice([GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE])
                        else:
                            gn.durum = GonulluDurumu.TEDAVIDE if gecen > 7 else GonulluDurumu.RANDOMIZE
                        if c.kollar:
                            gn.kol_id = r.choice(c.kollar).id
                        if havuz and r.random() < 0.6:
                            gn.hasta_id = havuz.pop(0).id
                    else:
                        if r.random() < 0.7:
                            gn.durum = GonulluDurumu.TARAMA_BASARISIZ
                            gn.tarama_basarisizlik_nedeni = r.choice(["Hb < 9 g/dL", "ECOG 2", "Hariç kriteri: MI öyküsü", "QTc > 450 ms", "Onam geri çekildi", "HbA1c aralık dışı"])
                        else:
                            gn.durum = r.choice([GonulluDurumu.TARAMA, GonulluDurumu.ONAM])
                    db.add(gn)
                    db.flush()
                    if gn.randomizasyon_tarihi and not gecmis:
                        _vizit_ve_formlar(db, c, gn, cm, r, son_gun, kullanicilar)
                    if gn.randomizasyon_tarihi and (not gecmis or r.random() < 0.5):
                        _advers_olaylar(db, c, gn, r, son_gun)

            if not gecmis and durum == "aktif":
                # izlem ziyaretleri ve sapmalar
                db.add(IzlemZiyareti(calisma_merkez_id=cm.id, cra_id=r.choice([cra1, cra2]).id, tip="SIV", planlanan=akt - timedelta(days=3),
                                     gerceklesen=akt - timedelta(days=3), sdv_orani=None, rapor_onay=datetime.combine(akt, datetime.min.time())))
                t = akt + timedelta(days=45)
                while t < BUGUN:
                    db.add(IzlemZiyareti(calisma_merkez_id=cm.id, cra_id=r.choice([cra1, cra2]).id, tip=r.choice(["IMV", "IMV", "uzaktan"]),
                                         planlanan=t, gerceklesen=t + timedelta(days=r.randint(0, 4)), sdv_orani=r.choice([20, 50, 100]),
                                         bulgular=[{"konu": r.choice(["Onam formunda tarih eksik", "İlaç sayım kaydı gecikmiş", "Kaynak belge-eCRF uyumsuzluğu"]),
                                                    "onem": r.choice(["minor", "major"]), "kapali": r.random() < 0.7}] if r.random() < 0.6 else []))
                    t += timedelta(days=r.randint(40, 75))
                db.add(IzlemZiyareti(calisma_merkez_id=cm.id, cra_id=r.choice([cra1, cra2]).id, tip="IMV", planlanan=BUGUN + timedelta(days=r.randint(5, 40))))
                for g_ in cm.gonulluler:
                    if r.random() < (0.3 if j == 3 else 0.05):
                        db.add(ProtokolSapmasi(calisma_merkez_id=cm.id, gonullu_id=g_.id, tarih=(g_.randomizasyon_tarihi or g_.onam_tarihi) + timedelta(days=r.randint(5, 80)),
                                               kategori=r.choice(["vizit", "vizit", "belge", "onam", "ilac", "prosedur"]),
                                               onem="major" if r.random() < 0.15 else "minor",
                                               aciklama=r.choice(["V3 viziti pencere dışında yapıldı (+6 gün)", "Onam formunda hasta imza tarihi eksik",
                                                                  "Protokolde tanımlı EKG çekilmedi", "Doz azaltımı kaydı gecikmeli girildi",
                                                                  "Yeni onam sürümü imzalatılmadan tedaviye devam edildi"]),
                                               kapali=r.random() < 0.6))
        # basvurular
        if not gecmis:
            _basvurular(db, c, cdef, merkezler, r)
            _belgeler(db, c, py, r)
    db.flush()

    # yapay zeka modullerini calistir
    from ..services.eslestirme import Eslestirici
    from ..services.merkez_zekasi import calisma_tahmin_guncelle
    from ..services.rbm import erken_uyari_calistir, qtl_guncelle

    e = Eslestirici()
    for kod in ("EBM-ONK-2025-003", "EBM-END-2026-001", "EBM-KRD-2026-004"):
        c = calismalar[kod]
        sonuclar = e.calisma_icin_tara(db, c)
        # bir kismi arastirmaci tarafindan incelenmis olsun (golge mod raporu icin)
        for s in sonuclar:
            if r.random() < 0.45:
                s.inceleme_karari = "onay" if (s.karar in ("uygun", "olasi") and r.random() < 0.9) or (s.karar == "belirsiz" and r.random() < 0.3) else ("beklet" if r.random() < 0.2 else "red")
                s.inceleyen_id = ara1.id
                s.inceleme_zamani = simdi() - timedelta(days=r.randint(1, 20))
                s.inceleme_notu = r.choice([None, "Patoloji raporu doğrulandı.", "Hb değeri güncel değil, tekrar bakılacak.", "Hasta başka çalışmada."])
        denetim.kaydet(db, ara1, "eslestirme", "eslestirme", c.id, yeni={"calisma": c.kod, "hasta": len(sonuclar), "model": e.model_surumu})
    for c in calismalar.values():
        if c.durum != CalismaDurumu.ARSIV:
            calisma_tahmin_guncelle(db, c)
            if c.durum in (CalismaDurumu.KAYIT, CalismaDurumu.IZLEM, CalismaDurumu.AKTIVASYON):
                erken_uyari_calistir(db, c, kullanici_id=cra1.id)
                qtl_guncelle(db, c)
    db.flush()


def t_list(h):
    return h.tanilar or []


def _vizit_ve_formlar(db, c, gn, cm, r, son_gun, kullanicilar):
    formlar = {f.kod: f for f in c.formlar}
    tanimlar = {t.ad: t for t in c.vizit_tanimlari}
    koord = kullanicilar["hemsire.demir"]
    cra = kullanicilar["burak.sen"]
    gecikmeli_merkez = cm.merkez_no == "03"
    for i, (ad, gun, pencere) in enumerate(ecrf.VIZIT_SABLONLARI["standart"]):
        plan = gn.randomizasyon_tarihi + timedelta(days=gun)
        v = Vizit(gonullu_id=gn.id, vizit_tanimi_id=tanimlar[ad].id if ad in tanimlar else None, ad=ad, sira=i,
                  planlanan=plan, pencere_gun=pencere, durum="planli")
        if plan <= son_gun:
            kayma = int(r.gauss(0, 1.4 if not gecikmeli_merkez else 4))
            v.gerceklesen = plan + timedelta(days=kayma)
            v.durum = "pencere_disi" if abs(kayma) > pencere else "yapildi"
            if r.random() < 0.015:
                v.gerceklesen, v.durum = None, "kacirildi"
        db.add(v)
        db.flush()
        if v.gerceklesen:
            for kod, f in formlar.items():
                if not f.vizitte_var(ad):
                    continue
                if kod in ("CM",) and r.random() < 0.5:
                    continue
                veriler = _form_verisi(kod, gn, v, r)
                gecikme = r.randint(0, 4) if not gecikmeli_merkez else r.randint(3, 20)
                durum = "tamamlandi"
                if v.gerceklesen < son_gun - timedelta(days=45):
                    durum = r.choice(["sdv", "sdv", "kilitli", "tamamlandi"])
                elif r.random() < 0.08:
                    durum = "taslak"
                fk = FormKaydi(gonullu_id=gn.id, form_id=f.id, vizit_id=v.id, veriler=veriler, durum=durum, giren_id=koord.id,
                               olusturma=datetime.combine(v.gerceklesen + timedelta(days=gecikme), datetime.min.time()) + timedelta(hours=10),
                               sdv_yapan_id=cra.id if durum in ("sdv", "kilitli") else None,
                               sdv_zamani=datetime.combine(v.gerceklesen + timedelta(days=gecikme + 20), datetime.min.time()) if durum in ("sdv", "kilitli") else None)
                db.add(fk)
                db.flush()
                # sorgular
                if r.random() < (0.22 if gecikmeli_merkez else 0.07):
                    alan = r.choice([a["kod"] for a in f.alanlar])
                    acilis = fk.olusturma + timedelta(days=r.randint(1, 10))
                    kapali = r.random() < (0.55 if gecikmeli_merkez else 0.8)
                    db.add(Sorgu(form_kaydi_id=fk.id, alan=alan, soru=r.choice([
                        f"'{alan}' değeri kaynak belgeyle uyumsuz; lütfen doğrulayın.",
                        f"'{alan}' beklenen aralığın dışında. Ölçüm tekrarlandı mı?",
                        f"'{alan}' boş bırakılmış; zorunlu alan.",
                    ]), kaynak=r.choice(["otomatik", "manuel"]), durum="kapali" if kapali else "acik",
                        acan_id=cra.id, acilis=acilis, kapanis=acilis + timedelta(days=r.randint(2, 12)) if kapali else None,
                        cevap="Kaynak belgeye göre düzeltildi." if kapali else None))


def _form_verisi(kod, gn, v, r):
    t = str(v.gerceklesen)
    if kod == "DM":
        return {"BRTHYR": gn.hasta.dogum_yili if gn.hasta else BUGUN.year - r.randint(30, 75), "SEX": "Kadın" if (gn.hasta and gn.hasta.cinsiyet == "K") or r.random() < 0.5 else "Erkek",
                "HEIGHT": r.randint(152, 185), "WEIGHT": r.randint(52, 110)}
    if kod == "IE":
        return {"IEYN": "Evet", "IEEXCL": "Hayır", "IECOM": ""}
    if kod == "VS":
        return {"VSDAT": t, "SYSBP": r.randint(105, 165), "DIABP": r.randint(62, 98), "PULSE": r.randint(58, 98), "TEMP": round(r.uniform(36.1, 37.4), 1)}
    if kod == "LB":
        return {"LBDAT": t, "HGB": round(r.uniform(9.0, 14.5), 1), "ANC": round(r.uniform(1.0, 6.0), 1), "PLT": r.randint(110, 350),
                "CREAT": round(r.uniform(0.6, 1.3), 2), "ALT": r.randint(10, 70), "HBA1C": round(r.uniform(6.5, 10.5), 1)}
    if kod == "EX":
        return {"EXDAT": t, "EXDOSE": r.choice([400, 200, 20, 100]), "EXDOSU": "mg", "EXADJ": ""}
    if kod == "CM":
        return {"CMTRT": r.choice(["Metformin", "Amlodipin", "Ondansetron", "Pantoprazol", "Levotiroksin"]), "CMINDC": r.choice(["Diyabet", "Hipertansiyon", "Bulantı", "Reflü", "Hipotiroidi"]),
                "CMSTDAT": str(v.gerceklesen - timedelta(days=r.randint(30, 900))), "CMONGO": "Evet"}
    if kod == "QS":
        return {"ECOG": str(r.choice([0, 1, 1]))}
    return {}


def _advers_olaylar(db, c, gn, r, son_gun):
    n = r.choice([0, 0, 1, 1, 2, 3])
    for _ in range(n):
        terim, pt, soc, siddet, ned, beklenen, ciddi = r.choice(AE_TERIMLER)
        bas = gn.randomizasyon_tarihi + timedelta(days=r.randint(3, 120))
        if bas > son_gun:
            continue
        ciddi = ciddi and r.random() < 0.7
        a = AdversOlay(gonullu_id=gn.id, terim=terim, meddra_pt=pt, meddra_soc=soc, baslangic=bas,
                       bitis=bas + timedelta(days=r.randint(2, 30)) if r.random() < 0.8 else None, siddet=siddet, nedensellik=ned,
                       beklenen=beklenen, ciddi=ciddi, sonuc=r.choice(["İyileşti", "İyileşti", "Devam ediyor", "Sekelle iyileşti"]),
                       alinan_onlem=r.choice(["Değişiklik yok", "Doz azaltıldı", "Geçici kesildi"]))
        if ciddi:
            a.ciddiyet_olcutu = r.choice(["hastaneye_yatis", "hastaneye_yatis", "tibbi_onemli", "yasam_tehdidi"])
            a.farkindalik_tarihi = bas + timedelta(days=r.randint(0, 2))
            if r.random() < 0.93:
                a.sponsor_bildirim = a.farkindalik_tarihi + timedelta(days=1 if r.random() < 0.9 else 3)
                a.titck_bildirim = a.farkindalik_tarihi + timedelta(days=r.choice([4, 6, 9, 12, 13]))
                a.etik_bildirim = a.titck_bildirim
        db.add(a)


def _basvurular(db, c, cdef, merkezler, r):
    bas = c.baslangic - timedelta(days=150)
    ek_sure, titck_sure = r.randint(35, 80), r.randint(45, 110)
    gonderildi = c.durum.value not in ("tasarim",)
    if gonderildi:
        db.add(Basvuru(calisma_id=c.id, kurum="etik_kurul", tip="ilk", referans_no=f"EK-{bas.year}/{r.randint(100, 999)}", gonderim_tarihi=bas,
                       karar="onay" if c.durum.value not in ("basvuru",) else "beklemede",
                       karar_tarihi=bas + timedelta(days=ek_sure) if c.durum.value not in ("basvuru",) else None))
        db.add(Basvuru(calisma_id=c.id, kurum="titck", tip="ilk", referans_no=f"TİTCK-KAD-{bas.year}-{r.randint(1000, 9999)}", gonderim_tarihi=bas + timedelta(days=10),
                       karar="onay" if c.durum.value not in ("basvuru",) else ("sartli_onay" if r.random() < 0.5 else "beklemede"),
                       karar_tarihi=bas + timedelta(days=10 + titck_sure) if c.durum.value not in ("basvuru",) or r.random() < 0.5 else None,
                       notlar="Araştırma broşürü güncel sürümü ile tamamlandı." if c.durum.value == "basvuru" else None))
        db.add(Basvuru(calisma_id=c.id, kurum="kvkk", tip="ilk", gonderim_tarihi=bas + timedelta(days=5), karar="onay", karar_tarihi=bas + timedelta(days=12),
                       notlar="Veri envanteri ve kimliksizleştirme akışı KVKK uyum birimi tarafından onaylandı."))
        if c.durum.value in ("kayit", "izlem"):
            db.add(Basvuru(calisma_id=c.id, kurum="etik_kurul", tip="degisiklik", referans_no="Protokol v2.0", gonderim_tarihi=c.baslangic + timedelta(days=40),
                           karar="onay", karar_tarihi=c.baslangic + timedelta(days=58)))
            db.add(Basvuru(calisma_id=c.id, kurum="titck", tip="degisiklik", referans_no="Protokol v2.0", gonderim_tarihi=c.baslangic + timedelta(days=40),
                           karar="onay", karar_tarihi=c.baslangic + timedelta(days=71)))
            db.add(Basvuru(calisma_id=c.id, kurum="etik_kurul", tip="yillik", gonderim_tarihi=BUGUN - timedelta(days=r.randint(5, 40)), karar="beklemede"))
        for mkod in cdef["merkezler"][:3]:
            m = merkezler[mkod]
            gt = bas + timedelta(days=r.randint(20, 60))
            db.add(Basvuru(calisma_id=c.id, merkez_id=m.id, kurum="kurum_izni", tip="ilk", gonderim_tarihi=gt,
                           karar="onay" if c.durum.value not in ("basvuru", "aktivasyon") or r.random() < 0.5 else "beklemede",
                           karar_tarihi=gt + timedelta(days=r.randint(10, 50)) if c.durum.value not in ("basvuru", "aktivasyon") or r.random() < 0.5 else None))


def _belgeler(db, c, py, r):
    import hashlib

    liste = [("01", "Çalışma yönetim planı", "1.0", "onayli"), ("01", "İzlem planı (risk bazlı)", "2.0", "onayli"),
             ("02", "Protokol", "2.0" if c.durum.value in ("kayit", "izlem") else "1.0", "onayli"),
             ("02", "Bilgilendirilmiş gönüllü olur formu", "2.0", "onayli"), ("02", "Araştırma broşürü", "7.0", "onayli"),
             ("03", "TİTCK onay yazısı", "1.0", "onayli" if c.durum.value not in ("tasarim", "basvuru") else "taslak"),
             ("04", "Etik kurul onay yazısı", "1.0", "onayli" if c.durum.value not in ("tasarim", "basvuru") else "taslak"),
             ("05", "Merkez imza ve yetki listesi", "1.0", "onayli"), ("06", "Araştırma ürünü sevk ve sayım kayıtları", "1.0", "taslak"),
             ("07", "Güvenlik yönetim planı", "1.0", "onayli"), ("10", "Veri yönetim planı", "1.1", "onayli"), ("10", "eCRF spesifikasyonu", "1.1", "onayli"),
             ("11", "İstatistiksel analiz planı", "1.0", "taslak" if c.durum.value != "izlem" else "onayli")]
    if c.durum.value == "tasarim":
        liste = liste[:3]
    for bolge, ad, ver, durum in liste:
        db.add(Belge(calisma_id=c.id, tmf_bolge=bolge, ad=ad, versiyon=ver, durum=durum, yukleyen_id=py.id,
                     dosya_adi=f"{c.kod}_{ad.replace(' ', '_')}_v{ver}.pdf", sha256=hashlib.sha256(f"{c.kod}{ad}{ver}".encode()).hexdigest(),
                     yukleme=simdi() - timedelta(days=r.randint(10, 300))))


if __name__ == "__main__":
    main()
