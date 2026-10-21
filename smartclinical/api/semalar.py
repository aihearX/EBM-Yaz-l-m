from datetime import datetime

from pydantic import BaseModel, Field


class CalismaOzet(BaseModel):
    id: int
    kod: str
    kisa_ad: str
    tur: str
    faz: str | None
    sponsor: str
    durum: str
    hedef_hasta: int
    kayitli: int
    aktif_merkez: int


class KriterGirdi(BaseModel):
    tip: str = Field(pattern="^(dahil|haric)$")
    metin: str


class KriterCikti(BaseModel):
    id: int
    tip: str
    sira: int
    metin: str
    yapisal: dict | None
    guven: float | None
    onaylandi: bool


class EslestirmeIstek(BaseModel):
    merkez_id: int | None = None
    limit: int = 500
    golge_mod: bool = False


class EslestirmeOzet(BaseModel):
    taranan: int
    uygun: int
    olasi: int
    belirsiz: int
    uygun_degil: int
    sure_sn: float
    model: str


class KimliksizlestirmeIstek(BaseModel):
    metin: str
    mod: str = "maske"


class KimliksizlestirmeCikti(BaseModel):
    metin: str
    istatistik: dict
    uyarilar: list[str]


class KriterYapilandirIstek(BaseModel):
    metin: str
    tip: str = "dahil"


class UyariCikti(BaseModel):
    id: int
    kri_kod: str
    seviye: str
    mesaj: str
    deger: float | None
    esik: float | None
    durum: str
    merkez: str | None
    olusturma: datetime


class HastaGirdi(BaseModel):
    merkez_id: int
    kayit_no: str
    dogum_yili: int | None = None
    cinsiyet: str | None = None
    tanilar: list[dict] = []
    ilaclar: list[dict] = []
    laboratuvar: list[dict] = []
    performans: dict | None = None
    metinler: list[dict] = []
