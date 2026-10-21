from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi, simdi


class Form(Taban):
    """eCRF tanimi. `alanlar` CDASH uyumlu alan listesi:
    [{"kod": "SYSBP", "etiket": "Sistolik KB", "tip": "sayi", "birim": "mmHg", "zorunlu": true,
      "min": 60, "max": 250, "secenekler": [...], "cdash": "VS.VSORRES"}]
    """

    __tablename__ = "form"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    kod: Mapped[str] = mapped_column(String(16))
    ad: Mapped[str] = mapped_column(String(120))
    vizit_adi: Mapped[str | None] = mapped_column(String(40), nullable=True)  # None -> her vizitte
    sira: Mapped[int] = mapped_column(Integer, default=0)
    alanlar: Mapped[list] = mapped_column(JSON, default=list)
    versiyon: Mapped[str] = mapped_column(String(8), default="1.0")

    calisma = relationship("Calisma", back_populates="formlar")


class FormKaydi(Taban, ZamanDamgasi):
    __tablename__ = "form_kaydi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gonullu_id: Mapped[int] = mapped_column(ForeignKey("gonullu.id"))
    form_id: Mapped[int] = mapped_column(ForeignKey("form.id"))
    vizit_id: Mapped[int | None] = mapped_column(ForeignKey("vizit.id"), nullable=True)
    veriler: Mapped[dict] = mapped_column(JSON, default=dict)
    durum: Mapped[str] = mapped_column(String(16), default="taslak")  # taslak | tamamlandi | sdv | kilitli
    giren_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    sdv_yapan_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    sdv_zamani: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    kilit_zamani: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    gonullu = relationship("Gonullu", back_populates="form_kayitlari")
    form = relationship("Form")
    vizit = relationship("Vizit")
    sorgular = relationship("Sorgu", back_populates="form_kaydi", cascade="all, delete-orphan")


class Sorgu(Taban):
    """Veri sorgusu (query). Otomatik edit-check veya CRA/veri yoneticisi tarafindan acilir."""

    __tablename__ = "sorgu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    form_kaydi_id: Mapped[int] = mapped_column(ForeignKey("form_kaydi.id"))
    alan: Mapped[str] = mapped_column(String(32))
    soru: Mapped[str] = mapped_column(Text)
    cevap: Mapped[str | None] = mapped_column(Text, nullable=True)
    kaynak: Mapped[str] = mapped_column(String(16), default="manuel")  # manuel | otomatik
    durum: Mapped[str] = mapped_column(String(16), default="acik")  # acik | cevaplandi | kapali
    acan_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    acilis: Mapped[datetime] = mapped_column(DateTime, default=simdi)
    kapanis: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    form_kaydi = relationship("FormKaydi", back_populates="sorgular")
    acan = relationship("Kullanici")

    @property
    def acik_gun(self) -> int:
        son = self.kapanis or simdi()
        return (son - self.acilis).days
