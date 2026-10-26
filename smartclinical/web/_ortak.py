"""Web katmani icin ortak bagimliliklar."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, Kullanici
from ..services.yetki import calisma_duzenleyebilir, calisma_erisimi, gerekli, mevcut_kullanici


def oturumlu(request: Request, k: Kullanici = Depends(mevcut_kullanici)) -> Kullanici:
    """Web sayfalarinin oturum bagimliligi. Ilk giris / suresi dolmus parola kontrolu mevcut_kullanici icindedir:
    /hesap/parola disindaki sayfalar 401 ile /giris'e, oradan da parola sayfasina yonlenir."""
    request.state.kullanici = k
    return k


def calisma_getir(calisma_id: int, request: Request, db: Session = Depends(get_db),
                  k: Kullanici = Depends(mevcut_kullanici)) -> Calisma:
    """/calismalar/{id}/* altindaki tum sayfalarin tek giris noktasi; erisim kurali yetki.calisma_erisimi'dir."""
    c = db.get(Calisma, calisma_id)
    if not c:
        raise HTTPException(404, "Çalışma bulunamadı")
    if not calisma_erisimi(db, k, c):
        raise HTTPException(403, "Bu çalışmaya erişiminiz yok")
    request.state.kullanici = k
    return c


def calisma_duzenleyen(c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
                       db: Session = Depends(get_db)) -> Kullanici:
    """Calisma icerigini degistiren rotalar: izin + calisma bazli duzenleme hakki (yetki.calisma_duzenleyebilir)."""
    if not calisma_duzenleyebilir(db, k, c):
        raise HTTPException(403, "Bu çalışmayı düzenleme yetkiniz yok")
    return k


def sayfala(liste: list, sayfa: int, boyut: int = 50, sorgu: str = "") -> tuple[list, dict]:
    """Listeyi sayfalar; _sayfalama.html icin baglam doner."""
    toplam = len(liste)
    toplam_sayfa = max(1, (toplam - 1) // boyut + 1)
    sayfa = min(max(1, sayfa), toplam_sayfa)
    dilim = liste[(sayfa - 1) * boyut: sayfa * boyut]
    return dilim, {"sayfa": sayfa, "toplam_sayfa": toplam_sayfa, "toplam": toplam, "sorgu": sorgu, "boyut": boyut}


def bilgi(request: Request, metin: str):
    request.session["mesaj"] = metin


def ip(request: Request) -> str | None:
    return request.client.host if request.client else None
