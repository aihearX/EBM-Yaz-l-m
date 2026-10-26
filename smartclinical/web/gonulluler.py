from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AdversOlay, CalismaMerkez, FormKaydi, Gonullu, GonulluDurumu, Kullanici, Sorgu, Vizit
from ..models import Form as CRF
from ..models._ortak import simdi
from ..models.guvenlik import CIDDIYET_OLCUTU, NEDENSELLIK, SIDDET, SOC_LISTESI, SONUC_LISTESI
from ..models.veri import KAYIT_DURUM_ETIKET, SORGU_ETIKET, VIZIT_DURUM_ETIKET
from ..services import denetim, ecrf
from ..services import gonullu as gsvc
from ..services import randomizasyon as rnd
from ..services.yetki import gerekli, gonullu_erisimi, izinli
from ._ortak import bilgi, ip, oturumlu
from .sablon import goster

router = APIRouter(prefix="/gonulluler")

ETIKETLER = {"VIZIT_DURUM_ETIKET": VIZIT_DURUM_ETIKET, "KAYIT_DURUM_ETIKET": KAYIT_DURUM_ETIKET,
             "SORGU_ETIKET": SORGU_ETIKET}



def _gonullu(db: Session, gid: int, k: Kullanici) -> Gonullu:
    g = db.get(Gonullu, gid)
    if not g:
        raise HTTPException(404, "Gönüllü bulunamadı")
    if not gonullu_erisimi(db, k, g):
        raise HTTPException(403, "Bu gönüllüye erişiminiz yok")
    return g


def _goruntule(request: Request, db: Session, k: Kullanici, varlik: str, vid: int, yeni: dict | None = None) -> None:
    """Gonullu / eCRF goruntuleme oturum basina bir kez denetim izine yazilir (erisim kaydi)."""
    anahtar = f"{varlik}:{vid}" + (f":{yeni.get('gonullu_id')}" if yeni else "")
    gorulen = list(request.session.get("gorulen") or [])
    if anahtar in gorulen:
        return
    denetim.kaydet(db, k, "goruntule", varlik, vid, yeni=yeni, ip=ip(request))
    db.commit()
    gorulen.append(anahtar)
    request.session["gorulen"] = gorulen[-200:]


def _tarih(v: str, varsayilan: date | None = None) -> date | None:
    try:
        return date.fromisoformat(v) if v else varsayilan
    except ValueError:
        raise HTTPException(400, "Tarih biçimi geçersiz (YYYY-AA-GG).")


def _kayitlar(g: Gonullu, f: CRF, vizit_id: int | None) -> list[FormKaydi]:
    return sorted((fk for fk in g.form_kayitlari if fk.form_id == f.id and fk.vizit_id == vizit_id),
                  key=lambda x: (x.tekrar_no or 1, x.id))


def _kayit_bul(g: Gonullu, f: CRF, vizit_id: int | None, tekrar_no: int | None = None,
               yeni: bool = False) -> FormKaydi | None:
    kayitlar = _kayitlar(g, f, vizit_id)
    if f.tekrarlayan:
        if yeni:
            return None
        if tekrar_no:
            return next((fk for fk in kayitlar if fk.tekrar_no == tekrar_no), None)
        return kayitlar[0] if kayitlar else None
    if kayitlar:
        return kayitlar[0]
    if vizit_id is not None:
        # vizite baglanmamis eski tarama kaydi: vizit hucresinden acilinca o kayit gosterilir
        bagsiz = _kayitlar(g, f, None)
        return bagsiz[0] if bagsiz else None
    return None


@router.post("/yeni")
def yeni(request: Request, k: Kullanici = Depends(gerekli("veri.gir")), db: Session = Depends(get_db),
         calisma_id: int = Form(...), calisma_merkez_id: int = Form(...), hasta_id: str = Form(""),
         onam_tarihi: str = Form(""), onam_versiyonu: str = Form("")):
    cm = db.get(CalismaMerkez, calisma_merkez_id)
    if not cm or cm.calisma_id != calisma_id:
        raise HTTPException(400, "Merkez çalışmaya ait değil")
    if cm.durum != "aktif":
        raise HTTPException(400, "Gönüllü yalnızca aktif merkeze kaydedilebilir")
    sira = len(cm.gonulluler) + 1
    onam = _tarih(onam_tarihi)
    g = Gonullu(calisma_id=calisma_id, calisma_merkez_id=cm.id, hasta_id=int(hasta_id) if hasta_id else None,
                gonullu_no=f"{cm.merkez_no}-{sira:03d}",
                durum=GonulluDurumu.ONAM if onam else GonulluDurumu.ADAY,
                onam_tarihi=onam, onam_versiyonu=onam_versiyonu or None)
    db.add(g)
    db.flush()
    if onam:
        gsvc.tarama_vizitleri_olustur(db, g, onam)
    denetim.kaydet(db, k, "olustur", "gonullu", g.id, yeni=denetim.varlik_sozluk(g), ip=ip(request))
    db.commit()
    bilgi(request, f"Gönüllü {g.gonullu_no} oluşturuldu.")
    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)


@router.get("/{gid}")
def detay(request: Request, gid: int, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    g = _gonullu(db, gid, k)
    _goruntule(request, db, k, "gonullu", g.id)
    # yalnizca yayindaki formlar veri girisinde gorunur; taslaklar tasarimcida kalir
    tum_formlar = sorted(g.calisma.formlar, key=lambda f: f.sira)
    formlar = [f for f in tum_formlar if f.durum != "taslak"]
    kayit_haritasi: dict[tuple[int, int | None], list[FormKaydi]] = {}
    for fk in sorted(g.form_kayitlari, key=lambda x: (x.tekrar_no or 1, x.id)):
        kayit_haritasi.setdefault((fk.form_id, fk.vizit_id), []).append(fk)
    bagsiz_kullanildi: set[int] = set()
    # vizit x form matrisi: Form.vizit_listesi bos ise her vizitte
    matris = []
    for v in sorted(g.vizitler, key=lambda x: (x.sira, x.id)):
        satir = {"vizit": v, "hucreler": []}
        for f in formlar:
            if not f.vizitte_var(v.ad):
                satir["hucreler"].append(None)
                continue
            kayitlar = kayit_haritasi.get((f.id, v.id), [])
            if not kayitlar and f.id not in bagsiz_kullanildi and (f.id, None) in kayit_haritasi:
                # vizite baglanmamis (onam/tarama asamasinda girilmis) kayit ilk uygun hucrede gosterilir
                kayitlar = kayit_haritasi[(f.id, None)]
                bagsiz_kullanildi.add(f.id)
            satir["hucreler"].append({"form": f, "kayitlar": kayitlar, "kayit": kayitlar[0] if kayitlar else None,
                                      "sayi": len(kayitlar)})
        matris.append(satir)
    bagsiz = [fk for (fid, vid), fks in kayit_haritasi.items() if vid is None and fid not in bagsiz_kullanildi
              for fk in fks if fk.form.durum != "taslak"]
    sorgular = [s for fk in g.form_kayitlari for s in fk.sorgular if s.durum != "kapali"]
    etiketler = gsvc.gonullu_durum_etiketleri(g.calisma)
    kol_sayisi = len(g.calisma.kollar)
    liste_var = kol_sayisi > 1 and rnd.liste_var(db, g.calisma)
    return goster(request, "gonulluler/detay.html", g=g, formlar=formlar, matris=matris, sorgular=sorgular, bagsiz=bagsiz,
                  taslak_form=len(tum_formlar) - len(formlar), sema_var=bool(g.calisma.vizit_tanimlari),
                  hedefler=gsvc.hedefler(g.durum), GD_ETIKET=etiketler, kol_sayisi=kol_sayisi, liste_var=liste_var,
                  uygunluk_ihlali=request.session.pop("uygunluk_ihlali", None) == g.id,
                  SIDDET=SIDDET, NEDENSELLIK=NEDENSELLIK, CIDDIYET=CIDDIYET_OLCUTU, SOC_LISTESI=SOC_LISTESI,
                  SONUC_LISTESI=SONUC_LISTESI, **ETIKETLER)


@router.post("/{gid}/durum")
def durum(request: Request, gid: int, k: Kullanici = Depends(gerekli("veri.gir")), db: Session = Depends(get_db),
          durum: str = Form(...), tarih: str = Form(""), neden: str = Form(""), kol_id: str = Form("")):
    g = _gonullu(db, gid, k)
    eski = g.durum.value
    try:
        yeni_durum = GonulluDurumu(durum)
    except ValueError:
        raise HTTPException(400, "Bilinmeyen durum.")
    etiketler = gsvc.gonullu_durum_etiketleri(g.calisma)
    if not gsvc.gecis_izinli(g.durum, yeni_durum):
        raise HTTPException(400, f"'{etiketler[g.durum]}' durumundan '{etiketler[yeni_durum]}' durumuna geçiş yapılamaz.")
    t = _tarih(tarih, date.today())
    kayit_yeni = {"durum": durum, "tarih": t.isoformat(), "neden": neden or None}
    if yeni_durum == GonulluDurumu.ONAM:
        g.onam_tarihi = t
        gsvc.tarama_vizitleri_olustur(db, g, t)
    elif yeni_durum == GonulluDurumu.TARAMA:
        g.tarama_tarihi = t
        gsvc.tarama_vizitleri_olustur(db, g, t)
    elif yeni_durum == GonulluDurumu.TARAMA_BASARISIZ:
        g.tarama_basarisizlik_nedeni = neden or None
    elif yeni_durum == GonulluDurumu.RANDOMIZE:
        # onam olmadan randomizasyon = major sapma; engelliyoruz
        if not g.onam_tarihi:
            bilgi(request, "Onam tarihi girilmeden randomizasyon yapılamaz (ICH E6 4.8).")
            return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)
        engel = gsvc.randomizasyon_engeli(g)
        if engel:
            bilgi(request, engel + " Uygun değilse gönüllüyü 'Tarama başarısız' yapın.")
            request.session["uygunluk_ihlali"] = g.id
            return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)
        kollar = g.calisma.kollar
        if len(kollar) > 1:
            if rnd.liste_var(db, g.calisma):
                try:
                    rnd.siradaki_tahsis(db, g)
                except ValueError as e:
                    bilgi(request, str(e))
                    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)
            else:
                kol = next((x for x in kollar if kol_id and str(x.id) == kol_id), None)
                if not kol:
                    bilgi(request, "Birden fazla kollu çalışmada kol seçilmeden randomizasyon yapılamaz.")
                    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)
                g.kol_id = kol.id
        elif kollar:
            g.kol_id = kollar[0].id
        g.randomizasyon_tarihi = t
        gsvc.vizitleri_olustur(db, g, t)
        gsvc.kayitlari_vizite_bagla(g)
        kayit_yeni["kol_id"] = g.kol_id
    elif yeni_durum in (GonulluDurumu.AYRILDI, GonulluDurumu.TAMAMLADI):
        g.bitis_tarihi = t
        g.ayrilma_nedeni = neden or None
    g.durum = yeni_durum
    denetim.kaydet(db, k, "guncelle", "gonullu", g.id, eski={"durum": eski}, yeni=kayit_yeni, ip=ip(request))
    db.commit()
    bilgi(request, f"Durum güncellendi: {etiketler[yeni_durum]}.")
    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)


@router.post("/{gid}/vizit/{vid}")
def vizit_kaydet(request: Request, gid: int, vid: int, k: Kullanici = Depends(gerekli("veri.gir")),
                 db: Session = Depends(get_db), gerceklesen: str = Form(""), durum: str = Form("yapildi"),
                 neden: str = Form("")):
    g = _gonullu(db, gid, k)
    v = db.get(Vizit, vid)
    if not v or v.gonullu_id != g.id:
        raise HTTPException(404)
    if durum not in ("yapildi", "kacirildi", "pencere_disi"):
        raise HTTPException(400, "Bilinmeyen vizit durumu.")
    eski = {"gerceklesen": v.gerceklesen, "durum": v.durum, "kacirilma_nedeni": v.kacirilma_nedeni}
    if durum == "kacirildi":
        if not neden.strip():
            raise HTTPException(400, "Kaçırılan vizit için gerekçe zorunludur.")
        v.gerceklesen = None
        v.kacirilma_nedeni = neden.strip()[:200]
    else:
        if not gerceklesen:
            raise HTTPException(400, "Gerçekleşen tarih girilmeli.")
        v.gerceklesen = _tarih(gerceklesen)
        v.kacirilma_nedeni = None
    v.durum = "pencere_disi" if durum == "yapildi" and v.pencere_disi else durum
    denetim.kaydet(db, k, "guncelle", "vizit", v.id, eski=eski,
                   yeni={"gerceklesen": v.gerceklesen, "durum": v.durum, "kacirilma_nedeni": v.kacirilma_nedeni},
                   ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{g.id}", status_code=303)


def _form(db: Session, g: Gonullu, form_id: int) -> CRF:
    f = db.get(CRF, form_id)
    if not f or f.calisma_id != g.calisma_id:
        raise HTTPException(404)
    return f


def _form_sayfasi(request: Request, g: Gonullu, f: CRF, kayit, vizit, veriler, sorunlar, **ek):
    satirlar = _kayitlar(g, f, vizit.id if vizit else None) if f.tekrarlayan else []
    return goster(request, "gonulluler/form.html", g=g, f=f, kayit=kayit, vizit=vizit, veriler=veriler,
                  sorunlar=sorunlar, sorun_alan={a: s for a, s in sorunlar if a}, satirlar=satirlar,
                  yeni_tekrar_no=(max((x.tekrar_no or 1 for x in satirlar), default=0) + 1), **ETIKETLER, **ek)


@router.get("/{gid}/form/{form_id}")
def form_goster(request: Request, gid: int, form_id: int, k: Kullanici = Depends(oturumlu),
                db: Session = Depends(get_db), vizit_id: int | None = None, tekrar_no: int | None = None,
                yeni: int = 0):
    g = _gonullu(db, gid, k)
    f = _form(db, g, form_id)
    _goruntule(request, db, k, "form", f.id, yeni={"gonullu_id": g.id, "gonullu": g.gonullu_no})
    kayit = _kayit_bul(g, f, vizit_id, tekrar_no, yeni=bool(yeni))
    vizit = db.get(Vizit, vizit_id) if vizit_id else None
    return _form_sayfasi(request, g, f, kayit, vizit, (kayit.veriler if kayit else {}), [], yeni_satir=bool(yeni))


@router.post("/{gid}/form/{form_id}")
async def form_kaydet(request: Request, gid: int, form_id: int, k: Kullanici = Depends(gerekli("veri.gir")),
                      db: Session = Depends(get_db)):
    g = _gonullu(db, gid, k)
    f = _form(db, g, form_id)
    request.state.kullanici = k  # formda kalinan yanitlar icin
    gelen = await request.form()
    vizit_id = int(gelen.get("vizit_id")) if gelen.get("vizit_id") else None
    tekrar_no = int(gelen.get("tekrar_no")) if str(gelen.get("tekrar_no") or "").isdigit() else None
    yeni_satir = gelen.get("yeni") == "1"
    islem = gelen.get("islem", "kaydet")
    veriler = ecrf.veri_oku(f, gelen)
    vizit = db.get(Vizit, vizit_id) if vizit_id else None
    kayit = _kayit_bul(g, f, vizit_id, tekrar_no, yeni=yeni_satir)
    if kayit and kayit.durum == "kilitli":
        raise HTTPException(403, "Kilitli form değiştirilemez")
    eski = kayit.veriler if kayit else None
    gerekce = gelen.get("gerekce", "")
    if kayit and kayit.durum in ("tamamlandi", "sdv") and not gerekce:
        return _form_sayfasi(request, g, f, kayit, vizit, veriler,
                             [("", "Tamamlanmış bir formda değişiklik için gerekçe girilmesi zorunludur (21 CFR 11.10(e)).")])
    if not kayit:
        satirlar = _kayitlar(g, f, vizit_id)
        kayit = FormKaydi(gonullu_id=g.id, form_id=f.id, vizit_id=vizit_id, giren_id=k.id,
                          tekrar_no=(max((x.tekrar_no or 1 for x in satirlar), default=0) + 1) if f.tekrarlayan else 1)
        db.add(kayit)
        g.form_kayitlari.append(kayit)
    elif vizit_id is not None and kayit.vizit_id is None:
        kayit.vizit_id = vizit_id  # bagsiz tarama kaydi vizit hucresinden kaydedilince baglanir
    kayit.veriler = veriler
    kayit.giren_id = k.id
    kayit.form_versiyon = f.versiyon
    if kayit.durum == "sdv":
        kayit.durum = "tamamlandi"  # degisiklik sonrasi SDV yenilenmeli
    sorunlar = ecrf.edit_check(f, veriler)
    if islem == "tamamla" and sorunlar:
        # yonlendirme yok: kullanici formda kalir, alan altinda uyari gorur; 'yine de tamamla' sorgulari acar
        db.flush()
        denetim.kaydet(db, k, "guncelle" if eski is not None else "olustur", "form_kaydi", kayit.id,
                       eski={"veriler": eski} if eski is not None else None,
                       yeni={"veriler": veriler, "durum": kayit.durum, "form": f.kod, "gonullu": g.gonullu_no},
                       gerekce=gerekce or None, ip=ip(request))
        db.commit()
        return _form_sayfasi(request, g, f, kayit, vizit, veriler, sorunlar, onay_bekliyor=True, gerekce=gerekce)
    if islem in ("tamamla", "tamamla_onayla"):
        kayit.durum = "tamamlandi"
    db.flush()
    # otomatik sorgular yalnizca tamamlanmis kayitta; ayni alan icin acik sorgu varsa tekrar acilmaz
    acilan = 0
    if kayit.durum == "tamamlandi":
        acik_alanlar = {s.alan for s in kayit.sorgular if s.durum == "acik"}
        for alan, soru in sorunlar:
            if alan and alan not in acik_alanlar:
                db.add(Sorgu(form_kaydi_id=kayit.id, alan=alan, soru=soru, kaynak="otomatik", acan_id=None))
                acilan += 1
    denetim.kaydet(db, k, "guncelle" if eski is not None else "olustur", "form_kaydi", kayit.id,
                   eski={"veriler": eski} if eski is not None else None,
                   yeni={"veriler": veriler, "durum": kayit.durum, "form": f.kod, "gonullu": g.gonullu_no,
                         "tekrar_no": kayit.tekrar_no, "form_versiyon": kayit.form_versiyon},
                   gerekce=gerekce or None, ip=ip(request))
    db.commit()
    if acilan:
        bilgi(request, f"Form kaydedildi; {acilan} otomatik sorgu açıldı.")
    else:
        bilgi(request, "Form kaydedildi.")
    if f.tekrarlayan:
        return RedirectResponse(f"/gonulluler/{g.id}/form/{f.id}?vizit_id={vizit_id or ''}", status_code=303)
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
    fk = db.get(FormKaydi, form_kaydi_id)
    if not fk or fk.gonullu_id != gid:
        raise HTTPException(404)
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


# --- Advers olay ----------------------------------------------------------------

def _advers_olay(db: Session, gid: int, aid: int) -> AdversOlay:
    a = db.get(AdversOlay, aid)
    if not a or a.gonullu_id != gid:
        raise HTTPException(404, "Advers olay bulunamadı")
    return a


def _sae_mesaji(a: AdversOlay) -> str:
    return (f"Ciddi advers olay kaydedildi. TİTCK bildirim süresi: {7 if a.ciddiyet_olcutu in ('olum', 'yasam_tehdidi') else 15} gün."
            + (" SUSAR kriterlerini karşılıyor; hızlandırılmış bildirim gerekir." if a.susar else ""))


@router.post("/{gid}/advers-olay")
def advers_olay(request: Request, gid: int, k: Kullanici = Depends(gerekli("guvenlik.bildir")), db: Session = Depends(get_db),
                terim: str = Form(...), baslangic: str = Form(...), bitis: str = Form(""), siddet: str = Form("1"),
                nedensellik: str = Form("olasi_degil"), beklenen: str = Form("1"), ciddi: str = Form("0"),
                ciddiyet_olcutu: str = Form(""), sonuc: str = Form(""), alinan_onlem: str = Form(""), anlatim: str = Form(""),
                meddra_soc: str = Form("")):
    g = _gonullu(db, gid, k)
    a = AdversOlay(gonullu_id=g.id, terim=terim, baslangic=_tarih(baslangic),
                   bitis=_tarih(bitis), siddet=siddet, nedensellik=nedensellik,
                   beklenen=beklenen == "1", ciddi=ciddi == "1", ciddiyet_olcutu=ciddiyet_olcutu or None,
                   sonuc=sonuc or None, alinan_onlem=alinan_onlem or None, anlatim=anlatim or None,
                   meddra_soc=meddra_soc if meddra_soc in SOC_LISTESI else None,
                   farkindalik_tarihi=date.today() if ciddi == "1" else None)
    db.add(a)
    db.flush()
    denetim.kaydet(db, k, "olustur", "advers_olay", a.id, yeni=denetim.varlik_sozluk(a), ip=ip(request))
    db.commit()
    if a.ciddi:
        bilgi(request, _sae_mesaji(a))
    return RedirectResponse(f"/gonulluler/{gid}", status_code=303)


@router.get("/{gid}/advers-olay/{aid}")
def advers_olay_goster(request: Request, gid: int, aid: int, k: Kullanici = Depends(oturumlu),
                       db: Session = Depends(get_db)):
    g = _gonullu(db, gid, k)
    a = _advers_olay(db, gid, aid)
    return goster(request, "gonulluler/advers_olay.html", g=g, a=a, hata=None, SIDDET=SIDDET, NEDENSELLIK=NEDENSELLIK,
                  CIDDIYET=CIDDIYET_OLCUTU, SOC_LISTESI=SOC_LISTESI, SONUC_LISTESI=SONUC_LISTESI)


@router.post("/{gid}/advers-olay/{aid}")
def advers_olay_guncelle(request: Request, gid: int, aid: int, k: Kullanici = Depends(gerekli("guvenlik.bildir")),
                         db: Session = Depends(get_db), bitis: str = Form(""), sonuc: str = Form(""),
                         siddet: str = Form(""), nedensellik: str = Form(""), ciddi: str = Form(""),
                         ciddiyet_olcutu: str = Form(""), takip_notu: str = Form(""), meddra_soc: str = Form(""),
                         meddra_pt: str = Form(""), farkindalik_tarihi: str = Form(""), gerekce: str = Form("")):
    g = _gonullu(db, gid, k)
    a = _advers_olay(db, gid, aid)
    request.state.kullanici = k
    if not gerekce.strip():
        return goster(request, "gonulluler/advers_olay.html", g=g, a=a, hata="Değişiklik için gerekçe zorunludur.",
                      SIDDET=SIDDET, NEDENSELLIK=NEDENSELLIK, CIDDIYET=CIDDIYET_OLCUTU, SOC_LISTESI=SOC_LISTESI,
                      SONUC_LISTESI=SONUC_LISTESI)
    eski = denetim.varlik_sozluk(a)
    a.bitis = _tarih(bitis)
    a.sonuc = sonuc or None
    if siddet in SIDDET:
        a.siddet = siddet
    if nedensellik in NEDENSELLIK:
        a.nedensellik = nedensellik
    a.ciddiyet_olcutu = ciddiyet_olcutu or None
    a.meddra_soc = meddra_soc if meddra_soc in SOC_LISTESI else None
    a.meddra_pt = meddra_pt.strip()[:120] or None
    yukseltildi = False
    if ciddi == "1" and not a.ciddi:
        # ciddiyet yalnizca yukseltilir; geri alma yok (bildirim yukumlulugu dogmus olabilir)
        a.ciddi = True
        yukseltildi = True
    if a.ciddi:
        a.farkindalik_tarihi = _tarih(farkindalik_tarihi) or a.farkindalik_tarihi or date.today()
    if takip_notu.strip():
        satir = f"{date.today().isoformat()} {k.ad_soyad}: {takip_notu.strip()}"
        a.takip_notu = (a.takip_notu + "\n" + satir) if a.takip_notu else satir
    yeni = denetim.varlik_sozluk(a)
    degisen = {ad: v for ad, v in yeni.items() if eski.get(ad) != v}
    denetim.kaydet(db, k, "guncelle", "advers_olay", a.id, eski={ad: eski.get(ad) for ad in degisen}, yeni=degisen,
                   gerekce=gerekce.strip(), ip=ip(request))
    db.commit()
    bilgi(request, _sae_mesaji(a) if yukseltildi else "Advers olay güncellendi.")
    return RedirectResponse(f"/gonulluler/{gid}/advers-olay/{aid}", status_code=303)


@router.post("/{gid}/advers-olay/{aid}/bildirim")
def sae_bildirim(request: Request, gid: int, aid: int, k: Kullanici = Depends(gerekli("guvenlik.bildir")),
                 db: Session = Depends(get_db), hedef: str = Form(...), tarih: str = Form("")):
    _gonullu(db, gid, k)
    a = _advers_olay(db, gid, aid)
    if hedef not in ("sponsor", "titck", "etik"):
        raise HTTPException(400, "Bilinmeyen bildirim hedefi.")
    t = _tarih(tarih, date.today())
    setattr(a, f"{hedef}_bildirim", t)
    denetim.kaydet(db, k, "guncelle", "advers_olay", a.id, yeni={f"{hedef}_bildirim": t.isoformat()}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/gonulluler/{gid}", status_code=303)
