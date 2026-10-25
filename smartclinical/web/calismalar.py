from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ayarlar
from ..db import get_db
from ..models import (
    Basvuru,
    Belge,
    Calisma,
    CalismaDurumu,
    CalismaMerkez,
    CalismaTuru,
    DenetimKaydi,
    GonulluDurumu,
    IzlemZiyareti,
    Kriter,
    Kullanici,
    Merkez,
    ProtokolSapmasi,
    ProtokolVersiyon,
    RiskUyarisi,
    Rol,
    Sorgu,
)
from ..models._ortak import simdi
from ..models.basvuru import BASVURU_TIPLERI, KURUMLAR
from ..models.belge import TMF_BOLGELER
from ..models.calisma import TUR_ETIKET
from ..models.izlem import SAPMA_KATEGORI
from ..models.merkez import CM_DURUMLAR
from ..services import denetim
from ..services.yetki import gerekli, izinli
from ._ortak import bilgi, calisma_getir, ip, oturumlu
from .sablon import goster, sablonlar

router = APIRouter(prefix="/calismalar")

# Sekme gorunurlugu rol izinlerine baglidir; ayni kurallar rotalarda 403 icin kullanilir.
# TODO(mert): calisma bazli ekip atamasi gelince (#142) buradaki rol listeleri ekip uyeligiyle daraltilacak.
_SEKMELER = [
    ("ozet", "Özet", ""),
    ("tasarim", "Tasarım", "/tasarim"),
    ("protokol", "Protokol ve Kriterler", "/protokol"),
    ("merkezler", "Merkezler", "/merkezler"),
    ("basvurular", "Etik / TİTCK", "/basvurular"),
    ("eslestirme", "Hasta Eşleştirme", "/eslestirme"),
    ("gonulluler", "Gönüllüler", "/gonulluler"),
    ("veri", "Veri (eCRF)", "/veri"),
    ("guvenlik", "Güvenlik", "/guvenlik"),
    ("merkez-zekasi", "Merkez Zekâsı", "/merkez-zekasi"),
    ("rbm", "Risk Bazlı İzlem", "/rbm"),
    ("izlem", "Ziyaret ve Sapmalar", "/izlem"),
    ("belgeler", "TMF", "/belgeler"),
    ("analiz", "Analiz", "/analiz"),
    ("denetim", "Denetim İzi", "/denetim"),
]
_ANALIZ_ROLLERI = (Rol.YONETICI, Rol.PROJE_YONETICISI, Rol.ARASTIRMACI, Rol.VERI_YONETICISI, Rol.ISTATISTIKCI)


def sekme_gorunur(k: Kullanici, anahtar: str) -> bool:
    rol = k.rol
    sponsor = rol == Rol.SPONSOR
    if anahtar in ("ozet", "protokol", "merkezler", "guvenlik"):
        return True
    if anahtar == "tasarim":
        return izinli(k, "calisma.duzenle") and not sponsor
    if anahtar == "basvurular":
        return izinli(k, "calisma.duzenle") or rol in (Rol.DENETCI, Rol.SPONSOR)
    if anahtar == "eslestirme":
        return izinli(k, "hasta.goruntule")
    if anahtar in ("gonulluler", "veri"):
        return not sponsor
    if anahtar == "rbm":
        return izinli(k, "rbm.goruntule")
    if anahtar == "merkez-zekasi":
        return izinli(k, "rbm.goruntule") and not sponsor
    if anahtar == "izlem":
        return (izinli(k, "rbm.goruntule") and not sponsor) or rol == Rol.KOORDINATOR
    if anahtar == "belgeler":
        return izinli(k, "belge.yukle") or rol in (Rol.DENETCI, Rol.SPONSOR)
    if anahtar == "analiz":
        return rol in _ANALIZ_ROLLERI
    if anahtar == "denetim":
        return izinli(k, "denetim.goruntule")
    return False


def sekme_kontrol(k: Kullanici, anahtar: str) -> None:
    if not sekme_gorunur(k, anahtar):
        raise HTTPException(403, "Bu sayfa rolünüze açık değil")


def gorunur_sekmeler(k: Kullanici, c: Calisma, o: dict) -> list[dict]:
    """_baslik.html icin sekme listesi: etiket, adres ve sayac."""
    sayaclar = {
        "protokol": (len(c.kriterler) or None, ""),
        "merkezler": (f"{o['aktif_merkez']}/{o['toplam_merkez']}", ""),
        "basvurular": (o["bekleyen_basvuru"] or None, ""),
        "gonulluler": (o["kayitli"], ""),
        "veri": (o["acik_sorgu"] or None, ""),
        "guvenlik": (o["bekleyen_sae"] or None, "kirmizi"),
        "rbm": (o["acik_uyari"] or None, "kirmizi" if o["aksiyon_uyari"] else ""),
    }
    liste = []
    for anahtar, etiket, yol in _SEKMELER:
        if not sekme_gorunur(k, anahtar):
            continue
        sayac, sinif = sayaclar.get(anahtar, (None, ""))
        liste.append({"anahtar": anahtar, "etiket": etiket, "url": f"/calismalar/{c.id}{yol}",
                      "sayac": sayac, "sinif": sinif})
    return liste


sablonlar.env.globals["sekmeler"] = gorunur_sekmeler

# TITCK basvurusu gerektiren calisma turleri; gozlemsel/akademik/kayit calismalarinda yalnizca etik kurul
TITCK_GEREKEN = {CalismaTuru.ILAC, CalismaTuru.BIYOBENZER, CalismaTuru.TIBBI_CIHAZ, CalismaTuru.IVD,
                 CalismaTuru.BIYOESDEGERLIK, CalismaTuru.ILERI_TEDAVI}
KAYITLI_DURUMLAR = (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE, GonulluDurumu.TAMAMLADI)


def kontrol_listesi(db: Session, c: Calisma) -> dict[CalismaDurumu, list[dict]]:
    """Her asama icin veriden hesaplanan kontrol maddeleri: etiket, tamam, baglanti.

    Zorlayici degil; eksikler detay sayfasinda baglantiyla gosterilir, asama kararini PY verir.
    TODO(mert): vizit semasi (VizitTanimi) tanimlaninca Tasarim asamasina "vizit semasi tanimli" maddesi eklenecek.
    """
    b = f"/calismalar/{c.id}"

    def m(etiket, tamam, url):
        return {"etiket": etiket, "tamam": bool(tamam), "url": url}

    kriterler = c.kriterler
    etik = [x for x in c.basvurular if x.kurum == "etik_kurul"]
    titck = [x for x in c.basvurular if x.kurum == "titck"]
    titck_gerekli = c.tur in TITCK_GEREKEN
    ilgili_basvuru = etik + (titck if titck_gerekli else [])
    aktif = [x for x in c.merkezler if x.durum == "aktif"]
    cm_ids = [x.id for x in c.merkezler]
    siv = False
    if cm_ids:
        siv = db.scalar(select(IzlemZiyareti.id).where(IzlemZiyareti.calisma_merkez_id.in_(cm_ids),
                        IzlemZiyareti.tip == "SIV", IzlemZiyareti.gerceklesen.isnot(None)).limit(1)) is not None
        siv = siv or any(t.tip == "siv" and t.gerceklesen for cm in c.merkezler for t in cm.kilometre_taslari)
    kayitli = sum(1 for g in c.gonulluler if g.durum in KAYITLI_DURUMLAR)
    kayitlar = [fk for g in c.gonulluler for fk in g.form_kayitlari]
    acik_sorgular = [s for fk in kayitlar for s in fk.sorgular if s.durum == "acik"]
    sae = [a for g in c.gonulluler for a in g.advers_olaylar if a.ciddi]
    aksiyon = db.scalar(select(RiskUyarisi.id).where(RiskUyarisi.calisma_id == c.id, RiskUyarisi.durum == "acik",
                        RiskUyarisi.seviye == "aksiyon").limit(1)) is not None
    belgeler = db.execute(select(Belge.tmf_bolge).where(Belge.calisma_id == c.id, Belge.durum == "onayli")).all()
    onayli_bolge = {x[0] for x in belgeler}
    eksik_bolge = [kod for kod in TMF_BOLGELER if kod not in onayli_bolge]

    liste = {
        CalismaDurumu.TASARIM: [
            m("Protokol sürümü kayıtlı", c.versiyonlar, f"{b}/protokol"),
            m("Dahil/hariç kriterleri tanımlı ve tümü onaylı", kriterler and all(x.onaylandi for x in kriterler), f"{b}/protokol"),
            m("En az bir çalışma kolu tanımlı", c.kollar, f"{b}/tasarim"),
            m("En az bir eCRF formu tanımlı", c.formlar, f"{b}/tasarim"),
        ],
        CalismaDurumu.FIZIBILITE: [
            m("En az bir aday merkez eklendi", c.merkezler, f"{b}/merkezler"),
            m("Merkez zekâsı puanı hesaplandı", any(x.fizibilite_puani is not None for x in c.merkezler), f"{b}/merkez-zekasi"),
        ],
        CalismaDurumu.BASVURU: [
            m("Etik kurul başvurusu kayıtlı", etik, f"{b}/basvurular"),
        ] + ([m("TİTCK başvurusu kayıtlı", titck, f"{b}/basvurular")] if titck_gerekli else []) + [
            m("Başvuru kararları onay", ilgili_basvuru and all(x.karar == "onay" for x in ilgili_basvuru), f"{b}/basvurular"),
        ],
        CalismaDurumu.AKTIVASYON: [
            m("En az bir aktif merkez", aktif, f"{b}/merkezler"),
            m("Başlatma ziyareti (SIV) yapıldı", siv, f"{b}/izlem"),
        ],
        CalismaDurumu.KAYIT: [
            m("En az bir randomize gönüllü", kayitli > 0, f"{b}/gonulluler"),
            m("Hedefin yüzde 25'ine ulaşıldı", c.hedef_hasta and kayitli >= c.hedef_hasta * 0.25, f"{b}/gonulluler"),
        ],
        CalismaDurumu.IZLEM: [
            m("14 günü geçen açık sorgu yok", not any(s.acik_gun > 14 for s in acik_sorgular), f"{b}/veri"),
            m("Bildirimi yapılmamış SAE yok", not any(a.titck_bildirim is None for a in sae), f"{b}/guvenlik"),
            m("Açık aksiyon seviyesinde uyarı yok", not aksiyon, f"{b}/rbm"),
        ],
        CalismaDurumu.KAPANIS: [
            m("Tüm form kayıtları kilitli", kayitlar and all(fk.durum == "kilitli" for fk in kayitlar), f"{b}/veri"),
        ],
        CalismaDurumu.ANALIZ: [
            m("TMF'nin 11 bölümünün her birinde onaylı belge var", not eksik_bolge, f"{b}/belgeler"),
        ],
    }
    liste[CalismaDurumu.ARSIV] = liste[CalismaDurumu.ANALIZ]
    return liste


def _ozet(db: Session, c: Calisma) -> dict:
    g = c.gonulluler
    kayitli = [x for x in g if x.durum in (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE,
                                           GonulluDurumu.TAMAMLADI)]
    on_tarama = [x for x in g if x.durum in (GonulluDurumu.ADAY, GonulluDurumu.ON_TARAMA)]
    tarama_bas = [x for x in g if x.durum == GonulluDurumu.TARAMA_BASARISIZ]
    ayrilan = [x for x in g if x.durum == GonulluDurumu.AYRILDI]
    gid = [x.id for x in g]
    acik_sorgu = db.scalar(select(Sorgu.id).join(Sorgu.form_kaydi).where(Sorgu.durum == "acik")
                           .limit(1)) is not None if gid else False
    acik_sorgu_n = len([s for s in db.execute(select(Sorgu).where(Sorgu.durum == "acik")).scalars()
                        if s.form_kaydi.gonullu.calisma_id == c.id])
    db.scalar(select(RiskUyarisi.id).where(RiskUyarisi.calisma_id == c.id, RiskUyarisi.durum == "acik")
                        .limit(1))
    uyarilar = db.execute(select(RiskUyarisi).where(RiskUyarisi.calisma_id == c.id, RiskUyarisi.durum == "acik")).scalars().all()
    sae = [a for x in g for a in x.advers_olaylar if a.ciddi]
    return {
        "kayitli": len(kayitli), "on_tarama": len(on_tarama), "tarama_basarisiz": len(tarama_bas),
        "ayrilan": len(ayrilan), "toplam_gonullu": len(g),
        "aktif_merkez": sum(1 for m in c.merkezler if m.durum == "aktif"),
        "toplam_merkez": len(c.merkezler),
        "acik_sorgu": acik_sorgu_n, "acik_uyari": len(uyarilar),
        "aksiyon_uyari": sum(1 for u in uyarilar if u.seviye == "aksiyon"),
        "sae": len(sae), "bekleyen_sae": sum(1 for a in sae if not a.titck_bildirim),
        "oran": (100 * len(kayitli) / c.hedef_hasta) if c.hedef_hasta else 0,
        "bekleyen_basvuru": sum(1 for b in c.basvurular if b.karar == "beklemede"),
        "acik_sorgu_var": acik_sorgu,
    }


@router.get("")
def liste(request: Request, k: Kullanici = Depends(oturumlu), db: Session = Depends(get_db),
          durum: str | None = None, tur: str | None = None, q: str | None = None):
    sorgu = select(Calisma).order_by(Calisma.durum, Calisma.kod)
    if durum:
        sorgu = sorgu.where(Calisma.durum == CalismaDurumu(durum))
    if tur:
        sorgu = sorgu.where(Calisma.tur == CalismaTuru(tur))
    if q:
        sorgu = sorgu.where((Calisma.kod.ilike(f"%{q}%")) | (Calisma.kisa_ad.ilike(f"%{q}%")) | (Calisma.sponsor.ilike(f"%{q}%")))
    if k.rol in (Rol.ARASTIRMACI, Rol.KOORDINATOR) and k.merkez_id:
        sorgu = sorgu.join(Calisma.merkezler).where(CalismaMerkez.merkez_id == k.merkez_id)
    if k.rol == Rol.SPONSOR:
        # sponsor yalnizca kendi kurumunun calismalarini gorur; kurum bossa hicbirini
        sorgu = sorgu.where(Calisma.sponsor == (k.kurum or ""))
    calismalar = db.execute(sorgu).scalars().unique().all()
    satirlar = [{"c": c, "o": _ozet(db, c)} for c in calismalar]
    sade = k.rol in (Rol.ARASTIRMACI, Rol.KOORDINATOR)
    return goster(request, "calismalar/liste.html", satirlar=satirlar, durum=durum, tur=tur, q=q or "",
                  turler=TUR_ETIKET, durumlar=CalismaDurumu, sade=sade)


@router.get("/yeni")
def yeni_form(request: Request, k: Kullanici = Depends(gerekli("calisma.olustur"))):
    request.state.kullanici = k
    return goster(request, "calismalar/yeni.html", turler=TUR_ETIKET, hata=None)


@router.post("/yeni")
def yeni(request: Request, k: Kullanici = Depends(gerekli("calisma.olustur")), db: Session = Depends(get_db),
         kod: str = Form(...), baslik: str = Form(...), kisa_ad: str = Form(...), tur: str = Form(...),
         faz: str = Form(""), sponsor: str = Form(...), terapotik_alan: str = Form(...), endikasyon: str = Form(""),
         hedef_hasta: int = Form(0), hedef_merkez: int = Form(0), tasarim: str = Form(""),
         baslangic: str = Form(""), planlanan_bitis: str = Form("")):
    request.state.kullanici = k
    if db.execute(select(Calisma).where(Calisma.kod == kod.strip().upper())).scalar_one_or_none():
        return goster(request, "calismalar/yeni.html", turler=TUR_ETIKET, hata="Bu protokol kodu zaten kayıtlı.")
    c = Calisma(kod=kod.strip().upper(), baslik=baslik.strip(), kisa_ad=kisa_ad.strip(), tur=CalismaTuru(tur),
                faz=faz or None, sponsor=sponsor, terapotik_alan=terapotik_alan, endikasyon=endikasyon or None,
                hedef_hasta=hedef_hasta, hedef_merkez=hedef_merkez, tasarim=tasarim or None,
                baslangic=date.fromisoformat(baslangic) if baslangic else None,
                planlanan_bitis=date.fromisoformat(planlanan_bitis) if planlanan_bitis else None)
    db.add(c)
    db.flush()
    # varsayilan KRI/QTL setini bagla
    from ..services.rbm import varsayilan_krileri_yukle

    varsayilan_krileri_yukle(db, c.id)
    denetim.kaydet(db, k, "olustur", "calisma", c.id, yeni=denetim.varlik_sozluk(c), ip=ip(request))
    db.commit()
    bilgi(request, f"{c.kod} çalışması oluşturuldu. Sıradaki adım: protokol ve kriterlerin yüklenmesi.")
    return RedirectResponse(f"/calismalar/{c.id}", status_code=303)


@router.get("/{calisma_id}")
def detay(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
          db: Session = Depends(get_db)):
    o = _ozet(db, c)
    # kayit egrisi: planlanan vs gerceklesen
    rand = sorted(g.randomizasyon_tarihi for g in c.gonulluler if g.randomizasyon_tarihi)
    egri = []
    if c.baslangic and c.planlanan_bitis and c.hedef_hasta:
        toplam_gun = max(1, (c.planlanan_bitis - c.baslangic).days)
        bugun = date.today()
        gun = 0
        while True:
            t = date.fromordinal(c.baslangic.toordinal() + gun)
            if t > min(bugun, c.planlanan_bitis) and gun > 0:
                break
            plan = round(c.hedef_hasta * min(1.0, gun / toplam_gun * 1.15))  # basit S-egrisi yerine lineer+rampa
            gercek = sum(1 for r in rand if r <= t)
            egri.append({"t": t.strftime("%m/%y"), "plan": plan, "gercek": gercek})
            gun += 30
    kontrol = kontrol_listesi(db, c).get(c.durum, [])
    son_denetim = db.execute(select(DenetimKaydi).where(DenetimKaydi.varlik.in_(["calisma", "kriter", "basvuru", "calisma_merkez"]),
                             DenetimKaydi.varlik_id == c.id).order_by(DenetimKaydi.id.desc()).limit(6)).scalars().all()
    return goster(request, "calismalar/detay.html", c=c, o=o, egri=egri, kontrol=kontrol, son_denetim=son_denetim,
                  sekme="ozet")


@router.post("/{calisma_id}/durum")
def durum_degistir(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
                   db: Session = Depends(get_db), durum: str = Form(...), gerekce: str = Form("")):
    if not gerekce.strip():
        bilgi(request, "UYARI: Aşama değişikliği için gerekçe zorunludur; işlem yapılmadı.")
        return RedirectResponse(f"/calismalar/{c.id}", status_code=303)
    eski = c.durum.value
    c.durum = CalismaDurumu(durum)
    denetim.kaydet(db, k, "guncelle", "calisma", c.id, eski={"durum": eski}, yeni={"durum": durum}, gerekce=gerekce, ip=ip(request))
    db.commit()
    bilgi(request, f"Çalışma aşaması '{c.durum_etiket}' olarak güncellendi.")
    return RedirectResponse(f"/calismalar/{c.id}", status_code=303)


# --- Protokol ve kriterler -------------------------------------------------

@router.get("/{calisma_id}/protokol")
def protokol(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
             db: Session = Depends(get_db)):
    return goster(request, "calismalar/protokol.html", c=c, o=_ozet(db, c), sekme="protokol",
                  bdm=ayarlar().bdm_saglayici, bdm_model=ayarlar().bdm_model)


@router.post("/{calisma_id}/protokol/versiyon")
def versiyon_ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
                  db: Session = Depends(get_db), versiyon: str = Form(...), tarih: str = Form(...),
                  ozet: str = Form(""), degisiklik_notu: str = Form(""), metin: str = Form("")):
    v = ProtokolVersiyon(calisma_id=c.id, versiyon=versiyon, tarih=date.fromisoformat(tarih), ozet=ozet or None,
                         degisiklik_notu=degisiklik_notu or None, metin=metin or None)
    db.add(v)
    db.flush()
    denetim.kaydet(db, k, "olustur", "protokol_versiyon", v.id, yeni={"calisma": c.kod, "versiyon": versiyon}, ip=ip(request))
    db.commit()
    bilgi(request, f"Protokol v{versiyon} kaydedildi.")
    return RedirectResponse(f"/calismalar/{c.id}/protokol", status_code=303)


@router.post("/{calisma_id}/protokol/kriter")
def kriter_ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
                db: Session = Depends(get_db), tip: str = Form(...), metin: str = Form(...)):
    from ..services.bdm import BDMIstemci

    satirlar = [s.strip(" -•\t") for s in metin.splitlines() if s.strip(" -•\t")]
    istemci = BDMIstemci.olustur()
    sira = len([x for x in c.kriterler if x.tip == tip])
    for s in satirlar:
        yapi = istemci.kriter_yapilandir(s, tip)
        sira += 1
        kr = Kriter(calisma_id=c.id, tip=tip, sira=sira, metin=s, yapisal=yapi.to_dict(), guven=yapi.guven,
                    onaylandi=False)
        db.add(kr)
        db.flush()
        denetim.kaydet(db, k, "olustur", "kriter", kr.id, yeni={"calisma": c.kod, "tip": tip, "metin": s,
                       "yontem": yapi.yontem, "guven": yapi.guven}, ip=ip(request))
    db.commit()
    bilgi(request, f"{len(satirlar)} kriter eklendi ve yapılandırıldı. Düşük güvenli olanları gözden geçirin.")
    return RedirectResponse(f"/calismalar/{c.id}/protokol", status_code=303)


@router.post("/{calisma_id}/protokol/kriter/{kriter_id}/onayla")
def kriter_onayla(request: Request, kriter_id: int, c: Calisma = Depends(calisma_getir),
                  k: Kullanici = Depends(gerekli("kriter.onayla")), db: Session = Depends(get_db),
                  yapisal: str = Form("")):
    import json

    kr = db.get(Kriter, kriter_id)
    if not kr or kr.calisma_id != c.id:
        raise HTTPException(404)
    eski = kr.yapisal
    if yapisal.strip():
        try:
            kr.yapisal = json.loads(yapisal)
        except json.JSONDecodeError:
            bilgi(request, "Yapısal sorgu geçerli JSON değil; değişiklik kaydedilmedi.")
            return RedirectResponse(f"/calismalar/{c.id}/protokol", status_code=303)
    kr.onaylandi = True
    kr.onaylayan_id = k.id
    denetim.kaydet(db, k, "guncelle", "kriter", kr.id, eski={"yapisal": eski, "onaylandi": False},
                   yeni={"yapisal": kr.yapisal, "onaylandi": True}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/protokol", status_code=303)


@router.post("/{calisma_id}/protokol/kriter/{kriter_id}/sil")
def kriter_sil(request: Request, kriter_id: int, c: Calisma = Depends(calisma_getir),
               k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db), gerekce: str = Form("")):
    kr = db.get(Kriter, kriter_id)
    if kr and kr.calisma_id == c.id:
        denetim.kaydet(db, k, "sil", "kriter", kr.id, eski=denetim.varlik_sozluk(kr), gerekce=gerekce, ip=ip(request))
        db.delete(kr)
        db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/protokol", status_code=303)


# --- Merkezler --------------------------------------------------------------

@router.get("/{calisma_id}/merkezler")
def merkezler(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
              db: Session = Depends(get_db)):
    tum_merkezler = db.execute(select(Merkez).order_by(Merkez.ad)).scalars().all()
    mevcut = {m.merkez_id for m in c.merkezler}
    adaylar = [m for m in tum_merkezler if m.id not in mevcut]
    return goster(request, "calismalar/merkezler.html", c=c, o=_ozet(db, c), sekme="merkezler", adaylar=adaylar,
                  durumlar=CM_DURUMLAR)


@router.post("/{calisma_id}/merkezler/ekle")
def merkez_ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("merkez.yonet")),
                db: Session = Depends(get_db), merkez_id: int = Form(...), hedef_hasta: int = Form(0)):
    no = f"{len(c.merkezler) + 1:02d}"
    cm = CalismaMerkez(calisma_id=c.id, merkez_id=merkez_id, merkez_no=no, hedef_hasta=hedef_hasta, durum="aday",
                       secim_tarihi=date.today())
    db.add(cm)
    db.flush()
    denetim.kaydet(db, k, "olustur", "calisma_merkez", cm.id, yeni={"calisma": c.kod, "merkez_id": merkez_id}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/merkezler", status_code=303)


@router.post("/{calisma_id}/merkezler/{cm_id}/durum")
def merkez_durum(request: Request, cm_id: int, c: Calisma = Depends(calisma_getir),
                 k: Kullanici = Depends(gerekli("merkez.yonet")), db: Session = Depends(get_db), durum: str = Form(...)):
    cm = db.get(CalismaMerkez, cm_id)
    if not cm or cm.calisma_id != c.id:
        raise HTTPException(404)
    eski = cm.durum
    cm.durum = durum
    if durum == "aktif" and not cm.aktivasyon_tarihi:
        cm.aktivasyon_tarihi = date.today()
    denetim.kaydet(db, k, "guncelle", "calisma_merkez", cm.id, eski={"durum": eski}, yeni={"durum": durum}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/merkezler", status_code=303)


# --- Basvurular -------------------------------------------------------------

@router.get("/{calisma_id}/basvurular")
def basvurular(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
               db: Session = Depends(get_db)):
    sekme_kontrol(k, "basvurular")
    return goster(request, "calismalar/basvurular.html", c=c, o=_ozet(db, c), sekme="basvurular",
                  kurumlar=KURUMLAR, tipler=BASVURU_TIPLERI)


@router.post("/{calisma_id}/basvurular")
def basvuru_ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("calisma.duzenle")),
                 db: Session = Depends(get_db), kurum: str = Form(...), tip: str = Form("ilk"),
                 merkez_id: str = Form(""), referans_no: str = Form(""), gonderim_tarihi: str = Form(""),
                 karar: str = Form("beklemede"), karar_tarihi: str = Form(""), notlar: str = Form("")):
    b = Basvuru(calisma_id=c.id, kurum=kurum, tip=tip, merkez_id=int(merkez_id) if merkez_id else None,
                referans_no=referans_no or None,
                gonderim_tarihi=date.fromisoformat(gonderim_tarihi) if gonderim_tarihi else None,
                karar=karar, karar_tarihi=date.fromisoformat(karar_tarihi) if karar_tarihi else None,
                notlar=notlar or None)
    db.add(b)
    db.flush()
    denetim.kaydet(db, k, "olustur", "basvuru", b.id, yeni=denetim.varlik_sozluk(b), ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/basvurular", status_code=303)


@router.post("/{calisma_id}/basvurular/{basvuru_id}/karar")
def basvuru_karar(request: Request, basvuru_id: int, c: Calisma = Depends(calisma_getir),
                  k: Kullanici = Depends(gerekli("calisma.duzenle")), db: Session = Depends(get_db),
                  karar: str = Form(...), karar_tarihi: str = Form(""), notlar: str = Form("")):
    b = db.get(Basvuru, basvuru_id)
    if not b or b.calisma_id != c.id:
        raise HTTPException(404)
    eski = {"karar": b.karar, "karar_tarihi": b.karar_tarihi}
    b.karar = karar
    b.karar_tarihi = date.fromisoformat(karar_tarihi) if karar_tarihi else date.today()
    if notlar:
        b.notlar = ((b.notlar or "") + "\n" + notlar).strip()
    denetim.kaydet(db, k, "guncelle", "basvuru", b.id, eski=eski, yeni={"karar": karar, "karar_tarihi": b.karar_tarihi}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/basvurular", status_code=303)


# --- Gonulluler (calisma sekmesi) -------------------------------------------

@router.get("/{calisma_id}/gonulluler")
def gonulluler(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
               db: Session = Depends(get_db), durum: str | None = None):
    sekme_kontrol(k, "gonulluler")
    liste = sorted(c.gonulluler, key=lambda g: g.gonullu_no)
    if durum:
        liste = [g for g in liste if g.durum.value == durum]
    huni = {}
    for g in c.gonulluler:
        huni[g.durum_etiket] = huni.get(g.durum_etiket, 0) + 1
    return goster(request, "calismalar/gonulluler.html", c=c, o=_ozet(db, c), sekme="gonulluler", liste=liste,
                  huni=huni, durumlar=GonulluDurumu, secili=durum)


# --- Veri (EDC) -------------------------------------------------------------

@router.get("/{calisma_id}/veri")
def veri(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
         db: Session = Depends(get_db)):
    sekme_kontrol(k, "veri")
    formlar = sorted(c.formlar, key=lambda f: f.sira)
    kayitlar = [fk for g in c.gonulluler for fk in g.form_kayitlari]
    durum_sayilari = {}
    for fk in kayitlar:
        durum_sayilari[fk.durum] = durum_sayilari.get(fk.durum, 0) + 1
    sorgular = [s for fk in kayitlar for s in fk.sorgular]
    acik = [s for s in sorgular if s.durum == "acik"]
    # merkez bazli veri giris durumu
    merkez_satir = []
    for cm in c.merkezler:
        fks = [fk for g in cm.gonulluler for fk in g.form_kayitlari]
        merkez_satir.append({
            "cm": cm, "toplam": len(fks),
            "tamamlanan": sum(1 for f in fks if f.durum in ("tamamlandi", "sdv", "kilitli")),
            "sdv": sum(1 for f in fks if f.durum in ("sdv", "kilitli")),
            "acik_sorgu": sum(1 for f in fks for s in f.sorgular if s.durum == "acik"),
        })
    return goster(request, "calismalar/veri.html", c=c, o=_ozet(db, c), sekme="veri", formlar=formlar,
                  durum_sayilari=durum_sayilari, toplam_kayit=len(kayitlar), acik_sorgular=acik,
                  merkez_satir=merkez_satir)


# --- Guvenlik ---------------------------------------------------------------

@router.get("/{calisma_id}/guvenlik")
def guvenlik(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
             db: Session = Depends(get_db)):
    olaylar = [a for g in c.gonulluler for a in g.advers_olaylar]
    olaylar.sort(key=lambda a: a.baslangic, reverse=True)
    soc = {}
    for a in olaylar:
        soc[a.meddra_soc or "Kodlanmamış"] = soc.get(a.meddra_soc or "Kodlanmamış", 0) + 1
    return goster(request, "calismalar/guvenlik.html", c=c, o=_ozet(db, c), sekme="guvenlik", olaylar=olaylar,
                  soc=sorted(soc.items(), key=lambda x: -x[1]),
                  sae=[a for a in olaylar if a.ciddi], susar=[a for a in olaylar if a.susar])


# --- Izlem (ziyaretler, sapmalar) ------------------------------------------

@router.get("/{calisma_id}/izlem")
def izlem(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
          db: Session = Depends(get_db)):
    sekme_kontrol(k, "izlem")
    cm_ids = [m.id for m in c.merkezler]
    ziyaretler = db.execute(select(IzlemZiyareti).where(IzlemZiyareti.calisma_merkez_id.in_(cm_ids))
                            .order_by(IzlemZiyareti.planlanan.desc())).scalars().all() if cm_ids else []
    sapmalar = db.execute(select(ProtokolSapmasi).where(ProtokolSapmasi.calisma_merkez_id.in_(cm_ids))
                          .order_by(ProtokolSapmasi.tarih.desc())).scalars().all() if cm_ids else []
    return goster(request, "calismalar/izlem.html", c=c, o=_ozet(db, c), sekme="izlem", ziyaretler=ziyaretler,
                  sapmalar=sapmalar, kategoriler=SAPMA_KATEGORI)


@router.post("/{calisma_id}/izlem/sapma")
def sapma_ekle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("rbm.yonet")),
               db: Session = Depends(get_db), calisma_merkez_id: int = Form(...), gonullu_id: str = Form(""),
               tarih: str = Form(...), kategori: str = Form(...), onem: str = Form("minor"), aciklama: str = Form(...)):
    s = ProtokolSapmasi(calisma_merkez_id=calisma_merkez_id, gonullu_id=int(gonullu_id) if gonullu_id else None,
                        tarih=date.fromisoformat(tarih), kategori=kategori, onem=onem, aciklama=aciklama)
    db.add(s)
    db.flush()
    denetim.kaydet(db, k, "olustur", "protokol_sapmasi", s.id, yeni=denetim.varlik_sozluk(s), ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/izlem", status_code=303)


@router.post("/{calisma_id}/izlem/ziyaret")
def ziyaret_planla(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("rbm.yonet")),
                   db: Session = Depends(get_db), calisma_merkez_id: int = Form(...), tip: str = Form(...),
                   planlanan: str = Form(...)):
    z = IzlemZiyareti(calisma_merkez_id=calisma_merkez_id, tip=tip, planlanan=date.fromisoformat(planlanan), cra_id=k.id)
    db.add(z)
    db.flush()
    denetim.kaydet(db, k, "olustur", "izlem_ziyareti", z.id, yeni=denetim.varlik_sozluk(z), ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/izlem", status_code=303)


# --- Belgeler (TMF) ---------------------------------------------------------

@router.get("/{calisma_id}/belgeler")
def belgeler(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(oturumlu),
             db: Session = Depends(get_db)):
    sekme_kontrol(k, "belgeler")
    liste = db.execute(select(Belge).where(Belge.calisma_id == c.id).order_by(Belge.tmf_bolge, Belge.ad)).scalars().all()
    bolgeler = {}
    for b in liste:
        bolgeler.setdefault(b.tmf_bolge, []).append(b)
    # TMF tamlik: her bolgede en az bir onayli belge var mi
    tamlik = {kod: any(b.durum == "onayli" for b in bolgeler.get(kod, [])) for kod in TMF_BOLGELER}
    return goster(request, "calismalar/belgeler.html", c=c, o=_ozet(db, c), sekme="belgeler", bolgeler=bolgeler,
                  TMF_BOLGELER=TMF_BOLGELER, tamlik=tamlik)


@router.post("/{calisma_id}/belgeler")
async def belge_yukle(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("belge.yukle")),
                      db: Session = Depends(get_db), tmf_bolge: str = Form(...), ad: str = Form(...),
                      versiyon: str = Form("1.0"), merkez_id: str = Form(""), dosya: UploadFile | None = None):
    import hashlib

    b = Belge(calisma_id=c.id, tmf_bolge=tmf_bolge, ad=ad, versiyon=versiyon, yukleyen_id=k.id,
              merkez_id=int(merkez_id) if merkez_id else None)
    if dosya and dosya.filename:
        icerik = await dosya.read()
        hedef = ayarlar().dosya_dizini / c.kod / tmf_bolge
        hedef.mkdir(parents=True, exist_ok=True)
        guvenli_ad = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in dosya.filename)
        yol = hedef / f"{simdi():%Y%m%d%H%M%S}_{guvenli_ad}"
        yol.write_bytes(icerik)
        b.dosya_adi = dosya.filename
        b.dosya_yolu = str(yol)
        b.sha256 = hashlib.sha256(icerik).hexdigest()
    db.add(b)
    db.flush()
    denetim.kaydet(db, k, "olustur", "belge", b.id, yeni={"calisma": c.kod, "ad": ad, "bolge": tmf_bolge, "sha256": b.sha256}, ip=ip(request))
    db.commit()
    return RedirectResponse(f"/calismalar/{c.id}/belgeler", status_code=303)


@router.post("/{calisma_id}/belgeler/{belge_id}/onayla")
def belge_onayla(request: Request, belge_id: int, c: Calisma = Depends(calisma_getir),
                 k: Kullanici = Depends(gerekli("belge.yukle")), db: Session = Depends(get_db), parola: str = Form(...)):
    from ..services.yetki import parola_dogrula

    b = db.get(Belge, belge_id)
    if not b or b.calisma_id != c.id:
        raise HTTPException(404)
    if not parola_dogrula(parola, k.parola_hash):
        bilgi(request, "E-imza için parola doğrulanamadı.")
        return RedirectResponse(f"/calismalar/{c.id}/belgeler", status_code=303)
    b.durum = "onayli"
    denetim.imzala(db, k, "belge", b.id, "Onaylandı", {"ad": b.ad, "versiyon": b.versiyon, "sha256": b.sha256}, ip=ip(request))
    db.commit()
    bilgi(request, f"'{b.ad}' elektronik imza ile onaylandı.")
    return RedirectResponse(f"/calismalar/{c.id}/belgeler", status_code=303)


# --- Denetim izi (calisma) --------------------------------------------------

@router.get("/{calisma_id}/denetim")
def calisma_denetim(request: Request, c: Calisma = Depends(calisma_getir), k: Kullanici = Depends(gerekli("denetim.goruntule")),
                    db: Session = Depends(get_db)):
    request.state.kullanici = k
    gid = [g.id for g in c.gonulluler]
    cmid = [m.id for m in c.merkezler]
    krid = [x.id for x in c.kriterler]
    kayitlar = db.execute(select(DenetimKaydi).where(
        ((DenetimKaydi.varlik == "calisma") & (DenetimKaydi.varlik_id == c.id)) |
        ((DenetimKaydi.varlik == "gonullu") & (DenetimKaydi.varlik_id.in_(gid))) |
        ((DenetimKaydi.varlik == "calisma_merkez") & (DenetimKaydi.varlik_id.in_(cmid))) |
        ((DenetimKaydi.varlik == "kriter") & (DenetimKaydi.varlik_id.in_(krid))) |
        ((DenetimKaydi.varlik == "eslestirme") & (DenetimKaydi.varlik_id == c.id))
    ).order_by(DenetimKaydi.id.desc()).limit(200)).scalars().all()
    return goster(request, "calismalar/denetim.html", c=c, o=_ozet(db, c), sekme="denetim", kayitlar=kayitlar)
