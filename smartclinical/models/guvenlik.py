from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi

SIDDET = {"1": "Hafif (Derece 1)", "2": "Orta (Derece 2)", "3": "Ağır (Derece 3)",
          "4": "Yaşamı tehdit eden (Derece 4)", "5": "Ölüm (Derece 5)"}
NEDENSELLIK = {"iliskisiz": "İlişkisiz", "olasi_degil": "Olası değil", "olasi": "Olası",
               "muhtemel": "Muhtemel", "kesin": "Kesin"}
CIDDIYET_OLCUTU = {"olum": "Ölüm", "yasam_tehdidi": "Yaşamı tehdit", "hastaneye_yatis": "Hastaneye yatış / uzama",
                   "sakatlik": "Kalıcı sakatlık", "konjenital": "Konjenital anomali", "tibbi_onemli": "Tıbbi açıdan önemli"}


class AdversOlay(Taban, ZamanDamgasi):
    __tablename__ = "advers_olay"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gonullu_id: Mapped[int] = mapped_column(ForeignKey("gonullu.id"))
    terim: Mapped[str] = mapped_column(String(200))
    meddra_pt: Mapped[str | None] = mapped_column(String(120), nullable=True)
    meddra_soc: Mapped[str | None] = mapped_column(String(120), nullable=True)
    baslangic: Mapped[date] = mapped_column(Date)
    bitis: Mapped[date | None] = mapped_column(Date, nullable=True)
    siddet: Mapped[str] = mapped_column(String(2), default="1")  # CTCAE derecesi
    nedensellik: Mapped[str] = mapped_column(String(16), default="olasi_degil")
    beklenen: Mapped[bool] = mapped_column(Boolean, default=True)  # SUSAR tespiti icin
    ciddi: Mapped[bool] = mapped_column(Boolean, default=False)
    ciddiyet_olcutu: Mapped[str | None] = mapped_column(String(24), nullable=True)
    sonuc: Mapped[str | None] = mapped_column(String(40), nullable=True)  # iyilesti | sekelle iyilesti | devam | olum
    alinan_onlem: Mapped[str | None] = mapped_column(String(60), nullable=True)  # doz azaltildi, kesildi...
    farkindalik_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)  # SAE icin sponsor farkindaligi
    sponsor_bildirim: Mapped[date | None] = mapped_column(Date, nullable=True)
    titck_bildirim: Mapped[date | None] = mapped_column(Date, nullable=True)
    etik_bildirim: Mapped[date | None] = mapped_column(Date, nullable=True)
    anlatim: Mapped[str | None] = mapped_column(Text, nullable=True)

    gonullu = relationship("Gonullu", back_populates="advers_olaylar")

    @property
    def susar(self) -> bool:
        return self.ciddi and not self.beklenen and self.nedensellik in ("olasi", "muhtemel", "kesin")

    @property
    def bildirim_suresi_gun(self) -> int | None:
        """TITCK'ya bildirim icin kalan/gecen sure. Olum veya yasam tehdidi: 7 gun, diger ciddi: 15 gun."""
        if not self.ciddi or not self.farkindalik_tarihi:
            return None
        limit = 7 if self.ciddiyet_olcutu in ("olum", "yasam_tehdidi") else 15
        son = self.titck_bildirim or date.today()
        return limit - (son - self.farkindalik_tarihi).days

    @property
    def siddet_etiket(self) -> str:
        return SIDDET.get(self.siddet, self.siddet)

    @property
    def nedensellik_etiket(self) -> str:
        return NEDENSELLIK.get(self.nedensellik, self.nedensellik)
