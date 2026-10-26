"""CDISC ODM ciktisi: StudyEventDef/Ref tutarliligi, ASCII OID'ler, merkez (Location/SiteRef), AE ve dispozisyon gruplari,
tekrarlayan formlar ve istege bagli AuditRecord; CSV paketi BOM ve ayirici."""
import io
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta

os.environ["SC_DB_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartclinical.db import oturum_fabrikasi, sifirla
from smartclinical.main import app
from smartclinical.models import (
    AdversOlay,
    Calisma,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    FormKaydi,
    Gonullu,
    GonulluDurumu,
    Kullanici,
    Merkez,
    Rol,
    Vizit,
)
from smartclinical.models import Form as CRF
from smartclinical.models.tasarim import VizitTanimi
from smartclinical.services import yetki
from smartclinical.web.disa_aktar import oid

PAROLA = "Test1234!xyz"
NS = {"o": "http://www.cdisc.org/ns/odm/v1.3"}


@pytest.fixture(scope="module")
def ortam():
    sifirla()
    db = oturum_fabrikasi()()
    m = Merkez(kod="DA-M1", ad="Çukurova Üniversitesi", sehir="Adana", kurum_tipi="universite")
    db.add(m)
    db.flush()
    admin = Kullanici(kullanici_adi="admin", ad_soyad="Admin", eposta="a@t.local", parola_hash=yetki.parola_hashle(PAROLA), rol=Rol.YONETICI)
    db.add(admin)
    db.flush()
    c = Calisma(kod="DA-001", baslik="Dışa aktarım", kisa_ad="Dışa", tur=CalismaTuru.ILAC, sponsor="S", terapotik_alan="Kardiyoloji", hedef_hasta=5)
    db.add(c)
    db.flush()
    cm = CalismaMerkez(calisma_id=c.id, merkez_id=m.id, merkez_no="01", durum="aktif", aktivasyon_tarihi=date.today() - timedelta(days=30))
    db.add(cm)
    db.add_all([VizitTanimi(calisma_id=c.id, ad="Tarama", sira=0, gun=-14), VizitTanimi(calisma_id=c.id, ad="Vizit 1", sira=1, gun=0),
                VizitTanimi(calisma_id=c.id, ad="Çalışma Sonu", sira=2, gun=84)])
    vs = CRF(calisma_id=c.id, kod="VS", ad="Vital bulgular", sira=1, durum="yayinda",
             alanlar=[{"kod": "SYSBP", "etiket": "Sistolik", "tip": "sayi", "cdash": "VSORRES"}, {"kod": "TARİH", "etiket": "Tarih", "tip": "tarih"}])
    cm_form = CRF(calisma_id=c.id, kod="EŞLİK", ad="Eşlik eden ilaçlar", sira=2, durum="yayinda", tekrarlayan=True,
                  alanlar=[{"kod": "İLAÇ", "etiket": "İlaç adı", "tip": "metin"}, {"kod": "ILAC", "etiket": "İlaç (ASCII)", "tip": "metin"}])
    db.add_all([vs, cm_form])
    db.flush()
    g = Gonullu(calisma_id=c.id, calisma_merkez_id=cm.id, gonullu_no="01-001", durum=GonulluDurumu.AYRILDI, onam_tarihi=date.today() - timedelta(days=20),
                bitis_tarihi=date.today(), ayrilma_nedeni="Onam geri çekildi")
    db.add(g)
    db.flush()
    v = Vizit(gonullu_id=g.id, ad="Vizit 1", sira=1, planlanan=date.today(), gerceklesen=date.today(), durum="yapildi")
    v_adsiz = Vizit(gonullu_id=g.id, ad="Ek vizit", sira=9, planlanan=date.today(), durum="planli")
    db.add_all([v, v_adsiz])
    db.flush()
    db.add_all([
        FormKaydi(gonullu_id=g.id, form_id=vs.id, vizit_id=v.id, veriler={"SYSBP": 128, "TARİH": "2024-02-02"}, durum="tamamlandi", giren_id=admin.id),
        FormKaydi(gonullu_id=g.id, form_id=cm_form.id, vizit_id=v.id, tekrar_no=1, veriler={"İLAÇ": "Metformin"}, durum="tamamlandi", giren_id=admin.id),
        FormKaydi(gonullu_id=g.id, form_id=cm_form.id, vizit_id=v.id, tekrar_no=2, veriler={"İLAÇ": "Ramipril"}, durum="tamamlandi", giren_id=admin.id),
        FormKaydi(gonullu_id=g.id, form_id=vs.id, vizit_id=v_adsiz.id, veriler={"SYSBP": 110}, durum="taslak"),
        AdversOlay(gonullu_id=g.id, terim="Baş ağrısı", meddra_pt="Headache", baslangic=date.today() - timedelta(days=5), siddet="1", nedensellik="olasi"),
    ])
    db.commit()
    cid = c.id
    db.close()
    with TestClient(app) as tc:
        tc.post("/giris", data={"kullanici_adi": "admin", "parola": PAROLA, "sonraki": "/"}, follow_redirects=False)
        yield tc, cid


def _odm(tc, cid, ek=""):
    r = tc.get(f"/calismalar/{cid}/veri/disa-aktar?bicim=odm{ek}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    return ET.fromstring(r.content)


def test_oid_ascii():
    assert oid("EŞLİK") == "ESLIK" and oid("Çalışma Sonu") == "Calisma_Sonu" and oid("a b/c") == "a_b_c" and oid("") == "X"


def test_study_event_ref_ve_oidler(ortam):
    tc, cid = ortam
    kok = _odm(tc, cid)
    mdv = kok.find("o:Study/o:MetaDataVersion", NS)
    tanimlar = {e.get("OID") for e in mdv.findall("o:StudyEventDef", NS)}
    assert {"SE.V0", "SE.V1", "SE.V2", "SE.DIGER", "SE.LOG"} <= tanimlar
    refler = {e.get("StudyEventOID") for e in mdv.findall("o:Protocol/o:StudyEventRef", NS)}
    assert refler == tanimlar
    kullanilan = {e.get("StudyEventOID") for e in kok.iter("{%s}StudyEventData" % NS["o"])}
    assert kullanilan <= tanimlar and "SE.V1" in kullanilan and "SE.DIGER" in kullanilan  # adsiz vizit planlanmamis olaya duser
    form_oidleri = [e.get("OID") for e in mdv.findall("o:FormDef", NS)]
    assert len(form_oidleri) == len(set(form_oidleri)) and "F.ESLIK" in form_oidleri
    # tum OID ve referanslar ASCII
    for e in kok.iter():
        for ad, deger in e.attrib.items():
            if ad.endswith("OID") or ad == "SubjectKey":
                assert deger.isascii(), (e.tag, ad, deger)
    # cakisan alan kodlari (İLAÇ / ILAC) ayri OID alir
    item_oidleri = [e.get("OID") for e in mdv.findall("o:ItemDef", NS)]
    assert len(item_oidleri) == len(set(item_oidleri)) and "I.F.ESLIK.ILAC" in item_oidleri and "I.F.ESLIK.ILAC_2" in item_oidleri
    for sed in mdv.findall("o:StudyEventDef", NS):
        for fr in sed.findall("o:FormRef", NS):
            assert fr.get("FormOID") in form_oidleri


def test_merkez_ae_dispozisyon_ve_tekrar(ortam):
    tc, cid = ortam
    kok = _odm(tc, cid)
    loc = kok.find("o:AdminData/o:Location", NS)
    assert loc is not None and loc.get("OID") == "LOC.01" and loc.get("LocationType") == "Site"
    subj = kok.find("o:ClinicalData/o:SubjectData", NS)
    assert subj.find("o:SiteRef", NS).get("LocationOID") == "LOC.01"
    mdv = kok.find("o:Study/o:MetaDataVersion", NS)
    ig = {e.get("OID"): e for e in mdv.findall("o:ItemGroupDef", NS)}
    assert "IG.AE" in ig and ig["IG.AE"].get("Repeating") == "Yes" and "IG.DS" in ig
    assert ig["IG.F.ESLIK"].get("Repeating") == "Yes" and ig["IG.F.VS"].get("Repeating") == "No"
    ae = [e for e in kok.iter("{%s}ItemGroupData" % NS["o"]) if e.get("ItemGroupOID") == "IG.AE"]
    assert len(ae) == 1 and any(i.get("ItemOID") == "I.AE.AETERM" and i.get("Value") == "Baş ağrısı" for i in ae[0])
    ds = [e for e in kok.iter("{%s}ItemGroupData" % NS["o"]) if e.get("ItemGroupOID") == "IG.DS"][0]
    degerler = {i.get("ItemOID"): i.get("Value") for i in ds}
    assert degerler["I.DS.DSDECOD"] == "ayrildi" and degerler["I.DS.DSTERM"] == "Onam geri çekildi" and "I.DS.DSSTDTC" in degerler
    tekrarlar = sorted(e.get("FormRepeatKey") for e in kok.iter("{%s}FormData" % NS["o"]) if e.get("FormOID") == "F.ESLIK")
    assert tekrarlar == ["1", "2"]
    assert not any(e.tag.endswith("AuditRecord") for e in kok.iter())


def test_denetim_kayitlari_istege_bagli(ortam):
    tc, cid = ortam
    kok = _odm(tc, cid, "&denetim=1")
    audit = [e for e in kok.iter("{%s}AuditRecord" % NS["o"])]
    assert audit and audit[0].find("o:UserRef", NS).get("UserOID") == "USR.1" and audit[0].find("o:LocationRef", NS).get("LocationOID") == "LOC.01"
    assert kok.find("o:AdminData/o:User", NS).get("OID") == "USR.1"
    db = oturum_fabrikasi()()
    son = db.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "disa_aktar").order_by(DenetimKaydi.id.desc())).scalars().first()
    assert son.yeni["bicim"] == "odm" and son.yeni["denetim"] is True
    db.close()


def test_csv_paketi_bom_ve_ayirici(ortam):
    tc, cid = ortam
    r = tc.get(f"/calismalar/{cid}/veri/disa-aktar?bicim=csv")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    adlar = z.namelist()
    assert "DA-001_AE.csv" in adlar and "DA-001_DISPOZISYON.csv" in adlar and "DA-001_VS.csv" in adlar
    icerik = z.read("DA-001_VS.csv").decode("utf-8")
    assert icerik.startswith("\ufeff") and icerik.splitlines()[0].lstrip("\ufeff") == "GONULLU;VIZIT;DURUM;SYSBP;TARİH"
    assert "\r\n" in icerik
