"""Ilk yonetici hesabini olusturur.

    python -m smartclinical.scripts.yonetici_olustur --kullanici admin --ad "Ad Soyad" --eposta a@b.c --mod cro --kurum "EBM CRO"
Parola stdin'den istenir. --mod verilirse kurulum ayari da yazilir (web'deki /kurulum ekraninin komut satiri karsiligi).
"""
import argparse
import getpass

from ..db import db_oturumu, tablolari_olustur
from ..models import Kullanici, Rol
from ..models._ortak import simdi
from ..models.kurulum import MOD_ETIKET, KurulumAyari  # noqa: F401  (tablo kaydi icin)
from ..services import kurulum as kurulum_svc
from ..services import yetki


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kullanici", required=True)
    p.add_argument("--ad", required=True)
    p.add_argument("--eposta", required=True)
    p.add_argument("--mod", choices=sorted(MOD_ETIKET), help="kurulum modu: cro | tekil | universite")
    p.add_argument("--kurum", default="", help="kurum adi (--mod ile)")
    a = p.parse_args()
    parola = getpass.getpass("Parola: ")
    hata = yetki.parola_politikasi(parola)
    if hata:
        raise SystemExit(hata)
    tablolari_olustur()
    with db_oturumu() as db:
        db.add(Kullanici(kullanici_adi=a.kullanici, ad_soyad=a.ad, eposta=a.eposta,
                         parola_hash=yetki.parola_hashle(parola), rol=Rol.YONETICI, parola_degisim=simdi()))
        if a.mod:
            mevcut = kurulum_svc.ayar_getir(db)
            kurulum_svc.ayar_yaz(db, a.mod, a.kurum or mevcut.kurum_adi, mevcut.varsayilan_merkez_id, mevcut.varsayilan_sponsor)
    print(f"Yonetici '{a.kullanici}' olusturuldu." + (f" Kurulum modu: {a.mod}." if a.mod else ""))


if __name__ == "__main__":
    main()
