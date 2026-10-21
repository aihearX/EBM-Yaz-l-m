from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import simdi

# DIA TMF Referans Modeli v3.x bolgeleri (kisaltilmis)
TMF_BOLGELER = {
    "01": "Çalışma Yönetimi",
    "02": "Merkezi Çalışma Belgeleri",
    "03": "Düzenleyici",
    "04": "Etik Kurul",
    "05": "Merkez Yönetimi",
    "06": "Araştırma Ürünü ve Çalışma Malzemeleri",
    "07": "Güvenlik Raporlama",
    "08": "Merkezi ve Lokal Test",
    "09": "Üçüncü Taraflar",
    "10": "Veri Yönetimi",
    "11": "İstatistik",
}


class Belge(Taban):
    __tablename__ = "belge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    merkez_id: Mapped[int | None] = mapped_column(ForeignKey("merkez.id"), nullable=True)
    tmf_bolge: Mapped[str] = mapped_column(String(2))
    ad: Mapped[str] = mapped_column(String(200))
    dosya_adi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dosya_yolu: Mapped[str | None] = mapped_column(String(400), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    versiyon: Mapped[str] = mapped_column(String(8), default="1.0")
    durum: Mapped[str] = mapped_column(String(12), default="taslak")  # taslak | onayli | eskimis
    yukleyen_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    yukleme: Mapped[datetime] = mapped_column(DateTime, default=simdi)
    son_gecerlilik: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)

    calisma = relationship("Calisma")
    merkez = relationship("Merkez")
    yukleyen = relationship("Kullanici")

    @property
    def bolge_etiket(self) -> str:
        return f"{self.tmf_bolge} - {TMF_BOLGELER.get(self.tmf_bolge, '?')}"
