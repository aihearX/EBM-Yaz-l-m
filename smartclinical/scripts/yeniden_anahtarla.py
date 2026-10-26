"""Takma ad anahtari (SC_TAKMA_AD_ANAHTARI) degisince mevcut Hasta.kayit_no degerlerini yeniler.

    python -m smartclinical.scripts.yeniden_anahtarla --ham-liste anahtar_listesi.csv --eski-anahtar ESKI_ANAHTAR
    python -m smartclinical.scripts.yeniden_anahtarla --eslem eslem.csv

--ham-liste: merkezdeki anahtar listesinin dokumu, noktali virgulle: merkez_id;sistem;deger
             (ham kimlikler yalnizca hesaplama icin okunur, sisteme yazilmaz). Eski takma ad --eski-anahtar,
             yeni takma ad gecerli anahtar (SC_TAKMA_AD_ANAHTARI) ile hesaplanir.
--eslem:     dogrudan eslem: merkez_id;eski_kayit_no;yeni_kayit_no
Hasta satirlari yerinde guncellenir; Gonullu.hasta_id ve eslestirme sonuclari hasta id'si uzerinden bagli oldugu
icin korunur. Islem denetim izine 'yeniden_anahtarla' olarak yazilir.
"""
import argparse
import csv
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import db_oturumu, tablolari_olustur
from ..models import Hasta
from ..services import denetim
from ..services.fhir import takma_kayit_no


def eslem_hesapla(satirlar, eski_anahtar: str | bytes, yeni_anahtar: str | bytes | None = None) -> list[tuple[int, str, str]]:
    """(merkez_id, sistem, deger) satirlarindan (merkez_id, eski_kayit_no, yeni_kayit_no) uretir."""
    sonuc = []
    for merkez_id, sistem, deger in satirlar:
        ident = [{"system": sistem or "", "value": deger}]
        sonuc.append((int(merkez_id), takma_kayit_no(ident, None, int(merkez_id), anahtar=eski_anahtar),
                      takma_kayit_no(ident, None, int(merkez_id), anahtar=yeni_anahtar)))
    return sonuc


def yeniden_anahtarla(db: Session, eslem: list[tuple[int, str, str]], ip: str | None = None) -> dict:
    """Eslemdeki her (merkez, eski, yeni) icin Hasta.kayit_no'yu gunceller. Commit etmez."""
    guncel = bulunamadi = cakisma = 0
    for merkez_id, eski, yeni in eslem:
        if eski == yeni:
            continue
        h = db.execute(select(Hasta).where(Hasta.merkez_id == merkez_id, Hasta.kayit_no == eski)).scalar_one_or_none()
        if not h:
            bulunamadi += 1
            continue
        var = db.execute(select(Hasta.id).where(Hasta.merkez_id == merkez_id, Hasta.kayit_no == yeni, Hasta.id != h.id)).first()
        if var:
            cakisma += 1  # ayni merkezde yeni takma ad baska bir kayitta var; dokunulmaz, raporlanir
            continue
        h.kayit_no = yeni
        guncel += 1
    sistem = SimpleNamespace(id=None, kullanici_adi="sistem")
    denetim.kaydet(db, sistem, "yeniden_anahtarla", "hasta", None,
                   yeni={"eslem": len(eslem), "guncellenen": guncel, "bulunamayan": bulunamadi, "cakisan": cakisma,
                         "kaynak": "komut_satiri"}, ip=ip)
    return {"eslem": len(eslem), "guncellenen": guncel, "bulunamayan": bulunamadi, "cakisan": cakisma}


def _csv_oku(yol: str) -> list[list[str]]:
    with Path(yol).open(encoding="utf-8-sig", newline="") as f:
        satirlar = [s for s in csv.reader(f, delimiter=";") if s and any(x.strip() for x in s)]
    if satirlar and not satirlar[0][0].strip().isdigit():
        satirlar = satirlar[1:]  # baslik satiri
    return [[x.strip() for x in s] for s in satirlar]


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ham-liste", help="merkez_id;sistem;deger dosyasi")
    g.add_argument("--eslem", help="merkez_id;eski_kayit_no;yeni_kayit_no dosyasi")
    p.add_argument("--eski-anahtar", help="--ham-liste ile zorunlu: onceki SC_TAKMA_AD_ANAHTARI degeri")
    a = p.parse_args()
    if a.ham_liste:
        if not a.eski_anahtar:
            raise SystemExit("--ham-liste ile --eski-anahtar gerekir")
        eslem = eslem_hesapla([(s[0], s[1], s[2]) for s in _csv_oku(a.ham_liste) if len(s) >= 3], a.eski_anahtar)
    else:
        eslem = [(int(s[0]), s[1], s[2]) for s in _csv_oku(a.eslem) if len(s) >= 3]
    tablolari_olustur()
    with db_oturumu() as db:
        sonuc = yeniden_anahtarla(db, eslem)
    print("Eslem: {eslem}, guncellenen: {guncellenen}, bulunamayan: {bulunamayan}, cakisan: {cakisan}".format(**sonuc))


if __name__ == "__main__":
    main()
