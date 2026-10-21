from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import ayarlar


class Taban(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def motor():
    global _engine, _SessionLocal
    if _engine is None:
        url = ayarlar().db_url
        if url.startswith("sqlite"):
            yol = url.replace("sqlite:///", "")
            if yol != ":memory:":
                Path(yol).parent.mkdir(parents=True, exist_ok=True)
            if yol == ":memory:":
                # testler: tum thread'ler ayni baglantiyi paylassin, yoksa her thread bos bir DB gorur
                _engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
            else:
                _engine = create_engine(url, connect_args={"check_same_thread": False})

            @event.listens_for(_engine, "connect")
            def _sqlite_pragma(dbapi_conn, _):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        else:
            _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def oturum_fabrikasi():
    motor()
    return _SessionLocal


def get_db():
    db: Session = oturum_fabrikasi()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_oturumu():
    db: Session = oturum_fabrikasi()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def tablolari_olustur():
    from . import models  # noqa: F401  (modelleri kaydet)

    Taban.metadata.create_all(motor())


def sifirla():
    """Sadece gelistirme/test icin. Uretimde Alembic ile migrasyon kullanilir."""
    from . import models  # noqa: F401

    Taban.metadata.drop_all(motor())
    Taban.metadata.create_all(motor())
