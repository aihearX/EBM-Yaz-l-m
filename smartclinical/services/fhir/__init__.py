"""HL7 FHIR R4 eslemeleri.

HBYS'den gelen Bundle -> Hasta (kimliksizlestirilmis) ve tersi. Kimlik tasiyan alanlar
(Patient.name, address, telecom, identifier, photo, contact) hicbir kosulda icerige alinmaz;
kayit_no identifier degerinin HMAC-SHA256 ozetinden turetilir (anahtar: SC_TAKMA_AD_ANAHTARI) ve
merkezdeki anahtar listesi disinda geri cozulemez. Anahtar degisirse scripts/yeniden_anahtarla.py
mevcut kayitlari eski->yeni eslemeyle gunceller.

Desteklenen kaynaklar: Patient, Condition, MedicationStatement, MedicationRequest, Observation,
DocumentReference, DiagnosticReport, ResearchStudy, ResearchSubject.
"""

import base64
import hashlib
import hmac
import os

from ...config import ayarlar
from ...models._ortak import simdi
from ..kimliksizlestirme import kimliksizlestir

ICD10_SISTEM = ("http://hl7.org/fhir/sid/icd-10", "icd-10", "icd10")
ATC_SISTEM = ("http://www.whocc.no/atc", "atc")
LOINC_SISTEM = ("http://loinc.org", "loinc")

# vital-signs profili LOINC kodlari -> vitaller sozlugu anahtari
VITAL_KODLARI = {
    "8480-6": "sistolik_kb", "8462-4": "diyastolik_kb", "8867-4": "nabiz", "8310-5": "ates",
    "9279-1": "solunum", "2708-6": "spo2", "59408-5": "spo2", "29463-7": "kilo", "8302-2": "boy",
    "39156-5": "vki", "85354-9": "kan_basinci",
}

# performans skorlari (ECOG / Karnofsky / NYHA) - Observation olarak gelir
PERFORMANS_KODLARI = {"89247-1": "ecog", "89243-0": "karnofsky", "89244-8": "nyha"}


class FHIRHatasi(Exception):
    pass


def _kod(cc: dict | None, sistemler: tuple[str, ...]) -> tuple[str | None, str | None]:
    """CodeableConcept icinden istenen sistemdeki (kod, gosterim) ciftini alir. Yoksa ilk kodu dondurur."""
    if not cc:
        return None, None
    kodlar = cc.get("coding") or []
    for k in kodlar:
        sistem = (k.get("system") or "").lower()
        if any(s in sistem for s in sistemler):
            return k.get("code"), k.get("display") or cc.get("text")
    if kodlar:
        return kodlar[0].get("code"), kodlar[0].get("display") or cc.get("text")
    return None, cc.get("text")


def _tarih(deger: str | None) -> str | None:
    if not deger:
        return None
    return deger[:10]  # dateTime -> YYYY-MM-DD; saat bilgisini tutmuyoruz


def takma_anahtari() -> bytes:
    """HMAC anahtari. Uretimde SC_TAKMA_AD_ANAHTARI zorunlu; gelistirmede secret_key'den turetilir."""
    # TODO(entegrasyon): config.py'ye takma_ad_anahtari alani eklenince env dali yalnizca yedek kalir
    a = ayarlar()
    anahtar = getattr(a, "takma_ad_anahtari", None) or os.environ.get("SC_TAKMA_AD_ANAHTARI", "")
    if anahtar:
        return anahtar.encode("utf-8")
    if a.uretim:
        raise RuntimeError("Uretim ortaminda SC_TAKMA_AD_ANAHTARI tanimlanmali")
    return hashlib.sha256(f"takma-ad:{a.secret_key}".encode("utf-8")).digest()


def takma_kayit_no(identifier: list | None, kaynak_id: str | None, merkez_id: int,
                   anahtar: bytes | str | None = None) -> str:
    """Patient.identifier (veya id) -> geri cozulemez, anahtara bagli takma ad (HMAC-SHA256)."""
    ham = ""
    for i in identifier or []:
        if i.get("value"):
            ham = f"{i.get('system', '')}|{i['value']}"
            break
    ham = ham or f"id|{kaynak_id or ''}"
    if anahtar is None:
        anahtar = takma_anahtari()
    elif isinstance(anahtar, str):
        anahtar = anahtar.encode("utf-8")
    ozet = hmac.new(anahtar, f"m{merkez_id}:{ham}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"P-{ozet[:12].upper()}"


def _kaynaklar(bundle: dict) -> list[dict]:
    if bundle.get("resourceType") != "Bundle":
        raise FHIRHatasi("Beklenen kaynak tipi Bundle, gelen: %s" % bundle.get("resourceType"))
    return [g.get("resource") for g in bundle.get("entry", []) if g.get("resource")]


def _metin_icerigi(kaynak: dict) -> str | None:
    # DocumentReference.content[].attachment.data (base64) veya DiagnosticReport.presentedForm / conclusion
    for c in kaynak.get("content", []):
        att = c.get("attachment", {})
        if att.get("data"):
            try:
                return base64.b64decode(att["data"]).decode("utf-8", errors="replace")
            except Exception:
                continue
    for pf in kaynak.get("presentedForm", []):
        if pf.get("data"):
            try:
                return base64.b64decode(pf["data"]).decode("utf-8", errors="replace")
            except Exception:
                continue
    if kaynak.get("conclusion"):
        return kaynak["conclusion"]
    div = (kaynak.get("text") or {}).get("div")
    if div:
        import re
        return re.sub(r"<[^>]+>", " ", div).strip()
    return None


def _metin_turu(kaynak: dict) -> str:
    kod, gosterim = _kod(kaynak.get("type") or kaynak.get("code"), LOINC_SISTEM)
    g = (gosterim or "").lower()
    if "patolo" in g or kod == "11526-1":
        return "patoloji"
    if "radyo" in g or kod in ("18748-4", "18782-3"):
        return "radyoloji"
    if "epikriz" in g or "discharge" in g or kod == "18842-5":
        return "epikriz"
    return gosterim or "klinik_not"


def bundle_to_hasta(bundle: dict, merkez_id: int) -> dict:
    """FHIR Bundle -> Hasta modeli kwargs. Serbest metinler kimliksizlestirilerek alinir."""
    hasta: dict = {
        "merkez_id": merkez_id, "kayit_no": None, "dogum_yili": None, "cinsiyet": None,
        "tanilar": [], "ilaclar": [], "laboratuvar": [], "vitaller": {}, "performans": {},
        "metinler": [], "kaynak": "hbys-fhir", "son_senkron": simdi(),
    }
    patient_bulundu = False
    for k in _kaynaklar(bundle):
        rt = k.get("resourceType")
        if rt == "Patient":
            patient_bulundu = True
            hasta["kayit_no"] = takma_kayit_no(k.get("identifier"), k.get("id"), merkez_id)
            dt = k.get("birthDate")
            hasta["dogum_yili"] = int(dt[:4]) if dt else None
            hasta["cinsiyet"] = {"female": "K", "male": "E"}.get(k.get("gender"))
            # NOT: name/address/telecom bilincli olarak okunmuyor
        elif rt == "Condition":
            kod, ad = _kod(k.get("code"), ICD10_SISTEM)
            durum, _ = _kod(k.get("clinicalStatus"), ())
            hasta["tanilar"].append({
                "icd10": kod, "ad": ad,
                "tarih": _tarih(k.get("onsetDateTime") or k.get("recordedDate")),
                "aktif": durum in (None, "active", "recurrence", "relapse"),
            })
        elif rt in ("MedicationStatement", "MedicationRequest"):
            kod, ad = _kod(k.get("medicationCodeableConcept"), ATC_SISTEM)
            if not ad and k.get("medicationReference"):
                ad = k["medicationReference"].get("display")
            durum = k.get("status")
            doz = None
            dz = k.get("dosage") or k.get("dosageInstruction") or []
            if dz and dz[0].get("text"):
                doz = dz[0]["text"]
            hasta["ilaclar"].append({
                "atc": kod, "ad": ad, "doz": doz,
                "aktif": durum in ("active", "intended", "on-hold", None),
                "baslangic": _tarih((k.get("effectivePeriod") or {}).get("start") or k.get("authoredOn")),
            })
        elif rt == "Observation":
            kod, ad = _kod(k.get("code"), LOINC_SISTEM)
            deger = None
            birim = None
            if "valueQuantity" in k:
                deger = k["valueQuantity"].get("value")
                birim = k["valueQuantity"].get("unit") or k["valueQuantity"].get("code")
            elif "valueCodeableConcept" in k:
                deger, _ = _kod(k["valueCodeableConcept"], ())
            elif "valueString" in k:
                deger = k["valueString"]
            elif "valueInteger" in k:
                deger = k["valueInteger"]
            tarih = _tarih(k.get("effectiveDateTime") or k.get("issued"))
            kategori = ""
            for c in k.get("category", []):
                ck, _ = _kod(c, ())
                kategori = ck or kategori
            if kod in VITAL_KODLARI or kategori == "vital-signs":
                if kod == "85354-9" and k.get("component"):
                    for comp in k["component"]:
                        ck, _ = _kod(comp.get("code"), LOINC_SISTEM)
                        if ck in VITAL_KODLARI and "valueQuantity" in comp:
                            hasta["vitaller"][VITAL_KODLARI[ck]] = comp["valueQuantity"].get("value")
                else:
                    hasta["vitaller"][VITAL_KODLARI.get(kod, kod)] = deger
                hasta["vitaller"].setdefault("tarih", tarih)
            elif kod in PERFORMANS_KODLARI:
                hasta["performans"][PERFORMANS_KODLARI[kod]] = deger
            else:
                hasta["laboratuvar"].append({"loinc": kod, "ad": ad, "deger": deger, "birim": birim, "tarih": tarih})
        elif rt in ("DocumentReference", "DiagnosticReport"):
            metin = _metin_icerigi(k)
            if metin:
                hasta["metinler"].append({
                    "tur": _metin_turu(k),
                    "tarih": _tarih(k.get("date") or k.get("effectiveDateTime") or k.get("issued")),
                    "metin": kimliksizlestir(metin).metin,
                })
    if not patient_bulundu:
        raise FHIRHatasi("Bundle icinde Patient kaynagi yok")
    return hasta


# ----------------------------------------------------------------------------- disari: Hasta -> FHIR

def _cc(sistem: str, kod: str | None, gosterim: str | None) -> dict:
    cc: dict = {}
    if kod:
        cc["coding"] = [{"system": sistem, "code": kod, "display": gosterim}]
    if gosterim:
        cc["text"] = gosterim
    return cc


def hasta_to_fhir(hasta) -> dict:
    """Hasta -> FHIR Bundle (collection). Kimlik tasimaz; Patient.identifier takma addir."""
    pid = f"Patient/{hasta.kayit_no}"
    girdiler = [{
        "resource": {
            "resourceType": "Patient", "id": hasta.kayit_no,
            "identifier": [{"system": "urn:ebm:smartclinical:takma-ad", "value": hasta.kayit_no}],
            "gender": {"K": "female", "E": "male"}.get(hasta.cinsiyet, "unknown"),
            "birthDate": str(hasta.dogum_yili) if hasta.dogum_yili else None,
            "managingOrganization": {"reference": f"Organization/merkez-{hasta.merkez_id}"},
        }
    }]
    for i, t in enumerate(hasta.tanilar or []):
        girdiler.append({"resource": {
            "resourceType": "Condition", "id": f"{hasta.kayit_no}-c{i}", "subject": {"reference": pid},
            "code": _cc(ICD10_SISTEM[0], t.get("icd10"), t.get("ad")),
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                           "code": "active" if t.get("aktif", True) else "inactive"}]},
            "onsetDateTime": t.get("tarih"),
        }})
    for i, il in enumerate(hasta.ilaclar or []):
        girdiler.append({"resource": {
            "resourceType": "MedicationStatement", "id": f"{hasta.kayit_no}-m{i}", "subject": {"reference": pid},
            "status": "active" if il.get("aktif", True) else "completed",
            "medicationCodeableConcept": _cc(ATC_SISTEM[0], il.get("atc"), il.get("ad")),
            "dosage": [{"text": il["doz"]}] if il.get("doz") else [],
        }})
    for i, lab in enumerate(hasta.laboratuvar or []):
        girdiler.append({"resource": {
            "resourceType": "Observation", "id": f"{hasta.kayit_no}-o{i}", "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                      "code": "laboratory"}]}],
            "subject": {"reference": pid}, "code": _cc(LOINC_SISTEM[0], lab.get("loinc"), lab.get("ad")),
            "effectiveDateTime": lab.get("tarih"),
            "valueQuantity": {"value": lab.get("deger"), "unit": lab.get("birim")},
        }})
    ters_vital = {v: k for k, v in VITAL_KODLARI.items()}
    for ad, deger in (hasta.vitaller or {}).items():
        if ad == "tarih" or ad not in ters_vital:
            continue
        girdiler.append({"resource": {
            "resourceType": "Observation", "id": f"{hasta.kayit_no}-v{ad}", "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                      "code": "vital-signs"}]}],
            "subject": {"reference": pid}, "code": _cc(LOINC_SISTEM[0], ters_vital[ad], ad),
            "effectiveDateTime": (hasta.vitaller or {}).get("tarih"),
            "valueQuantity": {"value": deger},
        }})
    for i, m in enumerate(hasta.metinler or []):
        girdiler.append({"resource": {
            "resourceType": "DocumentReference", "id": f"{hasta.kayit_no}-d{i}", "status": "current",
            "subject": {"reference": pid}, "date": m.get("tarih"),
            "type": {"text": m.get("tur")},
            "content": [{"attachment": {"contentType": "text/plain",
                                        "data": base64.b64encode((m.get("metin") or "").encode("utf-8")).decode()}}],
        }})
    return {"resourceType": "Bundle", "type": "collection", "entry": girdiler}


def calisma_to_research_study(calisma) -> dict:
    faz_kodu = {"I": "phase-1", "II": "phase-2", "III": "phase-3", "IV": "phase-4", "I/II": "phase-1-phase-2",
                "II/III": "phase-2-phase-3"}.get(calisma.faz or "", "n-a")
    durum_kodu = {
        "tasarim": "in-review", "fizibilite": "in-review", "basvuru": "in-review", "aktivasyon": "approved",
        "kayit": "active", "izlem": "active", "kapanis": "closed-to-accrual-and-intervention",
        "analiz": "completed", "arsiv": "completed",
    }.get(calisma.durum.value, "active")
    rs = {
        "resourceType": "ResearchStudy", "id": calisma.kod,
        "identifier": [{"system": "urn:ebm:smartclinical:calisma", "value": calisma.kod}],
        "title": calisma.baslik, "status": durum_kodu,
        "phase": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/research-study-phase", "code": faz_kodu}]},
        "category": [{"text": calisma.tur.value}],
        "condition": [{"text": calisma.endikasyon}] if calisma.endikasyon else [],
        "sponsor": {"display": calisma.sponsor},
        "period": {"start": str(calisma.baslangic) if calisma.baslangic else None,
                   "end": str(calisma.planlanan_bitis) if calisma.planlanan_bitis else None},
        "arm": [{"name": k.ad, "description": k.aciklama} for k in (calisma.kollar or [])],
        "enrollment": [{"display": f"hedef {calisma.hedef_hasta} gonullu"}],
    }
    if calisma.ct_gov_no:
        rs["identifier"].append({"system": "https://clinicaltrials.gov", "value": calisma.ct_gov_no})
    if calisma.eudract_no:
        rs["identifier"].append({"system": "https://eudract.ema.europa.eu", "value": calisma.eudract_no})
    return rs


def gonullu_to_research_subject(gonullu) -> dict:
    durum_kodu = {
        "aday": "candidate", "on_tarama": "screening", "onam": "eligible", "tarama": "screening",
        "tarama_basarisiz": "ineligible", "randomize": "on-study", "tedavide": "on-study-intervention",
        "takipte": "on-study-observation", "tamamladi": "off-study", "ayrildi": "withdrawn",
    }.get(gonullu.durum.value, "candidate")
    rs = {
        "resourceType": "ResearchSubject", "id": f"{gonullu.calisma_id}-{gonullu.gonullu_no}",
        "identifier": [{"system": "urn:ebm:smartclinical:gonullu", "value": gonullu.gonullu_no}],
        "status": durum_kodu,
        "study": {"reference": f"ResearchStudy/{gonullu.calisma.kod if gonullu.calisma else gonullu.calisma_id}"},
        "individual": {"reference": f"Patient/{gonullu.hasta.kayit_no}"} if gonullu.hasta else None,
        "period": {"start": str(gonullu.onam_tarihi) if gonullu.onam_tarihi else None,
                   "end": str(gonullu.bitis_tarihi) if gonullu.bitis_tarihi else None},
    }
    if gonullu.kol:
        rs["actualArm"] = gonullu.kol.ad
    if gonullu.onam_tarihi:
        rs["consent"] = {"display": f"ICF v{gonullu.onam_versiyonu or '?'} {gonullu.onam_tarihi}"}
    return rs


__all__ = ["bundle_to_hasta", "hasta_to_fhir", "calisma_to_research_study", "gonullu_to_research_subject",
           "takma_kayit_no", "takma_anahtari", "FHIRHatasi"]
