import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Kullanici
from ..services import denetim
from ..services.yetki import gerekli, mevcut_kullanici
from . import semalar

router = APIRouter(prefix="/yz")


@router.post("/kimliksizlestir", response_model=semalar.KimliksizlestirmeCikti)
def kimliksizlestir_api(g: semalar.KimliksizlestirmeIstek, db: Session = Depends(get_db), k: Kullanici = Depends(mevcut_kullanici)):
    from ..services.kimliksizlestirme import kimliksizlestir, metni_dogrula

    s = kimliksizlestir(g.metin, mod=g.mod)
    denetim.kaydet(db, k, "kimliksizlestir", "metin", None, yeni={"mod": g.mod, "uzunluk": len(g.metin), "api": True})
    db.commit()
    return semalar.KimliksizlestirmeCikti(metin=s.metin, istatistik=dict(s.istatistik), uyarilar=metni_dogrula(s.metin))


@router.post("/kriter-yapilandir")
def kriter_yapilandir(g: semalar.KriterYapilandirIstek, k: Kullanici = Depends(gerekli("bdm.kullan"))):
    from ..services.bdm import BDMIstemci

    y = BDMIstemci.olustur().kriter_yapilandir(g.metin, g.tip)
    return y.to_dict()


@router.get("/bdm/durum")
def bdm_durum(k: Kullanici = Depends(mevcut_kullanici)):
    from ..services.bdm import BDMIstemci

    return BDMIstemci.olustur().durum()


# --- Genel amacli Klinik BDM servis uclari ----------------------------------
# Platform disindaki uygulamalar (HBYS modulleri, arastirma veri ambari) icin yeniden kullanilabilir
# Turkce klinik NLP islevleri. Ulusal klinik BDM altyapisinin disa acilan yuzu.

class MetinIstek(BaseModel):
    metin: str


@router.post("/icd-kodla")
def icd_kodla(g: MetinIstek, k: Kullanici = Depends(gerekli("bdm.kullan"))):
    """Serbest metindeki tani ifadelerini ICD-10 on ekleriyle eslestirir (sozluk tabanli; BDM ile zenginlestirilecek)."""
    from ..services.kriter import sozluk as S

    m = S.sade(g.metin)
    bulgular = []
    for terim in S.TANI_TERIMLERI:
        if len(terim) < 4:
            continue
        if re.search(r"\b" + re.escape(S.sade(terim)) + r"\b", m):
            bulgular.append({"terim": terim, "icd10": S.TANI_SOZLUGU[terim]})
    return {"bulgular": bulgular, "yontem": "sozluk"}


@router.post("/ozet")
def klinik_ozet(g: MetinIstek, db: Session = Depends(get_db), k: Kullanici = Depends(gerekli("bdm.kullan"))):
    from ..services.bdm import BDMIstemci
    from ..services.kimliksizlestirme import kimliksizlestir

    temiz = kimliksizlestir(g.metin).metin  # servis ucu disaridan geldigi icin once kimliksizlestir
    i = BDMIstemci.olustur()
    denetim.kaydet(db, k, "bdm", "bdm", None, yeni={"gorev": "ozet", "uzunluk": len(g.metin), "api": True})
    db.commit()
    return {"ozet": i.klinik_ozet(temiz), "model": i.model_adi}
