from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from ..db import Taban


class VizitTanimi(Taban):
    """Calisma bazinda vizit semasi. Gonullu randomize edildiginde Vizit kayitlari buradan uretilir.

    `gun` baslangic (randomizasyon) gunune gore; tarama vizitleri icin negatif.
    """

    __tablename__ = "vizit_tanimi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calisma_id: Mapped[int] = mapped_column(ForeignKey("calisma.id"))
    ad: Mapped[str] = mapped_column(String(40))
    sira: Mapped[int] = mapped_column(Integer, default=0)
    gun: Mapped[int] = mapped_column(Integer, default=0)
    pencere_gun: Mapped[int] = mapped_column(Integer, default=3)

    # iliski bu tarafta kuruldu; models/calisma.py'ye dokunulmadi
    calisma = relationship("Calisma", backref=backref("vizit_tanimlari", order_by="VizitTanimi.sira",
                                                      cascade="all, delete-orphan"))
