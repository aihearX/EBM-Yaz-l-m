"""Gece isleri: tum aktif calismalarda KRI/QTL hesabi ve erken uyari, merkez zekasi tahmini, SAE bildirim suresi kontrolu.

    python -m smartclinical.scripts.gece_isleri [--kuru-calisma] [--calisma KOD]

Zamanlama: deploy/systemd/smartclinical-gece.timer (her gece 02:00) ya da cron. Sonuc ozeti stdout'a yazilir,
her calisma icin denetim izine 'zamanlanmis' olayi dusulur. Hasta verisi loglanmaz; yalnizca sayilar.
"""
import argparse
import logging
import sys

from sqlalchemy import select

from ..db import db_oturumu, tablolari_olustur
from ..models import Calisma, CalismaDurumu
from ..services import denetim
from ..services.merkez_zekasi import calisma_tahmin_guncelle
from ..services.rbm import erken_uyari_calistir, qtl_guncelle

log = logging.getLogger("smartclinical.gece")

# KRI ve tahmin hesabinin anlamli oldugu asamalar
AKTIF_DURUMLAR = (CalismaDurumu.FIZIBILITE, CalismaDurumu.BASVURU, CalismaDurumu.AKTIVASYON,
                  CalismaDurumu.KAYIT, CalismaDurumu.IZLEM)


def sae_kontrol(c: Calisma) -> dict:
    """TITCK bildirimi yapilmamis SAE'ler: suresi gecen ve 2 gun icinde dolacak olanlar."""
    gecikmis = yaklasan = bekleyen = 0
    for g in c.gonulluler:
        for a in g.advers_olaylar:
            if not a.ciddi or a.titck_bildirim:
                continue
            bekleyen += 1
            kalan = a.bildirim_suresi_gun
            if kalan is None:
                continue
            if kalan < 0:
                gecikmis += 1
            elif kalan <= 2:
                yaklasan += 1
    return {"sae_bekleyen": bekleyen, "sae_gecikmis": gecikmis, "sae_yaklasan": yaklasan}


def calisma_isle(db, c: Calisma) -> dict:
    uyarilar = erken_uyari_calistir(db, c)
    qtl_guncelle(db, c)
    tahmin = calisma_tahmin_guncelle(db, c)
    ozet = {"calisma": c.kod, "durum": c.durum.value, "uyari": len(uyarilar),
            "aksiyon": sum(1 for u in uyarilar if u.seviye == "aksiyon"), "tahmin_merkez": len(tahmin)}
    ozet.update(sae_kontrol(c))
    denetim.kaydet(db, None, "zamanlanmis", "calisma", c.id, yeni=dict(ozet, is_="gece_isleri"))
    return ozet


def calistir(db, kuru: bool = False, kod: str | None = None) -> list[dict]:
    sorgu = select(Calisma).where(Calisma.durum.in_(AKTIF_DURUMLAR)).order_by(Calisma.kod)
    if kod:
        sorgu = select(Calisma).where(Calisma.kod == kod.upper())
    sonuclar = []
    for c in db.execute(sorgu).scalars().all():
        try:
            sonuclar.append(calisma_isle(db, c))
        except Exception as e:  # bir calismanin hatasi digerlerini durdurmasin
            log.exception("Gece isi basarisiz: calisma=%s hata=%s", c.kod, type(e).__name__)
            db.rollback()
            sonuclar.append({"calisma": c.kod, "hata": type(e).__name__})
            continue
        if kuru:
            db.rollback()
        else:
            db.commit()
    return sonuclar


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Aktif calismalarda KRI, tahmin ve SAE sure kontrolu")
    p.add_argument("--kuru-calisma", action="store_true", help="hesapla ama yazma")
    p.add_argument("--calisma", help="yalnizca verilen protokol kodu")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    tablolari_olustur()
    with db_oturumu() as db:
        sonuclar = calistir(db, kuru=a.kuru_calisma, kod=a.calisma)
    hatali = [s for s in sonuclar if "hata" in s]
    for s in sonuclar:
        if "hata" in s:
            print(f"{s['calisma']}: HATA {s['hata']}")
        else:
            print(f"{s['calisma']} ({s['durum']}): {s['uyari']} uyari ({s['aksiyon']} aksiyon), "
                  f"{s['tahmin_merkez']} merkez tahmini, SAE bekleyen {s['sae_bekleyen']} "
                  f"(gecikmis {s['sae_gecikmis']}, 2 gun icinde {s['sae_yaklasan']})")
    print(f"{len(sonuclar)} calisma islendi{' (kuru calisma)' if a.kuru_calisma else ''}; {len(hatali)} hata.")
    return 1 if hatali else 0


if __name__ == "__main__":
    sys.exit(main())
