"""Dahili blok randomizasyon.

Permute blok listesi kol oranlarina gore uretilir, istege bagli merkez stratasi ile.
Liste e-imza ile uretilir (web katmani dogrular); tahsis `siradaki_tahsis` ile yapilir ve
koordinator siradaki kolu onceden goremez. Servis commit etmez.
"""
import random
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models._ortak import simdi
from ..models.calisma import Calisma
from ..models.hasta import Gonullu
from ..models.randomizasyon import RandomizasyonAyari, RandomizasyonKaydi

STRATALAR = ("yok", "merkez")
GENEL = "*"


def ayar_getir(db: Session, c: Calisma) -> RandomizasyonAyari | None:
    return db.execute(select(RandomizasyonAyari).where(RandomizasyonAyari.calisma_id == c.id)).scalar_one_or_none()


def liste_var(db: Session, c: Calisma) -> bool:
    a = ayar_getir(db, c)
    return bool(a and a.imza_zamani)


def strata_anahtari(ayar: RandomizasyonAyari | None, g: Gonullu) -> str:
    if ayar and ayar.strata == "merkez":
        return g.calisma_merkez.merkez_no
    return GENEL


def _strata_anahtarlari(c: Calisma, strata: str) -> list[str]:
    if strata == "merkez":
        anahtarlar = sorted({cm.merkez_no for cm in c.merkezler})
        return anahtarlar or [GENEL]
    return [GENEL]


def blok_boyutu_dogrula(c: Calisma, blok_boyutu: int) -> str | None:
    """Hata mesaji ya da None. Blok, oran toplaminin kati olmali ki her blok dengeli kapansin."""
    if len(c.kollar) < 2:
        return "Randomizasyon listesi için en az iki kol tanımlı olmalı."
    toplam = sum(max(1, k.oran or 1) for k in c.kollar)
    if blok_boyutu < toplam or blok_boyutu % toplam:
        return f"Blok boyutu kol oranlarının toplamının ({toplam}) katı olmalı."
    if blok_boyutu > 24:
        return "Blok boyutu en fazla 24 olabilir."
    return None


def liste_uret(db: Session, c: Calisma, blok_boyutu: int, strata: str = "yok", tohum: int | None = None,
               kayit_sayisi: int | None = None) -> list[RandomizasyonKaydi]:
    """Her strata icin permute bloklar uretir. Kullanilmis kaydi olan liste yeniden uretilemez."""
    hata = blok_boyutu_dogrula(c, blok_boyutu)
    if hata:
        raise ValueError(hata)
    if strata not in STRATALAR:
        raise ValueError("Bilinmeyen strata.")
    kullanilan = db.scalar(select(func.count(RandomizasyonKaydi.id)).where(
        RandomizasyonKaydi.calisma_id == c.id, RandomizasyonKaydi.gonullu_id.isnot(None))) or 0
    if kullanilan:
        raise ValueError("Tahsis yapılmış bir liste yeniden üretilemez.")
    for eski in db.execute(select(RandomizasyonKaydi).where(RandomizasyonKaydi.calisma_id == c.id)).scalars():
        db.delete(eski)
    db.flush()

    kollar = sorted(c.kollar, key=lambda k: k.id)
    toplam_oran = sum(max(1, k.oran or 1) for k in kollar)
    kat = blok_boyutu // toplam_oran
    blok_sablonu = [k.id for k in kollar for _ in range(max(1, k.oran or 1) * kat)]
    anahtarlar = _strata_anahtarlari(c, strata)
    # hedefin bir miktar uzerinde kayit: tarama basarisizligi ve yedek icin
    hedef = kayit_sayisi or max(blok_boyutu, int((c.hedef_hasta or 0) * 1.2) + blok_boyutu)
    strata_basi = -(-hedef // len(anahtarlar))  # yukari yuvarlanmis bolum
    blok_sayisi = -(-strata_basi // blok_boyutu)

    r = random.Random(tohum) if tohum is not None else random.SystemRandom()
    kayitlar = []
    for anahtar in anahtarlar:
        sira = 0
        for _ in range(blok_sayisi):
            blok = list(blok_sablonu)
            r.shuffle(blok)
            for kol_id in blok:
                sira += 1
                k = RandomizasyonKaydi(calisma_id=c.id, strata_anahtari=anahtar, sira=sira, kol_id=kol_id)
                db.add(k)
                kayitlar.append(k)
    db.flush()
    return kayitlar


def siradaki_tahsis(db: Session, g: Gonullu) -> RandomizasyonKaydi:
    """Gonullunun stratasindaki ilk kullanilmamis kaydi kilitleyip atar; g.kol_id yazilir."""
    ayar = ayar_getir(db, g.calisma)
    if not ayar or not ayar.imza_zamani:
        raise ValueError("Bu çalışmada randomizasyon listesi üretilmemiş.")
    anahtar = strata_anahtari(ayar, g)
    sorgu = (select(RandomizasyonKaydi)
             .where(RandomizasyonKaydi.calisma_id == g.calisma_id, RandomizasyonKaydi.strata_anahtari == anahtar,
                    RandomizasyonKaydi.gonullu_id.is_(None))
             .order_by(RandomizasyonKaydi.sira).limit(1))
    if db.bind is not None and db.bind.dialect.name != "sqlite":
        sorgu = sorgu.with_for_update(skip_locked=True)
    kayit = db.execute(sorgu).scalar_one_or_none()
    if not kayit:
        raise ValueError("Randomizasyon listesinde bu merkez için boş kayıt kalmadı; listeyi uzatın.")
    kayit.gonullu_id = g.id
    kayit.kullanim_zamani = simdi()
    g.kol_id = kayit.kol_id
    db.flush()
    return kayit


def ozet(db: Session, c: Calisma) -> list[dict]:
    """Strata bazinda yalnizca sayilar; kol dagilimi ve sira bilgisi disari verilmez."""
    satirlar = db.execute(
        select(RandomizasyonKaydi.strata_anahtari, func.count(RandomizasyonKaydi.id),
               func.count(RandomizasyonKaydi.gonullu_id))
        .where(RandomizasyonKaydi.calisma_id == c.id).group_by(RandomizasyonKaydi.strata_anahtari)
        .order_by(RandomizasyonKaydi.strata_anahtari)).all()
    return [{"strata": s, "toplam": t, "kullanilan": k, "kalan": t - k} for s, t, k in satirlar]


def son_tahsis(db: Session, c: Calisma) -> datetime | None:
    return db.scalar(select(func.max(RandomizasyonKaydi.kullanim_zamani)).where(RandomizasyonKaydi.calisma_id == c.id))
