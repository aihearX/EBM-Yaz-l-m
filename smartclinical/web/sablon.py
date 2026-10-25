from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from .. import __version__
from ..models.calisma import DURUM_ETIKET, DURUM_SIRASI, TUR_ETIKET
from ..models.kullanici import ROL_ETIKET
from ..models.kurulum import MOD_ETIKET, KurulumAyari
from ..services.yetki import izinli

sablonlar = Jinja2Templates(directory=Path(__file__).parent / "templates")


def tarih(v, bicim="%d.%m.%Y"):
    if not v:
        return "—"
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v)
        except ValueError:
            return v
    if isinstance(v, datetime):
        return v.strftime(bicim + " %H:%M") if bicim == "%d.%m.%Y" and v.time() != datetime.min.time() else v.strftime(bicim)
    if isinstance(v, date):
        return v.strftime(bicim)
    return str(v)


def yuzde(v, basamak=0):
    if v is None:
        return "—"
    return f"%{v:.{basamak}f}".replace(".", ",")


def sayi(v, basamak=1):
    if v is None:
        return "—"
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    return f"{v:.{basamak}f}".replace(".", ",")


def gun_farki(v):
    if not v:
        return None
    if isinstance(v, datetime):
        v = v.date()
    return (date.today() - v).days


sablonlar.env.filters.update({"tarih": tarih, "yuzde": yuzde, "sayi": sayi, "gun_farki": gun_farki})
sablonlar.env.globals.update({
    "surum": __version__,
    "izinli": izinli,
    "DURUM_ETIKET": DURUM_ETIKET,
    "DURUM_SIRASI": DURUM_SIRASI,
    "TUR_ETIKET": TUR_ETIKET,
    "ROL_ETIKET": ROL_ETIKET,
    "MOD_ETIKET": MOD_ETIKET,
    "bugun": date.today,
    # goster() disinda render edilen sayfalar (hata.html) icin gecici varsayilan; goster istek basina gercegini koyar
    "kurulum": KurulumAyari(id=1, mod="tekil", kurum_adi=""),
})


def kurulum_ayari(request) -> KurulumAyari:
    """Istek basina bir sorgu: mod ve kurum varsayilanlari request.state'te saklanir."""
    a = getattr(request.state, "kurulum", None)
    if a is None:
        from ..db import oturum_fabrikasi
        from ..services.kurulum import ayar_getir

        db = oturum_fabrikasi()()
        try:
            a = ayar_getir(db)
        finally:
            db.close()
        request.state.kurulum = a
    return a


def goster(request, ad: str, **baglam):
    baglam.setdefault("kullanici", getattr(request.state, "kullanici", None))
    baglam.setdefault("mesaj", request.session.pop("mesaj", None) if hasattr(request, "session") else None)
    baglam.setdefault("kurulum", kurulum_ayari(request))
    return sablonlar.TemplateResponse(request, ad, baglam)
