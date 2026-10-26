from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import simdi


class DenetimKaydi(Taban):
    """Degistirilemez denetim izi. 21 CFR Part 11 / EU GMP Annex 11 gereklilikleri.

    Kayitlar uygulama katmanindan silinemez; veritabani kullanicisinin bu tabloda
    sadece INSERT yetkisi olmalidir (bkz. deploy/postgres/yetkiler.sql).
    Her kayit bir oncekinin ozetini (onceki_hash) tasir; ozet HMAC-SHA256'dir (anahtar SC_SECRET_KEY'den
    turetilir), zincir bozulursa
    `scripts/denetim_dogrula.py` uyarir.
    """

    __tablename__ = "denetim_kaydi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zaman: Mapped[datetime] = mapped_column(DateTime, default=simdi, index=True)
    kullanici_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    kullanici_adi: Mapped[str | None] = mapped_column(String(64), nullable=True)  # kullanici silinse de kalsin
    islem: Mapped[str] = mapped_column(String(24))  # olustur | guncelle | sil | giris | cikis | imza | disa_aktar | goruntule | kilit_ac | zamanlanmis
    varlik: Mapped[str] = mapped_column(String(40), index=True)
    varlik_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eski: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    yeni: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gerekce: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    onceki_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    kullanici = relationship("Kullanici")


class DenetimZincir(Taban):
    """Zincirin son ozeti; tek satir (id=1). Yeni kayit eklenirken bu satir kilitlenir
    (PostgreSQL: SELECT ... FOR UPDATE, SQLite: BEGIN IMMEDIATE), boylece es zamanli
    yazimlar sirali hale gelir ve iki kaydin ayni onceki_hash'i tasimasi onlenir."""

    __tablename__ = "denetim_zincir"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    son_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    son_kayit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EImza(Taban):
    """Elektronik imza (21 CFR Part 11 Subpart C). Imza aninda parola yeniden istenir."""

    __tablename__ = "e_imza"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kullanici_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"))
    varlik: Mapped[str] = mapped_column(String(40))
    varlik_id: Mapped[int] = mapped_column(Integer)
    anlam: Mapped[str] = mapped_column(String(60))  # "Onaylandı", "Gözden geçirildi", "Sorumluluk alındı"
    zaman: Mapped[datetime] = mapped_column(DateTime, default=simdi)
    icerik_hash: Mapped[str] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    kullanici = relationship("Kullanici")
