from fastapi import APIRouter

from . import araclar, arge, calismalar, disa_aktar, eslestirme, giris, gonulluler, merkezler, pano, yonetim

router = APIRouter()
for m in (giris, pano, calismalar, gonulluler, merkezler, eslestirme, araclar, arge, disa_aktar, yonetim):
    router.include_router(m.router)
