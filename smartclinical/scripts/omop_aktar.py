"""Kimliksizlestirilmis hasta havuzunu OMOP CDM CSV dosyalarina aktarir.

    python -m smartclinical.scripts.omop_aktar --merkez 3 --dizin ./ciktilar/omop
"""
import argparse
from pathlib import Path

from sqlalchemy import select

from ..db import db_oturumu
from ..models import Hasta
from ..services.fhir.omop import omop_disa_aktar


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--merkez", type=int)
    p.add_argument("--dizin", default="./ciktilar/omop")
    a = p.parse_args()
    with db_oturumu() as db:
        q = select(Hasta)
        if a.merkez:
            q = q.where(Hasta.merkez_id == a.merkez)
        hastalar = db.scalars(q).all()
        ozet = omop_disa_aktar(hastalar, Path(a.dizin))
    print(ozet)


if __name__ == "__main__":
    main()
