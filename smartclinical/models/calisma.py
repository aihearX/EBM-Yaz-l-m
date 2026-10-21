import enum
from datetime import date

from sqlalchemy import JSON, Date, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban
from ._ortak import ZamanDamgasi


class CalismaTuru(str, enum.Enum):
    ILAC = "ilac"
    BIYOBENZER = "biyobenzer"
    TIBBI_CIHAZ = "tibbi_cihaz"
    IVD = "tani_kiti"          # in vitro tani
    GOZLEMSEL = "gozlemsel"
    AKADEMIK = "akademik"       # arastirmaci baslatimli
    BIYOESDEGERLIK = "biyoesdegerlik"
    ILERI_TEDAVI = "ileri_tedavi"  # hucre/gen tedavisi
    KAYIT = "kayit"             # registry / RWE


TUR_ETIKET = {
    CalismaTuru.ILAC: "İlaç",
    CalismaTuru.BIYOBENZER: "Biyobenzer",
    CalismaTuru.TIBBI_CIHAZ: "Tıbbi Cihaz",
    CalismaTuru.IVD: "In Vitro Tanı Kiti",
    CalismaTuru.GOZLEMSEL: "Gözlemsel",
    CalismaTuru.AKADEMIK: "Araştırmacı Başlatımlı",
    CalismaTuru.BIYOESDEGERLIK: "Biyoeşdeğerlik",
    CalismaTuru.ILERI_TEDAVI: "İleri Tedavi (ATMP)",
    CalismaTuru.KAYIT: "Kayıt / Gerçek Yaşam Verisi",
}


class CalismaDurumu(str, enum.Enum):
    TASARIM = "tasarim"
    FIZIBILITE = "fizibilite"
    BASVURU = "basvuru"
    AKTIVASYON = "aktivasyon"
    KAYIT = "kayit"
    IZLEM = "izlem"
    KAPANIS = "kapanis"
    ANALIZ = "analiz"
    ARSIV = "arsiv"


DURUM_ETIKET = {
    CalismaDurumu.TASARIM: "Tasarım",
    CalismaDurumu.FIZIBILITE: "Fizibilite",
    CalismaDurumu.BASVURU: "Etik / TİTCK Başvurusu",
    CalismaDurumu.AKTIVASYON: "Merkez Aktivasyonu",
    CalismaDurumu.KAYIT: "Hasta Kaydı",
    CalismaDurumu.IZLEM: "İzlem",
    CalismaDurumu.KAPANIS: "Kapanış",
    CalismaDurumu.ANALIZ: "Analiz ve Raporlama",
    CalismaDurumu.ARSIV: "Arşiv",
}

# Yasam dongusu sirasi - ilerleme cubugu ve kontrol listeleri icin
DURUM_SIRASI = list(CalismaDurumu)


class Calisma(Taban, ZamanDamgasi):
    __tablename__ = "calisma"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kod: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    baslik: Mapped[str] = mapped_column(Text)
    kisa_ad: Mapped[str] = mapped_column(String(80))
    tur: Mapped[CalismaTuru] = mapped_column(Enum(CalismaTuru))
    faz: Mapped[str | None] = mapped_column(String(16), nullable=True)  # I, II, III, IV, pilot, pivotal...
    tasarim: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sponsor: Mapped[str] = mapped_column(String(160))
    terapotik_alan: Mapped[str] = mapped_column(String(80))
    endikasyon: Mapped[str | None] = mapped_column(String(200), nullable=True)
    durum: Mapped[CalismaDurumu] = mapped_column(Enum(CalismaDurumu), default=CalismaDurumu.TASARIM)
    hedef_hasta: Mapped[int] = mapped_column(Integer, default=0)
    hedef_merkez: Mapped[int] = mapped_column(Integer, default=0)
    baslangic: Mapped[date | None] = mapped_column(Date, nullable=True)
    planlanan_bitis: Mapped[date | None] = mapped_column(Date, nullable=True)
    ct_gov_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    eudract_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_sinifi: Mapped[str | None] = mapped_column(String(16), nullable=True)  # dusuk/orta/yuksek (RBM)
    notlar: Mapped[str | None] = mapped_column(Text, nullable=True)

    versiyonlar = relationship("ProtokolVersiyon", back_populates="calisma", cascade="all, delete-orphan",
                               order_by="ProtokolVersiyon.id")
    kriterler = relationship("Kriter", back_populates="calisma", cascade="all, delete-orphan",
                             order_by="Kriter.sira")
    kollar = relationship("Kol", back_populates="calisma", cascade="all, delete-orphan")
    merkezler = relationship("CalismaMerkez", back_populates="calisma", cascade="all, delete-orphan")
    basvurular = relationship("Basvuru", back_populates="calisma", cascade="all, delete-orphan")
    gonulluler = relationship("Gonullu", back_populates="calisma", cascade="all, delete-orphan")
    formlar = relationship("Form", back_populates="calisma", cascade="all, delete-orphan")

    @property
    def tur_etiket(self) -> str:
        return TUR_ETIKET.get(self.tur, self.tur.value)

    @property
    def durum_etiket(self) -> str:
        return DURUM_ETIKET.get(self.durum, self.durum.value)

    @property
    def durum_indeks(self) -> int:
        return DURUM_SIRASI.index(self.durum)


class ProtokolVersiyon(Taban):
    __tablename__ = "protokol_versiyon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    versiyon: Mapped[str] = mapped_column(String(16))
    tarih: Mapped[date] = mapped_column(Date)
    ozet: Mapped[str | None] = mapped_column(Text, nullable=True)
    degisiklik_notu: Mapped[str | None] = mapped_column(Text, nullable=True)
    metin: Mapped[str | None] = mapped_column(Text, nullable=True)  # protokol tam metni (kriter cikarimi icin)

    calisma = relationship("Calisma", back_populates="versiyonlar")


class Kriter(Taban):
    """Dahil etme / haric tutma kriteri.

    `yapisal` alani BDM veya kural motoru tarafindan uretilen hesaplanabilir sorgudur
    (bkz. services/kriter). `guven` modelin kendi tahminine verdigi guven; dusukse
    arastirmaci onayina dusuyor.
    """

    __tablename__ = "kriter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    tip: Mapped[str] = mapped_column(String(8))  # dahil | haric
    sira: Mapped[int] = mapped_column(Integer, default=0)
    metin: Mapped[str] = mapped_column(Text)
    yapisal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    guven: Mapped[float | None] = mapped_column(Float, nullable=True)
    onaylandi: Mapped[bool] = mapped_column(Integer, default=False)
    onaylayan_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), nullable=True)

    calisma = relationship("Calisma", back_populates="kriterler")


class Kol(Taban):
    __tablename__ = "kol"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    ad: Mapped[str] = mapped_column(String(80))
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)
    oran: Mapped[int] = mapped_column(Integer, default=1)  # randomizasyon orani

    calisma = relationship("Calisma", back_populates="kollar")
