"""Yeni calisma sihirbazi: 4 adimda temel bilgiler, tasarim, merkez/ekip, eCRF ve basvuru.

Taslak kullanici basina tek kayit olarak CalismaTaslagi'nda tutulur; oturum kapansa da
kaldigi yerden surer. Veritabanina calisma yalnizca son adimda, tek islemde yazilir.
Mod (kurulum ayari) alanlari sadelestirir ve varsayilanlari secer.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Arastirmaci,
    Basvuru,
    Calisma,
    CalismaMerkez,
    CalismaTuru,
    Kol,
    Kriter,
    Kullanici,
    Merkez,
    Rol,
)
from ..models._ortak import simdi
from ..models.basvuru import KURUMLAR
from ..models.calisma import TUR_ETIKET
from ..models.ekip import CalismaUyesi
from ..models.kurulum import CalismaTaslagi
from ..services import denetim, yetki
from ..services import ecrf as ecrf_svc
from ..services import kurulum as kurulum_svc
from ..services.yetki import ATANABILIR_ROLLER, gerekli
from ._ortak import bilgi, ip
from .sablon import goster, sablonlar

router = APIRouter(prefix="/sihirbaz")

ADIMLAR = [(1, "Temel bilgiler"), (2, "Tasarım"), (3, "Merkez ve ekip"), (4, "eCRF ve başvuru")]
FAZLAR = ["I", "I/II", "II", "III", "IV", "pilot", "pivotal", "performans"]
MAKS_KOL = 6
# sponsor yerine "destekleyici / sorumlu kurum" denen turler; varsayilan kurum adidir
KURUM_TURLERI = {CalismaTuru.AKADEMIK, CalismaTuru.GOZLEMSEL, CalismaTuru.KAYIT}
# CRO modunda 3. adimda secilebilen ekip rolleri
EKIP_ROLLERI = (Rol.PROJE_YONETICISI, Rol.CRA, Rol.VERI_YONETICISI)

# Standart form paketleri icin kisa aciklama (sihirbaz 4. adim)
FORM_ACIKLAMA = {
    "DM": "Doğum yılı, cinsiyet, boy, kilo",
    "IE": "Dahil/hariç kriterleri karşılandı mı",
    "VS": "Kan basıncı, nabız, ateş",
    "LB": "Hemogram ve biyokimya",
    "EX": "Araştırma ürünü dozu ve tarihi",
    "CM": "Eşlik eden ilaçlar",
    "QS": "ECOG performans skoru",
}


def sihirbaz_acik(k: Kullanici, mod: str) -> bool:
    """'Yeni calisma' dugmesi ve sihirbaz: calisma.olustur izni; arastirmaci yalnizca tekil ve universite modunda."""
    return yetki.izinli(k, "calisma.olustur") and not (k.rol == Rol.ARASTIRMACI and mod == "cro")


sablonlar.env.globals["sihirbaz_acik"] = sihirbaz_acik


def sihirbazci(request: Request, k: Kullanici = Depends(gerekli("calisma.olustur")),
               db: Session = Depends(get_db)) -> Kullanici:
    if not sihirbaz_acik(k, kurulum_svc.ayar_getir(db).mod):
        raise HTTPException(403, "CRO modunda çalışmayı proje yöneticisi kurar")
    request.state.kullanici = k
    return k


# --- Taslak (CalismaTaslagi) --------------------------------------------------

def _taslak_kaydi(db: Session, k: Kullanici) -> CalismaTaslagi | None:
    return db.execute(select(CalismaTaslagi).where(CalismaTaslagi.kullanici_id == k.id)).scalar_one_or_none()


def _taslak(db: Session, k: Kullanici) -> dict:
    t = _taslak_kaydi(db, k)
    return dict(t.veri or {}) if t else {}


def _kaydet(db: Session, k: Kullanici, taslak: dict) -> None:
    t = _taslak_kaydi(db, k)
    if not t:
        t = CalismaTaslagi(kullanici_id=k.id)
        db.add(t)
    t.veri = dict(taslak)
    t.guncelleme = simdi()
    db.commit()


def _sil(db: Session, k: Kullanici) -> None:
    t = _taslak_kaydi(db, k)
    if t:
        db.delete(t)
        db.commit()


def _ilk_eksik_adim(taslak: dict) -> int:
    for n in range(1, 5):
        if f"adim{n}" not in taslak:
            return n
    return 4


def _ortak(request: Request, db: Session, adim: int, taslak: dict) -> dict:
    ayar = kurulum_svc.ayar_getir(db)
    return {"adim": adim, "adimlar": ADIMLAR, "ayar": ayar, "mod": ayar.mod, "t": taslak, "hata": None}


def _tur(taslak: dict) -> CalismaTuru | None:
    try:
        return CalismaTuru(taslak.get("adim1", {}).get("tur", ""))
    except ValueError:
        return None


def _adim_kontrol(taslak: dict, adim: int) -> RedirectResponse | None:
    """Onceki adimlar tamamlanmadan ileri gidilemez; eksik olan ilk adima yonlendirir."""
    for n in range(1, adim):
        if f"adim{n}" not in taslak:
            return RedirectResponse(f"/sihirbaz/{n}", status_code=303)
    return None


def _tur_listesi(mod: str) -> list[tuple[list, list]]:
    sik = kurulum_svc.SIK_TURLER.get(mod, [])
    diger = [x for x in CalismaTuru if x not in sik]
    return [[(x.value, TUR_ETIKET[x]) for x in sik], [(x.value, TUR_ETIKET[x]) for x in diger]]


@router.get("")
def baslangic(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    taslak = _taslak(db, k)
    if taslak:
        t = _taslak_kaydi(db, k)
        bilgi(request, f"Kaldığınız yerden devam ediyorsunuz (taslak {t.guncelleme:%d.%m.%Y %H:%M}). "
                       "Baştan başlamak için 'Vazgeç'i kullanın.")
        return RedirectResponse(f"/sihirbaz/{_ilk_eksik_adim(taslak)}", status_code=303)
    return RedirectResponse("/sihirbaz/1", status_code=303)


@router.get("/iptal")
def iptal(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    _sil(db, k)
    return RedirectResponse("/calismalar", status_code=303)


# --- Adim 1: temel bilgiler ---------------------------------------------------

def _adim1_baglam(request: Request, db: Session, taslak: dict, veri: dict | None = None) -> dict:
    b = _ortak(request, db, 1, taslak)
    ayar = b["ayar"]
    veri = dict(veri or taslak.get("adim1") or {})
    if not veri.get("kod"):
        veri["kod"] = kurulum_svc.protokol_kodu_oner(db, ayar.kurum_adi)
    if not veri.get("tur"):
        veri["tur"] = (kurulum_svc.SIK_TURLER.get(ayar.mod) or [CalismaTuru.ILAC])[0].value
    if not veri.get("sponsor"):
        try:
            kurum_turu = CalismaTuru(veri["tur"]) in KURUM_TURLERI
        except ValueError:
            kurum_turu = False
        veri["sponsor"] = ayar.varsayilan_sponsor or (ayar.kurum_adi if (ayar.mod != "cro" or kurum_turu) else "")
    sponsorlar = [x for (x,) in db.execute(select(Calisma.sponsor).distinct().order_by(Calisma.sponsor)).all() if x]
    b.update(veri=veri, sik_turler=_tur_listesi(ayar.mod)[0], diger_turler=_tur_listesi(ayar.mod)[1],
             faz_turleri=[x.value for x in kurulum_svc.FAZ_TURLERI], kurum_turleri=[x.value for x in KURUM_TURLERI],
             fazlar=FAZLAR, sponsorlar=sponsorlar, kurum_adi=ayar.kurum_adi)
    return b


@router.get("/1")
def adim1(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    return goster(request, "sihirbaz/adim1.html", **_adim1_baglam(request, db, _taslak(db, k)))


@router.post("/1")
async def adim1_kaydet(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    g = await request.form()
    ayar = kurulum_svc.ayar_getir(db)
    veri = {a: (g.get(a) or "").strip() for a in ("kod", "kisa_ad", "baslik", "tur", "faz", "sponsor", "terapotik_alan",
                                                  "hedef_hasta", "baslangic")}
    veri["kod"] = veri["kod"].upper()
    taslak = _taslak(db, k)

    def hata(metin):
        b = _adim1_baglam(request, db, taslak, veri)
        b["hata"] = metin
        return goster(request, "sihirbaz/adim1.html", **b)

    try:
        tur = CalismaTuru(veri["tur"])
    except ValueError:
        return hata("Çalışma türü seçin.")
    if not veri["sponsor"] and (ayar.mod == "tekil" or tur in KURUM_TURLERI):
        veri["sponsor"] = ayar.kurum_adi
    if not (veri["kod"] and veri["kisa_ad"] and veri["baslik"] and veri["terapotik_alan"]):
        return hata("Protokol kodu, kısa ad, tam başlık ve terapötik alan zorunludur.")
    if not veri["sponsor"]:
        return hata("Destekleyici / sorumlu kurum boş olamaz." if tur in KURUM_TURLERI else "Sponsor boş olamaz.")
    if kurulum_svc.kod_kullanimda(db, veri["kod"]):
        return hata(f"'{veri['kod']}' protokol kodu zaten kayıtlı; farklı bir kod girin.")
    if tur not in kurulum_svc.FAZ_TURLERI:
        veri["faz"] = ""  # faz yalnizca ilac/cihaz turlerinde anlamli
    if veri["baslangic"]:
        try:
            date.fromisoformat(veri["baslangic"])
        except ValueError:
            return hata("Planlanan başlangıç tarihi geçersiz.")
    veri["hedef_hasta"] = str(int(veri["hedef_hasta"])) if veri["hedef_hasta"].isdigit() else "0"
    eski_tur = taslak.get("adim1", {}).get("tur")
    taslak["adim1"] = veri
    if eski_tur != veri["tur"]:
        # tur degisince vizit/form/basvuru varsayilanlari yeniden hesaplansin
        for n in ("adim2", "adim4"):
            taslak.pop(n, None)
    _kaydet(db, k, taslak)
    return RedirectResponse("/sihirbaz/2", status_code=303)


# --- Adim 2: tasarim ----------------------------------------------------------

def _adim2_baglam(request: Request, db: Session, taslak: dict, veri: dict | None = None) -> dict:
    b = _ortak(request, db, 2, taslak)
    v = kurulum_svc.mod_varsayilanlari(b["mod"], taslak.get("adim1", {}).get("tur"))
    veri = dict(veri or taslak.get("adim2") or {})
    veri.setdefault("kollar", [{"ad": "Tek kol", "oran": 1}])
    veri.setdefault("vizit_sablonu", v["vizit_sablonu"])
    veri.setdefault("dahil", "")
    veri.setdefault("haric", "")
    veri.setdefault("protokol_var", False)
    b.update(veri=veri, sablonlar=ecrf_svc.VIZIT_SABLON_ETIKET, sablon_satirlar=ecrf_svc.VIZIT_SABLONLARI, maks_kol=MAKS_KOL)
    return b


@router.get("/2")
def adim2(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    taslak = _taslak(db, k)
    y = _adim_kontrol(taslak, 2)
    if y:
        return y
    return goster(request, "sihirbaz/adim2.html", **_adim2_baglam(request, db, taslak))


@router.post("/2")
async def adim2_kaydet(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    taslak = _taslak(db, k)
    y = _adim_kontrol(taslak, 2)
    if y:
        return y
    g = await request.form()
    adlar, oranlar = g.getlist("kol_ad"), g.getlist("kol_oran")
    kollar = []
    for i, ad in enumerate(adlar[:MAKS_KOL]):
        ad = (ad or "").strip()[:80]
        if not ad:
            continue
        oran = oranlar[i] if i < len(oranlar) else "1"
        kollar.append({"ad": ad, "oran": int(oran) if str(oran).isdigit() and int(oran) > 0 else 1})
    veri = {"kollar": kollar or [{"ad": "Tek kol", "oran": 1}], "vizit_sablonu": g.get("vizit_sablonu") or "",
            "dahil": (g.get("dahil") or "").strip(), "haric": (g.get("haric") or "").strip(),
            "protokol_var": bool(g.get("protokol_var"))}
    if veri["vizit_sablonu"] not in ecrf_svc.VIZIT_SABLONLARI:
        b = _adim2_baglam(request, db, taslak, veri)
        b["hata"] = "Vizit şablonu seçin."
        return goster(request, "sihirbaz/adim2.html", **b)
    taslak["adim2"] = veri
    _kaydet(db, k, taslak)
    return RedirectResponse("/sihirbaz/3", status_code=303)


# --- Adim 3: merkez ve ekip ---------------------------------------------------

def _ekip_adaylari(db: Session, k: Kullanici) -> list[Kullanici]:
    """CRO modunda secilebilen ekip: aktif PY, CRA ve veri yoneticileri (kurucu listede gosterilmez; kendiliginden uye)."""
    return db.execute(select(Kullanici).where(Kullanici.aktif.is_(True), Kullanici.rol.in_(EKIP_ROLLERI),
                                              Kullanici.id != k.id).order_by(Kullanici.rol, Kullanici.ad_soyad)).scalars().all()


def _adim3_baglam(request: Request, db: Session, taslak: dict, k: Kullanici, veri: dict | None = None) -> dict:
    b = _ortak(request, db, 3, taslak)
    ayar = b["ayar"]
    merkezler = db.execute(select(Merkez).order_by(Merkez.ad)).scalars().all()
    veri = dict(veri or taslak.get("adim3") or {})
    varsayilan = ayar.varsayilan_merkez_id or (merkezler[0].id if merkezler else None)
    veri.setdefault("merkez_id", varsayilan)
    veri.setdefault("merkezler", [])
    veri.setdefault("bolum", "")
    veri.setdefault("sonra", False)
    veri.setdefault("ekip", [])
    arastirmacilar = []
    if veri.get("merkez_id"):
        arastirmacilar = db.execute(select(Arastirmaci).where(Arastirmaci.merkez_id == int(veri["merkez_id"]))
                                    .order_by(Arastirmaci.ad_soyad)).scalars().all()
    bolumler = sorted({a.bolum for m in merkezler for a in m.arastirmacilar if a.bolum})
    b.update(veri=veri, merkezler=merkezler, arastirmacilar=arastirmacilar, bolumler=bolumler, k=k,
             secili={int(x["id"]): x["hedef"] for x in veri.get("merkezler", [])},
             ekip_adaylari=_ekip_adaylari(db, k) if ayar.mod == "cro" else [],
             secili_ekip={int(x) for x in veri.get("ekip", [])}, kurucu_uye=k.rol in ATANABILIR_ROLLER)
    return b


@router.get("/3")
def adim3(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    taslak = _taslak(db, k)
    y = _adim_kontrol(taslak, 3)
    if y:
        return y
    return goster(request, "sihirbaz/adim3.html", **_adim3_baglam(request, db, taslak, k))


@router.post("/3")
async def adim3_kaydet(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    taslak = _taslak(db, k)
    y = _adim_kontrol(taslak, 3)
    if y:
        return y
    g = await request.form()
    ayar = kurulum_svc.ayar_getir(db)
    veri: dict = {"mod": ayar.mod}

    def hata(metin):
        b = _adim3_baglam(request, db, taslak, k, veri)
        b["hata"] = metin
        return goster(request, "sihirbaz/adim3.html", **b)

    if ayar.mod == "cro":
        secilen = []
        for mid in g.getlist("merkez_id"):
            if not str(mid).isdigit() or not db.get(Merkez, int(mid)):
                continue
            hedef = g.get(f"hedef_{mid}") or "0"
            secilen.append({"id": int(mid), "hedef": int(hedef) if str(hedef).isdigit() else 0})
        veri.update(merkezler=secilen, sonra=bool(g.get("sonra")) or not secilen)
        aday_ids = {u.id for u in _ekip_adaylari(db, k)}
        veri["ekip"] = [int(x) for x in g.getlist("ekip") if str(x).isdigit() and int(x) in aday_ids]
    else:
        mid = g.get("merkez_id") or ayar.varsayilan_merkez_id
        if not mid or not db.get(Merkez, int(mid)):
            return hata("Merkez bulunamadı. Önce Ayarlar'dan varsayılan merkezi seçin.")
        veri["merkez_id"] = int(mid)
        if ayar.mod == "tekil":
            veri["bas_arastirmaci_ad"] = k.ad_soyad
            kadi = (g.get("koord_kullanici_adi") or "").strip().lower()
            if kadi:
                parola = g.get("koord_parola") or ""
                h = yetki.parola_politikasi(parola)
                if h:
                    return hata("Koordinatör parolası: " + h)
                if not (g.get("koord_ad_soyad") or "").strip() or not (g.get("koord_eposta") or "").strip():
                    return hata("Koordinatör için ad soyad ve e-posta gerekli.")
                if db.execute(select(Kullanici.id).where(Kullanici.kullanici_adi == kadi)).first():
                    return hata(f"'{kadi}' kullanıcı adı zaten kayıtlı.")
                veri["koordinator"] = {"kullanici_adi": kadi, "ad_soyad": g.get("koord_ad_soyad").strip(),
                                      "eposta": g.get("koord_eposta").strip(), "parola_hash": yetki.parola_hashle(parola)}
        else:
            veri["bolum"] = (g.get("bolum") or "").strip()[:80]
            aid = g.get("bas_arastirmaci_id") or ""
            if aid.isdigit():
                a = db.get(Arastirmaci, int(aid))
                if not a or a.merkez_id != veri["merkez_id"]:
                    return hata("Seçilen baş araştırmacı bu merkeze bağlı değil.")
                veri["bas_arastirmaci_id"] = a.id
                veri["bas_arastirmaci_ad"] = a.ad_soyad
            else:
                ad = (g.get("bas_arastirmaci_ad") or "").strip()
                if not ad:
                    return hata("Baş araştırmacı seçin ya da adını yazın.")
                veri["bas_arastirmaci_ad"] = ad[:120]
    taslak["adim3"] = veri
    _kaydet(db, k, taslak)
    return RedirectResponse("/sihirbaz/4", status_code=303)


# --- Adim 4: eCRF, basvuru ve olusturma --------------------------------------

def _basvuru_varsayilanlari(mod: str, tur) -> list[str]:
    kurumlar = list(kurulum_svc.mod_varsayilanlari(mod, tur)["basvuru_kurumlari"])
    if mod == "universite" and "sb_izin" not in kurumlar:
        kurumlar.append("sb_izin")  # universite hastanelerinde Saglik Bakanligi bilimsel arastirma izni on secili
    return kurumlar


def _adim4_baglam(request: Request, db: Session, taslak: dict, veri: dict | None = None) -> dict:
    b = _ortak(request, db, 4, taslak)
    tur = taslak.get("adim1", {}).get("tur")
    v = kurulum_svc.mod_varsayilanlari(b["mod"], tur)
    veri = dict(veri or taslak.get("adim4") or {})
    veri.setdefault("formlar", v["form_kodlari"])
    veri.setdefault("basvurular", _basvuru_varsayilanlari(b["mod"], tur))
    formlar = [(kod, s["ad"], FORM_ACIKLAMA.get(kod, "")) for kod, s in ecrf_svc.STANDART_FORMLAR.items() if kod != "ANKET"]
    merkez_adlari = {m.id: m.ad for m in db.execute(select(Merkez)).scalars()}
    a3 = taslak.get("adim3", {})
    ekip_adlari = []
    if a3.get("ekip"):
        ekip_adlari = [f"{u.ad_soyad} ({u.rol_etiket})" for u in db.execute(
            select(Kullanici).where(Kullanici.id.in_([int(x) for x in a3["ekip"]])).order_by(Kullanici.rol)).scalars()]
    t = _tur(taslak)
    b.update(veri=veri, formlar=formlar, kurumlar=KURUMLAR, tur_etiket=TUR_ETIKET.get(t, "—"),
             sablonlar=ecrf_svc.VIZIT_SABLON_ETIKET, sablon_satirlar=ecrf_svc.VIZIT_SABLONLARI, merkez_adlari=merkez_adlari,
             ekip_adlari=ekip_adlari, kurum_turu=t in KURUM_TURLERI)
    return b


@router.get("/4")
def adim4(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    taslak = _taslak(db, k)
    y = _adim_kontrol(taslak, 4)
    if y:
        return y
    return goster(request, "sihirbaz/adim4.html", **_adim4_baglam(request, db, taslak))


@router.post("/4")
async def adim4_olustur(request: Request, k: Kullanici = Depends(sihirbazci), db: Session = Depends(get_db)):
    taslak = _taslak(db, k)
    y = _adim_kontrol(taslak, 4)
    if y:
        return y
    g = await request.form()
    formlar = [kod for kod in g.getlist("form_kod") if kod in ecrf_svc.STANDART_FORMLAR]
    if g.get("anket"):
        formlar.append("ANKET")
    basvurular = [kod for kod in g.getlist("basvuru") if kod in KURUMLAR]
    taslak["adim4"] = {"formlar": formlar, "basvurular": basvurular}
    _kaydet(db, k, taslak)
    if kurulum_svc.kod_kullanimda(db, taslak["adim1"]["kod"]):
        b = _adim4_baglam(request, db, taslak)
        b["hata"] = "Protokol kodu bu arada başka bir çalışmada kullanılmış; 1. adımda değiştirin."
        return goster(request, "sihirbaz/adim4.html", **b)
    try:
        c = calisma_olustur(db, k, taslak, ip(request))
    except ValueError as e:
        db.rollback()
        b = _adim4_baglam(request, db, taslak)
        b["hata"] = str(e)
        return goster(request, "sihirbaz/adim4.html", **b)
    _sil(db, k)
    mesaj = "Çalışma hazır. Eksikler aşama kontrol listesinde."
    if taslak["adim3"].get("mod") == "cro" and not c.uyeler:
        mesaj = ("UYARI: Çalışma hazır ancak proje ekibi atanmadı; atama kısıtı etkinken ekip üyeleri çalışmayı "
                 "görmez. Ekip sekmesinden PY, CRA ve veri yöneticisi ekleyin.")
    bilgi(request, mesaj)
    if taslak.get("adim2", {}).get("protokol_var"):
        return RedirectResponse(f"/calismalar/{c.id}/tasarim/protokol-taslak", status_code=303)
    return RedirectResponse(f"/calismalar/{c.id}", status_code=303)


def calisma_olustur(db: Session, k: Kullanici, taslak: dict, ip_adresi: str | None = None) -> Calisma:
    """Taslaktan tum kayitlari tek islemde yazar: Calisma, KRI seti, kollar, vizit semasi, kriterler,
    merkezler, arastirmaci/kullanici, ekip uyelikleri, formlar, basvurular ve denetim kaydi. Tek commit."""
    from ..services.bdm import BDMIstemci
    from ..services.rbm import varsayilan_krileri_yukle

    a1, a2, a3, a4 = taslak["adim1"], taslak["adim2"], taslak["adim3"], taslak["adim4"]
    mod = a3.get("mod") or "tekil"
    tur = CalismaTuru(a1["tur"])
    secili_merkezler = a3.get("merkezler") or ([{"id": a3["merkez_id"], "hedef": int(a1.get("hedef_hasta") or 0)}]
                                               if a3.get("merkez_id") else [])
    hedef_merkez = len(secili_merkezler) if mod == "cro" else (kurulum_svc.mod_varsayilanlari(mod, tur)["hedef_merkez"] or 0)
    c = Calisma(kod=a1["kod"].strip().upper(), baslik=a1["baslik"], kisa_ad=a1["kisa_ad"][:80], tur=tur,
                faz=(a1.get("faz") or None) if tur in kurulum_svc.FAZ_TURLERI else None,
                sponsor=a1["sponsor"], terapotik_alan=a1["terapotik_alan"][:80],
                hedef_hasta=int(a1.get("hedef_hasta") or 0), hedef_merkez=hedef_merkez,
                baslangic=date.fromisoformat(a1["baslangic"]) if a1.get("baslangic") else None,
                tasarim=f"{len(a2['kollar'])} kol" if len(a2["kollar"]) > 1 else "Tek kol", olusturan_id=k.id)
    db.add(c)
    db.flush()
    varsayilan_krileri_yukle(db, c.id)
    for kol in a2["kollar"]:
        db.add(Kol(calisma_id=c.id, ad=kol["ad"], oran=int(kol.get("oran") or 1)))
    vizitler = ecrf_svc.vizit_semasi_uygula(db, c, a2["vizit_sablonu"])
    istemci = BDMIstemci.olustur()
    kriter_n = 0
    for tip in ("dahil", "haric"):
        for sira, s in enumerate((x.strip(" -•\t") for x in (a2.get(tip) or "").splitlines()), 1):
            if not s:
                continue
            yapi = istemci.kriter_yapilandir(s, tip)
            db.add(Kriter(calisma_id=c.id, tip=tip, sira=sira, metin=s, yapisal=yapi.to_dict(), guven=yapi.guven, onaylandi=False))
            kriter_n += 1
    # merkez ve ekip
    bas_arastirmaci = None
    if mod != "cro" and a3.get("merkez_id"):
        mid = int(a3["merkez_id"])
        if a3.get("bas_arastirmaci_id"):
            bas_arastirmaci = db.get(Arastirmaci, int(a3["bas_arastirmaci_id"]))
        elif a3.get("bas_arastirmaci_ad"):
            bas_arastirmaci = db.execute(select(Arastirmaci).where(Arastirmaci.merkez_id == mid,
                                         Arastirmaci.ad_soyad == a3["bas_arastirmaci_ad"])).scalars().first()
            if not bas_arastirmaci:
                bas_arastirmaci = Arastirmaci(merkez_id=mid, ad_soyad=a3["bas_arastirmaci_ad"], bolum=a3.get("bolum") or None)
                db.add(bas_arastirmaci)
                db.flush()
            elif a3.get("bolum") and not bas_arastirmaci.bolum:
                bas_arastirmaci.bolum = a3["bolum"]
    # tekil ve universite: tek merkez kurulumla birlikte aktif; CRO: merkezler aday olarak girer, fizibiliteyle ilerler
    bugun = date.today()
    tek_merkez = mod != "cro"
    for i, m in enumerate(secili_merkezler, 1):
        db.add(CalismaMerkez(calisma_id=c.id, merkez_id=int(m["id"]), merkez_no=f"{i:02d}", hedef_hasta=int(m.get("hedef") or 0),
                             durum="aktif" if tek_merkez else "aday", secim_tarihi=bugun,
                             aktivasyon_tarihi=bugun if tek_merkez else None,
                             bas_arastirmaci_id=bas_arastirmaci.id if (bas_arastirmaci and tek_merkez) else None))
    koordinator = None
    if a3.get("koordinator"):
        kd = a3["koordinator"]
        if db.execute(select(Kullanici.id).where((Kullanici.kullanici_adi == kd["kullanici_adi"]) | (Kullanici.eposta == kd["eposta"]))).first():
            raise ValueError(f"Koordinatör hesabı için '{kd['kullanici_adi']}' kullanıcı adı veya e-posta zaten kayıtlı.")
        koordinator = Kullanici(kullanici_adi=kd["kullanici_adi"], ad_soyad=kd["ad_soyad"], eposta=kd["eposta"],
                                parola_hash=kd["parola_hash"], rol=Rol.KOORDINATOR, merkez_id=int(a3["merkez_id"]),
                                parola_degisim=simdi(), ilk_giris_degisim=True)
        db.add(koordinator)
        db.flush()
    # ekip uyelikleri: kurucu atanabilir roldeyse kendiliginden uye; CRO'da secilen PY/CRA/VY eklenir
    uye_ids: list[int] = []
    if k.rol in ATANABILIR_ROLLER:
        uye_ids.append(k.id)
    for kid in a3.get("ekip") or []:
        u = db.get(Kullanici, int(kid))
        if u and u.aktif and u.rol in ATANABILIR_ROLLER and u.id not in uye_ids:
            uye_ids.append(u.id)
    for kid in uye_ids:
        db.add(CalismaUyesi(calisma_id=c.id, kullanici_id=kid, ekleyen_id=k.id))
    formlar = ecrf_svc.standart_formlari_ekle(db, c, a4.get("formlar") or [])
    for kurum in a4.get("basvurular") or []:
        db.add(Basvuru(calisma_id=c.id, kurum=kurum, tip="ilk", karar="beklemede"))
    db.flush()
    ozet = {**denetim.varlik_sozluk(c), "kaynak": "sihirbaz", "mod": mod, "kol": len(a2["kollar"]),
            "vizit_sablonu": a2["vizit_sablonu"], "vizit": len(vizitler), "kriter": kriter_n,
            "merkez": len(secili_merkezler), "form": [f.kod for f in formlar], "basvuru": a4.get("basvurular") or [],
            "bas_arastirmaci_id": bas_arastirmaci.id if bas_arastirmaci else None,
            "koordinator_id": koordinator.id if koordinator else None, "ekip": uye_ids}
    denetim.kaydet(db, k, "olustur", "calisma", c.id, yeni=ozet, ip=ip_adresi)
    if koordinator:
        denetim.kaydet(db, k, "olustur", "kullanici", koordinator.id, yeni=denetim.varlik_sozluk(koordinator), ip=ip_adresi)
    for uye in c.uyeler:
        u = db.get(Kullanici, uye.kullanici_id)
        denetim.kaydet(db, k, "olustur", "calisma_uyesi", uye.id,
                       yeni={"calisma": c.kod, "kullanici": u.kullanici_adi, "rol": u.rol.value, "kaynak": "sihirbaz"}, ip=ip_adresi)
    db.commit()
    return c
