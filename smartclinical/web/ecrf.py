"""Calisma tasarimi: kollar, vizit semasi, eCRF tasarimcisi ve protokolden taslak."""
import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Calisma, Kol, Kriter, Kullanici
from ..models import Form as CRF
from ..models.tasarim import VizitTanimi
from ..services import denetim
from ..services import ecrf as svc
from ..services import protokol as protokol_svc
from ..services.yetki import gerekli
from ._ortak import bilgi, calisma_getir, ip, oturumlu
from .calismalar import _ozet, sekme_kontrol
from .sablon import goster

router = APIRouter(prefix="/calismalar/{calisma_id}/tasarim")

# Tasarimcida alan tipine gore CDASH degisken onerileri (datalist)
CDASH_ONERILERI = [
    "DM.BRTHDTC", "DM.SEX", "DM.AGE", "VS.VSDTC", "VS.VSORRES", "VS.VSORRESU", "LB.LBDTC", "LB.LBORRES",
    "LB.LBORRESU", "AE.AETERM", "AE.AESTDTC", "AE.AEENDTC", "AE.AESEV", "AE.AESER", "CM.CMTRT", "CM.CMINDC",
    "CM.CMSTDTC", "CM.CMENDTC", "CM.CMONGO", "MH.MHTERM", "MH.MHSTDTC", "MH.MHONGO", "EX.EXDOSE", "EX.EXDOSU",
    "EX.EXSTDTC", "EX.EXENDTC", "IE.IEORRES", "IE.IETESTCD", "QS.QSORRES", "QS.QSSTRESN", "QS.QSDTC",
    "DS.DSTERM", "DS.DSSTDTC", "SV.SVSTDTC", "PE.PEORRES",
]
YUKLEME_SINIRI = 20 * 1024 * 1024  # protokol belgesi en cok 20 MB


def _yol(c: Calisma, ek: str = "") -> str:
    return f"/calismalar/{c.id}/tasarim{ek}"


def _form(db: Session, c: Calisma, form_id: int) -> CRF:
    f = db.get(CRF, form_id)
    if not f or f.calisma_id != c.id:
        raise HTTPException(404, "Form bulunamadı")
    return f


def _ortak(db: Session, c: Calisma) -> dict:
    return {"c": c, "o": _ozet(db, c), "sekme": "tasarim"}


# --- Ozet -------------------------------------------------------------------

@router.get("")
def ozet(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
         db: Session = Depends(get_db)):
    sekme_kontrol(k, "tasarim", db, c)
    formlar = sorted(c.formlar, key=lambda f: f.sira)
    mevcut = {f.kod for f in formlar}
    kol_gonullu = {kol.id: sum(1 for g in c.gonulluler if g.kol_id == kol.id) for kol in c.kollar}
    vizitler = sorted(c.vizit_tanimlari, key=lambda t: t.sira)
    # vizit x form matrisi: hangi form hangi vizitte doldurulur
    matris = [{"form": f, "vizitler": [f.vizitte_var(t.ad) for t in vizitler]} for f in formlar]
    return goster(request, "ecrf/ozet.html", **_ortak(db, c), formlar=formlar,
                  standart=[(kod, s["ad"]) for kod, s in svc.STANDART_FORMLAR.items() if kod not in mevcut],
                  sablonlar=svc.VIZIT_SABLON_ETIKET, sablon_satirlar=svc.VIZIT_SABLONLARI,
                  sema_degisir=svc.vizit_semasi_degistirilebilir(c), kol_gonullu=kol_gonullu,
                  kayitli_formlar={f.id for f in formlar if not svc.form_degistirilebilir(f)},
                  FORM_DURUMLARI=svc.FORM_DURUMLARI, vizitler=vizitler, matris=matris)


# --- Kollar -----------------------------------------------------------------

@router.post("/kol")
def kol_ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
             db: Session = Depends(get_db), ad: str = Form(...), aciklama: str = Form(""), oran: int = Form(1)):
    kol = Kol(calisma_id=c.id, ad=ad.strip()[:80], aciklama=aciklama.strip() or None, oran=max(1, oran))
    db.add(kol)
    db.flush()
    denetim.kaydet(db, k, "olustur", "kol", kol.id, yeni=denetim.varlik_sozluk(kol), ip=ip(request))
    db.commit()
    bilgi(request, f"'{kol.ad}' kolu eklendi.")
    return RedirectResponse(_yol(c), status_code=303)


@router.post("/kol/{kol_id}/sil")
def kol_sil(request: Request, kol_id: int, c: Calisma = Depends(calisma_getir),
            k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db)):
    kol = db.get(Kol, kol_id)
    if not kol or kol.calisma_id != c.id:
        raise HTTPException(404)
    if any(g.kol_id == kol.id for g in c.gonulluler):
        bilgi(request, "Gönüllü atanmış kol silinemez.")
        return RedirectResponse(_yol(c), status_code=303)
    denetim.kaydet(db, k, "sil", "kol", kol.id, eski=denetim.varlik_sozluk(kol), ip=ip(request))
    db.delete(kol)
    db.commit()
    return RedirectResponse(_yol(c), status_code=303)


# --- Vizit semasi -----------------------------------------------------------

@router.post("/vizit/sablon")
def vizit_sablon(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
                 db: Session = Depends(get_db), sablon: str = Form(...)):
    eski = [(t.ad, t.gun, t.pencere_gun) for t in c.vizit_tanimlari]
    try:
        yeni = svc.vizit_semasi_uygula(db, c, sablon)
    except ValueError as e:
        db.rollback()
        bilgi(request, str(e))
        return RedirectResponse(_yol(c), status_code=303)
    denetim.kaydet(db, k, "guncelle", "vizit_semasi", c.id, eski={"vizitler": eski},
                   yeni={"sablon": sablon, "vizitler": [(t.ad, t.gun, t.pencere_gun) for t in yeni]}, ip=ip(request))
    db.commit()
    bilgi(request, f"Vizit şeması uygulandı: {len(yeni)} vizit.")
    return RedirectResponse(_yol(c), status_code=303)


@router.post("/vizit")
def vizit_ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
               db: Session = Depends(get_db), ad: str = Form(...), gun: int = Form(...), pencere_gun: int = Form(3)):
    if not ad.strip():
        bilgi(request, "Vizit adı boş olamaz.")
        return RedirectResponse(_yol(c), status_code=303)
    if any(t.ad == ad.strip() for t in c.vizit_tanimlari):
        bilgi(request, f"'{ad.strip()}' adlı vizit zaten var.")
        return RedirectResponse(_yol(c), status_code=303)
    t = svc.vizit_ekle(db, c, ad, gun, pencere_gun)
    denetim.kaydet(db, k, "olustur", "vizit_tanimi", t.id, yeni=denetim.varlik_sozluk(t), ip=ip(request))
    db.commit()
    return RedirectResponse(_yol(c), status_code=303)


@router.post("/vizit/{vizit_id}/sil")
def vizit_sil(request: Request, vizit_id: int, c: Calisma = Depends(calisma_getir),
              k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db)):
    t = db.get(VizitTanimi, vizit_id)
    if not t or t.calisma_id != c.id:
        raise HTTPException(404)
    if not svc.vizit_semasi_degistirilebilir(c):
        bilgi(request, "Vizit kaydı oluşturulmuş gönüllüsü olan çalışmada vizit silinemez.")
        return RedirectResponse(_yol(c), status_code=303)
    denetim.kaydet(db, k, "sil", "vizit_tanimi", t.id, eski=denetim.varlik_sozluk(t), ip=ip(request))
    c.vizit_tanimlari.remove(t)
    db.delete(t)
    svc._vizit_sirala(c)
    db.commit()
    return RedirectResponse(_yol(c), status_code=303)


# --- Formlar ----------------------------------------------------------------

@router.post("/form/standart")
async def form_standart(request: Request, c: Calisma = Depends(calisma_getir),
                        k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db)):
    gelen = await request.form()
    kodlar = gelen.getlist("kodlar")
    eklenen = svc.standart_formlari_ekle(db, c, kodlar)
    for f in eklenen:
        denetim.kaydet(db, k, "olustur", "form", f.id, yeni={"calisma": c.kod, "kod": f.kod, "ad": f.ad,
                       "versiyon": f.versiyon, "durum": f.durum, "tekrarlayan": f.tekrarlayan, "alanlar": f.alanlar},
                       ip=ip(request))
    db.commit()
    taslak = [f.ad for f in eklenen if f.durum == "taslak"]
    mesaj = f"{len(eklenen)} standart form eklendi." if eklenen else "Eklenecek yeni form seçilmedi."
    if taslak:
        mesaj += f" {', '.join(taslak)} taslak olarak eklendi; alanlarını tasarımcıda tamamlayıp yayına alın."
    bilgi(request, mesaj)
    return RedirectResponse(_yol(c), status_code=303)


def _tasarimci(request, db, c, f: CRF | None, hatalar=None, taslak: dict | None = None):
    """Tasarimci sayfasi. `taslak` dogrulama hatasinda kullanicinin gonderdigi degerleri geri tasir."""
    return goster(request, "ecrf/form_tasarim.html", **_ortak(db, c), f=f, hatalar=hatalar or [],
                  taslak=taslak, tipler=svc.ALAN_TIPLERI, FORM_DURUMLARI=svc.FORM_DURUMLARI,
                  vizit_tanimlari=list(c.vizit_tanimlari), cdash_onerileri=CDASH_ONERILERI,
                  degistirilebilir=(svc.form_degistirilebilir(f) if f else True),
                  alanlar_json=json.dumps((taslak or {}).get("alanlar", f.alanlar if f else []), ensure_ascii=False))


@router.get("/form/yeni")
def form_yeni(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
              db: Session = Depends(get_db)):
    request.state.kullanici = k
    sekme_kontrol(k, "tasarim", db, c)
    return _tasarimci(request, db, c, None)


async def _form_girdisi(request: Request, c: Calisma, f: CRF | None) -> tuple[dict, list[str]]:
    gelen = await request.form()
    kod = (gelen.get("kod") or "").strip().upper()
    ad = (gelen.get("ad") or "").strip()
    try:
        ham = json.loads(gelen.get("alanlar_json") or "[]")
    except json.JSONDecodeError:
        ham = None
    alanlar = [svc.alan_normalize(a) for a in ham] if isinstance(ham, list) else []
    hatalar: list[str] = []
    if ham is None:
        hatalar.append("Alan listesi okunamadı (tarayıcıda betik çalışmıyor olabilir).")
    if not svc.FORM_KOD.match(kod):
        hatalar.append("Form kodu büyük harf, rakam ve alt çizgiden oluşmalı (en çok 16 karakter).")
    elif any(x.kod == kod and (f is None or x.id != f.id) for x in c.formlar):
        hatalar.append(f"'{kod}' kodlu bir form bu çalışmada zaten var.")
    if not ad:
        hatalar.append("Form adı boş olamaz.")
    hatalar += svc.form_dogrula(alanlar)
    durum = gelen.get("durum") or "taslak"
    if durum not in svc.FORM_DURUMLARI:
        durum = "taslak"
    vizit_adlari = {t.ad for t in c.vizit_tanimlari}
    vizitler = [v for v in gelen.getlist("vizitler") if v in vizit_adlari]
    if not vizit_adlari and f is not None:
        vizitler = f.vizit_listesi  # sema tanimli degilken eski baglanti korunur
    taslak = {"kod": kod, "ad": ad, "aciklama": (gelen.get("aciklama") or "").strip(), "durum": durum,
              "vizitler": vizitler, "alanlar": alanlar, "tekrarlayan": gelen.get("tekrarlayan") in ("1", "on", "true")}
    return taslak, hatalar


@router.post("/form/yeni")
async def form_olustur(request: Request, c: Calisma = Depends(calisma_getir),
                       k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db)):
    request.state.kullanici = k
    taslak, hatalar = await _form_girdisi(request, c, None)
    if hatalar:
        return _tasarimci(request, db, c, None, hatalar, taslak)
    f = CRF(calisma_id=c.id, kod=taslak["kod"], ad=taslak["ad"], aciklama=taslak["aciklama"] or None,
            durum=taslak["durum"], vizitler=taslak["vizitler"], alanlar=taslak["alanlar"], versiyon="1.0",
            tekrarlayan=taslak["tekrarlayan"], sira=max((x.sira for x in c.formlar), default=-1) + 1)
    db.add(f)
    db.flush()
    denetim.kaydet(db, k, "olustur", "form", f.id, yeni={"calisma": c.kod, "kod": f.kod, "ad": f.ad, "versiyon": f.versiyon,
                   "durum": f.durum, "vizitler": f.vizitler, "tekrarlayan": f.tekrarlayan, "alanlar": f.alanlar},
                   ip=ip(request))
    db.commit()
    bilgi(request, f"'{f.ad}' formu oluşturuldu (v{f.versiyon}).")
    return RedirectResponse(_yol(c, f"/form/{f.id}"), status_code=303)


@router.get("/form/{form_id}")
def form_duzenle(request: Request, form_id: int, c: Calisma = Depends(calisma_getir),
                 k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db)):
    request.state.kullanici = k
    sekme_kontrol(k, "tasarim", db, c)
    return _tasarimci(request, db, c, _form(db, c, form_id))


@router.post("/form/{form_id}")
async def form_kaydet(request: Request, form_id: int, c: Calisma = Depends(calisma_getir),
                      k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db)):
    request.state.kullanici = k
    f = _form(db, c, form_id)
    taslak, hatalar = await _form_girdisi(request, c, f)
    kaydi_var = not svc.form_degistirilebilir(f)
    if kaydi_var:
        hatalar += svc.alan_degisikligi_kontrol(f.alanlar, taslak["alanlar"])
    if hatalar:
        return _tasarimci(request, db, c, f, hatalar, taslak)
    eski = {"kod": f.kod, "ad": f.ad, "aciklama": f.aciklama, "durum": f.durum, "vizitler": f.vizit_listesi,
            "versiyon": f.versiyon, "tekrarlayan": f.tekrarlayan, "alanlar": f.alanlar}
    # normalize edilmis eski liste ile karsilastir; bos anahtar farklari surum artirmasin
    alan_degisti = taslak["alanlar"] != [svc.alan_normalize(a) for a in f.alanlar]
    f.kod, f.ad, f.aciklama, f.durum = taslak["kod"], taslak["ad"], taslak["aciklama"] or None, taslak["durum"]
    f.vizitler, f.vizit_adi = taslak["vizitler"], None
    f.alanlar = taslak["alanlar"]
    f.tekrarlayan = taslak["tekrarlayan"]
    if kaydi_var and alan_degisti:
        f.versiyon = svc.versiyon_artir(f.versiyon)
    yeni = {"kod": f.kod, "ad": f.ad, "aciklama": f.aciklama, "durum": f.durum, "vizitler": f.vizitler,
            "versiyon": f.versiyon, "tekrarlayan": f.tekrarlayan, "alanlar": f.alanlar}
    if yeni != eski:
        denetim.kaydet(db, k, "guncelle", "form", f.id, eski=eski, yeni=yeni, ip=ip(request))
    db.commit()
    bilgi(request, f"'{f.ad}' kaydedildi (v{f.versiyon})." + (" Kaydı olan formda değişiklik yeni sürüm oluşturdu."
                                                              if kaydi_var and alan_degisti else ""))
    return RedirectResponse(_yol(c, f"/form/{f.id}"), status_code=303)


@router.post("/form/{form_id}/sil")
def form_sil(request: Request, form_id: int, c: Calisma = Depends(calisma_getir),
             k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db)):
    f = _form(db, c, form_id)
    if not svc.form_degistirilebilir(f):
        bilgi(request, "Veri kaydı olan form silinemez; yayından kaldırmak için durumunu 'Taslak' yapın.")
        return RedirectResponse(_yol(c, f"/form/{f.id}"), status_code=303)
    denetim.kaydet(db, k, "sil", "form", f.id, eski={"kod": f.kod, "ad": f.ad, "alanlar": f.alanlar}, ip=ip(request))
    db.delete(f)
    db.commit()
    bilgi(request, f"'{f.ad}' formu silindi.")
    return RedirectResponse(_yol(c), status_code=303)


@router.get("/form/{form_id}/onizle")
def form_onizle(request: Request, form_id: int, c: Calisma = Depends(calisma_getir),
                k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db)):
    sekme_kontrol(k, "tasarim", db, c)
    f = _form(db, c, form_id)
    return goster(request, "gonulluler/form.html", g=None, f=f, kayit=None, vizit=None, veriler={}, sorunlar=[],
                  onizleme=True, geri=_yol(c, f"/form/{f.id}"))


# --- Protokolden taslak -----------------------------------------------------

@router.get("/protokol-taslak")
def protokol_taslak(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
                    db: Session = Depends(get_db)):
    request.state.kullanici = k
    sekme_kontrol(k, "tasarim", db, c)
    son = next((v.metin for v in reversed(c.versiyonlar) if v.metin), "")
    return goster(request, "ecrf/protokol_taslak.html", **_ortak(db, c), metin=son, taslak=None)


@router.post("/protokol-taslak/metin")
def protokol_taslak_metin(request: Request, c: Calisma = Depends(calisma_getir),
                          k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db),
                          metin: str = Form("")):
    """Oneri sayfasindan metne donus: textarea gonderilen metinle dolu gelir."""
    request.state.kullanici = k
    return goster(request, "ecrf/protokol_taslak.html", **_ortak(db, c), metin=metin, taslak=None)


def _oneri_sayfasi(request, db, c, t, metin):
    # yalnizca oneri: hicbir sey yazilmadi; mevcut tanimlarla cakisanlar isaretlenir
    mevcut_kriter = {protokol_svc.kriter_anahtar(x.metin) for x in c.kriterler}
    mevcut_kol = {x.ad.strip() for x in c.kollar}
    mevcut_vizit = {x.ad for x in c.vizit_tanimlari}
    mevcut_form = {x.kod for x in c.formlar}
    kriter_var = {s: protokol_svc.kriter_anahtar(s) in mevcut_kriter for s in t.dahil + t.haric + t.taninmayan}
    return goster(request, "ecrf/protokol_oneri.html", **_ortak(db, c), t=t, metin=metin,
                  mevcut={"kriter": kriter_var, "kol": mevcut_kol, "vizit": mevcut_vizit, "form": mevcut_form},
                  form_adlari={kod: s["ad"] for kod, s in svc.STANDART_FORMLAR.items()},
                  sema_degisir=svc.vizit_semasi_degistirilebilir(c))


@router.post("/protokol-taslak")
def protokol_taslak_cikar(request: Request, c: Calisma = Depends(calisma_getir),
                          k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db),
                          metin: str = Form("")):
    from ..services.bdm import BDMIstemci

    request.state.kullanici = k
    if not metin.strip():
        bilgi(request, "Önce protokol metnini yapıştırın.")
        return RedirectResponse(_yol(c, "/protokol-taslak"), status_code=303)
    t = protokol_svc.taslak_cikar(metin, BDMIstemci.olustur())
    return _oneri_sayfasi(request, db, c, t, metin)


@router.post("/protokol-taslak/dosya")
async def protokol_taslak_dosya(request: Request, c: Calisma = Depends(calisma_getir),
                                k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db),
                                dosya: UploadFile | None = None):
    """PDF/DOCX protokol belgesi: metin sunucuda cikarilir, dosya saklanmaz, taslak hemen uretilir."""
    from ..services.bdm import BDMIstemci

    request.state.kullanici = k
    if dosya is None or not dosya.filename:
        bilgi(request, "Bir PDF ya da DOCX dosyası seçin.")
        return RedirectResponse(_yol(c, "/protokol-taslak"), status_code=303)
    icerik = await dosya.read(YUKLEME_SINIRI + 1)
    if len(icerik) > YUKLEME_SINIRI:
        bilgi(request, "Dosya 20 MB sınırını aşıyor; ilgili bölümleri metin olarak yapıştırın.")
        return RedirectResponse(_yol(c, "/protokol-taslak"), status_code=303)
    try:
        metin = protokol_svc.belge_metni(icerik, dosya.filename)
    except ValueError as e:
        bilgi(request, str(e))
        return RedirectResponse(_yol(c, "/protokol-taslak"), status_code=303)
    except Exception:
        bilgi(request, "Dosya okunamadı; bozuk ya da şifreli olabilir. Metni yapıştırarak deneyin.")
        return RedirectResponse(_yol(c, "/protokol-taslak"), status_code=303)
    if not metin.strip():
        bilgi(request, "Dosyadan metin çıkarılamadı (taranmış PDF olabilir). Metni yapıştırarak deneyin.")
        return RedirectResponse(_yol(c, "/protokol-taslak"), status_code=303)
    denetim.kaydet(db, k, "protokol_belge", "calisma", c.id,
                   yeni={"calisma": c.kod, "dosya": dosya.filename, "karakter": len(metin), "saklandi": False}, ip=ip(request))
    db.commit()
    t = protokol_svc.taslak_cikar(metin, BDMIstemci.olustur())
    t.notlar.insert(0, f"'{dosya.filename}' dosyasından {len(metin)} karakter metin çıkarıldı; dosya saklanmadı.")
    return _oneri_sayfasi(request, db, c, t, metin)


@router.post("/protokol-taslak/uygula")
async def protokol_taslak_uygula(request: Request, c: Calisma = Depends(calisma_getir),
                                 k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db)):
    from ..services.bdm import BDMIstemci

    gelen = await request.form()
    istemci = BDMIstemci.olustur()
    sayac = {"kriter": 0, "kol": 0, "vizit": 0, "form": 0}
    # taninmayan satirlar: kullanici tek tikla dahil / haric / kol olarak isaretler
    ek = {"dahil": [], "haric": [], "kollar": []}
    for anahtar in gelen.keys():
        if not anahtar.startswith("tn_tip_"):
            continue
        tip = gelen.get(anahtar)
        metin = (gelen.get("tn_metin_" + anahtar[len("tn_tip_"):]) or "").strip()
        if metin and tip in ("dahil", "haric"):
            ek[tip].append(metin)
        elif metin and tip == "kol":
            ek["kollar"].append(metin)
    # kriterler: calismalar.kriter_ekle ile ayni yol (BDM yapilandirma + onay bekler)
    for tip in ("dahil", "haric"):
        sira = len([x for x in c.kriterler if x.tip == tip])
        mevcut = {protokol_svc.kriter_anahtar(x.metin) for x in c.kriterler}
        for s in list(gelen.getlist(tip)) + ek[tip]:
            s = s.strip()
            if not s or protokol_svc.kriter_anahtar(s) in mevcut:
                continue
            yapi = istemci.kriter_yapilandir(s, tip)
            sira += 1
            kr = Kriter(calisma_id=c.id, tip=tip, sira=sira, metin=s, yapisal=yapi.to_dict(), guven=yapi.guven,
                        onaylandi=False)
            db.add(kr)
            db.flush()
            denetim.kaydet(db, k, "olustur", "kriter", kr.id, yeni={"calisma": c.kod, "tip": tip, "metin": s,
                           "yontem": yapi.yontem, "guven": yapi.guven, "kaynak": "protokol_taslak"}, ip=ip(request))
            mevcut.add(protokol_svc.kriter_anahtar(s))
            sayac["kriter"] += 1
    # kollar
    mevcut_kol = {x.ad.strip() for x in c.kollar}
    for ad in list(gelen.getlist("kollar")) + ek["kollar"]:
        ad = ad.strip()[:80]
        if not ad or ad in mevcut_kol:
            continue
        kol = Kol(calisma_id=c.id, ad=ad, oran=1)
        db.add(kol)
        db.flush()
        denetim.kaydet(db, k, "olustur", "kol", kol.id, yeni=denetim.varlik_sozluk(kol), ip=ip(request))
        mevcut_kol.add(ad)
        sayac["kol"] += 1
    # vizitler: "ad|gun|pencere"
    secili_vizit = []
    for v in gelen.getlist("vizitler"):
        try:
            ad, gun, pencere = v.rsplit("|", 2)
            secili_vizit.append((ad.strip()[:40], int(gun), int(pencere)))
        except ValueError:
            continue
    if secili_vizit:
        if not svc.vizit_semasi_degistirilebilir(c):
            bilgi(request, "Vizit kaydı oluşturulmuş gönüllüsü olan çalışmada vizit şeması değiştirilemez; vizitler atlandı.")
        elif not c.vizit_tanimlari:
            yeni = svc.vizit_semasi_uygula(db, c, secili_vizit)
            denetim.kaydet(db, k, "guncelle", "vizit_semasi", c.id, eski={"vizitler": []},
                           yeni={"kaynak": "protokol_taslak", "vizitler": [(t.ad, t.gun, t.pencere_gun) for t in yeni]},
                           ip=ip(request))
            sayac["vizit"] = len(yeni)
        else:
            mevcut_vizit = {t.ad for t in c.vizit_tanimlari}
            for ad, gun, pencere in secili_vizit:
                if ad in mevcut_vizit:
                    continue
                t = svc.vizit_ekle(db, c, ad, gun, pencere)
                denetim.kaydet(db, k, "olustur", "vizit_tanimi", t.id, yeni=denetim.varlik_sozluk(t), ip=ip(request))
                mevcut_vizit.add(ad)
                sayac["vizit"] += 1
    # formlar
    eklenen = svc.standart_formlari_ekle(db, c, gelen.getlist("formlar"))
    for f in eklenen:
        denetim.kaydet(db, k, "olustur", "form", f.id, yeni={"calisma": c.kod, "kod": f.kod, "ad": f.ad,
                       "versiyon": f.versiyon, "durum": f.durum, "alanlar": f.alanlar, "kaynak": "protokol_taslak"},
                       ip=ip(request))
    sayac["form"] = len(eklenen)
    db.commit()
    bilgi(request, f"Taslak uygulandı: {sayac['kriter']} kriter, {sayac['kol']} kol, {sayac['vizit']} vizit, "
                   f"{sayac['form']} form eklendi. Kriterler onay bekliyor.")
    return RedirectResponse(_yol(c), status_code=303)
