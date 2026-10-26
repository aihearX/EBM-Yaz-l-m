"""Vizite bagli olmayan form kayitlari olan gonulluler icin tarama vizitlerini uretir ve kayitlari baglar.

Kullanim: python -m smartclinical.scripts.onarim_tarama_vizitleri [--kuru-calisma]
"""
import argparse
import sys
from datetime import date

from sqlalchemy import select

from ..db import db_oturumu
from ..models import FormKaydi, Gonullu
from ..services import denetim
from ..services import gonullu as gsvc


def onar(db, kuru: bool) -> list[tuple[str, int, int]]:
    gidler = db.execute(select(FormKaydi.gonullu_id).where(FormKaydi.vizit_id.is_(None)).distinct()).scalars().all()
    sonuc = []
    for gid in gidler:
        g = db.get(Gonullu, gid)
        if not g:
            continue
        tarih = g.tarama_tarihi or g.onam_tarihi or g.randomizasyon_tarihi or date.today()
        yeni = gsvc.tarama_vizitleri_olustur(db, g, tarih)
        baglanan = gsvc.kayitlari_vizite_bagla(g)
        sonuc.append((g.gonullu_no, len(yeni), baglanan))
        if not kuru and (yeni or baglanan):
            denetim.kaydet(db, None, "onarim", "gonullu", g.id,
                           yeni={"tarama_viziti": len(yeni), "baglanan_kayit": baglanan, "kaynak": "onarim_tarama_vizitleri"})
    return sonuc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bagsiz tarama formlarini vizite baglar.")
    p.add_argument("--kuru-calisma", action="store_true", help="degisiklik yazmaz, yalnizca listeler")
    a = p.parse_args(argv)
    with db_oturumu() as db:
        sonuc = onar(db, a.kuru_calisma)
        if a.kuru_calisma:
            db.rollback()
    if not sonuc:
        print("Bagsiz kayit yok; yapilacak bir sey yok.")
        return 0
    for no, v, b in sonuc:
        print(f"{no}: {v} tarama viziti, {b} kayit baglandi")
    print(("Kuru calisma: " if a.kuru_calisma else "") + f"{len(sonuc)} gonullu islendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
