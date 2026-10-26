"""Hasta havuzu saklama suresi ve veri sahibi talepleri.

    python -m smartclinical.scripts.hasta_saklama [--ay 6] [--kuru-calisma]
    python -m smartclinical.scripts.hasta_saklama --kayit-no <takma ad> [--kisitla] [--kuru-calisma]

Kural: merkezin acik calismasi kalmamis ve son calisma kaydi --ay ay once kapanmissa, Gonullu baglantisi olmayan
(onam verilmemis) Hasta kayitlari silinir. Gonulluye bagli kayitlar mevzuat geregi silinmez; --kayit-no ile
gelen veri sahibi talebinde bu kayitlarda silme yerine isleme kisitlamasi (--kisitla) uygulanir: klinik icerik
bosaltilir, kaynak 'kisitli' olur ve kayit eslestirmeye girmez. Her islem denetim izine yazilir; takma ad loglanmaz.
"""
import argparse
import sys
from datetime import timedelta

from sqlalchemy import select

from ..db import db_oturumu, tablolari_olustur
from ..models import CalismaDurumu, CalismaMerkez, EslestirmeSonucu, Gonullu, Hasta
from ..models._ortak import simdi
from ..services import denetim

ACIK_CALISMA = (CalismaDurumu.TASARIM, CalismaDurumu.FIZIBILITE, CalismaDurumu.BASVURU, CalismaDurumu.AKTIVASYON,
                CalismaDurumu.KAYIT, CalismaDurumu.IZLEM, CalismaDurumu.KAPANIS)
ICERIK_ALANLARI = ("tanilar", "ilaclar", "laboratuvar", "vitaller", "performans", "metinler")


def merkez_kapanisi(db, merkez_id: int):
    """Merkezin tum calismalari kapandiysa en son kapanis zamani; acik calisma varsa None."""
    satirlar = db.execute(select(CalismaMerkez).where(CalismaMerkez.merkez_id == merkez_id)).scalars().all()
    if not satirlar:
        return False  # hic calisma yok: hasta kaydinin kendi guncellemesi esas alinir
    if any(cm.durum != "kapali" and cm.calisma.durum in ACIK_CALISMA for cm in satirlar):
        return None
    return max(cm.guncelleme for cm in satirlar)


def gonulluye_bagli(db, hasta_id: int) -> bool:
    return db.scalar(select(Gonullu.id).where(Gonullu.hasta_id == hasta_id).limit(1)) is not None


def silinecekler(db, ay: int) -> list[Hasta]:
    esik = simdi() - timedelta(days=round(ay * 30.44))
    kapanis_onbellek = {}
    sonuc = []
    for h in db.execute(select(Hasta).order_by(Hasta.id)).scalars().all():
        if h.merkez_id not in kapanis_onbellek:
            kapanis_onbellek[h.merkez_id] = merkez_kapanisi(db, h.merkez_id)
        kapanis = kapanis_onbellek[h.merkez_id]
        if kapanis is None:
            continue
        referans = h.guncelleme if kapanis is False else kapanis
        if referans > esik or gonulluye_bagli(db, h.id):
            continue
        sonuc.append(h)
    return sonuc


def hasta_sil(db, h: Hasta, neden: str) -> None:
    for es in db.execute(select(EslestirmeSonucu).where(EslestirmeSonucu.hasta_id == h.id)).scalars().all():
        db.delete(es)
    denetim.kaydet(db, None, "sil", "hasta", h.id, yeni={"merkez_id": h.merkez_id, "neden": neden})
    db.delete(h)


def hasta_kisitla(db, h: Hasta) -> None:
    for alan in ICERIK_ALANLARI:
        setattr(h, alan, None)
    h.kaynak = "kisitli"
    denetim.kaydet(db, None, "kisitla", "hasta", h.id, yeni={"merkez_id": h.merkez_id, "neden": "veri_sahibi_talebi"})


def calistir(db, ay: int = 6, kayit_no: str | None = None, kisitla: bool = False, kuru: bool = False) -> dict:
    sonuc = {"silinen": 0, "kisitlanan": 0, "atlanan": 0}
    if kayit_no:
        for h in db.execute(select(Hasta).where(Hasta.kayit_no == kayit_no)).scalars().all():
            if gonulluye_bagli(db, h.id) or kisitla:
                hasta_kisitla(db, h)
                sonuc["kisitlanan"] += 1
            else:
                hasta_sil(db, h, "veri_sahibi_talebi")
                sonuc["silinen"] += 1
    else:
        for h in silinecekler(db, ay):
            hasta_sil(db, h, f"saklama_suresi_{ay}_ay")
            sonuc["silinen"] += 1
    if kuru:
        db.rollback()
    else:
        db.commit()
    return sonuc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Hasta havuzu saklama suresi ve veri sahibi talepleri")
    p.add_argument("--ay", type=int, default=6, help="calisma kapanisindan sonra saklama suresi (ay)")
    p.add_argument("--kayit-no", help="tek bir takma ad icin silme / kisitlama (veri sahibi talebi)")
    p.add_argument("--kisitla", action="store_true", help="--kayit-no ile: silmek yerine isleme kisitlamasi uygula")
    p.add_argument("--kuru-calisma", action="store_true", help="hesapla ama yazma")
    a = p.parse_args(argv)
    tablolari_olustur()
    with db_oturumu() as db:
        s = calistir(db, ay=a.ay, kayit_no=a.kayit_no, kisitla=a.kisitla, kuru=a.kuru_calisma)
    print(f"{s['silinen']} hasta kaydi silindi, {s['kisitlanan']} kayit kisitlandi"
          f"{' (kuru calisma, yazilmadi)' if a.kuru_calisma else ''}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
