"""Denetim izi servisi.

Her kayit bir onceki kaydin hash'ini tasir (zincir). Boylece veritabanina dogrudan
mudahale edilse bile `zinciri_dogrula` ile tespit edilebilir.
"""
import hashlib
import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DenetimKaydi, EImza, Kullanici
from ..models._ortak import simdi


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
    h = hashlib.sha256()
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


def kaydet(db: Session, kullanici: Kullanici | None, islem: str, varlik: str, varlik_id: int | None = None,
           eski: Any = None, yeni: Any = None, gerekce: str | None = None, ip: str | None = None) -> DenetimKaydi:
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
    return kayit


def zinciri_dogrula(db: Session) -> tuple[bool, int | None]:
    """(gecerli_mi, ilk_bozuk_kayit_id) dondurur."""
    onceki = None
    for k in db.execute(select(DenetimKaydi).order_by(DenetimKaydi.id)).scalars():
        beklenen = _ozet(onceki, k.zaman, k.kullanici_adi, k.islem, k.varlik, k.varlik_id, k.eski, k.yeni)
        if k.hash != beklenen or k.onceki_hash != onceki:
            return False, k.id
        onceki = k.hash
    return True, None


def imzala(db: Session, kullanici: Kullanici, varlik: str, varlik_id: int, anlam: str,
           icerik: Any, ip: str | None = None) -> EImza:
    imza = EImza(
        kullanici_id=kullanici.id,
        varlik=varlik,
        varlik_id=varlik_id,
        anlam=anlam,
        icerik_hash=hashlib.sha256(_json(icerik).encode()).hexdigest(),
        ip=ip,
    )
    db.add(imza)
    kaydet(db, kullanici, "imza", varlik, varlik_id, yeni={"anlam": anlam, "hash": imza.icerik_hash}, ip=ip)
    return imza
