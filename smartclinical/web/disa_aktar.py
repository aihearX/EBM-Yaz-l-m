"""Disa aktarim ve raporlar: CDISC ODM / CSV veri aktarimi, sponsor fizibilite raporu."""
import csv
import io
import zipfile
from datetime import date
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import __version__
from ..db import get_db
from ..models import Calisma, Kullanici
from ..models._ortak import simdi
from ..services import denetim
from ..services.yetki import gerekli
from ._ortak import calisma_getir, ip
from .calismalar import _ozet
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}")


def _odm(c: Calisma) -> str:
    """CDISC ODM 1.3.2 ClinicalData. Gonullu kimligi yerine gonullu numarasi kullanilir."""
    t = simdi().isoformat(timespec="seconds")
    s = [f'<?xml version="1.0" encoding="UTF-8"?>\n<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3" ODMVersion="1.3.2" '
         f'FileType="Snapshot" FileOID="{escape(c.kod)}-{t}" CreationDateTime="{t}" SourceSystem="EBM SmartClinical" '
         f'SourceSystemVersion="{__version__}">',
         f'<Study OID="{escape(c.kod)}"><GlobalVariables><StudyName>{escape(c.kisa_ad)}</StudyName>'
         f'<StudyDescription>{escape(c.baslik)}</StudyDescription><ProtocolName>{escape(c.kod)}</ProtocolName></GlobalVariables>',
         '<MetaDataVersion OID="MDV.1" Name="v1">']
    for f in sorted(c.formlar, key=lambda x: x.sira):
        s.append(f'<FormDef OID="F.{escape(f.kod)}" Name="{escape(f.ad)}" Repeating="No"><ItemGroupRef ItemGroupOID="IG.{escape(f.kod)}" Mandatory="Yes"/></FormDef>')
        s.append(f'<ItemGroupDef OID="IG.{escape(f.kod)}" Name="{escape(f.ad)}" Repeating="No">' +
                 "".join(f'<ItemRef ItemOID="I.{escape(f.kod)}.{escape(a["kod"])}" Mandatory="{"Yes" if a.get("zorunlu") else "No"}"/>' for a in f.alanlar) + '</ItemGroupDef>')
        for a in f.alanlar:
            tip = {"sayi": "float", "tarih": "date"}.get(a.get("tip"), "text")
            s.append(f'<ItemDef OID="I.{escape(f.kod)}.{escape(a["kod"])}" Name="{escape(a["etiket"])}" DataType="{tip}"'
                     + (f' SDSVarName="{escape(a["cdash"])}"' if a.get("cdash") else "") + '/>')
    s.append('</MetaDataVersion></Study>')
    s.append(f'<ClinicalData StudyOID="{escape(c.kod)}" MetaDataVersionOID="MDV.1">')
    for g in sorted(c.gonulluler, key=lambda x: x.gonullu_no):
        if not g.form_kayitlari:
            continue
        s.append(f'<SubjectData SubjectKey="{escape(g.gonullu_no)}">')
        vizitler = {}
        for fk in g.form_kayitlari:
            vizitler.setdefault(fk.vizit.ad if fk.vizit else "Tarama", []).append(fk)
        for vad, kayitlar in vizitler.items():
            s.append(f'<StudyEventData StudyEventOID="SE.{escape(vad)}">')
            for fk in kayitlar:
                s.append(f'<FormData FormOID="F.{escape(fk.form.kod)}"><ItemGroupData ItemGroupOID="IG.{escape(fk.form.kod)}">')
                for kod, v in (fk.veriler or {}).items():
                    if v not in ("", None):
                        s.append(f'<ItemData ItemOID="I.{escape(fk.form.kod)}.{escape(kod)}" Value="{escape(str(v))}"/>')
                s.append('</ItemGroupData></FormData>')
            s.append('</StudyEventData>')
        s.append('</SubjectData>')
    s.append('</ClinicalData></ODM>')
    return "\n".join(s)


def _csv_zip(c: Calisma) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(c.formlar, key=lambda x: x.sira):
            out = io.StringIO()
            w = csv.writer(out, delimiter=";")
            w.writerow(["GONULLU", "VIZIT", "DURUM"] + [a["kod"] for a in f.alanlar])
            for g in sorted(c.gonulluler, key=lambda x: x.gonullu_no):
                for fk in g.form_kayitlari:
                    if fk.form_id != f.id:
                        continue
                    w.writerow([g.gonullu_no, fk.vizit.ad if fk.vizit else "", fk.durum] + [fk.veriler.get(a["kod"], "") for a in f.alanlar])
            z.writestr(f"{c.kod}_{f.kod}.csv", "﻿" + out.getvalue())
        out = io.StringIO()
        w = csv.writer(out, delimiter=";")
        w.writerow(["GONULLU", "MERKEZ", "DURUM", "ONAM", "RANDOMIZASYON", "KOL", "BITIS", "AYRILMA_NEDENI"])
        for g in sorted(c.gonulluler, key=lambda x: x.gonullu_no):
            w.writerow([g.gonullu_no, g.calisma_merkez.merkez_no, g.durum.value, g.onam_tarihi or "", g.randomizasyon_tarihi or "",
                        g.kol.ad if g.kol else "", g.bitis_tarihi or "", g.ayrilma_nedeni or ""])
        z.writestr(f"{c.kod}_DISPOZISYON.csv", "﻿" + out.getvalue())
        out = io.StringIO()
        w = csv.writer(out, delimiter=";")
        w.writerow(["GONULLU", "TERIM", "MEDDRA_PT", "SOC", "BASLANGIC", "BITIS", "DERECE", "NEDENSELLIK", "CIDDI", "SONUC"])
        for g in c.gonulluler:
            for a in g.advers_olaylar:
                w.writerow([g.gonullu_no, a.terim, a.meddra_pt or "", a.meddra_soc or "", a.baslangic, a.bitis or "", a.siddet,
                            a.nedensellik, "E" if a.ciddi else "H", a.sonuc or ""])
        z.writestr(f"{c.kod}_AE.csv", "﻿" + out.getvalue())
    return buf.getvalue()


@router.get("/veri/disa-aktar")
def disa_aktar(request: Request, bicim: str = "csv", c: Calisma = Depends(calisma_getir),
               k: Kullanici = Depends(gerekli("disa_aktar")), db: Session = Depends(get_db)):
    denetim.kaydet(db, k, "disa_aktar", "calisma", c.id, yeni={"calisma": c.kod, "bicim": bicim}, ip=ip(request))
    db.commit()
    if bicim == "odm":
        return Response(_odm(c), media_type="application/xml",
                        headers={"Content-Disposition": f'attachment; filename="{c.kod}_ODM.xml"'})
    return Response(_csv_zip(c), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{c.kod}_veri.zip"'})


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
