from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi

KURUMLAR = {
    "etik_kurul": "Etik Kurul",
    "titck": "TİTCK",
    "kurum_izni": "Kurum İzni",
    "sb_izin": "Sağlık Bakanlığı Bilimsel Araştırma İzni",
    "kvkk": "KVKK / Veri Sorumlusu",
}
BASVURU_TIPLERI = {
    "ilk": "İlk Başvuru",
    "degisiklik": "Önemli Değişiklik",
    "yillik": "Yıllık Bildirim",
    "guvenlik": "Güvenlik Bildirimi",
    "sapma": "Sapma Bildirimi",
    "sonlandirma": "Sonlandırma Bildirimi",
}


class Basvuru(Taban, ZamanDamgasi):
    __tablename__ = "basvuru"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    merkez_id: Mapped[int | None] = mapped_column(ForeignKey("merkez.id"), nullable=True)
    kurum: Mapped[str] = mapped_column(String(20))
    tip: Mapped[str] = mapped_column(String(20), default="ilk")
    referans_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gonderim_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    eksik_bildirim_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    karar_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    karar: Mapped[str] = mapped_column(String(20), default="beklemede")  # beklemede | onay | sartli_onay | red | geri_cekildi
    notlar: Mapped[str | None] = mapped_column(Text, nullable=True)

    calisma = relationship("Calisma", back_populates="basvurular")
    merkez = relationship("Merkez")

    @property
    def kurum_etiket(self) -> str:
        return KURUMLAR.get(self.kurum, self.kurum)

    @property
    def tip_etiket(self) -> str:
        return BASVURU_TIPLERI.get(self.tip, self.tip)

    @property
    def sure_gun(self) -> int | None:
        if not self.gonderim_tarihi:
            return None
        son = self.karar_tarihi or date.today()
        return (son - self.gonderim_tarihi).days
