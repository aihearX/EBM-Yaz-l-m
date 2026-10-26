"""Denetim izi servisi.

Her kayit bir onceki kaydin ozetini tasir (zincir). Ozet HMAC-SHA256'dir; anahtar SC_SECRET_KEY'den
turetilir, bu yuzden veritabanina dogrudan mudahale eden biri kayitlari yeniden ozetleyemez.
Zincirin ucu `denetim_zincir` tablosundaki tek satirda tutulur ve her yazimda kilitlenir:
PostgreSQL'de SELECT ... FOR UPDATE, SQLite'ta BEGIN IMMEDIATE. Boylece es zamanli iki kayit
ayni onceki_hash'i alamaz. `zinciri_dogrula` ayni anahtarla bastan sona yeniden hesaplar.
"""
import hashlib
import hmac
import json
import os
import threading
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DenetimKaydi, EImza, Kullanici
from ..models._ortak import simdi
from ..models.denetim import DenetimZincir

_VARSAYILAN_ANAHTAR = "gelistirme-anahtari-uretimde-degistir"
# ayni surec icinde paylasilan baglanti (StaticPool, :memory:) icin ek guvence; cok surecli kurulumda
# asil sira veritabani kilidiyle saglanir
_KILIT = threading.Lock()


def _anahtar() -> bytes:
    # config.ayarlar() .env'i os.environ'a yazar; burada yalnizca ortam okunur ki betikler ve testler de ayni yolu kullansin
    gizli = os.environ.get("SC_SECRET_KEY") or _VARSAYILAN_ANAHTAR
    return hashlib.sha256(b"smartclinical-denetim|" + gizli.encode("utf-8")).digest()


def _json(v: Any) -> str:
    def _vars(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if hasattr(o, "value"):  # Enum
            return o.value
        return str(o)

    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=_vars)


def _ozet(onceki_hash: str | None, zaman: datetime, kullanici_adi: str | None, islem: str,
          varlik: str, varlik_id: int | None, eski: Any, yeni: Any) -> str:
    h = hmac.new(_anahtar(), digestmod=hashlib.sha256)
    h.update((onceki_hash or "").encode())
    h.update(zaman.isoformat().encode())
    h.update((kullanici_adi or "").encode())
    h.update(f"{islem}|{varlik}|{varlik_id}".encode())
    h.update(_json(eski).encode())
    h.update(_json(yeni).encode())
    return h.hexdigest()


def varlik_sozluk(obj, alanlar: list[str] | None = None) -> dict:
    """SQLAlchemy nesnesini JSON'a cevrilebilir sozluge indirger (iliskiler haric)."""
    if obj is None:
        return {}
    sonuc = {}
    for col in obj.__table__.columns:
        if alanlar and col.name not in alanlar:
            continue
        v = getattr(obj, col.name)
        if isinstance(v, (datetime, date)):
            v = v.isoformat()
        elif hasattr(v, "value"):
            v = v.value
        sonuc[col.name] = v
    sonuc.pop("parola_hash", None)
    return sonuc


def _zinciri_kilitle(db: Session) -> DenetimZincir:
    """Zincir satirini kilitli olarak dondurur; yoksa olusturur."""
    baglanti = db.connection()
    lehce = baglanti.dialect.name
    if lehce == "sqlite":
        ham = baglanti.connection.dbapi_connection
        # pysqlite islemi ilk DML'de baslatir; islem henuz acilmadiysa yazma kilidini simdi al
        if ham is not None and not getattr(ham, "in_transaction", True):
            baglanti.exec_driver_sql("BEGIN IMMEDIATE")
    sorgu = select(DenetimZincir).where(DenetimZincir.id == 1)
    if lehce == "postgresql":
        sorgu = sorgu.with_for_update()
    z = db.execute(sorgu).scalar_one_or_none()
    if z is None:
        if lehce == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(DenetimZincir).values(id=1, son_hash=None, son_kayit_id=None).on_conflict_do_nothing())
        z = db.execute(sorgu).scalar_one()
    return z


def kaydet(db: Session, kullanici: Kullanici | None, islem: str, varlik: str, varlik_id: int | None = None,
           eski: Any = None, yeni: Any = None, gerekce: str | None = None, ip: str | None = None) -> DenetimKaydi:
    with _KILIT:
        z = _zinciri_kilitle(db)
        onceki = z.son_hash
        if onceki is None and z.son_kayit_id is None:
            # zincir tablosu sonradan eklendiyse mevcut son kayittan devam et
            son = db.execute(select(DenetimKaydi).order_by(DenetimKaydi.id.desc()).limit(1)).scalar_one_or_none()
            onceki = son.hash if son else None
        zaman = simdi()
        kadi = kullanici.kullanici_adi if kullanici else None
        kayit = DenetimKaydi(
            zaman=zaman,
            kullanici_id=kullanici.id if kullanici else None,
            kullanici_adi=kadi,
            islem=islem,
            varlik=varlik,
            varlik_id=varlik_id,
            eski=eski,
            yeni=yeni,
            gerekce=gerekce,
            ip=ip,
            onceki_hash=onceki,
            hash=_ozet(onceki, zaman, kadi, islem, varlik, varlik_id, eski, yeni),
        )
        db.add(kayit)
        db.flush()
        z.son_hash = kayit.hash
        z.son_kayit_id = kayit.id
        db.flush()
    return kayit


def zinciri_dogrula(db: Session) -> tuple[bool, int | None]:
    """(gecerli_mi, ilk_bozuk_kayit_id) dondurur. Anahtar degismisse ilk kayitta durur."""
    onceki = None
    son_id = None
    for k in db.execute(select(DenetimKaydi).order_by(DenetimKaydi.id)).scalars():
        beklenen = _ozet(onceki, k.zaman, k.kullanici_adi, k.islem, k.varlik, k.varlik_id, k.eski, k.yeni)
        if k.hash != beklenen or k.onceki_hash != onceki:
            return False, k.id
        onceki = k.hash
        son_id = k.id
    z = db.get(DenetimZincir, 1)
    if z is not None and z.son_kayit_id is not None and son_id is not None and z.son_hash != onceki:
        return False, son_id
    return True, None


def imzala(db: Session, kullanici: Kullanici, varlik: str, varlik_id: int, anlam: str,
           icerik: Any, ip: str | None = None) -> EImza:
    """Icerik ozeti anahtara bagli degildir (duz SHA-256): imzalanan icerik yillar sonra da ayni ozeti verir."""
    imza = EImza(
        kullanici_id=kullanici.id,
        varlik=varlik,
        varlik_id=varlik_id,
        anlam=anlam,
        icerik_hash=icerik_ozeti(icerik),
        ip=ip,
    )
    db.add(imza)
    kaydet(db, kullanici, "imza", varlik, varlik_id, yeni={"anlam": anlam, "hash": imza.icerik_hash}, ip=ip)
    return imza


def icerik_ozeti(icerik: Any) -> str:
    return hashlib.sha256(_json(icerik).encode()).hexdigest()


def son_imza(db: Session, varlik: str, varlik_id: int, anlam: str | None = None) -> EImza | None:
    sorgu = select(EImza).where(EImza.varlik == varlik, EImza.varlik_id == varlik_id)
    if anlam:
        sorgu = sorgu.where(EImza.anlam == anlam)
    return db.execute(sorgu.order_by(EImza.id.desc()).limit(1)).scalar_one_or_none()
