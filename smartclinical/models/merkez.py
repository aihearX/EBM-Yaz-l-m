from datetime import date

from sqlalchemy import JSON, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi

CM_DURUMLAR = [
    ("aday", "Aday"),
    ("fizibilite", "Fizibilite"),
    ("secildi", "Seçildi"),
    ("etik", "Etik Kurul"),
    ("sozlesme", "Sözleşme"),
    ("siv", "Başlatma Ziyareti"),
    ("aktif", "Aktif"),
    ("kayit_kapali", "Kayıt Kapalı"),
    ("kapali", "Kapalı"),
]
CM_DURUM_ETIKET = dict(CM_DURUMLAR)


class Merkez(Taban, ZamanDamgasi):
    __tablename__ = "merkez"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kod: Mapped[str] = mapped_column(String(16), unique=True)
    ad: Mapped[str] = mapped_column(String(200))
    sehir: Mapped[str] = mapped_column(String(60))
    kurum_tipi: Mapped[str] = mapped_column(String(40))  # universite | egitim_arastirma | sehir | ozel
    yatak_sayisi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    terapotik_alanlar: Mapped[list | None] = mapped_column(JSON, nullable=True)
    hbys: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fhir_uc_noktasi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notlar: Mapped[str | None] = mapped_column(Text, nullable=True)

    arastirmacilar = relationship("Arastirmaci", back_populates="merkez", cascade="all, delete-orphan")
    calismalar = relationship("CalismaMerkez", back_populates="merkez")


class Arastirmaci(Taban):
    __tablename__ = "arastirmaci"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merkez_id: Mapped[int] = mapped_column(ForeignKey("merkez.id"))
    ad_soyad: Mapped[str] = mapped_column(String(120))
    unvan: Mapped[str | None] = mapped_column(String(40), nullable=True)
    uzmanlik: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gcp_egitim_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    cv_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    tamamlanan_calisma: Mapped[int] = mapped_column(Integer, default=0)

    merkez = relationship("Merkez", back_populates="arastirmacilar")


class CalismaMerkez(Taban, ZamanDamgasi):
    __tablename__ = "calisma_merkez"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    merkez_id: Mapped[int] = mapped_column(ForeignKey("merkez.id"))
    bas_arastirmaci_id: Mapped[int | None] = mapped_column(ForeignKey("arastirmaci.id"), nullable=True)
    merkez_no: Mapped[str] = mapped_column(String(8))  # calisma icindeki merkez numarasi (01, 02...)
    durum: Mapped[str] = mapped_column(String(20), default="aday")
    hedef_hasta: Mapped[int] = mapped_column(Integer, default=0)
    secim_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    aktivasyon_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    ilk_hasta_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    fizibilite_puani: Mapped[float | None] = mapped_column(Float, nullable=True)
    tahmini_kazanim: Mapped[float | None] = mapped_column(Float, nullable=True)  # hasta/ay (model ciktisi)
    tahmin_alt: Mapped[float | None] = mapped_column(Float, nullable=True)
    tahmin_ust: Mapped[float | None] = mapped_column(Float, nullable=True)
    gecikme_riski: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1
    risk_puani: Mapped[float | None] = mapped_column(Float, nullable=True)  # RBM bilesik puan
    notlar: Mapped[str | None] = mapped_column(Text, nullable=True)

    calisma = relationship("Calisma", back_populates="merkezler")
    merkez = relationship("Merkez", back_populates="calismalar")
    bas_arastirmaci = relationship("Arastirmaci")
    kilometre_taslari = relationship("KilometreTasi", back_populates="calisma_merkez",
                                     cascade="all, delete-orphan", order_by="KilometreTasi.planlanan")
    gonulluler = relationship("Gonullu", back_populates="calisma_merkez")

    @property
    def durum_etiket(self) -> str:
        return CM_DURUM_ETIKET.get(self.durum, self.durum)


class KilometreTasi(Taban):
    __tablename__ = "kilometre_tasi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_merkez_id: Mapped[int] = mapped_column(ForeignKey("calisma_merkez.id"))
    tip: Mapped[str] = mapped_column(String(40))  # fizibilite, etik_onay, titck_onay, sozlesme, siv, ilk_hasta, son_hasta, kapanis
    planlanan: Mapped[date | None] = mapped_column(Date, nullable=True)
    gerceklesen: Mapped[date | None] = mapped_column(Date, nullable=True)

    calisma_merkez = relationship("CalismaMerkez", back_populates="kilometre_taslari")
