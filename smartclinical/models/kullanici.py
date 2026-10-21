import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi


class Rol(str, enum.Enum):
    YONETICI = "yonetici"
    SPONSOR = "sponsor"
    PROJE_YONETICISI = "proje_yoneticisi"
    CRA = "cra"
    ARASTIRMACI = "arastirmaci"
    KOORDINATOR = "koordinator"
    VERI_YONETICISI = "veri_yoneticisi"
    ISTATISTIKCI = "istatistikci"
    FARMAKOVIJILANS = "farmakovijilans"
    DENETCI = "denetci"  # sadece okuma + denetim izi


ROL_ETIKET = {
    Rol.YONETICI: "Sistem Yöneticisi",
    Rol.SPONSOR: "Sponsor",
    Rol.PROJE_YONETICISI: "Proje Yöneticisi",
    Rol.CRA: "Klinik Araştırma Uzmanı (CRA)",
    Rol.ARASTIRMACI: "Araştırmacı",
    Rol.KOORDINATOR: "Çalışma Koordinatörü",
    Rol.VERI_YONETICISI: "Veri Yöneticisi",
    Rol.ISTATISTIKCI: "Biyoistatistikçi",
    Rol.FARMAKOVIJILANS: "Farmakovijilans",
    Rol.DENETCI: "Denetçi / Gözlemci",
}


class Kullanici(Taban, ZamanDamgasi):
    __tablename__ = "kullanici"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kullanici_adi: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ad_soyad: Mapped[str] = mapped_column(String(120))
    eposta: Mapped[str] = mapped_column(String(160), unique=True)
    parola_hash: Mapped[str] = mapped_column(String(256))
    rol: Mapped[Rol] = mapped_column(Enum(Rol), default=Rol.ARASTIRMACI)
    merkez_id: Mapped[int | None] = mapped_column(ForeignKey("merkez.id"), nullable=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    son_giris: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hatali_giris: Mapped[int] = mapped_column(Integer, default=0)
    parola_degisim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    merkez = relationship("Merkez", foreign_keys=[merkez_id])

    @property
    def rol_etiket(self) -> str:
        return ROL_ETIKET.get(self.rol, self.rol.value)
