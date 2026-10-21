"""REST API (v1). Web arayuzunun kullandigi islemlerin bir kismi ile HBYS/EDC
entegrasyonlari icin uc noktalar. Oturum cerezi ile kimlik dogrulanir; makine-makine
entegrasyonlari icin API anahtari destegi planlandi (bkz. docs/api.md)."""
from fastapi import APIRouter

from . import calismalar, entegrasyon, hastalar, sistem, yapay_zeka

router = APIRouter()
router.include_router(sistem.router, tags=["sistem"])
router.include_router(calismalar.router, prefix="/calismalar", tags=["calismalar"])
router.include_router(hastalar.router, tags=["hastalar"])
router.include_router(yapay_zeka.router, tags=["yapay-zeka"])
router.include_router(entegrasyon.router, tags=["entegrasyon"])
