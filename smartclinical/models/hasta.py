import enum
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi, simdi


class Hasta(Taban, ZamanDamgasi):
    """HBYS'den alinan, kimliksizlestirilmis hasta kaydi.

    Kimlik bilgisi tutulmaz; `kayit_no` merkez tarafinda tutulan anahtar listesiyle
    eslesen takma addir (pseudonym). Serbest metinler kimliksizlestirme modulunden
    gecmeden bu tabloya yazilamaz (bkz. services/kimliksizlestirme).
    """

    __tablename__ = "hasta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merkez_id: Mapped[int] = mapped_column(ForeignKey("merkez.id"))
    kayit_no: Mapped[str] = mapped_column(String(40), index=True)
    dogum_yili: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cinsiyet: Mapped[str | None] = mapped_column(String(1), nullable=True)  # K | E
    tanilar: Mapped[list | None] = mapped_column(JSON, nullable=True)   # [{"icd10": "C50.9", "ad": "...", "tarih": "..."}]
    ilaclar: Mapped[list | None] = mapped_column(JSON, nullable=True)   # [{"atc": "...", "ad": "...", "aktif": true}]
    laboratuvar: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{"loinc": "...", "ad": "...", "deger": .., "birim": "", "tarih": ""}]
    vitaller: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    performans: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # ECOG, NYHA vb.
    metinler: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{"tur": "epikriz", "tarih": "", "metin": "..."}]
    kaynak: Mapped[str | None] = mapped_column(String(40), nullable=True)  # hbys-fhir | manuel | csv
    son_senkron: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    merkez = relationship("Merkez")

    @property
    def yas(self) -> int | None:
        if not self.dogum_yili:
            return None
        return date.today().year - self.dogum_yili


class GonulluDurumu(str, enum.Enum):
    ADAY = "aday"
    ON_TARAMA = "on_tarama"
    ONAM = "onam"
    TARAMA = "tarama"
    TARAMA_BASARISIZ = "tarama_basarisiz"
    RANDOMIZE = "randomize"
    TEDAVIDE = "tedavide"
    TAKIPTE = "takipte"
    TAMAMLADI = "tamamladi"
    AYRILDI = "ayrildi"


GD_ETIKET = {
    GonulluDurumu.ADAY: "Aday",
    GonulluDurumu.ON_TARAMA: "Ön Tarama",
    GonulluDurumu.ONAM: "Onam Alındı",
    GonulluDurumu.TARAMA: "Tarama",
    GonulluDurumu.TARAMA_BASARISIZ: "Tarama Başarısız",
    GonulluDurumu.RANDOMIZE: "Randomize",
    GonulluDurumu.TEDAVIDE: "Tedavide",
    GonulluDurumu.TAKIPTE: "Takipte",
    GonulluDurumu.TAMAMLADI: "Tamamladı",
    GonulluDurumu.AYRILDI: "Ayrıldı",
}


class Gonullu(Taban, ZamanDamgasi):
    __tablename__ = "gonullu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    calisma_merkez_id: Mapped[int] = mapped_column(ForeignKey("calisma_merkez.id"))
    hasta_id: Mapped[int | None] = mapped_column(ForeignKey("hasta.id"), nullable=True)
    gonullu_no: Mapped[str] = mapped_column(String(16), index=True)  # 01-003 gibi
    durum: Mapped[GonulluDurumu] = mapped_column(Enum(GonulluDurumu), default=GonulluDurumu.ADAY)
    kol_id: Mapped[int | None] = mapped_column(ForeignKey("kol.id"), nullable=True)
    onam_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    onam_versiyonu: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tarama_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    randomizasyon_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    bitis_tarihi: Mapped[date | None] = mapped_column(Date, nullable=True)
    ayrilma_nedeni: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tarama_basarisizlik_nedeni: Mapped[str | None] = mapped_column(String(200), nullable=True)

    calisma = relationship("Calisma", back_populates="gonulluler")
    calisma_merkez = relationship("CalismaMerkez", back_populates="gonulluler")
    hasta = relationship("Hasta")
    kol = relationship("Kol")
    vizitler = relationship("Vizit", back_populates="gonullu", cascade="all, delete-orphan", order_by="Vizit.planlanan")
    form_kayitlari = relationship("FormKaydi", back_populates="gonullu", cascade="all, delete-orphan")
    advers_olaylar = relationship("AdversOlay", back_populates="gonullu", cascade="all, delete-orphan")

    @property
    def durum_etiket(self) -> str:
        return GD_ETIKET.get(self.durum, self.durum.value)


class Vizit(Taban):
    __tablename__ = "vizit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gonullu_id: Mapped[int] = mapped_column(ForeignKey("gonullu.id"))
    ad: Mapped[str] = mapped_column(String(40))  # Tarama, V1, V2, ... , Çalışma Sonu
    sira: Mapped[int] = mapped_column(Integer, default=0)
    planlanan: Mapped[date | None] = mapped_column(Date, nullable=True)
    pencere_gun: Mapped[int] = mapped_column(Integer, default=3)
    gerceklesen: Mapped[date | None] = mapped_column(Date, nullable=True)
    durum: Mapped[str] = mapped_column(String(16), default="planli")  # planli | yapildi | kacirildi | pencere_disi

    gonullu = relationship("Gonullu", back_populates="vizitler")

    @property
    def pencere_disi(self) -> bool:
        if not (self.planlanan and self.gerceklesen):
            return False
        return abs((self.gerceklesen - self.planlanan).days) > self.pencere_gun


class EslestirmeSonucu(Taban):
    """Protokol-hasta eslestirme motorunun ciktisi. Her oneri kaynak cumleyle gerekcelendirilir."""

    __tablename__ = "eslestirme_sonucu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    hasta_id: Mapped[int] = mapped_column(ForeignKey("hasta.id"))
    skor: Mapped[float] = mapped_column(Float)  # 0-1
    karar: Mapped[str] = mapped_column(String(16))  # uygun | olasi | uygun_degil | belirsiz
    kriter_sonuclari: Mapped[list] = mapped_column(JSON)  # [{"kriter_id", "sonuc", "kanit", "guven"}]
    belirsiz_sayisi: Mapped[int] = mapped_column(Integer, default=0)
    model_surumu: Mapped[str] = mapped_column(String(60))
    sure_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    olusturma: Mapped[datetime] = mapped_column(DateTime, default=simdi)
    inceleyen_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)
    inceleme_karari: Mapped[str | None] = mapped_column(String(16), nullable=True)  # onay | red | beklet
    inceleme_notu: Mapped[str | None] = mapped_column(Text, nullable=True)
    inceleme_zamani: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    golge_mod: Mapped[bool] = mapped_column(Boolean, default=False)  # pilot: manuel taramayla karsilastirma

    calisma = relationship("Calisma")
    hasta = relationship("Hasta")
    inceleyen = relationship("Kullanici")
