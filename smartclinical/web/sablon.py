import json
from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from .. import __version__
from ..models.calisma import DURUM_ETIKET, DURUM_SIRASI, TUR_ETIKET
from ..models.kullanici import ROL_ETIKET
from ..models.kurulum import MOD_ETIKET, KurulumAyari
from ..services.kriter.okunur import kriter_cumlesi
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


def json_tr(v, girinti=1):
    """Turkce karakterleri kacirmadan JSON; <pre> icinde okunur."""
    return json.dumps(v, ensure_ascii=False, indent=girinti, default=str)


class _KurulumVekili:
    """goster() disinda render edilen sayfalar (hata.html) icin: her erisimde gercek ayari okur.

    Istek nesnesi olmadan da dogru modu verir; veritabanina ulasilamazsa tekil mod varsayilir.
    """

    def __getattr__(self, ad):
        try:
            from ..db import oturum_fabrikasi
            from ..services.kurulum import ayar_getir

            db = oturum_fabrikasi()()
            try:
                a = ayar_getir(db)
                return getattr(a, ad)
            finally:
                db.close()
        except Exception:
            return getattr(KurulumAyari(id=1, mod="tekil", kurum_adi=""), ad)


sablonlar.env.filters.update({"tarih": tarih, "yuzde": yuzde, "sayi": sayi, "gun_farki": gun_farki, "json_tr": json_tr})
sablonlar.env.globals.update({
    "surum": __version__,  # yalnizca yonetim/sistem.html ve fizibilite raporu kullanir
    "izinli": izinli,
    "kriter_cumlesi": kriter_cumlesi,
    "DURUM_ETIKET": DURUM_ETIKET,
    "DURUM_SIRASI": DURUM_SIRASI,
    "TUR_ETIKET": TUR_ETIKET,
    "ROL_ETIKET": ROL_ETIKET,
    "MOD_ETIKET": MOD_ETIKET,
    "bugun": date.today,
    "kurulum": _KurulumVekili(),
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


def hata_sayfasi(request, kod: int, mesaj: str):
    """hata.html'i gercek kurulum ayari ve (varsa) oturum kullanicisiyla render eder; main.http_hata bunu cagirir."""
    baglam = {"kod": kod, "hata_mesaji": mesaj, "mesaj": None, "kullanici": getattr(request.state, "kullanici", None)}
    try:
        baglam["kurulum"] = kurulum_ayari(request)
    except Exception:
        baglam["kurulum"] = KurulumAyari(id=1, mod="tekil", kurum_adi="")
    return sablonlar.TemplateResponse(request, "hata.html", baglam, status_code=kod)
