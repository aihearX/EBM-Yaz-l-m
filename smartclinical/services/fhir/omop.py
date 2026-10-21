"""OMOP CDM v5.4 disa aktarim.

Merkez zekasi ve BDM egitim veri setleri icin ortak veri modeli ciktisi. Sadece kimliksizlestirilmis
Hasta kayitlari girdi olarak kabul edilir (zaten baska turu sistemde yok).

Vocabulary eslemesi: tam Athena sozlugunu tasimiyoruz; sik kodlar icin kucuk bir tablo var,
bilinmeyenler concept_id=0 ve *_source_value ile cikar. ETL sonrasi Athena ile yeniden eslenir.
"""

import csv
from datetime import date
from pathlib import Path

# ICD-10 -> SNOMED standart concept_id (OHDSI Athena)
ICD10_CONCEPT = {
    "C50.9": 4112853,  # Malignant neoplasm of breast
    "C34.1": 4157454,  # Malignant neoplasm of upper lobe, bronchus or lung
    "C34.9": 4115276,
    "C18.9": 443381,   # Malignant neoplasm of colon
    "C61": 4163261,    # Malignant neoplasm of prostate
    "E11.9": 201826,   # Type 2 diabetes mellitus
    "I10": 320128,     # Essential hypertension
    "I50.9": 316139,   # Heart failure
    "N18.3": 443601,   # CKD stage 3
    "J44.9": 255573,   # COPD
    "M06.9": 80809,    # Rheumatoid arthritis
    "G35": 374919,     # Multiple sclerosis
}
ATC_CONCEPT = {
    "A10BA02": 1503297,  # metformin
    "L02BA01": 1436678,  # tamoxifen
    "C10AA05": 1545958,  # atorvastatin
    "C09AA05": 1334456,  # ramipril
    "L01XC17": 1594034,  # nivolumab (placeholder, Athena'dan dogrulanacak)
    "C07AB02": 1307046,  # metoprolol
    "C03CA01": 956874,   # furosemide
}
LOINC_CONCEPT = {
    "718-7": 3000963,    # hemoglobin
    "2160-0": 3016723,   # creatinine
    "1742-6": 3006923,   # ALT
    "4548-4": 3004410,   # HbA1c
    "2345-7": 3004501,   # glucose
    "33762-6": 3029187,  # NT-proBNP
    "8480-6": 3004249,   # systolic BP
    "8462-4": 3012888,   # diastolic BP
    "8867-4": 3027018,   # heart rate
    "29463-7": 3025315,  # body weight
    "39156-5": 3038553,  # BMI
}
GENDER_CONCEPT = {"K": 8532, "E": 8507}
NOT_TIPI_CONCEPT = {"epikriz": 44814637, "patoloji": 44814638, "radyoloji": 44814639}


def _tarih(s: str | None) -> str:
    return (s or "")[:10]


def omop_disa_aktar(hastalar: list, dizin: Path) -> dict[str, int]:
    """Hasta listesini OMOP CDM tablolarina (CSV) yazar. Donus: tablo -> satir sayisi."""
    dizin = Path(dizin)
    dizin.mkdir(parents=True, exist_ok=True)
    sayac = {"person": 0, "condition_occurrence": 0, "drug_exposure": 0, "measurement": 0, "note": 0}

    person_f = open(dizin / "person.csv", "w", newline="", encoding="utf-8")
    cond_f = open(dizin / "condition_occurrence.csv", "w", newline="", encoding="utf-8")
    drug_f = open(dizin / "drug_exposure.csv", "w", newline="", encoding="utf-8")
    meas_f = open(dizin / "measurement.csv", "w", newline="", encoding="utf-8")
    note_f = open(dizin / "note.csv", "w", newline="", encoding="utf-8")
    try:
        person = csv.writer(person_f)
        person.writerow(["person_id", "gender_concept_id", "year_of_birth", "race_concept_id",
                         "ethnicity_concept_id", "care_site_id", "person_source_value", "gender_source_value"])
        cond = csv.writer(cond_f)
        cond.writerow(["condition_occurrence_id", "person_id", "condition_concept_id", "condition_start_date",
                       "condition_end_date", "condition_type_concept_id", "condition_source_value"])
        drug = csv.writer(drug_f)
        drug.writerow(["drug_exposure_id", "person_id", "drug_concept_id", "drug_exposure_start_date",
                       "drug_exposure_end_date", "drug_type_concept_id", "sig", "drug_source_value"])
        meas = csv.writer(meas_f)
        meas.writerow(["measurement_id", "person_id", "measurement_concept_id", "measurement_date",
                       "measurement_type_concept_id", "value_as_number", "unit_source_value",
                       "measurement_source_value"])
        note = csv.writer(note_f)
        note.writerow(["note_id", "person_id", "note_date", "note_type_concept_id", "note_class_concept_id",
                       "note_title", "note_text", "encoding_concept_id", "language_concept_id"])

        c_id = d_id = m_id = n_id = 0
        for h in hastalar:
            pid = h.id or sayac["person"] + 1
            person.writerow([pid, GENDER_CONCEPT.get(h.cinsiyet, 0), h.dogum_yili or "", 0, 0,
                             h.merkez_id, h.kayit_no, h.cinsiyet or ""])
            sayac["person"] += 1
            for t in h.tanilar or []:
                c_id += 1
                cond.writerow([c_id, pid, ICD10_CONCEPT.get(t.get("icd10"), 0), _tarih(t.get("tarih")), "",
                               32817, t.get("icd10") or t.get("ad") or ""])  # 32817 = EHR
                sayac["condition_occurrence"] += 1
            for il in h.ilaclar or []:
                d_id += 1
                drug.writerow([d_id, pid, ATC_CONCEPT.get(il.get("atc"), 0), _tarih(il.get("baslangic")), "",
                               32817, il.get("doz") or "", il.get("atc") or il.get("ad") or ""])
                sayac["drug_exposure"] += 1
            for lab in h.laboratuvar or []:
                m_id += 1
                meas.writerow([m_id, pid, LOINC_CONCEPT.get(lab.get("loinc"), 0), _tarih(lab.get("tarih")),
                               32817, lab.get("deger") if isinstance(lab.get("deger"), (int, float)) else "",
                               lab.get("birim") or "", lab.get("loinc") or lab.get("ad") or ""])
                sayac["measurement"] += 1
            ters = {"sistolik_kb": "8480-6", "diyastolik_kb": "8462-4", "nabiz": "8867-4", "kilo": "29463-7",
                    "vki": "39156-5"}
            v = h.vitaller or {}
            for ad, loinc in ters.items():
                if ad in v and v[ad] is not None:
                    m_id += 1
                    meas.writerow([m_id, pid, LOINC_CONCEPT.get(loinc, 0), _tarih(v.get("tarih")), 32817,
                                   v[ad], "", loinc])
                    sayac["measurement"] += 1
            for m in h.metinler or []:
                n_id += 1
                note.writerow([n_id, pid, _tarih(m.get("tarih")), 32817,
                               NOT_TIPI_CONCEPT.get(m.get("tur"), 0), m.get("tur") or "",
                               m.get("metin") or "", 32678, 4182504])  # UTF-8, Turkish
                sayac["note"] += 1
    finally:
        for f in (person_f, cond_f, drug_f, meas_f, note_f):
            f.close()

    (dizin / "_etl_bilgi.txt").write_text(
        f"OMOP CDM v5.4 disa aktarim - {date.today().isoformat()}\n"
        + "\n".join(f"{k}: {v}" for k, v in sayac.items()) + "\n", encoding="utf-8")
    return sayac


__all__ = ["omop_disa_aktar", "ICD10_CONCEPT", "ATC_CONCEPT", "LOINC_CONCEPT"]
