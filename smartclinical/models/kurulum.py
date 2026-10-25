from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Taban

MODLAR = [
    ("tekil", "Tekil araştırmacı"),
    ("universite", "Üniversite / hastane"),
    ("cro", "CRO / sponsor"),
]
MOD_ETIKET = dict(MODLAR)


class KurulumAyari(Taban):
    """Kurulum modu ve kurum varsayilanlari. Tek satir (id=1); ilk kurulumda yazilir, Ayarlar'dan degisir."""

    __tablename__ = "kurulum_ayari"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    mod: Mapped[str] = mapped_column(String(16), default="tekil")  # cro | tekil | universite
    kurum_adi: Mapped[str] = mapped_column(String(160), default="")
    varsayilan_merkez_id: Mapped[int | None] = mapped_column(ForeignKey("merkez.id"), nullable=True)
    varsayilan_sponsor: Mapped[str | None] = mapped_column(String(160), nullable=True)

    # sablonlar oturum kapandiktan sonra da okuyabilsin diye tek sorguda yuklenir
    varsayilan_merkez = relationship("Merkez", lazy="joined")

    @property
    def mod_etiket(self) -> str:
        return MOD_ETIKET.get(self.mod, self.mod)
