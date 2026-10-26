from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi, simdi

VIZIT_DURUM_ETIKET = {"planli": "Planlı", "yapildi": "Yapıldı", "kacirildi": "Kaçırıldı", "pencere_disi": "Pencere dışı"}
KAYIT_DURUM_ETIKET = {"taslak": "Taslak", "tamamlandi": "Tamamlandı", "sdv": "SDV yapıldı", "kilitli": "Kilitli"}
# sorgu kaynagi ve durumu ayni sozlukte; anahtarlar cakismiyor
SORGU_ETIKET = {"manuel": "Manuel", "otomatik": "Otomatik", "acik": "Açık", "cevaplandi": "Cevaplandı", "kapali": "Kapalı"}


class Form(Taban):
    """eCRF tanimi. `alanlar` alan sozlugu listesi (standart: services/ecrf.ALAN_ANAHTARLARI):
    [{"kod": "SYSBP", "etiket": "Sistolik KB", "tip": "sayi", "birim": "mmHg", "zorunlu": true,
      "min": 60, "max": 250, "secenekler": [...], "cdash": "VS.VSORRES", "bolum": "Olcumler",
      "kosul": {"alan": "VSYN", "deger": "Evet"}}]
    tip: metin | metin_uzun | sayi | tarih | secim | coklu_secim | evet_hayir
    """

    __tablename__ = "form"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    kod: Mapped[str] = mapped_column(String(16))
    ad: Mapped[str] = mapped_column(String(120))
    vizit_adi: Mapped[str | None] = mapped_column(String(40), nullable=True)  # eski alan; bkz. vizit_listesi
    vizitler: Mapped[list] = mapped_column(JSON, default=list)  # vizit adi listesi; bos -> her vizitte
    sira: Mapped[int] = mapped_column(Integer, default=0)
    alanlar: Mapped[list] = mapped_column(JSON, default=list)
    versiyon: Mapped[str] = mapped_column(String(8), default="1.0")
    durum: Mapped[str] = mapped_column(String(12), default="taslak")  # taslak | yayinda
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)
    tekrarlayan: Mapped[bool] = mapped_column(Boolean, default=False)  # ayni vizitte birden fazla satir (CM, AE gibi)

    calisma = relationship("Calisma", back_populates="formlar")

    @property
    def vizit_listesi(self) -> list[str]:
        """Formun bagli oldugu vizit adlari; bos liste her vizit demektir."""
        if self.vizitler:
            return [v for v in self.vizitler if v and v != "*"]
        if self.vizit_adi and self.vizit_adi != "*":
            return [self.vizit_adi]
        return []

    def vizitte_var(self, vizit_adi: str) -> bool:
        liste = self.vizit_listesi
        return not liste or vizit_adi in liste


class FormKaydi(Taban, ZamanDamgasi):
    __tablename__ = "form_kaydi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gonullu_id: Mapped[int] = mapped_column(ForeignKey("gonullu.id"))
    form_id: Mapped[int] = mapped_column(ForeignKey("form.id"))
    vizit_id: Mapped[int | None] = mapped_column(ForeignKey("vizit.id"), nullable=True)
    tekrar_no: Mapped[int] = mapped_column(Integer, default=1)  # tekrarlayan formda satir numarasi
    form_versiyon: Mapped[str | None] = mapped_column(String(8), nullable=True)  # kayit anindaki form surumu
    veriler: Mapped[dict] = mapped_column(JSON, default=dict)
    durum: Mapped[str] = mapped_column(String(16), default="taslak")  # taslak | tamamlandi | sdv | kilitli
    giren_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    sdv_yapan_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    sdv_zamani: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    kilit_zamani: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    gonullu = relationship("Gonullu", back_populates="form_kayitlari")
    form = relationship("Form")
    vizit = relationship("Vizit")
    giren = relationship("Kullanici", foreign_keys=[giren_id])
    sdv_yapan = relationship("Kullanici", foreign_keys=[sdv_yapan_id])
    sorgular = relationship("Sorgu", back_populates="form_kaydi", cascade="all, delete-orphan")

    @property
    def durum_etiket(self) -> str:
        return KAYIT_DURUM_ETIKET.get(self.durum, self.durum)


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
        return max(0, (son - self.acilis).days)  # saat farki yuzunden -1 gorunmesin
