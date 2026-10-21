import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import __version__
from .api import router as api_router
from .config import ayarlar
from .db import tablolari_olustur
from .web import router as web_router
from .web.sablon import sablonlar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smartclinical")


@asynccontextmanager
async def yasam_dongusu(app: FastAPI):
    a = ayarlar()
    tablolari_olustur()
    a.dosya_dizini.mkdir(parents=True, exist_ok=True)
    log.info("SmartClinical %s baslatildi (ortam=%s, bdm=%s/%s)", __version__, a.ortam, a.bdm_saglayici, a.bdm_model)
    yield


app = FastAPI(
    title="EBM SmartClinical",
    version=__version__,
    docs_url="/api/belgeler",
    redoc_url=None,
    openapi_url="/api/openapi.json",
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
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse

        return JSONResponse({"hata": exc.detail}, status_code=exc.status_code)
    if exc.status_code == 401:
        return RedirectResponse(f"/giris?sonraki={request.url.path}", status_code=303)
    return sablonlar.TemplateResponse(
        request, "hata.html", {"kod": exc.status_code, "mesaj": exc.detail}, status_code=exc.status_code
    )
