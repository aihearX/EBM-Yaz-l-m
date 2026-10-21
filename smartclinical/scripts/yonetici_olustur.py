"""Ilk yonetici hesabini olusturur.

    python -m smartclinical.scripts.yonetici_olustur --kullanici admin --ad "Ad Soyad" --eposta a@b.c
Parola stdin'den istenir.
"""
import argparse
import getpass

from ..db import db_oturumu, tablolari_olustur
from ..models import Kullanici, Rol
from ..models._ortak import simdi
from ..services import yetki


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kullanici", required=True)
    p.add_argument("--ad", required=True)
    p.add_argument("--eposta", required=True)
    a = p.parse_args()
    parola = getpass.getpass("Parola: ")
    hata = yetki.parola_politikasi(parola)
    if hata:
        raise SystemExit(hata)
    tablolari_olustur()
    with db_oturumu() as db:
        db.add(Kullanici(kullanici_adi=a.kullanici, ad_soyad=a.ad, eposta=a.eposta,
                         parola_hash=yetki.parola_hashle(parola), rol=Rol.YONETICI, parola_degisim=simdi()))
    print(f"Yonetici '{a.kullanici}' olusturuldu.")


if __name__ == "__main__":
    main()
