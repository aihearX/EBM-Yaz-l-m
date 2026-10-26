from fastapi import APIRouter

from . import (
    analiz,
    araclar,
    belgeler,
    calismalar,
    disa_aktar,
    ecrf,
    ekip,
    eslestirme,
    giris,
    gonulluler,
    hesap,
    izlem,
    merkezler,
    pano,
    randomizasyon,
    sihirbaz,
    sponsor,
    veri_islem,
    yonetim,
)

router = APIRouter()
# /calismalar/{id}/... altinda calisan moduller (izlem, belgeler, veri_islem, randomizasyon, ecrf, ekip, analiz)
# calismalar'dan sonra kaydedilir
for m in (giris, hesap, pano, calismalar, izlem, belgeler, veri_islem, randomizasyon, ecrf, ekip, analiz, sihirbaz,
          sponsor, gonulluler, merkezler, eslestirme, araclar, disa_aktar, yonetim):
    router.include_router(m.router)
