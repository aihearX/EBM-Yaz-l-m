"""HBYS FHIR adaptoru.

Merkezlerde HBYS saglayicilarinin FHIR R4 arayuzu uzerinden Patient + Condition +
MedicationStatement + Observation + DocumentReference cekiyoruz. Her saglayicinin arama
parametreleri biraz farkli; simdilik _has:Condition sorgusu + Patient/$everything ile gidiyoruz.
Sorgu desteklenmezse Condition uzerinden hasta listesi toplanip tek tek $everything cagriliyor.

Veri hastane agi disina cikmaz: adaptor hastane icindeki uygulama sunucusunda calisir.
"""

import base64
from datetime import date, timedelta

import httpx

from . import FHIRHatasi, bundle_to_hasta


class HBYSHatasi(FHIRHatasi):
    pass


class HBYSAdaptoru:
    def __init__(self, url: str, token: str = "", zaman_asimi: float = 30.0):
        self.url = url.rstrip("/")
        self.token = token
        self.zaman_asimi = zaman_asimi
        self._istemci = None

    def _baslik(self) -> dict:
        b = {"Accept": "application/fhir+json"}
        if self.token:
            b["Authorization"] = f"Bearer {self.token}"
        return b

    def _get(self, yol_veya_url: str, params: dict | None = None) -> dict:
        url = yol_veya_url if yol_veya_url.startswith("http") else f"{self.url}/{yol_veya_url.lstrip('/')}"
        try:
            with httpx.Client(timeout=self.zaman_asimi, headers=self._baslik()) as c:
                r = c.get(url, params=params)
        except httpx.TimeoutException as e:
            raise HBYSHatasi(f"HBYS FHIR sunucusu zaman asimina ugradi ({url})") from e
        except httpx.HTTPError as e:
            raise HBYSHatasi(f"HBYS FHIR sunucusuna baglanilamadi ({url}): {e}") from e
        if r.status_code == 401:
            raise HBYSHatasi("HBYS FHIR sunucusu kimlik dogrulamayi reddetti (401); token kontrol edilmeli")
        if r.status_code >= 400:
            raise HBYSHatasi(f"HBYS FHIR sunucusu hata dondurdu: {r.status_code} {r.text[:200]}")
        try:
            return r.json()
        except ValueError as e:
            raise HBYSHatasi("HBYS yaniti JSON degil") from e

    def _sayfalari_gez(self, ilk: dict, limit: int):
        bundle = ilk
        toplam = 0
        while bundle:
            for g in bundle.get("entry", []):
                yield g.get("resource")
                toplam += 1
                if toplam >= limit:
                    return
            sonraki = next((link["url"] for link in bundle.get("link", []) if link.get("relation") == "next"), None)
            bundle = self._get(sonraki) if sonraki else None

    def hasta_kimlikleri(self, tani_kodlari: list[str], son_ay: int = 12, limit: int = 200) -> list[str]:
        """Verilen ICD-10 kodlarindan biriyle son N ayda tanisi olan hastalarin FHIR id listesi."""
        baslangic = (date.today() - timedelta(days=30 * son_ay)).isoformat()
        kodlar = ",".join(f"http://hl7.org/fhir/sid/icd-10|{k}" for k in tani_kodlari)
        params = {"_has:Condition:patient:code": kodlar, "_has:Condition:patient:onset-date": f"ge{baslangic}",
                  "_count": "50", "_elements": "id"}
        try:
            ilk = self._get("Patient", params)
        except HBYSHatasi:
            # _has desteklenmiyor olabilir -> Condition uzerinden topla
            ilk = self._get("Condition", {"code": kodlar, "onset-date": f"ge{baslangic}", "_count": "50",
                                          "_elements": "subject"})
            idler: list[str] = []
            for c in self._sayfalari_gez(ilk, limit * 3):
                ref = ((c or {}).get("subject") or {}).get("reference", "")
                if ref.startswith("Patient/") and ref[8:] not in idler:
                    idler.append(ref[8:])
                if len(idler) >= limit:
                    break
            return idler
        return [p["id"] for p in self._sayfalari_gez(ilk, limit) if p and p.get("id")]

    def hasta_cek(self, fhir_id: str, merkez_id: int) -> dict:
        bundle = self._get(f"Patient/{fhir_id}/$everything", {"_count": "500"})
        return bundle_to_hasta(bundle, merkez_id)

    def hastalari_cek(self, tani_kodlari: list[str], son_ay: int = 12, limit: int = 200,
                      merkez_id: int = 0) -> list[dict]:
        hastalar = []
        for fid in self.hasta_kimlikleri(tani_kodlari, son_ay, limit):
            try:
                hastalar.append(self.hasta_cek(fid, merkez_id))
            except FHIRHatasi:
                # tek hasta hatasi tum senkronu durdurmasin; loglanacak
                # TODO(ayse): yapisal loglama eklenince buraya uyari dus
                continue
        return hastalar


class MockHBYS(HBYSAdaptoru):
    """FHIR uc noktasi olmayan ortamlar (gelistirme, demo) icin sentetik veri. Gercek hasta yok."""

    def __init__(self, *_, **__):
        super().__init__(url="mock://hbys")

    def hastalari_cek(self, tani_kodlari: list[str], son_ay: int = 12, limit: int = 200,
                      merkez_id: int = 0) -> list[dict]:
        return [bundle_to_hasta(b, merkez_id) for b in _ornek_bundlelar()][:limit]

    def hasta_kimlikleri(self, tani_kodlari, son_ay=12, limit=200):
        return [b["entry"][0]["resource"]["id"] for b in _ornek_bundlelar()][:limit]


def adaptor_olustur(url: str, token: str = "") -> HBYSAdaptoru:
    return HBYSAdaptoru(url, token) if url else MockHBYS()


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode()


def _ornek_bundlelar() -> list[dict]:
    def hasta(fid, yil, cins, tanilar, ilaclar, labs, vital, metin, ecog=None):
        entry = [{"resource": {"resourceType": "Patient", "id": fid,
                               "identifier": [{"system": "urn:hbys:protokol", "value": f"HBYS-{fid}"}],
                               "name": [{"family": "GİZLİ", "given": ["GİZLİ"]}],  # adaptor bunu okumamali
                               "birthDate": f"{yil}-01-01", "gender": cins}}]
        for kod, ad, tarih in tanilar:
            entry.append({"resource": {"resourceType": "Condition", "subject": {"reference": f"Patient/{fid}"},
                                       "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": kod,
                                                            "display": ad}]},
                                       "onsetDateTime": tarih}})
        for atc, ad in ilaclar:
            entry.append({"resource": {"resourceType": "MedicationStatement", "status": "active",
                                       "subject": {"reference": f"Patient/{fid}"},
                                       "medicationCodeableConcept": {"coding": [{"system": "http://www.whocc.no/atc",
                                                                                 "code": atc, "display": ad}]}}})
        for loinc, ad, deger, birim in labs:
            entry.append({"resource": {"resourceType": "Observation", "status": "final",
                                       "subject": {"reference": f"Patient/{fid}"},
                                       "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": ad}]},
                                       "effectiveDateTime": "2026-09-15", "valueQuantity": {"value": deger, "unit": birim}}})
        for loinc, deger in vital:
            entry.append({"resource": {"resourceType": "Observation", "status": "final",
                                       "category": [{"coding": [{"code": "vital-signs"}]}],
                                       "subject": {"reference": f"Patient/{fid}"},
                                       "code": {"coding": [{"system": "http://loinc.org", "code": loinc}]},
                                       "effectiveDateTime": "2026-09-15", "valueQuantity": {"value": deger}}})
        if ecog is not None:
            entry.append({"resource": {"resourceType": "Observation", "status": "final",
                                       "subject": {"reference": f"Patient/{fid}"},
                                       "code": {"coding": [{"system": "http://loinc.org", "code": "89247-1"}]},
                                       "valueInteger": ecog}})
        entry.append({"resource": {"resourceType": "DocumentReference", "status": "current",
                                   "type": {"coding": [{"system": "http://loinc.org", "code": "18842-5",
                                                        "display": "Epikriz"}]},
                                   "date": "2026-09-20", "subject": {"reference": f"Patient/{fid}"},
                                   "content": [{"attachment": {"contentType": "text/plain", "data": _b64(metin)}}]}})
        return {"resourceType": "Bundle", "type": "searchset", "entry": entry}

    return [
        hasta("m1", 1961, "female",
              [("C50.9", "Meme malign neoplazmı", "2025-11-03")],
              [("L02BA01", "Tamoksifen", ), ("C10AA05", "Atorvastatin")],
              [("718-7", "Hemoglobin", 12.1, "g/dL"), ("2160-0", "Kreatinin", 0.8, "mg/dL"),
               ("1742-6", "ALT", 24, "U/L")],
              [("8480-6", 128), ("8462-4", 78), ("29463-7", 68)],
              "Hasta Ayşe Yılmaz 64 yaşında kadın. Sol meme invaziv duktal karsinom, ER pozitif, HER2 negatif. "
              "Evre IIA. Mastektomi sonrası adjuvan tamoksifen almakta. Prof. Dr. Mehmet Kaya takibinde. "
              "Karaciğer ve böbrek fonksiyonları normal sınırlarda. Metastaz bulgusu yok.", ecog=1),
        hasta("m2", 1954, "male",
              [("C34.1", "Akciğer üst lob malign neoplazmı", "2026-02-14"), ("I10", "Esansiyel hipertansiyon", "2019-05-01")],
              [("C09AA05", "Ramipril", ), ("L01XC17", "Nivolumab")],
              [("718-7", "Hemoglobin", 10.4, "g/dL"), ("2160-0", "Kreatinin", 1.4, "mg/dL")],
              [("8480-6", 146), ("8462-4", 92)],
              "72 yaşında erkek hasta. Sağ üst lob küçük hücreli dışı akciğer kanseri, evre IIIB. PD-L1 %60. "
              "İmmünoterapi 2. siklus. Beyin MR'da metastaz saptanmadı. Tel: 0532 111 22 33.", ecog=1),
        hasta("m3", 1979, "female",
              [("E11.9", "Tip 2 diabetes mellitus", "2021-08-10")],
              [("A10BA02", "Metformin", )],
              [("4548-4", "HbA1c", 8.4, "%"), ("2345-7", "Glukoz", 176, "mg/dL"), ("2160-0", "Kreatinin", 0.7, "mg/dL")],
              [("8480-6", 122), ("8462-4", 76), ("39156-5", 31.2)],
              "47 yaşında kadın, tip 2 DM, metformin 2x1000 mg altında HbA1c 8.4. İnsülin kullanmıyor. "
              "Diyabetik retinopati yok. Gebelik planı yok."),
        hasta("m4", 1948, "male",
              [("I50.9", "Kalp yetmezliği", "2023-03-02"), ("N18.3", "Kronik böbrek hastalığı evre 3", "2024-01-20")],
              [("C07AB02", "Metoprolol", ), ("C03CA01", "Furosemid")],
              [("2160-0", "Kreatinin", 1.9, "mg/dL"), ("33762-6", "NT-proBNP", 2100, "pg/mL")],
              [("8480-6", 110), ("8462-4", 70), ("8867-4", 88)],
              "78 yaşında erkek, NYHA sınıf III kalp yetmezliği, EF %30. eGFR 38. Son 6 ayda 2 kez "
              "dekompansasyon nedeniyle yatış. Ankara Şehir Hastanesi kardiyoloji takibinde."),
    ]


__all__ = ["HBYSAdaptoru", "MockHBYS", "HBYSHatasi", "adaptor_olustur"]
