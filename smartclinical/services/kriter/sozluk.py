"""Kriter ayristirici icin terim sozlukleri.

Tani terimleri ICD-10 on ekine, laboratuvar adlari LOINC koduna, ilac siniflari ATC
on ekine eslenir. Liste kapsayici degil; sik gorulen endikasyonlar icin yeterli.
Eksik terimler BDM katmanindan gelir, kural tabanli yol "serbest" kategoriye duser.
"""

import re

# ---------------------------------------------------------------------------
# Turkce normalizasyon
# ---------------------------------------------------------------------------

_TR_KUCUK = str.maketrans("İIÇĞÖŞÜÂÎÛ", "iıçğöşüaiu")


def normalize(metin: str) -> str:
    """Turkce'ye uygun kucuk harfe cevirir, fazla bosluklari toplar."""
    if not metin:
        return ""
    metin = metin.translate(_TR_KUCUK).lower()
    metin = metin.replace("≥", ">=").replace("≤", "<=").replace("–", "-").replace("—", "-")
    metin = re.sub(r"['’`]", " ", metin)  # 18'den -> 18 den
    metin = re.sub(r"\s+", " ", metin)
    return metin.strip()


def sade(metin: str) -> str:
    """Normalize + Turkce karakterleri ASCII'ye indirger (eslestirme icin)."""
    m = normalize(metin)
    return m.translate(str.maketrans("çğıöşü", "cgiosu"))


# ---------------------------------------------------------------------------
# Tani terimleri -> ICD-10 on ekleri
# (terim, [icd10 prefix...]) ; terimler sade() formunda yazildi
# ---------------------------------------------------------------------------

TANI_SOZLUGU: dict[str, list[str]] = {
    # Onkoloji
    "meme kanseri": ["C50"], "meme karsinomu": ["C50"], "breast cancer": ["C50"], "breast carcinoma": ["C50"],
    "kucuk hucreli disi akciger kanseri": ["C34"], "khdak": ["C34"], "nsclc": ["C34"],
    "non-small cell lung cancer": ["C34"], "akciger kanseri": ["C34"], "lung cancer": ["C34"],
    "kucuk hucreli akciger kanseri": ["C34"], "sclc": ["C34"],
    "kolorektal kanser": ["C18", "C19", "C20"], "colorectal cancer": ["C18", "C19", "C20"],
    "kolon kanseri": ["C18"], "colon cancer": ["C18"], "rektum kanseri": ["C20"], "rectal cancer": ["C20"],
    "mide kanseri": ["C16"], "gastric cancer": ["C16"], "pankreas kanseri": ["C25"], "pancreatic cancer": ["C25"],
    "prostat kanseri": ["C61"], "prostate cancer": ["C61"], "over kanseri": ["C56"], "ovarian cancer": ["C56"],
    "mesane kanseri": ["C67"], "bladder cancer": ["C67"], "bobrek kanseri": ["C64"], "renal cell carcinoma": ["C64"],
    "hepatoselüler karsinom": ["C22"], "hepatoseluler karsinom": ["C22"], "hepatocellular carcinoma": ["C22"],
    "melanom": ["C43"], "melanoma": ["C43"], "lenfoma": ["C81", "C82", "C83", "C84", "C85"],
    "lymphoma": ["C81", "C82", "C83", "C84", "C85"], "hodgkin lenfoma": ["C81"],
    "multipl miyelom": ["C90"], "multiple myeloma": ["C90"],
    "akut miyeloid losemi": ["C92"], "aml": ["C92"], "kronik lenfositik losemi": ["C91.1"], "kll": ["C91.1"],
    "glioblastom": ["C71"], "baş boyun kanseri": ["C00", "C01", "C02", "C03", "C04", "C05", "C06", "C09", "C10", "C13", "C14", "C32"],
    "bas boyun kanseri": ["C00", "C01", "C02", "C03", "C04", "C05", "C06", "C09", "C10", "C13", "C14", "C32"],
    "serviks kanseri": ["C53"], "cervical cancer": ["C53"], "endometrium kanseri": ["C54"],
    "tiroid kanseri": ["C73"], "ozofagus kanseri": ["C15"],
    # Kardiyoloji
    "hipertansiyon": ["I10", "I11", "I12", "I13", "I15"], "hypertension": ["I10", "I11", "I12", "I13", "I15"],
    "kalp yetmezligi": ["I50"], "kalp yetersizligi": ["I50"], "heart failure": ["I50"], "ky": ["I50"],
    "atriyal fibrilasyon": ["I48"], "atrial fibrillation": ["I48"], "af": ["I48"],
    "miyokard enfarktusu": ["I21", "I22"], "myocardial infarction": ["I21", "I22"], "mi": ["I21", "I22"],
    "koroner arter hastaligi": ["I25"], "coronary artery disease": ["I25"],
    "inme": ["I63", "I64"], "stroke": ["I63", "I64"], "iskemik inme": ["I63"],
    "pulmoner emboli": ["I26"], "pulmonary embolism": ["I26"], "derin ven trombozu": ["I80"],
    "unstable angina": ["I20.0"], "kararsiz angina": ["I20.0"],
    # Endokrin / metabolik
    "tip 2 diyabet": ["E11"], "tip 2 diabetes mellitus": ["E11"], "type 2 diabetes": ["E11"], "t2dm": ["E11"],
    "tip 1 diyabet": ["E10"], "type 1 diabetes": ["E10"], "tip 1 diabetes mellitus": ["E10"], "tip 1 diabetes": ["E10"], "t1dm": ["E10"], "diyabet": ["E10", "E11"], "diabetes": ["E10", "E11"],
    "obezite": ["E66"], "obesity": ["E66"], "hipotiroidi": ["E03"], "hipertiroidi": ["E05"],
    "hiperlipidemi": ["E78"], "dislipidemi": ["E78"],
    # Solunum
    "koah": ["J44"], "copd": ["J44"], "kronik obstruktif akciger hastaligi": ["J44"],
    "astim": ["J45"], "asthma": ["J45"], "idiyopatik pulmoner fibrozis": ["J84.1"], "ipf": ["J84.1"],
    # Nefroloji
    "kronik bobrek hastaligi": ["N18"], "kbh": ["N18"], "chronic kidney disease": ["N18"], "ckd": ["N18"],
    "bobrek yetmezligi": ["N17", "N18", "N19"],
    # Romatoloji / immunoloji
    "romatoid artrit": ["M05", "M06"], "rheumatoid arthritis": ["M05", "M06"], "ra": ["M05", "M06"],
    "ankilozan spondilit": ["M45"], "psoriatik artrit": ["L40.5"], "psoriasis": ["L40"], "sedef": ["L40"],
    "sistemik lupus eritematozus": ["M32"], "sle": ["M32"], "lupus": ["M32"],
    "crohn hastaligi": ["K50"], "crohn's disease": ["K50"], "ulseratif kolit": ["K51"], "ulcerative colitis": ["K51"],
    # Noroloji / psikiyatri
    "multipl skleroz": ["G35"], "multiple sclerosis": ["G35"],
    "epilepsi": ["G40"], "epilepsy": ["G40"], "parkinson": ["G20"], "alzheimer": ["G30"],
    "migren": ["G43"], "migraine": ["G43"],
    "majör depresif bozukluk": ["F32", "F33"], "major depresif bozukluk": ["F32", "F33"], "depresyon": ["F32", "F33"],
    "major depressive disorder": ["F32", "F33"], "depression": ["F32", "F33"],
    "sizofreni": ["F20"], "schizophrenia": ["F20"], "bipolar bozukluk": ["F31"], "bipolar disorder": ["F31"],
    # Enfeksiyon
    "hepatit b": ["B18.1", "B16"], "hepatitis b": ["B18.1", "B16"], "hbv": ["B18.1", "B16"],
    "hepatit c": ["B18.2", "B17.1"], "hepatitis c": ["B18.2", "B17.1"], "hcv": ["B18.2", "B17.1"],
    "hiv": ["B20", "B21", "B22", "B23", "B24", "Z21"], "tuberkuloz": ["A15", "A16", "A17", "A18", "A19"],
    "tuberculosis": ["A15", "A16", "A17", "A18", "A19"], "covid-19": ["U07.1"],
    # Hematoloji / diger
    "anemi": ["D50", "D51", "D52", "D53", "D64"], "anemia": ["D50", "D51", "D52", "D53", "D64"],
    "osteoporoz": ["M80", "M81"], "osteoporosis": ["M80", "M81"],
    "siroz": ["K74"], "cirrhosis": ["K74"], "karaciger sirozu": ["K74"],
}

# Terimleri uzunluga gore sirala; "akciger kanseri" "kucuk hucreli disi akciger kanseri" icinde gecer,
# once uzun olani yakalamak lazim.
TANI_TERIMLERI = sorted(TANI_SOZLUGU.keys(), key=len, reverse=True)

# ---------------------------------------------------------------------------
# Laboratuvar: ad -> (loinc, varsayilan birim, es anlamlilar)
# ---------------------------------------------------------------------------

LAB_SOZLUGU: dict[str, dict] = {
    "hemoglobin": {"loinc": "718-7", "birim": "g/dL", "es": ["hb", "hgb", "haemoglobin"]},
    "qtc": {"loinc": "8636-3", "birim": "ms", "es": ["qtcf", "qtcb", "duzeltilmis qt", "qt araligi", "qtc interval"]},
    "hematokrit": {"loinc": "4544-3", "birim": "%", "es": ["hct", "hematocrit"]},
    "lokosit": {"loinc": "6690-2", "birim": "10^9/L", "es": ["wbc", "beyaz kure", "white blood cell", "leukocyte", "lökosit"]},
    "notrofil": {"loinc": "751-8", "birim": "10^9/L", "es": ["anc", "mutlak notrofil", "absolute neutrophil count", "nötrofil", "neutrophil"]},
    "trombosit": {"loinc": "777-3", "birim": "10^9/L", "es": ["plt", "platelet", "platelets", "platelet count"]},
    "lenfosit": {"loinc": "731-0", "birim": "10^9/L", "es": ["lymphocyte"]},
    "kreatinin": {"loinc": "2160-0", "birim": "mg/dL", "es": ["creatinine", "serum kreatinin", "serum creatinine"]},
    "egfr": {"loinc": "62238-1", "birim": "mL/min/1.73m2", "es": ["glomeruler filtrasyon", "tahmini gfr", "gfr", "estimated glomerular filtration rate", "creatinine clearance", "kreatinin klirensi", "kreatinin klerensi", "crcl", "ckd-epi"]},
    "ast": {"loinc": "1920-8", "birim": "U/L", "es": ["aspartat aminotransferaz", "sgot", "aspartate aminotransferase"]},
    "alt": {"loinc": "1742-6", "birim": "U/L", "es": ["alanin aminotransferaz", "sgpt", "alanine aminotransferase"]},
    "total bilirubin": {"loinc": "1975-2", "birim": "mg/dL", "es": ["bilirubin", "bilirubin total", "t. bilirubin"]},
    "alkalen fosfataz": {"loinc": "6768-6", "birim": "U/L", "es": ["alp", "alkaline phosphatase"]},
    "albumin": {"loinc": "1751-7", "birim": "g/dL", "es": ["albümin", "serum albumin"]},
    "hba1c": {"loinc": "4548-4", "birim": "%", "es": ["glikozile hemoglobin", "glycated hemoglobin", "a1c"]},
    "aclik glukozu": {"loinc": "1558-6", "birim": "mg/dL", "es": ["aclik kan sekeri", "akş", "aks", "fasting glucose", "fasting plasma glucose", "fpg", "glukoz", "glucose"]},
    "ldl": {"loinc": "13457-7", "birim": "mg/dL", "es": ["ldl kolesterol", "ldl-c", "ldl cholesterol"]},
    "hdl": {"loinc": "2085-9", "birim": "mg/dL", "es": ["hdl kolesterol", "hdl-c"]},
    "total kolesterol": {"loinc": "2093-3", "birim": "mg/dL", "es": ["kolesterol", "total cholesterol"]},
    "trigliserid": {"loinc": "2571-8", "birim": "mg/dL", "es": ["tg", "triglycerides", "trigliserit"]},
    "inr": {"loinc": "6301-6", "birim": "", "es": ["international normalized ratio"]},
    "aptt": {"loinc": "3173-2", "birim": "sn", "es": ["aktive parsiyel tromboplastin"]},
    "tsh": {"loinc": "3016-3", "birim": "mIU/L", "es": ["tiroid stimulan hormon", "thyroid stimulating hormone"]},
    "crp": {"loinc": "1988-5", "birim": "mg/L", "es": ["c-reaktif protein", "c-reactive protein"]},
    "sedimentasyon": {"loinc": "4537-7", "birim": "mm/sa", "es": ["esr", "sedim", "eritrosit sedimantasyon"]},
    "potasyum": {"loinc": "2823-3", "birim": "mmol/L", "es": ["k+", "potassium", "serum potasyum"]},
    "sodyum": {"loinc": "2951-2", "birim": "mmol/L", "es": ["na+", "sodium", "serum sodyum"]},
    "kalsiyum": {"loinc": "17861-6", "birim": "mg/dL", "es": ["calcium", "serum kalsiyum"]},
    "magnezyum": {"loinc": "19123-9", "birim": "mg/dL", "es": ["magnesium"]},
    "ure": {"loinc": "3094-0", "birim": "mg/dL", "es": ["bun", "üre", "kan ure azotu"]},
    "urik asit": {"loinc": "3084-1", "birim": "mg/dL", "es": ["ürik asit", "uric acid"]},
    "ldh": {"loinc": "2532-0", "birim": "U/L", "es": ["laktat dehidrogenaz", "lactate dehydrogenase"]},
    "ferritin": {"loinc": "2276-4", "birim": "ng/mL", "es": []},
    "b12": {"loinc": "2132-9", "birim": "pg/mL", "es": ["vitamin b12", "kobalamin"]},
    "vitamin d": {"loinc": "1989-3", "birim": "ng/mL", "es": ["25-oh vitamin d", "25-hidroksi vitamin d"]},
    "troponin": {"loinc": "10839-9", "birim": "ng/mL", "es": ["troponin i", "troponin t", "hs-troponin"]},
    "nt-probnp": {"loinc": "33762-6", "birim": "pg/mL", "es": ["ntprobnp", "probnp", "bnp"]},
    "psa": {"loinc": "2857-1", "birim": "ng/mL", "es": ["prostat spesifik antijen"]},
    "cea": {"loinc": "2039-6", "birim": "ng/mL", "es": ["karsinoembriyonik antijen"]},
    "ca 15-3": {"loinc": "6875-9", "birim": "U/mL", "es": ["ca15-3", "ca-15-3"]},
    "ca 19-9": {"loinc": "24108-3", "birim": "U/mL", "es": ["ca19-9", "ca-19-9"]},
    "ca 125": {"loinc": "10334-1", "birim": "U/mL", "es": ["ca125", "ca-125"]},
    "lvef": {"loinc": "10230-1", "birim": "%", "es": ["ejeksiyon fraksiyonu", "sol ventrikul ejeksiyon fraksiyonu", "ejection fraction", "ef"]},
    "hbsag": {"loinc": "5195-3", "birim": "", "es": ["hepatit b yuzey antijeni"]},
    "anti-hcv": {"loinc": "16128-1", "birim": "", "es": ["hcv antikoru"]},
    "proteinuri": {"loinc": "2888-6", "birim": "mg/gün", "es": ["proteinüri", "idrar protein", "proteinuria"]},
    "bmi": {"loinc": "39156-5", "birim": "kg/m2", "es": ["vucut kitle indeksi", "vki", "body mass index"]},
}

# ad/es anlamli -> kanonik ad ; uzun terim once
_LAB_INDEKS: list[tuple[str, str]] = []
for _ad, _b in LAB_SOZLUGU.items():
    _LAB_INDEKS.append((sade(_ad), _ad))
    for _e in _b["es"]:
        _LAB_INDEKS.append((sade(_e), _ad))
_LAB_INDEKS.sort(key=lambda x: len(x[0]), reverse=True)


def lab_bul(metin: str) -> tuple[str, dict] | None:
    """Metinde gecen ilk laboratuvar testini dondurur (kanonik ad, tanim)."""
    m = sade(metin)
    for terim, ad in _LAB_INDEKS:
        # kisa kisaltmalarda (alt, ast, ef...) kelime siniri sart
        if re.search(r"(?<![a-z0-9])" + re.escape(terim) + r"(?![a-z0-9])", m):
            return ad, LAB_SOZLUGU[ad]
    return None


# ---------------------------------------------------------------------------
# Ilac siniflari -> ATC on ekleri
# ---------------------------------------------------------------------------

ILAC_SOZLUGU: dict[str, list[str]] = {
    "metformin": ["A10BA02"], "insulin": ["A10A"], "insülin": ["A10A"], "sulfonilure": ["A10BB"],
    "sglt2": ["A10BK"], "sglt2 inhibitoru": ["A10BK"], "dpp-4": ["A10BH"], "glp-1": ["A10BJ"],
    "statin": ["C10AA"], "antikoagulan": ["B01AA", "B01AE", "B01AF"], "anticoagulant": ["B01AA", "B01AE", "B01AF"],
    "varfarin": ["B01AA03"], "warfarin": ["B01AA03"], "doak": ["B01AE", "B01AF"], "noak": ["B01AE", "B01AF"],
    "antiagregan": ["B01AC"], "aspirin": ["B01AC06"], "klopidogrel": ["B01AC04"],
    "ace inhibitoru": ["C09A"], "ace inhibitor": ["C09A"], "arb": ["C09C"], "beta bloker": ["C07"], "beta blocker": ["C07"],
    "kalsiyum kanal blokeri": ["C08"], "diuretik": ["C03"], "diüretik": ["C03"],
    "kortikosteroid": ["H02"], "steroid": ["H02"], "sistemik steroid": ["H02"], "prednizolon": ["H02AB06"],
    "immunsupresif": ["L04"], "immunosuppressant": ["L04"], "metotreksat": ["L01BA01", "L04AX03"],
    "methotrexate": ["L01BA01", "L04AX03"], "biyolojik ajan": ["L04AB", "L04AC"], "anti-tnf": ["L04AB"],
    "kemoterapi": ["L01A", "L01B", "L01C", "L01D", "L01XA"], "chemotherapy": ["L01A", "L01B", "L01C", "L01D", "L01XA"],
    "sitotoksik": ["L01A", "L01B", "L01C", "L01D", "L01XA"],
    "immunoterapi": ["L01FF", "L01XC"], "checkpoint inhibitoru": ["L01FF"], "pd-1": ["L01FF"], "pd-l1": ["L01FF"],
    "trastuzumab": ["L01FD01"], "bevacizumab": ["L01FG01"], "rituksimab": ["L01FA01"],
    "tirozin kinaz inhibitoru": ["L01E"], "tki": ["L01E"], "egfr tki": ["L01EB"],
    "hormonal tedavi": ["L02"], "tamoksifen": ["L02BA01"], "aromataz inhibitoru": ["L02BG"],
    "opioid": ["N02A"], "antidepresan": ["N06A"], "antiepileptik": ["N03"], "antipsikotik": ["N05A"],
    "antibiyotik": ["J01"], "antiviral": ["J05"], "nsaii": ["M01A"], "nsaid": ["M01A"],
    "bifosfonat": ["M05BA"], "cyp3a4 inhibitoru": [], "guclu cyp3a4": [],
}
ILAC_TERIMLERI = sorted(ILAC_SOZLUGU.keys(), key=len, reverse=True)

# ---------------------------------------------------------------------------
# Performans olcekleri
# ---------------------------------------------------------------------------

PERFORMANS_OLCEKLERI = {
    "ecog": {"alan": "ecog", "min": 0, "max": 5, "yon": "dusuk_iyi"},
    "who performans": {"alan": "ecog", "min": 0, "max": 5, "yon": "dusuk_iyi"},
    "karnofsky": {"alan": "karnofsky", "min": 0, "max": 100, "yon": "yuksek_iyi"},
    "kps": {"alan": "karnofsky", "min": 0, "max": 100, "yon": "yuksek_iyi"},
    "nyha": {"alan": "nyha", "min": 1, "max": 4, "yon": "dusuk_iyi"},
    "mrs": {"alan": "mrs", "min": 0, "max": 6, "yon": "dusuk_iyi"},
    "modified rankin": {"alan": "mrs", "min": 0, "max": 6, "yon": "dusuk_iyi"},
    "edss": {"alan": "edss", "min": 0, "max": 10, "yon": "dusuk_iyi"},
    "child-pugh": {"alan": "child_pugh", "min": 0, "max": 15, "yon": "dusuk_iyi"},
    "gold": {"alan": "gold", "min": 1, "max": 4, "yon": "dusuk_iyi"},
}

# ---------------------------------------------------------------------------
# Birim normalizasyonu  (hedef birime donusum carpani)
# Anahtar: (kaynak birim, hedef birim) -> carpan
# ---------------------------------------------------------------------------

_BIRIM_ESANLAM = {
    "g/dl": "g/dL", "gr/dl": "g/dL", "g/l": "g/L", "mg/dl": "mg/dL", "mg/l": "mg/L",
    "mmol/l": "mmol/L", "umol/l": "umol/L", "µmol/l": "umol/L", "μmol/l": "umol/L",
    "u/l": "U/L", "iu/l": "U/L", "ui/l": "U/L", "miu/l": "mIU/L", "uiu/ml": "mIU/L", "µiu/ml": "mIU/L",
    "10^9/l": "10^9/L", "10*9/l": "10^9/L", "x10^9/l": "10^9/L", "x10⁹/l": "10^9/L", "10⁹/l": "10^9/L",
    "/ul": "/uL", "/µl": "/uL", "/mm3": "/uL", "/mm³": "/uL", "cells/ul": "/uL", "hucre/ul": "/uL", "hücre/µl": "/uL",
    "k/ul": "10^9/L", "k/µl": "10^9/L", "bin/ul": "10^9/L", "bin/mm3": "10^9/L",
    "ml/min/1.73m2": "mL/min/1.73m2", "ml/min/1.73 m2": "mL/min/1.73m2", "ml/dk/1.73m2": "mL/min/1.73m2",
    "ml/dk/1.73 m2": "mL/min/1.73m2", "ml/min/1.73m²": "mL/min/1.73m2", "ml/min": "mL/min", "ml/dk": "mL/min",
    "ng/ml": "ng/mL", "pg/ml": "pg/mL", "u/ml": "U/mL", "%": "%", "kg/m2": "kg/m2", "kg/m²": "kg/m2",
    "mm/sa": "mm/sa", "mm/h": "mm/sa", "mm/hr": "mm/sa", "sn": "sn", "s": "sn", "mg/gün": "mg/gün", "mg/gun": "mg/gün",
    "mg/24h": "mg/gün", "mmhg": "mmHg", "bpm": "atim/dk", "atim/dk": "atim/dk", "atım/dk": "atim/dk",
}

_BIRIM_CARPAN = {
    ("g/L", "g/dL"): 0.1, ("g/dL", "g/L"): 10.0,
    ("/uL", "10^9/L"): 0.001, ("10^9/L", "/uL"): 1000.0,
    ("umol/L", "mg/dL"): 1 / 88.42, ("mg/dL", "umol/L"): 88.42,   # kreatinin icin
    ("mL/min", "mL/min/1.73m2"): 1.0,                               # kaba yaklasim; TODO(mert): vucut yuzey alani duzeltmesi
    ("mmol/L", "mg/dL"): 18.0, ("mg/dL", "mmol/L"): 1 / 18.0,       # glukoz icin; diger analitlerde gecerli degil
}


def birim_normalize(birim: str | None) -> str:
    if not birim:
        return ""
    b = birim.strip().translate(_TR_KUCUK).lower()
    b = b.replace(" ", "") if "/" in b and "1.73" not in b else b
    return _BIRIM_ESANLAM.get(b, _BIRIM_ESANLAM.get(b.replace(" ", ""), birim.strip()))


def birim_cevir(deger: float, kaynak: str | None, hedef: str | None) -> float | None:
    """Degeri hedef birime cevirir; cevrilemiyorsa None."""
    k, h = birim_normalize(kaynak), birim_normalize(hedef)
    if not k or not h or k == h:
        return deger
    carpan = _BIRIM_CARPAN.get((k, h))
    if carpan is None:
        return None
    return deger * carpan


# ---------------------------------------------------------------------------
# Cesitli
# ---------------------------------------------------------------------------

KADIN_TERIMLERI = ["kadın", "kadin", "kadınlar", "female", "women", "woman", "bayan"]
ERKEK_TERIMLERI = ["erkek", "erkekler", "male", "men", "man"]

GEBELIK_TERIMLERI = ["gebe", "gebelik", "hamile", "emziren", "emzirme", "laktasyon", "pregnan", "lactating",
                     "breastfeeding", "breast-feeding", "nursing"]

# "son 6 ay icinde", "within the last 6 months", "gecmis 12 hafta" vb.
ZAMAN_KALIPLARI = [
    r"son\s+(\d+)\s*(gun|gün|hafta|ay|yil|yıl)",
    r"(\d+)\s*(gun|gün|hafta|ay|yil|yıl)\s+(icinde|içinde|icerisinde|içerisinde)",
    r"(?:within|in)\s+(?:the\s+)?(?:last|past|previous)?\s*(\d+)\s*(day|week|month|year)s?",
    r"(\d+)\s*(day|week|month|year)s?\s+(?:prior|before)",
    r"gecmis\s+(\d+)\s*(gun|gün|hafta|ay|yil|yıl)",
    r"geçmiş\s+(\d+)\s*(gun|gün|hafta|ay|yil|yıl)",
]
_ZAMAN_GUN = {"gun": 1, "gün": 1, "day": 1, "hafta": 7, "week": 7, "ay": 30, "month": 30, "yil": 365, "yıl": 365, "year": 365}


def zaman_penceresi_gun(metin: str) -> int | None:
    m = normalize(metin)
    for k in ZAMAN_KALIPLARI:
        e = re.search(k, m)
        if e:
            return int(e.group(1)) * _ZAMAN_GUN.get(e.group(2), 30)
    return None


# Yas, lab vb. sayilarda Turkce virgul: "1,5" -> 1.5
def sayi(s: str) -> float:
    return float(s.replace(",", "."))
