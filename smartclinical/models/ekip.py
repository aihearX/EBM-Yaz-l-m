from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from ..db import Taban
from ._ortak import simdi


class CalismaUyesi(Taban):
    """Calisma ekibi uyeligi (kullanici x calisma). Rol globaldir; uyelik yalnizca gorunurlugu belirler.

    Tabloda hic kayit yokken kisit uygulanmaz (tekil kurulum). Ilk atamayla birlikte
    atanabilir rollerdeki kullanicilar yalnizca uyesi olduklari calismalari gorur (bkz. services/yetki).
    """

    __tablename__ = "calisma_uyesi"
    __table_args__ = (UniqueConstraint("calisma_id", "kullanici_id", name="uq_calisma_uyesi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"), index=True)
    kullanici_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"), index=True)
    ekleyen_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    olusturma: Mapped[datetime] = mapped_column(DateTime, default=simdi, nullable=False)

    calisma = relationship("Calisma", backref=backref("uyeler", cascade="all, delete-orphan"))
    kullanici = relationship("Kullanici", foreign_keys=[kullanici_id],
                             backref=backref("uyelikler", cascade="all, delete-orphan"))
    ekleyen = relationship("Kullanici", foreign_keys=[ekleyen_id])
