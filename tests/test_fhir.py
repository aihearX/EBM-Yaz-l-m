import base64
import csv
from types import SimpleNamespace

import pytest

from smartclinical.services.fhir import (
    FHIRHatasi,
    bundle_to_hasta,
    calisma_to_research_study,
    gonullu_to_research_subject,
    hasta_to_fhir,
    takma_kayit_no,
)
from smartclinical.services.fhir.hbys import MockHBYS, adaptor_olustur
from smartclinical.services.fhir.omop import omop_disa_aktar


def _b64(s):
    return base64.b64encode(s.encode("utf-8")).decode()


@pytest.fixture
def bundle():
    return {
        "resourceType": "Bundle", "type": "searchset",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "123",
                          "identifier": [{"system": "urn:hbys", "value": "HBYS-123"}],
                          "name": [{"family": "Yılmaz", "given": ["Ayşe"]}],
                          "telecom": [{"system": "phone", "value": "05321234567"}],
                          "address": [{"city": "İstanbul"}],
                          "birthDate": "1961-04-12", "gender": "female"}},
            {"resource": {"resourceType": "Condition", "subject": {"reference": "Patient/123"},
                          "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "C50.9",
                                               "display": "Meme malign neoplazmı"}]},
                          "clinicalStatus": {"coding": [{"code": "active"}]},
                          "onsetDateTime": "2025-11-03T10:00:00Z"}},
            {"resource": {"resourceType": "MedicationRequest", "status": "active", "authoredOn": "2025-12-01",
                          "subject": {"reference": "Patient/123"},
                          "medicationCodeableConcept": {"coding": [{"system": "http://www.whocc.no/atc",
                                                                    "code": "L02BA01", "display": "Tamoksifen"}]},
                          "dosageInstruction": [{"text": "20 mg 1x1"}]}},
            {"resource": {"resourceType": "Observation", "status": "final", "subject": {"reference": "Patient/123"},
                          "code": {"coding": [{"system": "http://loinc.org", "code": "718-7", "display": "Hemoglobin"}]},
                          "effectiveDateTime": "2026-09-15", "valueQuantity": {"value": 12.1, "unit": "g/dL"}}},
            {"resource": {"resourceType": "Observation", "status": "final", "subject": {"reference": "Patient/123"},
                          "category": [{"coding": [{"code": "vital-signs"}]}],
                          "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9"}]},
                          "effectiveDateTime": "2026-09-15",
                          "component": [
                              {"code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                               "valueQuantity": {"value": 128}},
                              {"code": {"coding": [{"system": "http://loinc.org", "code": "8462-4"}]},
                               "valueQuantity": {"value": 78}}]}},
            {"resource": {"resourceType": "Observation", "status": "final", "subject": {"reference": "Patient/123"},
                          "code": {"coding": [{"system": "http://loinc.org", "code": "89247-1"}]}, "valueInteger": 1}},
            {"resource": {"resourceType": "DocumentReference", "status": "current", "date": "2026-09-20",
                          "type": {"coding": [{"system": "http://loinc.org", "code": "18842-5", "display": "Epikriz"}]},
                          "subject": {"reference": "Patient/123"},
                          "content": [{"attachment": {"contentType": "text/plain",
                                                      "data": _b64("Hasta Ayşe Yılmaz, sol meme Ca, ER pozitif. "
                                                                   "Tel 0532 123 45 67.")}}]}},
            {"resource": {"resourceType": "DiagnosticReport", "status": "final", "issued": "2026-09-21",
                          "code": {"coding": [{"system": "http://loinc.org", "code": "11526-1", "display": "Patoloji"}]},
                          "subject": {"reference": "Patient/123"},
                          "conclusion": "İnvaziv duktal karsinom, grade 2."}},
        ],
    }


def test_bundle_to_hasta(bundle):
    h = bundle_to_hasta(bundle, merkez_id=3)
    assert h["kayit_no"].startswith("P-") and "123" not in h["kayit_no"]
    assert h["dogum_yili"] == 1961 and h["cinsiyet"] == "K" and h["kaynak"] == "hbys-fhir"
    assert h["tanilar"][0]["icd10"] == "C50.9" and h["tanilar"][0]["tarih"] == "2025-11-03"
    assert h["ilaclar"][0]["atc"] == "L02BA01" and h["ilaclar"][0]["doz"] == "20 mg 1x1"
    assert h["laboratuvar"][0]["loinc"] == "718-7" and h["laboratuvar"][0]["deger"] == 12.1
    assert h["vitaller"]["sistolik_kb"] == 128 and h["vitaller"]["diyastolik_kb"] == 78
    assert h["performans"]["ecog"] == 1
    assert len(h["metinler"]) == 2
    turler = {m["tur"] for m in h["metinler"]}
    assert turler == {"epikriz", "patoloji"}


def test_kimlik_alanlari_asla_tasinmaz(bundle):
    h = bundle_to_hasta(bundle, merkez_id=3)
    duz = str(h)
    assert "Yılmaz" not in duz and "Ayşe" not in duz and "05321234567" not in duz and "İstanbul" not in duz
    assert "0532" not in duz  # serbest metindeki telefon da kimliksizlestirildi
    assert "[AD]" in h["metinler"][0]["metin"]


def test_takma_kayit_no_deterministik_ve_merkeze_bagli():
    a = takma_kayit_no([{"system": "x", "value": "1"}], None, 1)
    assert a == takma_kayit_no([{"system": "x", "value": "1"}], None, 1)
    assert a != takma_kayit_no([{"system": "x", "value": "1"}], None, 2)
    assert a != takma_kayit_no([{"system": "x", "value": "2"}], None, 1)


def test_patient_yoksa_hata():
    with pytest.raises(FHIRHatasi):
        bundle_to_hasta({"resourceType": "Bundle", "entry": []}, 1)
    with pytest.raises(FHIRHatasi):
        bundle_to_hasta({"resourceType": "Patient"}, 1)


def _hasta_nesnesi(bundle):
    h = bundle_to_hasta(bundle, merkez_id=3)
    h["id"] = 7
    return SimpleNamespace(**h)


def test_hasta_to_fhir_gidis_donus(bundle):
    h = _hasta_nesnesi(bundle)
    b = hasta_to_fhir(h)
    assert b["resourceType"] == "Bundle"
    tipler = [e["resource"]["resourceType"] for e in b["entry"]]
    assert tipler[0] == "Patient"
    assert tipler.count("Condition") == 1 and tipler.count("MedicationStatement") == 1
    assert tipler.count("Observation") == 3  # 1 lab + 2 vital
    assert tipler.count("DocumentReference") == 2
    assert "name" not in b["entry"][0]["resource"]
    geri = bundle_to_hasta(b, merkez_id=3)
    assert geri["tanilar"][0]["icd10"] == "C50.9"
    assert geri["vitaller"]["sistolik_kb"] == 128


def test_research_study_ve_subject():
    calisma = SimpleNamespace(kod="EBM-ONK-024", baslik="Faz III meme", faz="III", durum=SimpleNamespace(value="kayit"),
                              tur=SimpleNamespace(value="ilac"), endikasyon="Meme kanseri", sponsor="X İlaç",
                              baslangic=None, planlanan_bitis=None, kollar=[SimpleNamespace(ad="A", aciklama="")],
                              hedef_hasta=120, ct_gov_no="NCT01234567", eudract_no=None)
    rs = calisma_to_research_study(calisma)
    assert rs["status"] == "active" and rs["phase"]["coding"][0]["code"] == "phase-3"
    assert any(i["value"] == "NCT01234567" for i in rs["identifier"])

    gonullu = SimpleNamespace(calisma_id=1, gonullu_no="01-003", durum=SimpleNamespace(value="randomize"),
                              calisma=calisma, hasta=SimpleNamespace(kayit_no="P-ABC"), onam_tarihi="2026-01-05",
                              onam_versiyonu="2.0", bitis_tarihi=None, kol=SimpleNamespace(ad="A"))
    rsub = gonullu_to_research_subject(gonullu)
    assert rsub["status"] == "on-study" and rsub["individual"]["reference"] == "Patient/P-ABC"
    assert rsub["actualArm"] == "A"


def test_mock_hbys():
    a = adaptor_olustur("")
    assert isinstance(a, MockHBYS)
    hastalar = a.hastalari_cek(["C50.9"], merkez_id=1)
    assert 3 <= len(hastalar) <= 4
    for h in hastalar:
        assert "GİZLİ" not in str(h)
        assert h["kayit_no"].startswith("P-")
    assert a.hasta_kimlikleri(["C50.9"])


def test_omop_disa_aktar(bundle, tmp_path):
    h = _hasta_nesnesi(bundle)
    sayac = omop_disa_aktar([h], tmp_path)
    assert sayac["person"] == 1 and sayac["condition_occurrence"] == 1 and sayac["note"] == 2
    assert sayac["measurement"] == 3
    with open(tmp_path / "condition_occurrence.csv", encoding="utf-8") as f:
        satirlar = list(csv.DictReader(f))
    assert satirlar[0]["condition_concept_id"] == "4112853"
    assert satirlar[0]["condition_source_value"] == "C50.9"
    with open(tmp_path / "person.csv", encoding="utf-8") as f:
        p = list(csv.DictReader(f))[0]
    assert p["gender_concept_id"] == "8532" and p["year_of_birth"] == "1961"
    assert (tmp_path / "_etl_bilgi.txt").exists()
