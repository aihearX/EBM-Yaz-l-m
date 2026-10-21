from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


def simdi() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ZamanDamgasi:
    olusturma: Mapped[datetime] = mapped_column(DateTime, default=simdi, nullable=False)
    guncelleme: Mapped[datetime] = mapped_column(DateTime, default=simdi, onupdate=simdi, nullable=False)
