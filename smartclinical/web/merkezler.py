from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Arastirmaci, Hasta, Kullanici, Merkez
from ..services import denetim
from ..services import kurulum as kurulum_svc
from ..services.yetki import gerekli
from ._ortak import bilgi, ip, oturumlu
from .sablon import goster

router = APIRouter(prefix="/merkezler")


def _performans(m: Merkez) -> dict:
    """Merkezin gecmis calismalardaki performans ozeti (merkez zekasi girdisi)."""
    cms = m.calismalar
    toplam_kayit = 0
    toplam_ay = 0.0
    akt_sureleri = []
    for cm in cms:
        kayitli = [g for g in cm.gonulluler if g.randomizasyon_tarihi]
        toplam_kayit += len(kayitli)
        if cm.aktivasyon_tarihi:
            bitis = date.today()
            toplam_ay += max(0.5, (bitis - cm.aktivasyon_tarihi).days / 30.4)
            if cm.secim_tarihi:
                akt_sureleri.append((cm.aktivasyon_tarihi - cm.secim_tarihi).days)
    return {
        "calisma": len(cms), "kayit": toplam_kayit,
        "hasta_ay": (toplam_kayit / toplam_ay) if toplam_ay else None,
        "aktivasyon_gun": (sum(akt_sureleri) / len(akt_sureleri)) if akt_sureleri else None,
    }


KURUM_TIPLERI = [("universite", "Üniversite"), ("egitim_arastirma", "Eğitim ve Araştırma"),
                 ("sehir", "Şehir Hastanesi"), ("ozel", "Özel")]


@router.get("")
def liste(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db), q: str = "", bolum: str = ""):
    """Mod bazli gorunum: tekil -> tek merkez karti; universite -> bolum bazinda arastirmacilar; cro -> tablo."""
    ayar = kurulum_svc.ayar_getir(db)
    sorgu = select(Merkez).order_by(Merkez.ad)
    if q:
        sorgu = sorgu.where(Merkez.ad.ilike(f"%{q}%") | Merkez.sehir.ilike(f"%{q}%"))
    merkezler = db.execute(sorgu).scalars().all()
    satirlar = [{"m": m, "p": _performans(m), "hasta": db.scalar(select(Hasta.id).where(Hasta.merkez_id == m.id).limit(1)) is not None}
                for m in merkezler]
    baglam = {"satirlar": satirlar, "q": q, "ayar": ayar, "kurum_tipleri": KURUM_TIPLERI, "bolum": bolum,
              "bolumler": [], "gruplar": [], "tek": None}
    if ayar.mod == "tekil":
        tek = ayar.varsayilan_merkez or (merkezler[0] if merkezler else None)
        baglam["tek"] = next((s for s in satirlar if tek and s["m"].id == tek.id), None) or (
            {"m": tek, "p": _performans(tek), "hasta": False} if tek else None)
    elif ayar.mod == "universite":
        arastirmacilar = [a for m in merkezler for a in m.arastirmacilar]
        baglam["bolumler"] = sorted({a.bolum for a in arastirmacilar if a.bolum})
        if bolum:
            arastirmacilar = [a for a in arastirmacilar if (a.bolum or "") == bolum]
        gruplar: dict[str, list] = {}
        for a in sorted(arastirmacilar, key=lambda x: ((x.bolum or "~"), x.ad_soyad)):
            gruplar.setdefault(a.bolum or "", []).append(a)
        baglam["gruplar"] = sorted(gruplar.items(), key=lambda g: (g[0] == "", g[0]))
    return goster(request, "merkezler/liste.html", **baglam)


@router.get("/{mid}")
def detay(request: Request, mid: int, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    m = db.get(Merkez, mid)
    if not m:
        raise HTTPException(404)
    hasta_n = len(db.execute(select(Hasta.id).where(Hasta.merkez_id == m.id)).all())
    return goster(request, "merkezler/detay.html", m=m, p=_performans(m), hasta_n=hasta_n)


@router.post("")
def ekle(request: Request, k: Kullanici = Depends(gerekli("merkez.yonet")), db: Session = Depends(get_db),
         kod: str = Form(...), ad: str = Form(...), sehir: str = Form(...), kurum_tipi: str = Form(...),
         yatak_sayisi: str = Form(""), hbys: str = Form(""), terapotik_alanlar: str = Form("")):
    m = Merkez(kod=kod.strip().upper(), ad=ad, sehir=sehir, kurum_tipi=kurum_tipi,
               yatak_sayisi=int(yatak_sayisi) if yatak_sayisi else None, hbys=hbys or None,
               terapotik_alanlar=[t.strip() for t in terapotik_alanlar.split(",") if t.strip()] or None)
    db.add(m)
    db.flush()
    denetim.kaydet(db, k, "olustur", "merkez", m.id, yeni=denetim.varlik_sozluk(m), ip=ip(request))
    db.commit()
    return RedirectResponse(f"/merkezler/{m.id}", status_code=303)


@router.post("/{mid}/duzenle")
def duzenle(request: Request, mid: int, k: Kullanici = Depends(gerekli("merkez.yonet")), db: Session = Depends(get_db),
            ad: str = Form(...), sehir: str = Form(...), kurum_tipi: str = Form(...), yatak_sayisi: str = Form(""),
            hbys: str = Form(""), terapotik_alanlar: str = Form(""), fhir_uc_noktasi: str = Form(""), notlar: str = Form("")):
    m = db.get(Merkez, mid)
    if not m:
        raise HTTPException(404)
    eski = denetim.varlik_sozluk(m)
    m.ad, m.sehir, m.kurum_tipi = ad.strip()[:200], sehir.strip()[:60], kurum_tipi
    m.yatak_sayisi = int(yatak_sayisi) if yatak_sayisi.strip().isdigit() else None
    m.hbys = hbys.strip() or None
    m.fhir_uc_noktasi = fhir_uc_noktasi.strip() or None
    m.notlar = notlar.strip() or None
    m.terapotik_alanlar = [t.strip() for t in terapotik_alanlar.split(",") if t.strip()] or None
    denetim.kaydet(db, k, "guncelle", "merkez", m.id, eski=eski, yeni=denetim.varlik_sozluk(m), ip=ip(request))
    db.commit()
    bilgi(request, "Merkez bilgileri güncellendi.")
    return RedirectResponse(request.headers.get("referer") or f"/merkezler/{m.id}", status_code=303)


@router.post("/{mid}/arastirmaci")
def arastirmaci_ekle(request: Request, mid: int, k: Kullanici = Depends(gerekli("merkez.yonet")), db: Session = Depends(get_db),
                     ad_soyad: str = Form(...), unvan: str = Form(""), uzmanlik: str = Form(""), gcp_egitim_tarihi: str = Form(""),
                     bolum: str = Form("")):
    a = Arastirmaci(merkez_id=mid, ad_soyad=ad_soyad, unvan=unvan or None, uzmanlik=uzmanlik or None, bolum=bolum.strip()[:80] or None,
                    gcp_egitim_tarihi=date.fromisoformat(gcp_egitim_tarihi) if gcp_egitim_tarihi else None)
    db.add(a)
    db.flush()
    denetim.kaydet(db, k, "olustur", "arastirmaci", a.id, yeni={"merkez_id": mid, "ad_soyad": ad_soyad, "bolum": a.bolum}, ip=ip(request))
    db.commit()
    return RedirectResponse(request.headers.get("referer") or f"/merkezler/{mid}", status_code=303)


# --- CSV ile hasta havuzu yukleme (FHIR olmayan kurulumlar icin dusuk esikli yol) --------------

@router.get("/{mid}/hasta-yukle")
def hasta_yukle_form(request: Request, mid: int, k: Kullanici = Depends(gerekli("hasta.goruntule")), db: Session = Depends(get_db)):
    request.state.kullanici = k
    m = db.get(Merkez, mid)
    if not m:
        raise HTTPException(404)
    return goster(request, "merkezler/hasta_yukle.html", m=m, sonuc=None)


@router.post("/{mid}/hasta-yukle")
async def hasta_yukle(request: Request, mid: int, k: Kullanici = Depends(gerekli("hasta.goruntule")), db: Session = Depends(get_db)):
    """CSV kolonlari: kayit_no;dogum_yili;cinsiyet;icd10;metin  (icd10 virgulle ayrilmis).
    kayit_no HBYS kimligi ise sha256 ile takma ada cevrilir; metinler kimliksizlestirilir."""
    import csv
    import hashlib
    import io

    from ..models._ortak import simdi
    from ..services.kimliksizlestirme import kimliksizlestir, metni_dogrula

    request.state.kullanici = k
    m = db.get(Merkez, mid)
    if not m:
        raise HTTPException(404)
    form = await request.form()
    dosya = form.get("dosya")
    icerik = (await dosya.read()).decode("utf-8-sig") if dosya else ""
    okuyucu = csv.DictReader(io.StringIO(icerik), delimiter=";")
    yeni = guncel = red = 0
    uyarilar = []
    for i, satir in enumerate(okuyucu, 1):
        ham = (satir.get("kayit_no") or "").strip()
        if not ham:
            continue
        kayit_no = "P-" + hashlib.sha256(f"{mid}:{ham}".encode()).hexdigest()[:12]
        metin = (satir.get("metin") or "").strip()
        metinler = []
        if metin:
            s = kimliksizlestir(metin)
            if metni_dogrula(s.metin):
                red += 1
                uyarilar.append(f"Satır {i}: kimliksizleştirme sonrası şüpheli kalıp kaldı; kayıt alınmadı.")
                continue
            metinler = [{"tur": "epikriz", "tarih": str(date.today()), "metin": s.metin}]
        tanilar = [{"icd10": kod.strip().upper(), "ad": "", "tarih": ""} for kod in (satir.get("icd10") or "").split(",") if kod.strip()]
        mevcut = db.execute(select(Hasta).where(Hasta.merkez_id == mid, Hasta.kayit_no == kayit_no)).scalar_one_or_none()
        h = mevcut or Hasta(merkez_id=mid, kayit_no=kayit_no)
        h.dogum_yili = int(satir["dogum_yili"]) if (satir.get("dogum_yili") or "").strip().isdigit() else h.dogum_yili
        h.cinsiyet = (satir.get("cinsiyet") or h.cinsiyet or "").strip()[:1].upper() or None
        h.tanilar = tanilar or h.tanilar
        h.metinler = metinler or h.metinler
        h.kaynak, h.son_senkron = "csv", simdi()
        db.add(h)
        guncel += mevcut is not None
        yeni += mevcut is None
    denetim.kaydet(db, k, "yukle", "merkez", mid, yeni={"yeni": yeni, "guncel": guncel, "red": red, "kaynak": "csv"}, ip=ip(request))
    db.commit()
    return goster(request, "merkezler/hasta_yukle.html", m=m, sonuc={"yeni": yeni, "guncel": guncel, "red": red, "uyarilar": uyarilar[:20]})
