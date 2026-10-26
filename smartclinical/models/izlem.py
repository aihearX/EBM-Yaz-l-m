from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi, simdi

ZIYARET_TIP_ETIKET = {
    "SIV": "Başlatma ziyareti",
    "IMV": "Ara izlem ziyareti",
    "COV": "Kapanış ziyareti",
    "uzaktan": "Uzaktan izlem",
    "tetiklenmis": "Tetiklenmiş ziyaret",
}
ZIYARET_DURUM_ETIKET = {"planli": "Planlı", "yapildi": "Yapıldı", "raporlandi": "Rapor yazıldı", "onaylandi": "Rapor onaylı"}
# ziyaret kontrol listesi maddeleri; kontrol_listesi JSON'unda anahtar -> bool
ZIYARET_KONTROL = {
    "onam": "Onam formları eksiksiz ve güncel sürümde",
    "isf": "Araştırmacı dosyası (ISF) güncel",
    "ilac": "Araştırma ürünü muhasebesi uyumlu",
    "sapma": "Protokol sapmaları gözden geçirildi",
}
BULGU_ONEM_ETIKET = {"minor": "Minör", "major": "Majör", "kritik": "Kritik"}
SAPMA_ONEM_ETIKET = {"minor": "Minör", "major": "Majör"}

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
    sorumlu_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    hedef_tarih: Mapped[date | None] = mapped_column(Date, nullable=True)
    kapanis_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    kapali: Mapped[bool] = mapped_column(Boolean, default=False)

    calisma_merkez = relationship("CalismaMerkez")
    gonullu = relationship("Gonullu")
    sorumlu = relationship("Kullanici", foreign_keys=[sorumlu_id])

    @property
    def kategori_etiket(self) -> str:
        return SAPMA_KATEGORI.get(self.kategori, self.kategori)

    @property
    def onem_etiket(self) -> str:
        return SAPMA_ONEM_ETIKET.get(self.onem, self.onem)

    @property
    def durum_etiket(self) -> str:
        return "Kapalı" if self.kapali else "Açık"

    @property
    def etik_bildirim_gerekli(self) -> bool:
        return self.onem == "major"


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
    katilimcilar: Mapped[str | None] = mapped_column(Text, nullable=True)
    kontrol_listesi: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # ZIYARET_KONTROL anahtarlari -> bool
    onaylayan_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)

    calisma_merkez = relationship("CalismaMerkez")
    cra = relationship("Kullanici", foreign_keys=[cra_id])
    onaylayan = relationship("Kullanici", foreign_keys=[onaylayan_id])
    tetikleyen_uyari = relationship("RiskUyarisi", foreign_keys=[tetikleyen_uyari_id])

    @property
    def tip_etiket(self) -> str:
        return ZIYARET_TIP_ETIKET.get(self.tip, self.tip)

    @property
    def durum(self) -> str:
        if self.rapor_onay:
            return "onaylandi"
        if self.rapor:
            return "raporlandi"
        if self.gerceklesen:
            return "yapildi"
        return "planli"

    @property
    def durum_etiket(self) -> str:
        return ZIYARET_DURUM_ETIKET.get(self.durum, self.durum)

    @property
    def acik_bulgular(self) -> list[dict]:
        return [b for b in (self.bulgular or []) if not b.get("kapali")]


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
