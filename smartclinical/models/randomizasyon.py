from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import simdi

STRATA_ETIKET = {"yok": "Yok (tek liste)", "merkez": "Merkeze göre"}


class RandomizasyonAyari(Taban):
    """Calisma basina bir ayar. Liste e-imza ile uretilir; imza_zamani bos ise liste yoktur."""

    __tablename__ = "randomizasyon_ayari"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"), unique=True)
    blok_boyutu: Mapped[int] = mapped_column(Integer, default=4)
    strata: Mapped[str] = mapped_column(String(12), default="yok")  # yok | merkez
    olusturan_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    imza_zamani: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    olusturma: Mapped[datetime] = mapped_column(DateTime, default=simdi)

    calisma = relationship("Calisma")
    olusturan = relationship("Kullanici")

    @property
    def strata_etiket(self) -> str:
        return STRATA_ETIKET.get(self.strata, self.strata)


class RandomizasyonKaydi(Taban):
    """Permute blok listesinin bir satiri. Kol sutunu kullaniciya gosterilmez; tahsis siradaki_tahsis ile yapilir."""

    __tablename__ = "randomizasyon_kaydi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"), index=True)
    strata_anahtari: Mapped[str] = mapped_column(String(40), default="*")  # "*" veya merkez_no
    sira: Mapped[int] = mapped_column(Integer)
    kol_id: Mapped[int] = mapped_column(ForeignKey("kol.id"))
    gonullu_id: Mapped[int | None] = mapped_column(ForeignKey("gonullu.id"), nullable=True)
    kullanim_zamani: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    kol = relationship("Kol")
    gonullu = relationship("Gonullu")
