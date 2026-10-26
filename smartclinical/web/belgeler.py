"""TMF belge yonetimi: liste (merkez bazli ISF gorunumu), yukleme (uzanti/boyut/icerik kontrolu, surum zinciri),
e-imzali onay ve indirme. Rotalar /calismalar/{id}/belgeler altinda."""
import hashlib
import mimetypes

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ayarlar
from ..db import get_db
from ..models import Belge, Calisma, Kullanici
from ..models._ortak import simdi
from ..models.belge import DOSYA_IMZALARI, IZINLI_UZANTILAR, MAKS_BELGE_BOYUTU, TMF_BOLGELER
from ..services import denetim
from ..services.yetki import gerekli, parola_dogrula
from ._ortak import bilgi, calisma_getir, ip, oturumlu
from .calismalar import _merkez_sinirli, _ozet, sekme_kontrol
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}/belgeler")


def _belge(db: Session, k: Kullanici, c: Calisma, belge_id: int) -> Belge:
    b = db.get(Belge, belge_id)
    if not b or b.calisma_id != c.id:
        raise HTTPException(404, "Belge bulunamadı")
    if _merkez_sinirli(k) and b.merkez_id is not None and b.merkez_id != k.merkez_id:
        raise HTTPException(403, "Bu merkezin belgelerine erişiminiz yok")
    return b


def dosya_kontrol(dosya_adi: str, icerik_turu: str | None, icerik: bytes) -> str | None:
    """Hata mesaji dondurur; uygunsa None. Uzanti, boyut, bildirilen tur ve ilk baytlar birlikte kontrol edilir."""
    uzanti = dosya_adi.rsplit(".", 1)[-1].lower() if "." in dosya_adi else ""
    if uzanti not in IZINLI_UZANTILAR:
        return "Yalnızca PDF, DOCX, XLSX, PNG ve JPG dosyaları yüklenebilir."
    if len(icerik) > MAKS_BELGE_BOYUTU:
        return "Dosya 25 MB sınırını aşıyor."
    if not icerik:
        return "Dosya boş."
    if icerik_turu and icerik_turu not in IZINLI_UZANTILAR[uzanti]:
        return "Dosya türü uzantıyla uyuşmuyor."
    if not any(icerik.startswith(imza) for imza in DOSYA_IMZALARI[uzanti]):
        return "Dosya içeriği uzantıyla uyuşmuyor."
    return None


@router.get("")
def belgeler(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
             db: Session = Depends(get_db), merkez_id: int | None = None):
    sekme_kontrol(k, "belgeler")
    if _merkez_sinirli(k):
        merkez_id = k.merkez_id
    sorgu = select(Belge).where(Belge.calisma_id == c.id).order_by(Belge.tmf_bolge, Belge.ad, Belge.id.desc())
    if merkez_id:
        # merkez dosyasi (ISF): calisma duzeyindeki belgeler + secilen merkezin belgeleri
        sorgu = sorgu.where((Belge.merkez_id.is_(None)) | (Belge.merkez_id == merkez_id))
    liste = db.execute(sorgu).scalars().all()
    bolgeler, eskimis = {}, {}
    for b in liste:
        (eskimis if b.durum == "eskimis" else bolgeler).setdefault(b.tmf_bolge, []).append(b)
    tamlik = {kod: any(b.durum == "onayli" for b in bolgeler.get(kod, [])) for kod in TMF_BOLGELER}
    yuzde = round(100 * sum(1 for v in tamlik.values() if v) / len(TMF_BOLGELER))
    return goster(request, "calismalar/belgeler.html", c=c, o=_ozet(db, c), sekme="belgeler", bolgeler=bolgeler,
                  eskimis=eskimis, TMF_BOLGELER=TMF_BOLGELER, tamlik=tamlik, tamlik_yuzde=yuzde, secili_merkez=merkez_id,
                  merkez_secilebilir=not _merkez_sinirli(k))


@router.post("")
async def belge_yukle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("belge.yukle")),
                      db: Session = Depends(get_db), tmf_bolge: str = Form(...), ad: str = Form(...),
                      versiyon: str = Form("1.0"), merkez_id: str = Form(""), dosya: UploadFile | None = None):
    hedef_url = f"/calismalar/{c.id}/belgeler"
    if tmf_bolge not in TMF_BOLGELER:
        raise HTTPException(400, "Geçersiz TMF bölgesi")
    mid = int(merkez_id) if merkez_id else None
    if _merkez_sinirli(k) and mid != k.merkez_id:
        raise HTTPException(403, "Yalnızca kendi merkezinizin belgesini yükleyebilirsiniz")
    b = Belge(calisma_id=c.id, tmf_bolge=tmf_bolge, ad=ad.strip(), versiyon=versiyon.strip() or "1.0", yukleyen_id=k.id,
              merkez_id=mid)
    if dosya and dosya.filename:
        icerik = await dosya.read()
        hata = dosya_kontrol(dosya.filename, dosya.content_type, icerik)
        if hata:
            bilgi(request, "Belge yüklenemedi: " + hata)
            return RedirectResponse(hedef_url, status_code=303)
        hedef = ayarlar().dosya_dizini / c.kod / tmf_bolge
        hedef.mkdir(parents=True, exist_ok=True)
        guvenli_ad = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in dosya.filename)
        yol = hedef / f"{simdi():%Y%m%d%H%M%S%f}_{guvenli_ad}"
        yol.write_bytes(icerik)
        b.dosya_adi = dosya.filename
        b.dosya_yolu = str(yol)
        b.sha256 = hashlib.sha256(icerik).hexdigest()
    # ayni bolge + ad + merkez icin onceki surum eskir, zincir onceki_id ile kurulur
    onceki = db.execute(select(Belge).where(Belge.calisma_id == c.id, Belge.tmf_bolge == tmf_bolge, Belge.ad == b.ad,
                                            Belge.merkez_id.is_(None) if mid is None else Belge.merkez_id == mid,
                                            Belge.durum != "eskimis").order_by(Belge.id.desc())).scalars().all()
    db.add(b)
    db.flush()
    for o in onceki:
        eski_durum = o.durum
        o.durum = "eskimis"
        denetim.kaydet(db, k, "guncelle", "belge", o.id, eski={"durum": eski_durum},
                       yeni={"durum": "eskimis", "yeni_surum_id": b.id}, ip=ip(request))
    if onceki:
        b.onceki_id = onceki[0].id
    denetim.kaydet(db, k, "olustur", "belge", b.id, yeni={"calisma": c.kod, "ad": b.ad, "bolge": tmf_bolge, "versiyon": b.versiyon,
                                                          "sha256": b.sha256, "onceki_id": b.onceki_id}, ip=ip(request))
    db.commit()
    bilgi(request, f"'{b.ad}' yüklendi." + (f" Önceki {len(onceki)} sürüm eskimiş olarak işaretlendi." if onceki else ""))
    return RedirectResponse(hedef_url, status_code=303)


@router.post("/{belge_id}/onayla")
def belge_onayla(request: Request, belge_id: int, c: Calisma = Depends(calisma_getir),
                 k: Kullanici = Depends(gerekli("belge.yukle")), db: Session = Depends(get_db), parola: str = Form(...)):
    b = _belge(db, k, c, belge_id)
    hedef_url = f"/calismalar/{c.id}/belgeler"
    if b.durum != "taslak":
        bilgi(request, "Yalnızca taslak belge onaylanır.")
        return RedirectResponse(hedef_url, status_code=303)
    if not parola_dogrula(parola, k.parola_hash):
        bilgi(request, "E-imza için parola doğrulanamadı.")
        return RedirectResponse(hedef_url, status_code=303)
    b.durum = "onayli"
    denetim.imzala(db, k, "belge", b.id, "Onaylandı", {"ad": b.ad, "versiyon": b.versiyon, "sha256": b.sha256}, ip=ip(request))
    db.commit()
    bilgi(request, f"'{b.ad}' elektronik imza ile onaylandı.")
    return RedirectResponse(hedef_url, status_code=303)


@router.get("/{belge_id}/indir")
def belge_indir(request: Request, belge_id: int, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
                db: Session = Depends(get_db)):
    sekme_kontrol(k, "belgeler")
    b = _belge(db, k, c, belge_id)
    if not b.dosya_yolu:
        raise HTTPException(404, "Bu belge kaydına dosya eklenmemiş")
    from pathlib import Path

    yol = Path(b.dosya_yolu)
    if not yol.is_file():
        raise HTTPException(404, "Dosya depoda bulunamadı")
    if b.sha256 and hashlib.sha256(yol.read_bytes()).hexdigest() != b.sha256:
        raise HTTPException(409, "Dosya özeti kayıtla uyuşmuyor; belge bütünlüğü bozulmuş olabilir")
    denetim.kaydet(db, k, "goruntule", "belge", b.id, yeni={"ad": b.ad, "versiyon": b.versiyon, "sha256": b.sha256}, ip=ip(request))
    db.commit()
    tur = mimetypes.guess_type(b.dosya_adi or "")[0] or "application/octet-stream"
    return FileResponse(str(yol), media_type=tur, filename=b.dosya_adi, content_disposition_type="attachment")
