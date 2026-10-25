from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AdversOlay, CalismaMerkez, FormKaydi, Gonullu, GonulluDurumu, Kullanici, Sorgu, Vizit
from ..models import Form as CRF
from ..models._ortak import simdi
from ..models.guvenlik import CIDDIYET_OLCUTU, NEDENSELLIK, SIDDET
from ..models.hasta import GD_ETIKET
from ..services import denetim, ecrf
from ..services.yetki import calisma_erisimi, gerekli, izinli
from ._ortak import bilgi, ip, oturumlu
from .sablon import goster

router = APIRouter(prefix="/gonulluler")

def _gonullu(db: Session, gid: int, k: Kullanici) -> Gonullu:
    g = db.get(Gonullu, gid)
    if not g:
        raise HTTPException(404, "Gönüllü bulunamadı")
    if not calisma_erisimi(db, k, g.calisma):
        raise HTTPException(403, "Bu çalışmaya erişiminiz yok")
    return g


@router.post("/yeni")
def yeni(request: Request, k: Kullanici = Depends(gerekli("veri.gir")), db: Session = Depends(get_db),
         calisma_id: int = Form(...), calisma_merkez_id: int = Form(...), hasta_id: str = Form(""),
         onam_tarihi: str = Form(""), onam_versiyonu: str = Form("")):
    cm = db.get(CalismaMerkez, calisma_merkez_id)
    if not cm or cm.calisma_id != calisma_id:
        raise HTTPException(400, "Merkez çalışmaya ait değil")
    sira = len(cm.gonulluler) + 1
    g = Gonullu(calisma_id=calisma_id, calisma_merkez_id=cm.id, hasta_id=int(hasta_id) if hasta_id else None,
                gonullu_no=f"{cm.merkez_no}-{sira:03d}",
                durum=GonulluDurumu.ONAM if onam_tarihi else GonulluDurumu.ON_TARAMA,
                onam_tarihi=date.fromisoformat(onam_tarihi) if onam_tarihi else None,
                onam_versiyonu=onam_versiyonu or None)
    db.add(g)
    db.flush()
    denetim.kaydet(db, k, "olustur", "gonullu", g.id, yeni=denetim.varlik_sozluk(g), ip=ip(request))
    db.commit()
    bilgi(request, f"Gönüllü {g.gonullu_no} oluşturuldu.")
    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)


@router.get("/{gid}")
def detay(request: Request, gid: int, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    g = _gonullu(db, gid, k)
    # yalnizca yayindaki formlar veri girisinde gorunur; taslaklar tasarimcida kalir
    tum_formlar = sorted(g.calisma.formlar, key=lambda f: f.sira)
    formlar = [f for f in tum_formlar if f.durum != "taslak"]
    kayit_haritasi = {(fk.form_id, fk.vizit_id): fk for fk in g.form_kayitlari}
    # vizit x form matrisi: Form.vizit_listesi bos ise her vizitte
    matris = []
    for v in g.vizitler:
        satir = {"vizit": v, "hucreler": []}
        for f in formlar:
            if not f.vizitte_var(v.ad):
                satir["hucreler"].append(None)
                continue
            satir["hucreler"].append({"form": f, "kayit": kayit_haritasi.get((f.id, v.id))})
        matris.append(satir)
    sorgular = [s for fk in g.form_kayitlari for s in fk.sorgular if s.durum != "kapali"]
    return goster(request, "gonulluler/detay.html", g=g, formlar=formlar, matris=matris, sorgular=sorgular,
                  taslak_form=len(tum_formlar) - len(formlar), sema_var=bool(g.calisma.vizit_tanimlari),
                  durumlar=GonulluDurumu, GD_ETIKET=GD_ETIKET, SIDDET=SIDDET, NEDENSELLIK=NEDENSELLIK,
                  CIDDIYET=CIDDIYET_OLCUTU)


@router.post("/{gid}/durum")
def durum(request: Request, gid: int, k: Kullanici = Depends(gerekli("veri.gir")), db: Session = Depends(get_db),
          durum: str = Form(...), tarih: str = Form(""), neden: str = Form(""), kol_id: str = Form("")):
    g = _gonullu(db, gid, k)
    eski = g.durum.value
    yeni_durum = GonulluDurumu(durum)
    t = date.fromisoformat(tarih) if tarih else date.today()
    g.durum = yeni_durum
    if yeni_durum == GonulluDurumu.ONAM:
        g.onam_tarihi = t
    elif yeni_durum == GonulluDurumu.TARAMA:
        g.tarama_tarihi = t
    elif yeni_durum == GonulluDurumu.TARAMA_BASARISIZ:
        g.tarama_basarisizlik_nedeni = neden or None
    elif yeni_durum == GonulluDurumu.RANDOMIZE:
        # onam olmadan randomizasyon = major sapma; engelliyoruz
        if not g.onam_tarihi:
            bilgi(request, "Onam tarihi girilmeden randomizasyon yapılamaz (ICH E6 4.8).")
            g.durum = GonulluDurumu(eski)
            return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)
        g.randomizasyon_tarihi = t
        if kol_id:
            g.kol_id = int(kol_id)
        if not g.vizitler:
            ecrf.gonullu_vizitleri_olustur(db, g, t)
    elif yeni_durum in (GonulluDurumu.AYRILDI, GonulluDurumu.TAMAMLADI):
        g.bitis_tarihi = t
        g.ayrilma_nedeni = neden or None
    denetim.kaydet(db, k, "guncelle", "gonullu", g.id, eski={"durum": eski}, yeni={"durum": durum, "tarih": t.isoformat(),
                   "neden": neden or None}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)


@router.post("/{gid}/vizit/{vid}")
def vizit_kaydet(request: Request, gid: int, vid: int, k: Kullanici = Depends(gerekli("veri.gir")),
                 db: Session = Depends(get_db), gerceklesen: str = Form(""), durum: str = Form("yapildi")):
    g = _gonullu(db, gid, k)
    v = db.get(Vizit, vid)
    if not v or v.gonullu_id != g.id:
        raise HTTPException(404)
    eski = {"gerceklesen": v.gerceklesen, "durum": v.durum}
    v.gerceklesen = date.fromisoformat(gerceklesen) if gerceklesen else None
    v.durum = durum
    if v.pencere_disi:
        v.durum = "pencere_disi"
    denetim.kaydet(db, k, "guncelle", "vizit", v.id, eski=eski, yeni={"gerceklesen": v.gerceklesen, "durum": v.durum}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)


@router.get("/{gid}/form/{form_id}")
def form_goster(request: Request, gid: int, form_id: int, k: Kullanici = Depends(oturumlu),
                db: Session = Depends(get_db), vizit_id: int | None = None):
    g = _gonullu(db, gid, k)
    f = db.get(CRF, form_id)
    if not f or f.calisma_id != g.calisma_id:
        raise HTTPException(404)
    kayit = next((fk for fk in g.form_kayitlari if fk.form_id == f.id and fk.vizit_id == vizit_id), None)
    vizit = db.get(Vizit, vizit_id) if vizit_id else None
    return goster(request, "gonulluler/form.html", g=g, f=f, kayit=kayit, vizit=vizit,
                  veriler=(kayit.veriler if kayit else {}), sorunlar=[])


@router.post("/{gid}/form/{form_id}")
async def form_kaydet(request: Request, gid: int, form_id: int, k: Kullanici = Depends(gerekli("veri.gir")),
                      db: Session = Depends(get_db)):
    g = _gonullu(db, gid, k)
    f = db.get(CRF, form_id)
    if not f or f.calisma_id != g.calisma_id:
        raise HTTPException(404)
    gelen = await request.form()
    vizit_id = int(gelen.get("vizit_id")) if gelen.get("vizit_id") else None
    islem = gelen.get("islem", "kaydet")
    veriler = ecrf.veri_oku(f, gelen)
    kayit = next((fk for fk in g.form_kayitlari if fk.form_id == f.id and fk.vizit_id == vizit_id), None)
    if kayit and kayit.durum == "kilitli":
        raise HTTPException(403, "Kilitli form değiştirilemez")
    eski = kayit.veriler if kayit else None
    gerekce = gelen.get("gerekce", "")
    if kayit and kayit.durum in ("tamamlandi", "sdv") and not gerekce:
        vizit = db.get(Vizit, vizit_id) if vizit_id else None
        return goster(request, "gonulluler/form.html", g=g, f=f, kayit=kayit, vizit=vizit, veriler=veriler,
                      sorunlar=[("", "Tamamlanmış bir formda değişiklik için gerekçe girilmesi zorunludur (21 CFR 11.10(e)).")])
    if not kayit:
        kayit = FormKaydi(gonullu_id=g.id, form_id=f.id, vizit_id=vizit_id, giren_id=k.id)
        db.add(kayit)
    kayit.veriler = veriler
    kayit.giren_id = k.id
    if kayit.durum == "sdv":
        kayit.durum = "tamamlandi"  # degisiklik sonrasi SDV yenilenmeli
    sorunlar = ecrf.edit_check(f, veriler)
    if islem == "tamamla":
        kayit.durum = "tamamlandi"
    db.flush()
    # otomatik sorgular (ayni alan icin acik sorgu varsa tekrar acma)
    acik_alanlar = {s.alan for s in kayit.sorgular if s.durum == "acik"}
    for alan, soru in sorunlar:
        if alan and alan not in acik_alanlar:
            db.add(Sorgu(form_kaydi_id=kayit.id, alan=alan, soru=soru, kaynak="otomatik", acan_id=None))
    denetim.kaydet(db, k, "guncelle" if eski is not None else "olustur", "form_kaydi", kayit.id,
                   eski={"veriler": eski} if eski is not None else None,
                   yeni={"veriler": veriler, "durum": kayit.durum, "form": f.kod, "gonullu": g.gonullu_no},
                   gerekce=gerekce or None, ip=ip(request))
    db.commit()
    if sorunlar:
        bilgi(request, f"Form kaydedildi; {len(sorunlar)} otomatik sorgu açıldı.")
    else:
        bilgi(request, "Form kaydedildi.")
    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)


@router.post("/{gid}/form-kaydi/{fk_id}/sdv")
def sdv(request: Request, gid: int, fk_id: int, k: Kullanici = Depends(gerekli("veri.sdv")), db: Session = Depends(get_db)):
    _gonullu(db, gid, k)
    fk = db.get(FormKaydi, fk_id)
    if not fk or fk.gonullu_id != gid:
        raise HTTPException(404)
    fk.durum = "sdv"
    fk.sdv_yapan_id = k.id
    fk.sdv_zamani = simdi()
    denetim.kaydet(db, k, "guncelle", "form_kaydi", fk.id, yeni={"durum": "sdv"}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{gid}", status_code=303)


@router.post("/{gid}/form-kaydi/{fk_id}/kilitle")
def kilitle(request: Request, gid: int, fk_id: int, k: Kullanici = Depends(gerekli("veri.kilitle")),
            db: Session = Depends(get_db), parola: str = Form(...)):
    from ..services.yetki import parola_dogrula

    _gonullu(db, gid, k)
    fk = db.get(FormKaydi, fk_id)
    if not fk or fk.gonullu_id != gid:
        raise HTTPException(404)
    if not parola_dogrula(parola, k.parola_hash):
        bilgi(request, "E-imza için parola doğrulanamadı; kilit uygulanmadı.")
        return RedirectResponse(f"/gonulluler/{gid}", status_code=303)
    if any(s.durum == "acik" for s in fk.sorgular):
        bilgi(request, "Açık sorgusu olan form kilitlenemez.")
        return RedirectResponse(f"/gonulluler/{gid}", status_code=303)
    fk.durum = "kilitli"
    fk.kilit_zamani = simdi()
    denetim.imzala(db, k, "form_kaydi", fk.id, "Veri kilidi", fk.veriler, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{gid}", status_code=303)


@router.post("/{gid}/sorgu")
def sorgu_ac(request: Request, gid: int, k: Kullanici = Depends(gerekli("sorgu.ac")), db: Session = Depends(get_db),
             form_kaydi_id: int = Form(...), alan: str = Form(...), soru: str = Form(...)):
    _gonullu(db, gid, k)
    s = Sorgu(form_kaydi_id=form_kaydi_id, alan=alan, soru=soru, acan_id=k.id, kaynak="manuel")
    db.add(s)
    db.flush()
    denetim.kaydet(db, k, "olustur", "sorgu", s.id, yeni={"alan": alan, "soru": soru}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{gid}", status_code=303)


@router.post("/{gid}/sorgu/{sid}")
def sorgu_islem(request: Request, gid: int, sid: int, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db),
                islem: str = Form(...), cevap: str = Form("")):
    _gonullu(db, gid, k)
    s = db.get(Sorgu, sid)
    if not s or s.form_kaydi.gonullu_id != gid:
        raise HTTPException(404)
    if islem == "cevapla" and izinli(k, "sorgu.cevapla"):
        s.cevap = cevap
        s.durum = "cevaplandi"
    elif islem == "kapat" and izinli(k, "sorgu.ac"):
        s.durum = "kapali"
        s.kapanis = simdi()
    else:
        raise HTTPException(403, "Yetkiniz yok")
    denetim.kaydet(db, k, "guncelle", "sorgu", s.id, yeni={"durum": s.durum, "cevap": cevap or None}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{gid}", status_code=303)


@router.post("/{gid}/advers-olay")
def advers_olay(request: Request, gid: int, k: Kullanici = Depends(gerekli("guvenlik.bildir")), db: Session = Depends(get_db),
                terim: str = Form(...), baslangic: str = Form(...), bitis: str = Form(""), siddet: str = Form("1"),
                nedensellik: str = Form("olasi_degil"), beklenen: str = Form("1"), ciddi: str = Form("0"),
                ciddiyet_olcutu: str = Form(""), sonuc: str = Form(""), alinan_onlem: str = Form(""), anlatim: str = Form("")):
    g = _gonullu(db, gid, k)
    a = AdversOlay(gonullu_id=g.id, terim=terim, baslangic=date.fromisoformat(baslangic),
                   bitis=date.fromisoformat(bitis) if bitis else None, siddet=siddet, nedensellik=nedensellik,
                   beklenen=beklenen == "1", ciddi=ciddi == "1", ciddiyet_olcutu=ciddiyet_olcutu or None,
                   sonuc=sonuc or None, alinan_onlem=alinan_onlem or None, anlatim=anlatim or None,
                   farkindalik_tarihi=date.today() if ciddi == "1" else None)
    db.add(a)
    db.flush()
    denetim.kaydet(db, k, "olustur", "advers_olay", a.id, yeni=denetim.varlik_sozluk(a), ip=ip(request))
    db.commit()
    if a.ciddi:
        bilgi(request, f"Ciddi advers olay kaydedildi. TİTCK bildirim süresi: {7 if a.ciddiyet_olcutu in ('olum','yasam_tehdidi') else 15} gün."
              + (" SUSAR kriterlerini karşılıyor; hızlandırılmış bildirim gerekir." if a.susar else ""))
    return RedirectResponse(f"/gonulluler/{gid}", status_code=303)


@router.post("/{gid}/advers-olay/{aid}/bildirim")
def sae_bildirim(request: Request, gid: int, aid: int, k: Kullanici = Depends(gerekli("guvenlik.bildir")),
                 db: Session = Depends(get_db), hedef: str = Form(...), tarih: str = Form("")):
    _gonullu(db, gid, k)
    a = db.get(AdversOlay, aid)
    if not a or a.gonullu_id != gid:
        raise HTTPException(404)
    t = date.fromisoformat(tarih) if tarih else date.today()
    setattr(a, {"sponsor": "sponsor_bildirim", "titck": "titck_bildirim", "etik": "etik_bildirim"}[hedef], t)
    denetim.kaydet(db, k, "guncelle", "advers_olay", a.id, yeni={f"{hedef}_bildirim": t.isoformat()}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{gid}", status_code=303)
