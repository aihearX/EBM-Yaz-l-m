from fastapi import APIRouter

from . import (
    analiz,
    araclar,
    calismalar,
    disa_aktar,
    ecrf,
    ekip,
    eslestirme,
    giris,
    gonulluler,
    merkezler,
    pano,
    sihirbaz,
    sponsor,
    yonetim,
)

router = APIRouter()
# ecrf, ekip ve analiz /calismalar/{id}/... altinda calisir; calismalar'dan sonra kaydedilir
for m in (giris, pano, calismalar, ecrf, ekip, analiz, sihirbaz, sponsor, gonulluler, merkezler, eslestirme, araclar,
          disa_aktar, yonetim):
    router.include_router(m.router)
