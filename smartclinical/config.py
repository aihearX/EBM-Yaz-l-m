import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

KOK_DIZIN = Path(__file__).resolve().parent.parent


def _env(ad: str, varsayilan: str = "") -> str:
    return os.environ.get(ad, varsayilan)


class Ayarlar(BaseModel):
    ortam: str = "gelistirme"
    secret_key: str = "gelistirme-anahtari-uretimde-degistir"
    db_url: str = f"sqlite:///{KOK_DIZIN / 'veri' / 'smartclinical.db'}"
    oturum_suresi_dk: int = 30

    bdm_saglayici: str = "kural"
    bdm_url: str = "http://localhost:11434"
    bdm_model: str = "ebm-klinik-tr-7b-q4"
    bdm_zaman_asimi_sn: int = 60

    gomme_model: str = "ebm-klinik-tr-embed-v2"
    gomme_url: str = "http://localhost:8081"

    dosya_dizini: Path = KOK_DIZIN / "yuklemeler"

    fhir_sunucu_url: str = ""
    fhir_token: str = ""

    parola_min: int = 12
    parola_gun: int = 90
    takma_ad_anahtari: str = ""

    @property
    def uretim(self) -> bool:
        return self.ortam == "uretim"


@lru_cache
def ayarlar() -> Ayarlar:
    # .env dosyasini elle okuyoruz; python-dotenv bagimliligi eklemek istemedik
    env_dosya = KOK_DIZIN / ".env"
    if env_dosya.exists():
        for satir in env_dosya.read_text(encoding="utf-8").splitlines():
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            k, v = satir.split("=", 1)
            v = v.split("#", 1)[0].strip()
            os.environ.setdefault(k.strip(), v)

    a = Ayarlar(
        ortam=_env("SC_ORTAM", "gelistirme"),
        secret_key=_env("SC_SECRET_KEY", "gelistirme-anahtari-uretimde-degistir"),
        db_url=_env("SC_DB_URL", f"sqlite:///{KOK_DIZIN / 'veri' / 'smartclinical.db'}"),
        oturum_suresi_dk=int(_env("SC_OTURUM_SURESI_DK", "30")),
        bdm_saglayici=_env("SC_BDM_SAGLAYICI", "kural"),
        bdm_url=_env("SC_BDM_URL", "http://localhost:11434"),
        bdm_model=_env("SC_BDM_MODEL", "ebm-klinik-tr-7b-q4"),
        bdm_zaman_asimi_sn=int(_env("SC_BDM_ZAMAN_ASIMI_SN", "60")),
        gomme_model=_env("SC_GOMME_MODEL", "ebm-klinik-tr-embed-v2"),
        gomme_url=_env("SC_GOMME_URL", "http://localhost:8081"),
        dosya_dizini=Path(_env("SC_DOSYA_DIZINI", str(KOK_DIZIN / "yuklemeler"))),
        fhir_sunucu_url=_env("SC_FHIR_SUNUCU_URL", ""),
        fhir_token=_env("SC_FHIR_TOKEN", ""),
        parola_min=int(_env("SC_PAROLA_MIN", "12")),
        parola_gun=int(_env("SC_PAROLA_GUN", "90")),
        takma_ad_anahtari=_env("SC_TAKMA_AD_ANAHTARI", ""),
    )
    if a.uretim and a.secret_key.startswith("gelistirme-"):
        raise RuntimeError("Uretim ortaminda SC_SECRET_KEY tanimlanmali")
    if a.uretim and not a.takma_ad_anahtari:
        raise RuntimeError("Uretim ortaminda SC_TAKMA_AD_ANAHTARI tanimlanmali")
    return a
