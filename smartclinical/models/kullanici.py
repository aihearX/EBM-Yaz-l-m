import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi, simdi


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
    kurum: Mapped[str | None] = mapped_column(String(160), nullable=True)  # sponsor/CRO kullanicilari icin kurum adi
    kilit_bitis: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # sureli kilit; None = kilitli degil
    parola_gecmisi: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)  # son 5 hash
    # yonetici gecici parola belirledi: ilk giriste degistirilmesi zorunlu. Kullanicinin kendi sectigi
    # parolayla acilan hesaplarda (kurulum, komut satiri) False.
    ilk_giris_degisim: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    merkez = relationship("Merkez", foreign_keys=[merkez_id])

    @property
    def rol_etiket(self) -> str:
        return ROL_ETIKET.get(self.rol, self.rol.value)

    @property
    def kilitli(self) -> bool:
        return bool(self.kilit_bitis and self.kilit_bitis > simdi())


class ApiAnahtari(Taban):
    """Makine-makine entegrasyon anahtari. Ham anahtar yalnizca olusturulurken bir kez gosterilir;
    veritabaninda SHA-256 ozeti tutulur. Anahtar sahibinin rol izinleriyle sinirlidir."""

    __tablename__ = "api_anahtari"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kullanici_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"))
    ad: Mapped[str] = mapped_column(String(80))
    onek: Mapped[str] = mapped_column(String(12))  # tanimlama icin anahtarin ilk 8 karakteri
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    olusturma: Mapped[datetime] = mapped_column(DateTime, default=simdi)
    son_kullanim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    son_gecerlilik: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    kullanici = relationship("Kullanici")
