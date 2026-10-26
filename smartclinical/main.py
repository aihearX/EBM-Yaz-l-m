import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import __version__
from .api import router as api_router
from .config import ayarlar
from .db import tablolari_olustur
from .models import Kullanici
from .services.yetki import mevcut_kullanici
from .web import router as web_router
from .web.sablon import hata_sayfasi

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smartclinical")


@asynccontextmanager
async def yasam_dongusu(app: FastAPI):
    a = ayarlar()
    tablolari_olustur()
    a.dosya_dizini.mkdir(parents=True, exist_ok=True)
    log.info("SmartClinical %s baslatildi (ortam=%s, bdm=%s/%s)", __version__, a.ortam, a.bdm_saglayici, a.bdm_model)
    yield


# API belgeleri ve OpenAPI semasi anonim acilmaz; asagidaki iki rota oturum ister
app = FastAPI(
    title="EBM SmartClinical",
    version=__version__,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=yasam_dongusu,
)

_a = ayarlar()
app.add_middleware(
    SessionMiddleware,
    secret_key=_a.secret_key,
    session_cookie="sc_oturum",
    max_age=_a.oturum_suresi_dk * 60,
    same_site="strict",
    https_only=_a.uretim,
)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(api_router, prefix="/api/v1")
app.include_router(web_router)


@app.get("/saglik", include_in_schema=False)
def saglik_kok():
    # Dockerfile HEALTHCHECK ve yuk dengeleyici icin kisa yol
    from .api.sistem import saglik
    from .db import oturum_fabrikasi

    db = oturum_fabrikasi()()
    try:
        return saglik(db)
    finally:
        db.close()


@app.get("/api/openapi.json", include_in_schema=False)
def openapi_semasi(k: Kullanici = Depends(mevcut_kullanici)):
    return JSONResponse(app.openapi())


@app.get("/api/belgeler", include_in_schema=False)
def api_belgeleri(k: Kullanici = Depends(mevcut_kullanici)):
    """Kapali agda dis kaynak yuklenmez; sema kisa bir HTML listesi olarak sunulur, tam sema /api/openapi.json'dadir."""
    from html import escape

    sema = app.openapi()
    satirlar = []
    for yol, yontemler in sorted(sema.get("paths", {}).items()):
        for yontem, bilgi in yontemler.items():
            etiket = ", ".join(bilgi.get("tags", []))
            satirlar.append(f"<tr><td><code>{yontem.upper()}</code></td><td><code>{escape(yol)}</code></td>"
                            f"<td>{escape(bilgi.get('summary') or (bilgi.get('description') or '').split(chr(10))[0])}</td><td>{escape(etiket)}</td></tr>")
    govde = ("<!doctype html><html lang='tr'><head><meta charset='utf-8'><title>SmartClinical API</title>"
             "<style>body{font-family:system-ui,sans-serif;margin:24px;color:#1b2a41}table{border-collapse:collapse}"
             "td,th{border-bottom:1px solid #dde3ea;padding:6px 10px;text-align:left;font-size:14px}code{font-size:13px}</style></head>"
             "<body><h1>EBM SmartClinical REST API</h1><p>Taban yol <code>/api/v1</code>; kimlik doğrulama oturum çerezi veya "
             "<code>X-SC-Anahtar</code> başlığı. Tam şema: <a href='/api/openapi.json'>/api/openapi.json</a>. Ayrıntılar: docs/api.md.</p>"
             "<table><tr><th>Yöntem</th><th>Yol</th><th>Açıklama</th><th>Etiket</th></tr>" + "".join(satirlar) + "</table></body></html>")
    return HTMLResponse(govde)


@app.middleware("http")
async def guvenlik_basliklari(request: Request, call_next):
    yanit = await call_next(request)
    yanit.headers["X-Content-Type-Options"] = "nosniff"
    yanit.headers["X-Frame-Options"] = "DENY"
    yanit.headers["Referrer-Policy"] = "same-origin"
    yanit.headers["Cache-Control"] = "no-store"
    return yanit


@app.exception_handler(StarletteHTTPException)
async def http_hata(request: Request, exc: StarletteHTTPException):
    # /api/belgeler tarayicidan acilan bir sayfadir; oturumsuz istek girise yonlenir, diger API yollari JSON doner
    if request.url.path.startswith("/api/") and request.url.path != "/api/belgeler":
        return JSONResponse({"hata": exc.detail}, status_code=exc.status_code)
    if exc.status_code == 401:
        return RedirectResponse(f"/giris?sonraki={request.url.path}", status_code=303)
    # istegin oturumu kapanmis olabilir; sablon kullanici iliskilerine (merkez) dokunur, taze bir oturumla yeniden yukle
    from .db import oturum_fabrikasi

    k = getattr(request.state, "kullanici", None)
    db = oturum_fabrikasi()() if k is not None else None
    try:
        if db is not None:
            request.state.kullanici = db.get(Kullanici, k.id)
        return hata_sayfasi(request, exc.status_code, exc.detail)
    finally:
        if db is not None:
            db.close()
