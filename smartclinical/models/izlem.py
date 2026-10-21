from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi, simdi

SAPMA_KATEGORI = {
    "onam": "Bilgilendirilmiş onam",
    "uygunluk": "Dahil/hariç kriteri",
    "vizit": "Vizit penceresi",
    "ilac": "Araştırma ürünü / doz",
    "prosedur": "Protokol prosedürü",
    "guvenlik": "Güvenlik bildirimi",
    "belge": "Kaynak belge / kayıt",
    "diger": "Diğer",
}


class ProtokolSapmasi(Taban, ZamanDamgasi):
    __tablename__ = "protokol_sapmasi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_merkez_id: Mapped[int] = mapped_column(ForeignKey("calisma_merkez.id"))
    gonullu_id: Mapped[int | None] = mapped_column(ForeignKey("gonullu.id"), nullable=True)
    tarih: Mapped[date] = mapped_column(Date)
    kategori: Mapped[str] = mapped_column(String(20))
    onem: Mapped[str] = mapped_column(String(8), default="minor")  # minor | major
    aciklama: Mapped[str] = mapped_column(Text)
    kok_neden: Mapped[str | None] = mapped_column(Text, nullable=True)
    duzeltici_faaliyet: Mapped[str | None] = mapped_column(Text, nullable=True)
    etik_bildirim: Mapped[date | None] = mapped_column(Date, nullable=True)
    kapali: Mapped[bool] = mapped_column(Boolean, default=False)

    calisma_merkez = relationship("CalismaMerkez")
    gonullu = relationship("Gonullu")

    @property
    def kategori_etiket(self) -> str:
        return SAPMA_KATEGORI.get(self.kategori, self.kategori)


class IzlemZiyareti(Taban, ZamanDamgasi):
    __tablename__ = "izlem_ziyareti"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_merkez_id: Mapped[int] = mapped_column(ForeignKey("calisma_merkez.id"))
    cra_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    tip: Mapped[str] = mapped_column(String(12))  # SIV | IMV | COV | uzaktan | tetiklenmis
    planlanan: Mapped[date | None] = mapped_column(Date, nullable=True)
    gerceklesen: Mapped[date | None] = mapped_column(Date, nullable=True)
    sdv_orani: Mapped[float | None] = mapped_column(Float, nullable=True)
    bulgular: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{"konu", "onem", "aksiyon", "kapali"}]
    rapor: Mapped[str | None] = mapped_column(Text, nullable=True)
    rapor_onay: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tetikleyen_uyari_id: Mapped[int | None] = mapped_column(ForeignKey("risk_uyarisi.id"), nullable=True)

    calisma_merkez = relationship("CalismaMerkez")
    cra = relationship("Kullanici")


class RiskGostergesi(Taban):
    """Anahtar Risk Gostergesi (KRI) tanimi. ICH E6(R3) Bolum 3.10 ile uyumlu."""

    __tablename__ = "risk_gostergesi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int | None] = mapped_column(ForeignKey("calisma.id"), nullable=True)  # None -> genel sablon
    kod: Mapped[str] = mapped_column(String(24))
    ad: Mapped[str] = mapped_column(String(120))
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)
    hesaplama: Mapped[str] = mapped_column(String(40))  # services/rbm icindeki fonksiyon adi
    birim: Mapped[str | None] = mapped_column(String(16), nullable=True)
    yon: Mapped[str] = mapped_column(String(8), default="yuksek")  # yuksek=kotu | dusuk=kotu
    esik_uyari: Mapped[float | None] = mapped_column(Float, nullable=True)
    esik_aksiyon: Mapped[float | None] = mapped_column(Float, nullable=True)
    agirlik: Mapped[float] = mapped_column(Float, default=1.0)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)


class KaliteToleransLimiti(Taban):
    """Kalite Tolerans Limiti (QTL) - calisma duzeyinde, ICH E6(R2/R3)."""

    __tablename__ = "kalite_tolerans_limiti"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    parametre: Mapped[str] = mapped_column(String(120))
    hesaplama: Mapped[str] = mapped_column(String(40))
    limit: Mapped[float] = mapped_column(Float)
    ikincil_limit: Mapped[float | None] = mapped_column(Float, nullable=True)  # erken uyari esigi
    birim: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gerekce: Mapped[str | None] = mapped_column(Text, nullable=True)
    mevcut_deger: Mapped[float | None] = mapped_column(Float, nullable=True)
    son_hesaplama: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    calisma = relationship("Calisma")

    @property
    def asildi(self) -> bool:
        return self.mevcut_deger is not None and self.mevcut_deger > self.limit


class RiskUyarisi(Taban):
    __tablename__ = "risk_uyarisi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    calisma_merkez_id: Mapped[int | None] = mapped_column(ForeignKey("calisma_merkez.id"), nullable=True)
    kri_kod: Mapped[str] = mapped_column(String(24))
    deger: Mapped[float | None] = mapped_column(Float, nullable=True)
    esik: Mapped[float | None] = mapped_column(Float, nullable=True)
    seviye: Mapped[str] = mapped_column(String(8))  # bilgi | uyari | aksiyon
    mesaj: Mapped[str] = mapped_column(Text)
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)  # aciklanabilirlik: neden tetiklendi
    olusturma: Mapped[datetime] = mapped_column(DateTime, default=simdi)
    durum: Mapped[str] = mapped_column(String(12), default="acik")  # acik | inceleniyor | kapandi | yanlis_alarm
    atanan_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    kapanis_notu: Mapped[str | None] = mapped_column(Text, nullable=True)
    kapanis: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    calisma = relationship("Calisma")
    calisma_merkez = relationship("CalismaMerkez")
    atanan = relationship("Kullanici")
