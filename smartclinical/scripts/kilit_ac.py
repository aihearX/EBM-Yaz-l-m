"""Kilitli kullanici hesabini komut satirindan acar.

    python -m smartclinical.scripts.kilit_ac --kullanici drahmet
Sureli kilit ve hatali giris sayaci sifirlanir; islem denetim izine 'kilit_ac' olarak yazilir.
"""
import argparse
from types import SimpleNamespace

from sqlalchemy import select

from ..db import db_oturumu, tablolari_olustur
from ..models import Kullanici
from ..services import denetim, yetki


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kullanici", required=True, help="kullanici adi")
    a = p.parse_args()
    tablolari_olustur()
    with db_oturumu() as db:
        k = db.execute(select(Kullanici).where(Kullanici.kullanici_adi == a.kullanici.strip().lower())).scalar_one_or_none()
        if not k:
            raise SystemExit(f"Kullanici bulunamadi: {a.kullanici}")
        eski = {"hatali_giris": k.hatali_giris, "kilit_bitis": k.kilit_bitis.isoformat() if k.kilit_bitis else None}
        yetki.kilit_ac(db, k)
        sistem = SimpleNamespace(id=None, kullanici_adi="sistem")
        denetim.kaydet(db, sistem, "kilit_ac", "kullanici", k.id, eski=eski,
                       yeni={"hatali_giris": 0, "kilit_bitis": None, "kaynak": "komut_satiri"})
    print(f"'{k.kullanici_adi}' hesabinin kilidi acildi.")


if __name__ == "__main__":
    main()
