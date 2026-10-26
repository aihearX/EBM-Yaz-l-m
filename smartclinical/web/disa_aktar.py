"""Disa aktarim ve raporlar: CDISC ODM / CSV veri paketi, operasyon listeleri (CSV), sponsor fizibilite raporu.

CSV ciktilarinin tumu noktali virgulle ayrilir ve UTF-8 BOM ile baslar (Excel'in Turkce karakterleri dogru acmasi icin).
Her dısa aktarim denetim izine 'disa_aktar' olarak yazilir."""
import csv
import io
import unicodedata
import zipfile
from datetime import date
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import __version__
from ..db import get_db
from ..models import Calisma, IzlemZiyareti, Kullanici, ProtokolSapmasi
from ..models._ortak import simdi
from ..models.veri import SORGU_ETIKET
from ..services import denetim
from ..services.yetki import gerekli
from ._ortak import calisma_getir, ip, oturumlu
from .calismalar import _gorunur_cm, _ozet, sekme_kontrol
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}")

BOM = "﻿"
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def oid(metin: str) -> str:
    """ODM OID'leri ASCII olmali: Turkce harfler cevrilir, diger karakterler alt cizgiye doner."""
    m = unicodedata.normalize("NFKD", str(metin).translate(_TR)).encode("ascii", "ignore").decode()
    m = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in m).strip("_")
    return m or "X"


def _benzersiz_oidler(nesneler, anahtar, ayrilmis=()) -> dict:
    """Ayni OID'ye cokusen kodlara sonek ekler; ayrilmis OID'ler (F.AE, F.DS) kullanilmaz."""
    sonuc, kullanilan = {}, set(ayrilmis)
    for n in nesneler:
        aday = taban = oid(anahtar(n))
        i = 2
        while aday in kullanilan:
            aday = f"{taban}_{i}"
            i += 1
        kullanilan.add(aday)
        sonuc[n] = aday
    return sonuc


AE_ALANLAR = [("AETERM", "Olay terimi", "text"), ("AEDECOD", "MedDRA PT", "text"), ("AEBODSYS", "Sistem-organ sınıfı", "text"),
              ("AESTDTC", "Başlangıç", "date"), ("AEENDTC", "Bitiş", "date"), ("AETOXGR", "CTCAE derecesi", "text"),
              ("AEREL", "Nedensellik", "text"), ("AESER", "Ciddi", "text"), ("AEOUT", "Sonuç", "text")]
DS_ALANLAR = [("DSDECOD", "Gönüllü durumu", "text"), ("DSTERM", "Ayrılma / tarama başarısızlık nedeni", "text"),
              ("DSSTDTC", "Bitiş tarihi", "date"), ("RFICDTC", "Onam tarihi", "date"), ("ARMCD", "Kol", "text")]


def _odm(c: Calisma, denetim_izi: bool = False) -> str:
    """CDISC ODM 1.3.2 Snapshot. Gonullu kimligi yerine gonullu numarasi; merkezler AdminData/Location + SiteRef."""
    t = simdi().isoformat(timespec="seconds")
    formlar = sorted(c.formlar, key=lambda x: x.sira)
    form_oid = _benzersiz_oidler(formlar, lambda f: "F." + f.kod, ayrilmis=("F.AE", "F.DS"))
    # alan kodu -> OID (form basina; ayni koda cokusen alanlar sonek alir, ilk alan kazanir)
    alan_oid = {}
    for f in formlar:
        sira = _benzersiz_oidler(range(len(f.alanlar)), lambda i, f=f: f.alanlar[i]["kod"])
        alan_oid[f] = {}
        for i, a in enumerate(f.alanlar):
            alan_oid[f].setdefault(a["kod"], sira[i])
    vizitler = sorted(c.vizit_tanimlari, key=lambda v: v.sira)
    vizit_oid = {v.ad: f"SE.V{v.sira}" for v in vizitler}
    s = [f'<?xml version="1.0" encoding="UTF-8"?>\n<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3" ODMVersion="1.3.2" '
         f'FileType="Snapshot" FileOID="{oid(c.kod)}-{t}" CreationDateTime="{t}" SourceSystem="EBM SmartClinical" '
         f'SourceSystemVersion="{__version__}">',
         f'<Study OID="{oid(c.kod)}"><GlobalVariables><StudyName>{escape(c.kisa_ad)}</StudyName>'
         f'<StudyDescription>{escape(c.baslik)}</StudyDescription><ProtocolName>{escape(c.kod)}</ProtocolName></GlobalVariables>',
         '<MetaDataVersion OID="MDV.1" Name="v1">']
    # protokol: tum vizitler + planlanmamis/kayit (log) olayi
    olaylar = [(vizit_oid[v.ad], v.ad, [form_oid[f] for f in formlar if f.vizitte_var(v.ad)]) for v in vizitler]
    olaylar.append(("SE.DIGER", "Planlanmamış", [form_oid[f] for f in formlar]))
    olaylar.append(("SE.LOG", "Kayıt formları (AE, dispozisyon)", ["F.AE", "F.DS"]))
    s.append("<Protocol>" + "".join(f'<StudyEventRef StudyEventOID="{o}" OrderNumber="{i}" Mandatory="No"/>'
                                    for i, (o, _, _) in enumerate(olaylar, 1)) + "</Protocol>")
    for o, ad, fo in olaylar:
        tip = "Common" if o in ("SE.DIGER", "SE.LOG") else "Scheduled"
        s.append(f'<StudyEventDef OID="{o}" Name="{escape(ad)}" Repeating="{"Yes" if o == "SE.DIGER" else "No"}" Type="{tip}">'
                 + "".join(f'<FormRef FormOID="{x}" OrderNumber="{i}" Mandatory="No"/>' for i, x in enumerate(fo, 1)) + "</StudyEventDef>")
    for f in formlar:
        fo = form_oid[f]
        tekrar = "Yes" if f.tekrarlayan else "No"
        sira = _benzersiz_oidler(range(len(f.alanlar)), lambda i, f=f: f.alanlar[i]["kod"])
        s.append(f'<FormDef OID="{fo}" Name="{escape(f.ad)}" Repeating="{tekrar}"><ItemGroupRef ItemGroupOID="IG.{fo}" Mandatory="Yes"/></FormDef>')
        s.append(f'<ItemGroupDef OID="IG.{fo}" Name="{escape(f.ad)}" Repeating="{tekrar}">' +
                 "".join(f'<ItemRef ItemOID="I.{fo}.{sira[i]}" OrderNumber="{i + 1}" Mandatory="{"Yes" if a.get("zorunlu") else "No"}"/>'
                         for i, a in enumerate(f.alanlar)) + '</ItemGroupDef>')
        for i, a in enumerate(f.alanlar):
            tip = {"sayi": "float", "tarih": "date"}.get(a.get("tip"), "text")
            s.append(f'<ItemDef OID="I.{fo}.{sira[i]}" Name="{escape(a["etiket"])}" DataType="{tip}"'
                     + (f' SDSVarName="{escape(a["cdash"])}"' if a.get("cdash") else "") + '/>')
    for fo, ad, alanlar in (("F.AE", "Advers olaylar", AE_ALANLAR), ("F.DS", "Dispozisyon", DS_ALANLAR)):
        tekrar = "Yes" if fo == "F.AE" else "No"
        s.append(f'<FormDef OID="{fo}" Name="{ad}" Repeating="{tekrar}"><ItemGroupRef ItemGroupOID="IG.{fo[2:]}" Mandatory="No"/></FormDef>')
        s.append(f'<ItemGroupDef OID="IG.{fo[2:]}" Name="{ad}" Repeating="{tekrar}" Domain="{fo[2:]}">' +
                 "".join(f'<ItemRef ItemOID="I.{fo[2:]}.{kod}" OrderNumber="{i}" Mandatory="No"/>' for i, (kod, _, _) in enumerate(alanlar, 1)) + "</ItemGroupDef>")
        for kod, etiket, tip in alanlar:
            s.append(f'<ItemDef OID="I.{fo[2:]}.{kod}" Name="{etiket}" DataType="{tip}" SDSVarName="{kod}"/>')
    s.append('</MetaDataVersion></Study>')
    # merkezler ve (istege bagli) kullanicilar
    kullanicilar = {}
    s.append("<AdminData>")
    if denetim_izi:
        for g in c.gonulluler:
            for fk in g.form_kayitlari:
                for u in (fk.giren, fk.sdv_yapan):
                    if u and u.id not in kullanicilar:
                        kullanicilar[u.id] = u
        for u in kullanicilar.values():
            s.append(f'<User OID="USR.{u.id}" UserType="Investigator"><FullName>{escape(u.ad_soyad)}</FullName></User>')
    for cm in sorted(c.merkezler, key=lambda m: m.merkez_no):
        s.append(f'<Location OID="LOC.{oid(cm.merkez_no)}" Name="{escape(cm.merkez.ad)}" LocationType="Site">'
                 f'<MetaDataVersionRef StudyOID="{oid(c.kod)}" MetaDataVersionOID="MDV.1" EffectiveDate="{(cm.aktivasyon_tarihi or cm.olusturma.date()).isoformat()}"/></Location>')
    s.append("</AdminData>")
    s.append(f'<ClinicalData StudyOID="{oid(c.kod)}" MetaDataVersionOID="MDV.1">')
    for g in sorted(c.gonulluler, key=lambda x: x.gonullu_no):
        s.append(f'<SubjectData SubjectKey="{escape(g.gonullu_no)}"><SiteRef LocationOID="LOC.{oid(g.calisma_merkez.merkez_no)}"/>')
        olay_kayitlari = {}
        for fk in g.form_kayitlari:
            ad = fk.vizit.ad if fk.vizit else None
            olay_kayitlari.setdefault(vizit_oid.get(ad, "SE.DIGER"), []).append(fk)
        for se_oid, kayitlar in olay_kayitlari.items():
            s.append(f'<StudyEventData StudyEventOID="{se_oid}">')
            for fk in sorted(kayitlar, key=lambda x: (x.form_id, x.tekrar_no)):
                fo = form_oid.get(fk.form)
                if fo is None:
                    continue
                kod_oid = alan_oid[fk.form]
                tekrar = f' FormRepeatKey="{fk.tekrar_no}"' if fk.form.tekrarlayan else ""
                s.append(f'<FormData FormOID="{fo}"{tekrar}>')
                if denetim_izi:
                    s.append(_audit(fk.giren_id, fk.guncelleme, g.calisma_merkez.merkez_no))
                s.append(f'<ItemGroupData ItemGroupOID="IG.{fo}">')
                for kod, v in (fk.veriler or {}).items():
                    if v not in ("", None) and kod in kod_oid:
                        s.append(f'<ItemData ItemOID="I.{fo}.{kod_oid[kod]}" Value="{escape(str(v))}"/>')
                s.append('</ItemGroupData></FormData>')
            s.append('</StudyEventData>')
        # kayit formlari: AE satirlari ve dispozisyon
        s.append('<StudyEventData StudyEventOID="SE.LOG">')
        for i, a in enumerate(sorted(g.advers_olaylar, key=lambda x: (x.baslangic, x.id)), 1):
            degerler = [("AETERM", a.terim), ("AEDECOD", a.meddra_pt), ("AEBODSYS", a.meddra_soc), ("AESTDTC", a.baslangic),
                        ("AEENDTC", a.bitis), ("AETOXGR", a.siddet), ("AEREL", a.nedensellik), ("AESER", "Y" if a.ciddi else "N"),
                        ("AEOUT", a.sonuc)]
            s.append(f'<FormData FormOID="F.AE" FormRepeatKey="{i}"><ItemGroupData ItemGroupOID="IG.AE" ItemGroupRepeatKey="{i}">'
                     + "".join(f'<ItemData ItemOID="I.AE.{k}" Value="{escape(str(v))}"/>' for k, v in degerler if v not in (None, ""))
                     + "</ItemGroupData></FormData>")
        degerler = [("DSDECOD", g.durum.value), ("DSTERM", g.ayrilma_nedeni or g.tarama_basarisizlik_nedeni),
                    ("DSSTDTC", g.bitis_tarihi), ("RFICDTC", g.onam_tarihi), ("ARMCD", g.kol.ad if g.kol else None)]
        s.append('<FormData FormOID="F.DS"><ItemGroupData ItemGroupOID="IG.DS">'
                 + "".join(f'<ItemData ItemOID="I.DS.{k}" Value="{escape(str(v))}"/>' for k, v in degerler if v not in (None, ""))
                 + "</ItemGroupData></FormData></StudyEventData>")
        s.append('</SubjectData>')
    s.append('</ClinicalData></ODM>')
    return "\n".join(s)


def _audit(kullanici_id, zaman, merkez_no) -> str:
    kullanici = f'<UserRef UserOID="USR.{kullanici_id}"/>' if kullanici_id else ""
    return (f'<AuditRecord>{kullanici}<LocationRef LocationOID="LOC.{oid(merkez_no)}"/>'
            f'<DateTimeStamp>{zaman.isoformat(timespec="seconds") if zaman else ""}</DateTimeStamp></AuditRecord>')


def _csv(satirlar: list[list]) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    for r in satirlar:
        w.writerow(["" if v is None else v for v in r])
    return BOM + out.getvalue()


def _csv_yaniti(icerik: str, dosya_adi: str) -> Response:
    return Response(icerik.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{dosya_adi}"'})


def _csv_zip(c: Calisma) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(c.formlar, key=lambda x: x.sira):
            satirlar = [["GONULLU", "VIZIT", "DURUM"] + [a["kod"] for a in f.alanlar]]
            for g in sorted(c.gonulluler, key=lambda x: x.gonullu_no):
                for fk in g.form_kayitlari:
                    if fk.form_id != f.id:
                        continue
                    satirlar.append([g.gonullu_no, fk.vizit.ad if fk.vizit else "", fk.durum] + [fk.veriler.get(a["kod"], "") for a in f.alanlar])
            z.writestr(f"{c.kod}_{f.kod}.csv", _csv(satirlar))
        satirlar = [["GONULLU", "MERKEZ", "DURUM", "ONAM", "RANDOMIZASYON", "KOL", "BITIS", "AYRILMA_NEDENI"]]
        for g in sorted(c.gonulluler, key=lambda x: x.gonullu_no):
            satirlar.append([g.gonullu_no, g.calisma_merkez.merkez_no, g.durum.value, g.onam_tarihi or "", g.randomizasyon_tarihi or "",
                             g.kol.ad if g.kol else "", g.bitis_tarihi or "", g.ayrilma_nedeni or ""])
        z.writestr(f"{c.kod}_DISPOZISYON.csv", _csv(satirlar))
        satirlar = [["GONULLU", "TERIM", "MEDDRA_PT", "SOC", "BASLANGIC", "BITIS", "DERECE", "NEDENSELLIK", "CIDDI", "SONUC"]]
        for g in c.gonulluler:
            for a in g.advers_olaylar:
                satirlar.append([g.gonullu_no, a.terim, a.meddra_pt or "", a.meddra_soc or "", a.baslangic, a.bitis or "", a.siddet,
                                 a.nedensellik, "E" if a.ciddi else "H", a.sonuc or ""])
        z.writestr(f"{c.kod}_AE.csv", _csv(satirlar))
    return buf.getvalue()


def _kaydet(db: Session, k: Kullanici, c: Calisma, request: Request, **ek) -> None:
    denetim.kaydet(db, k, "disa_aktar", "calisma", c.id, yeni={"calisma": c.kod, **ek}, ip=ip(request))
    db.commit()


@router.get("/veri/disa-aktar")
def disa_aktar(request: Request, bicim: str = "csv", denetim_izi: int = Query(0, alias="denetim"), c: Calisma = Depends(calisma_getir),
               k: Kullanici = Depends(gerekli("disa_aktar")), db: Session = Depends(get_db)):
    _kaydet(db, k, c, request, bicim=bicim, denetim=bool(denetim_izi))
    if bicim == "odm":
        return Response(_odm(c, denetim_izi=bool(denetim_izi)), media_type="application/xml",
                        headers={"Content-Disposition": f'attachment; filename="{c.kod}_ODM.xml"'})
    return Response(_csv_zip(c), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{c.kod}_veri.zip"'})


# --- Operasyon listeleri (CSV) ---------------------------------------------

@router.get("/veri/sorgular.csv")
def sorgular_csv(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
                 db: Session = Depends(get_db), durum: str = "acik", merkez_id: int | None = None):
    sekme_kontrol(k, "veri")
    satirlar = [["GONULLU", "MERKEZ", "FORM", "VIZIT", "ALAN", "SORGU", "CEVAP", "KAYNAK", "DURUM", "ACAN", "ACILIS", "KAPANIS", "ACIK_GUN"]]
    for cm in _gorunur_cm(k, c):
        if merkez_id and cm.id != merkez_id:
            continue
        for g in sorted(cm.gonulluler, key=lambda x: x.gonullu_no):
            for fk in g.form_kayitlari:
                for s in fk.sorgular:
                    if durum != "hepsi" and s.durum != durum:
                        continue
                    satirlar.append([g.gonullu_no, cm.merkez_no, fk.form.kod, fk.vizit.ad if fk.vizit else "", s.alan, s.soru, s.cevap,
                                     SORGU_ETIKET.get(s.kaynak, s.kaynak), SORGU_ETIKET.get(s.durum, s.durum),
                                     s.acan.kullanici_adi if s.acan else "sistem", s.acilis.isoformat(timespec="minutes"),
                                     s.kapanis.isoformat(timespec="minutes") if s.kapanis else "", s.acik_gun])
    _kaydet(db, k, c, request, liste="sorgular", durum=durum, satir=len(satirlar) - 1)
    return _csv_yaniti(_csv(satirlar), f"{c.kod}_sorgular.csv")


@router.get("/gonulluler.csv")
def gonulluler_csv(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
                   db: Session = Depends(get_db), durum: str = "", merkez_id: int | None = None):
    sekme_kontrol(k, "gonulluler")
    satirlar = [["GONULLU", "MERKEZ", "DURUM", "KOL", "ONAM", "ONAM_SURUMU", "TARAMA", "RANDOMIZASYON", "BITIS", "AYRILMA_NEDENI",
                 "TARAMA_BASARISIZLIK", "FORM_KAYDI", "ACIK_SORGU", "ADVERS_OLAY"]]
    for cm in _gorunur_cm(k, c):
        if merkez_id and cm.id != merkez_id:
            continue
        for g in sorted(cm.gonulluler, key=lambda x: x.gonullu_no):
            if durum and g.durum.value != durum:
                continue
            satirlar.append([g.gonullu_no, cm.merkez_no, g.durum_etiket, g.kol.ad if g.kol else "", g.onam_tarihi, g.onam_versiyonu,
                             g.tarama_tarihi, g.randomizasyon_tarihi, g.bitis_tarihi, g.ayrilma_nedeni, g.tarama_basarisizlik_nedeni,
                             len(g.form_kayitlari), sum(1 for fk in g.form_kayitlari for s in fk.sorgular if s.durum == "acik"),
                             len(g.advers_olaylar)])
    _kaydet(db, k, c, request, liste="gonulluler", durum=durum or "hepsi", satir=len(satirlar) - 1)
    return _csv_yaniti(_csv(satirlar), f"{c.kod}_gonulluler.csv")


@router.get("/izlem/ziyaretler.csv")
def ziyaretler_csv(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
                   db: Session = Depends(get_db), merkez_id: int | None = None):
    sekme_kontrol(k, "izlem")
    cm_ids = [m.id for m in _gorunur_cm(k, c) if not merkez_id or m.id == merkez_id]
    ziyaretler = db.execute(select(IzlemZiyareti).where(IzlemZiyareti.calisma_merkez_id.in_(cm_ids))
                            .order_by(IzlemZiyareti.planlanan)).scalars().all() if cm_ids else []
    satirlar = [["MERKEZ", "TIP", "PLANLANAN", "GERCEKLESEN", "CRA", "SDV_ORANI", "BULGU", "ACIK_BULGU", "DURUM", "RAPOR_ONAY", "ONAYLAYAN", "TETIKLEYEN_UYARI"]]
    for z in ziyaretler:
        satirlar.append([z.calisma_merkez.merkez_no, z.tip_etiket, z.planlanan, z.gerceklesen, z.cra.kullanici_adi if z.cra else "",
                         z.sdv_orani, len(z.bulgular or []), len(z.acik_bulgular), z.durum_etiket,
                         z.rapor_onay.isoformat(timespec="minutes") if z.rapor_onay else "",
                         z.onaylayan.kullanici_adi if z.onaylayan else "", z.tetikleyen_uyari_id or ""])
    _kaydet(db, k, c, request, liste="ziyaretler", satir=len(satirlar) - 1)
    return _csv_yaniti(_csv(satirlar), f"{c.kod}_ziyaretler.csv")


@router.get("/izlem/sapmalar.csv")
def sapmalar_csv(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
                 db: Session = Depends(get_db), merkez_id: int | None = None, durum: str = "hepsi"):
    sekme_kontrol(k, "izlem")
    cm_ids = [m.id for m in _gorunur_cm(k, c) if not merkez_id or m.id == merkez_id]
    sapmalar = db.execute(select(ProtokolSapmasi).where(ProtokolSapmasi.calisma_merkez_id.in_(cm_ids))
                          .order_by(ProtokolSapmasi.tarih)).scalars().all() if cm_ids else []
    satirlar = [["TARIH", "MERKEZ", "GONULLU", "KATEGORI", "ONEM", "ACIKLAMA", "KOK_NEDEN", "DUZELTICI_FAALIYET", "SORUMLU",
                 "HEDEF_TARIH", "ETIK_BILDIRIM", "DURUM", "KAPANIS"]]
    for s in sapmalar:
        if durum == "acik" and s.kapali or durum == "kapali" and not s.kapali:
            continue
        satirlar.append([s.tarih, s.calisma_merkez.merkez_no, s.gonullu.gonullu_no if s.gonullu else "", s.kategori_etiket, s.onem_etiket,
                         s.aciklama, s.kok_neden, s.duzeltici_faaliyet, s.sorumlu.kullanici_adi if s.sorumlu else "", s.hedef_tarih,
                         s.etik_bildirim, s.durum_etiket, s.kapanis_tarihi])
    _kaydet(db, k, c, request, liste="sapmalar", durum=durum, satir=len(satirlar) - 1)
    return _csv_yaniti(_csv(satirlar), f"{c.kod}_sapmalar.csv")


@router.get("/merkez-zekasi/rapor")
def fizibilite_raporu(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("rbm.goruntule")),
                      db: Session = Depends(get_db)):
    """Sponsor icin yazdirilabilir fizibilite ve kazanim raporu."""
    from ..services.merkez_zekasi import merkez_sirala

    request.state.kullanici = k
    bugun = date.today()
    satirlar = []
    for cm in sorted(c.merkezler, key=lambda m: m.merkez_no):
        kayitli = sum(1 for g in cm.gonulluler if g.randomizasyon_tarihi)
        ay = ((bugun - cm.aktivasyon_tarihi).days / 30.4) if cm.aktivasyon_tarihi else 0
        satirlar.append({"cm": cm, "kayitli": kayitli, "ay": ay, "hiz": (kayitli / ay) if ay >= 1 else None,
                         "tarama": len(cm.gonulluler), "basarisiz": sum(1 for g in cm.gonulluler if g.durum.value == "tarama_basarisiz")})
    adaylar = [{"merkez_id": s["cm"].merkez_id, "ad": f"{s['cm'].merkez_no} {s['cm'].merkez.ad}", "tahmini_kazanim": s["cm"].tahmini_kazanim or 0,
                "gecikme_riski": s["cm"].gecikme_riski if s["cm"].gecikme_riski is not None else 0.5, "sapma_orani": 0, "sorgu_orani": 0,
                "tamamlanan_calisma": sum(1 for x in s["cm"].merkez.calismalar if x.durum == "kapali"), "rekabet": 0, "bolge_bos": True,
                "gcp_egitim_guncel": True} for s in satirlar]
    siralama = merkez_sirala(adaylar) if adaylar else []
    denetim.kaydet(db, k, "rapor", "calisma", c.id, yeni={"calisma": c.kod, "rapor": "fizibilite"}, ip=ip(request))
    db.commit()
    return goster(request, "eslestirme/fizibilite_rapor.html", c=c, o=_ozet(db, c), satirlar=satirlar, siralama=siralama,
                  toplam_hiz=sum(s["cm"].tahmini_kazanim or 0 for s in satirlar), bugun=bugun)
