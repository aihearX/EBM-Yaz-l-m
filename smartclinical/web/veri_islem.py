"""Veri yonetimi kapanisi: arastirmaci (PI) imzasi, toplu kilit on kontrolu ve kilit, kilit acma, toplu sorgu kapatma.

Rotalar /calismalar/{id}/veri altinda calisir; sayfa sablonlari templates/veri/."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, CalismaMerkez, EImza, FormKaydi, Gonullu, Kullanici, Rol, Sorgu
from ..models._ortak import simdi
from ..models.veri import KAYIT_DURUM_ETIKET, SORGU_ETIKET
from ..services import denetim
from ..services.yetki import gerekli, gonullu_erisimi, parola_dogrula
from ._ortak import bilgi, calisma_getir, ip, oturumlu
from .calismalar import _gorunur_cm, _ozet, sekme_kontrol
from .sablon import goster, sablonlar

router = APIRouter(prefix="/calismalar/{calisma_id}/veri")

PI_IMZA_ANLAMI = "Araştırmacı imzası"
KAPSAM_ETIKET = {"calisma": "Tüm çalışma", "merkez": "Merkez", "gonullu": "Gönüllü"}
IMZA_DURUM_ETIKET = {"yok": "İmzalanmadı", "imzali": "İmzalı", "yenilenmeli": "İmza yenilenmeli", "bos": "Kayıt yok"}

sablonlar.env.globals.update({"SORGU_ETIKET": SORGU_ETIKET, "KAYIT_DURUM_ETIKET": KAYIT_DURUM_ETIKET,
                              "IMZA_DURUM_ETIKET": IMZA_DURUM_ETIKET})


def kayit_ozeti(g: Gonullu) -> dict:
    """Gonullunun tum form kayitlarinin icerik ozeti; PI imzasinin imzaladigi icerik budur."""
    return {str(fk.id): denetim.icerik_ozeti({"form": fk.form_id, "vizit": fk.vizit_id, "tekrar": fk.tekrar_no,
                                              "veriler": fk.veriler}) for fk in sorted(g.form_kayitlari, key=lambda x: x.id)}


def imza_durumu(db: Session, g: Gonullu) -> tuple[str, EImza | None]:
    """yok | imzali | yenilenmeli | bos. Imzadan sonra guncellenen form kaydi varsa imza yenilenmeli."""
    if not g.form_kayitlari:
        return "bos", None
    imza = denetim.son_imza(db, "gonullu", g.id, PI_IMZA_ANLAMI)
    if imza is None:
        return "yok", None
    if imza.icerik_hash != denetim.icerik_ozeti(kayit_ozeti(g)):
        return "yenilenmeli", imza
    if any(fk.guncelleme and fk.guncelleme > imza.zaman for fk in g.form_kayitlari):
        return "yenilenmeli", imza
    return "imzali", imza


def _gonulluler(k: Kullanici, c: Calisma) -> list[Gonullu]:
    return sorted((g for cm in _gorunur_cm(k, c) for g in cm.gonulluler), key=lambda g: g.gonullu_no)


# --- Arastirmaci imzasi -----------------------------------------------------

@router.get("/imza")
def imza_listesi(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
                 db: Session = Depends(get_db)):
    sekme_kontrol(k, "veri")
    satirlar = []
    for g in _gonulluler(k, c):
        durum, imza = imza_durumu(db, g)
        satirlar.append({"g": g, "durum": durum, "imza": imza, "kayit": len(g.form_kayitlari),
                         "kilitli": sum(1 for fk in g.form_kayitlari if fk.durum == "kilitli")})
    sayac = {d: sum(1 for s in satirlar if s["durum"] == d) for d in IMZA_DURUM_ETIKET}
    return goster(request, "veri/imza.html", c=c, o=_ozet(db, c), sekme="veri", satirlar=satirlar, sayac=sayac,
                  imzalayabilir=k.rol == Rol.ARASTIRMACI)


@router.post("/imza/{gid}")
def imzala(request: Request, gid: int, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("veri.gir")),
           db: Session = Depends(get_db), parola: str = Form(...)):
    if k.rol != Rol.ARASTIRMACI:
        raise HTTPException(403, "Gönüllü verisini araştırmacı imzalar")
    g = db.get(Gonullu, gid)
    if not g or g.calisma_id != c.id:
        raise HTTPException(404, "Gönüllü bulunamadı")
    if not gonullu_erisimi(db, k, g):
        raise HTTPException(403, "Bu gönüllüye erişiminiz yok")
    hedef = f"/calismalar/{c.id}/veri/imza"
    if not g.form_kayitlari:
        bilgi(request, f"{g.gonullu_no}: imzalanacak form kaydı yok.")
        return RedirectResponse(hedef, status_code=303)
    if not parola_dogrula(parola, k.parola_hash):
        bilgi(request, "E-imza için parola doğrulanamadı.")
        return RedirectResponse(hedef, status_code=303)
    denetim.imzala(db, k, "gonullu", g.id, PI_IMZA_ANLAMI, kayit_ozeti(g), ip=ip(request))
    db.commit()
    bilgi(request, f"{g.gonullu_no} için araştırmacı imzası kaydedildi ({len(g.form_kayitlari)} form kaydı).")
    return RedirectResponse(hedef, status_code=303)


# --- Toplu kilit ------------------------------------------------------------

def _kapsam_gonulluler(db: Session, k: Kullanici, c: Calisma, kapsam: str, kapsam_id: int | None) -> tuple[list[Gonullu], str]:
    gonulluler = _gonulluler(k, c)
    if kapsam == "merkez" and kapsam_id:
        cm = db.get(CalismaMerkez, kapsam_id)
        if not cm or cm.calisma_id != c.id:
            raise HTTPException(404, "Merkez bulunamadı")
        return [g for g in gonulluler if g.calisma_merkez_id == cm.id], f"{cm.merkez_no} – {cm.merkez.sehir}"
    if kapsam == "gonullu" and kapsam_id:
        g = db.get(Gonullu, kapsam_id)
        if not g or g.calisma_id != c.id:
            raise HTTPException(404, "Gönüllü bulunamadı")
        return [x for x in gonulluler if x.id == g.id], g.gonullu_no
    return gonulluler, c.kod


def kilit_on_kontrol(db: Session, gonulluler: list[Gonullu]) -> dict:
    """Kilitlenmemis kayitlari engel turune gore ayirir: acik sorgu, SDV yok, PI imzasi yok/yenilenmeli, taslak."""
    uygun, engelli = [], []
    for g in gonulluler:
        imza, _ = imza_durumu(db, g)
        for fk in g.form_kayitlari:
            if fk.durum == "kilitli":
                continue
            nedenler = []
            if fk.durum == "taslak":
                nedenler.append("taslak")
            if any(s.durum == "acik" for s in fk.sorgular):
                nedenler.append("acik_sorgu")
            if fk.durum not in ("sdv", "kilitli"):
                nedenler.append("sdv_yok")
            if imza != "imzali":
                nedenler.append("imza_yok")
            (engelli if nedenler else uygun).append({"fk": fk, "g": g, "nedenler": nedenler})
    sayac = {ad: sum(1 for e in engelli if ad in e["nedenler"]) for ad in ("acik_sorgu", "sdv_yok", "imza_yok", "taslak")}
    return {"uygun": uygun, "engelli": engelli, "sayac": sayac}


NEDEN_ETIKET = {"acik_sorgu": "Açık sorgu", "sdv_yok": "SDV yapılmadı", "imza_yok": "Araştırmacı imzası eksik", "taslak": "Taslak"}
sablonlar.env.globals["NEDEN_ETIKET"] = NEDEN_ETIKET


@router.get("/kilit")
def kilit(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
          db: Session = Depends(get_db), kapsam: str = "calisma", kapsam_id: int | None = None):
    sekme_kontrol(k, "veri")
    if kapsam not in KAPSAM_ETIKET:
        raise HTTPException(400, "Geçersiz kapsam")
    gonulluler, kapsam_ad = _kapsam_gonulluler(db, k, c, kapsam, kapsam_id)
    sonuc = kilit_on_kontrol(db, gonulluler)
    kilitli = sum(1 for g in gonulluler for fk in g.form_kayitlari if fk.durum == "kilitli")
    return goster(request, "veri/kilit.html", c=c, o=_ozet(db, c), sekme="veri", kapsam=kapsam, kapsam_id=kapsam_id,
                  kapsam_ad=kapsam_ad, KAPSAM_ETIKET=KAPSAM_ETIKET, sonuc=sonuc, kilitli=kilitli,
                  merkezler=_gorunur_cm(k, c), gonulluler=_gonulluler(k, c), kilitleyebilir=k.rol in (Rol.YONETICI, Rol.VERI_YONETICISI))


@router.post("/kilit")
def toplu_kilit(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("veri.kilitle")),
                db: Session = Depends(get_db), kapsam: str = Form("calisma"), kapsam_id: str = Form(""), parola: str = Form(...)):
    if kapsam not in KAPSAM_ETIKET:
        raise HTTPException(400, "Geçersiz kapsam")
    kid = int(kapsam_id) if kapsam_id else None
    hedef = f"/calismalar/{c.id}/veri/kilit?kapsam={kapsam}" + (f"&kapsam_id={kid}" if kid else "")
    if not parola_dogrula(parola, k.parola_hash):
        bilgi(request, "E-imza için parola doğrulanamadı; kilit uygulanmadı.")
        return RedirectResponse(hedef, status_code=303)
    gonulluler, kapsam_ad = _kapsam_gonulluler(db, k, c, kapsam, kid)
    sonuc = kilit_on_kontrol(db, gonulluler)
    if not sonuc["uygun"]:
        bilgi(request, "Ön kontrolü geçen kayıt yok; kilit uygulanmadı.")
        return RedirectResponse(hedef, status_code=303)
    zaman = simdi()
    ozet = {}
    for u in sonuc["uygun"]:
        fk = u["fk"]
        fk.durum = "kilitli"
        fk.kilit_zamani = zaman
        ozet[str(fk.id)] = denetim.icerik_ozeti(fk.veriler)
        denetim.kaydet(db, k, "guncelle", "form_kaydi", fk.id, eski={"durum": "sdv"}, yeni={"durum": "kilitli"}, ip=ip(request))
    varlik, varlik_id = {"calisma": ("calisma", c.id), "merkez": ("calisma_merkez", kid), "gonullu": ("gonullu", kid)}[kapsam]
    # tek e-imza: kapsam + kilitlenen kayitlarin icerik ozetleri
    denetim.imzala(db, k, varlik, varlik_id or c.id, "Toplu veri kilidi", {"kapsam": kapsam_ad, "kayitlar": ozet}, ip=ip(request))
    db.commit()
    mesaj = f"{len(ozet)} form kaydı kilitlendi ({kapsam_ad})."
    if sonuc["engelli"]:
        mesaj += f" {len(sonuc['engelli'])} kayıt ön kontrolü geçemedi; aşağıda listelenir."
    bilgi(request, mesaj)
    return RedirectResponse(hedef, status_code=303)


@router.post("/kilit-ac/{fk_id}")
def kilit_ac(request: Request, fk_id: int, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("veri.kilitle")),
             db: Session = Depends(get_db), gerekce: str = Form("")):
    fk = db.get(FormKaydi, fk_id)
    if not fk or fk.gonullu.calisma_id != c.id:
        raise HTTPException(404, "Form kaydı bulunamadı")
    hedef = f"/calismalar/{c.id}/veri/kilit?kapsam=gonullu&kapsam_id={fk.gonullu_id}"
    if not gerekce.strip():
        bilgi(request, "Kilit açma için gerekçe zorunlu; işlem yapılmadı.")
        return RedirectResponse(hedef, status_code=303)
    if fk.durum != "kilitli":
        bilgi(request, "Kayıt zaten kilitli değil.")
        return RedirectResponse(hedef, status_code=303)
    fk.durum = "tamamlandi"
    fk.kilit_zamani = None
    denetim.kaydet(db, k, "kilit_ac", "form_kaydi", fk.id, eski={"durum": "kilitli"}, yeni={"durum": "tamamlandi"},
                   gerekce=gerekce.strip(), ip=ip(request))
    db.commit()
    bilgi(request, f"{fk.gonullu.gonullu_no} / {fk.form.kod} kilidi açıldı; kayıt yeniden SDV ve kilit ister.")
    return RedirectResponse(hedef, status_code=303)


# --- Toplu sorgu kapatma ----------------------------------------------------

@router.post("/sorgu-toplu")
def sorgu_toplu(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("sorgu.ac")),
                db: Session = Depends(get_db), sorgu_id: list[int] = Form([]), islem: str = Form("kapat")):
    hedef = f"/calismalar/{c.id}/veri"
    if islem != "kapat":
        raise HTTPException(400, "Desteklenmeyen işlem")
    if not sorgu_id:
        bilgi(request, "Sorgu seçilmedi.")
        return RedirectResponse(hedef, status_code=303)
    gorunur_cm = {cm.id for cm in _gorunur_cm(k, c)}
    sorgular = db.execute(select(Sorgu).where(Sorgu.id.in_(sorgu_id))).scalars().all()
    kapanan = 0
    for s in sorgular:
        g = s.form_kaydi.gonullu
        if g.calisma_id != c.id or g.calisma_merkez_id not in gorunur_cm or s.durum == "kapali":
            continue
        eski = s.durum
        s.durum = "kapali"
        s.kapanis = simdi()
        denetim.kaydet(db, k, "guncelle", "sorgu", s.id, eski={"durum": eski}, yeni={"durum": "kapali", "toplu": True}, ip=ip(request))
        kapanan += 1
    db.commit()
    bilgi(request, f"{kapanan} sorgu kapatıldı.")
    return RedirectResponse(hedef, status_code=303)
