"""Gonullu yasam dongusu: durum gecisleri, tarama ve takip vizitleri, bagsiz kayitlarin vizite baglanmasi.

web/gonulluler.py ve scripts/onarim_tarama_vizitleri.py bu modulu kullanir. Servis commit etmez.
services/ecrf.gonullu_vizitleri_olustur eski akis icin yerinde duruyor; yeni akista
tarama vizitleri onam/tarama aninda, takip vizitleri randomizasyonda uretilir.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models.hasta import GD_ETIKET, Gonullu, GonulluDurumu, Vizit
from ..models.veri import Form
from .ecrf import VIZIT_SABLONLARI

D = GonulluDurumu

# Izinli ileri gecisler; geri yonlu gecis yok. on_tarama eski kayitlar icin aday ile ayni.
GECISLER: dict[GonulluDurumu, tuple[GonulluDurumu, ...]] = {
    D.ADAY: (D.ONAM, D.TARAMA_BASARISIZ),
    D.ON_TARAMA: (D.ONAM, D.TARAMA_BASARISIZ),
    D.ONAM: (D.TARAMA, D.TARAMA_BASARISIZ, D.AYRILDI),
    D.TARAMA: (D.RANDOMIZE, D.TARAMA_BASARISIZ, D.AYRILDI),
    D.RANDOMIZE: (D.TEDAVIDE, D.TAKIPTE, D.AYRILDI),
    D.TEDAVIDE: (D.TAKIPTE, D.TAMAMLADI, D.AYRILDI),
    D.TAKIPTE: (D.TAMAMLADI, D.AYRILDI),
    D.TARAMA_BASARISIZ: (),
    D.TAMAMLADI: (),
    D.AYRILDI: (),
}


def _durum(d) -> GonulluDurumu:
    return d if isinstance(d, GonulluDurumu) else GonulluDurumu(d)


def gecis_izinli(eski, yeni) -> bool:
    try:
        return _durum(yeni) in GECISLER.get(_durum(eski), ())
    except ValueError:
        return False


def hedefler(durum) -> list[GonulluDurumu]:
    return list(GECISLER.get(_durum(durum), ()))


def gonullu_durum_etiketleri(calisma) -> dict[GonulluDurumu, str]:
    """GD_ETIKET'in calismaya gore kopyasi: tek kollu / kolsuz calismada 'Randomize' yerine 'Çalışmaya alındı'."""
    etiketler = dict(GD_ETIKET)
    if calisma is None or len(calisma.kollar) <= 1:
        etiketler[D.RANDOMIZE] = "Çalışmaya alındı"
    return etiketler


# --- vizitler ---------------------------------------------------------------

def _sema(calisma) -> list[tuple[str, int, int, int | None]]:
    """(ad, gun, pencere, tanim_id) satirlari; sema yoksa standart sablon."""
    tanimlar = list(calisma.vizit_tanimlari)
    if tanimlar:
        return [(t.ad, t.gun, t.pencere_gun, t.id) for t in sorted(tanimlar, key=lambda x: (x.sira, x.gun))]
    return [(ad, gun, pencere, None) for ad, gun, pencere in VIZIT_SABLONLARI["standart"]]


def _mevcut(g: Gonullu, tanim_id: int | None, ad: str) -> bool:
    for v in g.vizitler:
        if tanim_id is not None and v.vizit_tanimi_id == tanim_id:
            return True
        if tanim_id is None and v.ad == ad:
            return True
    return False


def tarama_vizitleri_olustur(db: Session, g: Gonullu, tarih: date) -> list[Vizit]:
    """Semadaki gun<0 vizitlerini uretir (planli, gerceklesen bos). Var olanlar atlanir; tekrar cagrilabilir."""
    satirlar = [s for s in _sema(g.calisma) if s[1] < 0]
    if not satirlar:
        return []
    ilk_gun = min(s[1] for s in satirlar)
    yeni = []
    for i, (ad, gun, pencere, tanim_id) in enumerate(_sema(g.calisma)):
        if gun >= 0 or _mevcut(g, tanim_id, ad):
            continue
        v = Vizit(gonullu_id=g.id, vizit_tanimi_id=tanim_id, ad=ad, sira=i,
                  planlanan=tarih + timedelta(days=gun - ilk_gun), pencere_gun=pencere, durum="planli")
        db.add(v)
        g.vizitler.append(v)
        yeni.append(v)
    db.flush()
    return yeni


def vizitleri_olustur(db: Session, g: Gonullu, baslangic: date) -> list[Vizit]:
    """gun>=0 vizitlerini uretir. Gun 0 'yapildi' (gerceklesen=baslangic); gerisi 'planli'.

    Gecmis tarihli planlanan vizit otomatik 'yapildi' sayilmaz; gerceklesen tarihi kullanici girer.
    """
    yeni = []
    for i, (ad, gun, pencere, tanim_id) in enumerate(_sema(g.calisma)):
        if gun < 0 or _mevcut(g, tanim_id, ad):
            continue
        v = Vizit(gonullu_id=g.id, vizit_tanimi_id=tanim_id, ad=ad, sira=i,
                  planlanan=baslangic + timedelta(days=gun), pencere_gun=pencere,
                  durum="yapildi" if gun == 0 else "planli", gerceklesen=baslangic if gun == 0 else None)
        db.add(v)
        g.vizitler.append(v)
        yeni.append(v)
    db.flush()
    return yeni


def tarama_vizitleri(g: Gonullu) -> list[Vizit]:
    """Sema gununa gore tarama vizitleri; tanimsiz vizitlerde ada bakilir."""
    sonuc = []
    for v in sorted(g.vizitler, key=lambda x: x.sira):
        if v.vizit_tanimi is not None:
            if v.vizit_tanimi.gun < 0:
                sonuc.append(v)
        elif "tarama" in v.ad.lower():
            sonuc.append(v)
    return sonuc


def uygun_vizit(g: Gonullu, form: Form) -> Vizit | None:
    """Bagsiz bir form kaydi icin en uygun vizit: formun vizit listesindeki ilk tarama viziti, yoksa ilk uygun vizit."""
    adaylar = [v for v in sorted(g.vizitler, key=lambda x: x.sira) if form.vizitte_var(v.ad)]
    if not adaylar:
        return None
    tarama = set(id(v) for v in tarama_vizitleri(g))
    for v in adaylar:
        if id(v) in tarama:
            return v
    return adaylar[0]


def kayitlari_vizite_bagla(g: Gonullu) -> int:
    """vizit_id bos kayitlari en uygun vizite baglar; baglanan kayit sayisini dondurur."""
    n = 0
    for fk in g.form_kayitlari:
        if fk.vizit_id is not None:
            continue
        v = uygun_vizit(g, fk.form)
        if v is None:
            continue
        fk.vizit_id = v.id
        fk.vizit = v
        n += 1
    return n


# --- uygunluk (IE) ------------------------------------------------------------

def _haric_alani(alan: dict) -> bool:
    kod = str(alan.get("kod", "")).upper()
    etiket = str(alan.get("etiket", "")).lower()
    return kod.startswith("IEEX") or "hariç" in etiket or "haric" in etiket


def uygunluk_sorunlari(form: Form, veriler: dict) -> list[str]:
    """IE formunda uygunlukla celisen cevaplar. Dahil etme sorulari 'Evet', haric tutma sorulari 'Hayır' olmali."""
    sorunlar = []
    for alan in form.alanlar:
        sec = [str(s) for s in alan.get("secenekler") or []]
        if alan.get("tip") not in ("secim", "evet_hayir") or set(sec) != {"Evet", "Hayır"}:
            continue
        beklenen = "Hayır" if _haric_alani(alan) else "Evet"
        v = str(veriler.get(alan["kod"], "") or "")
        if v != beklenen:
            sorunlar.append(f"{alan.get('etiket', alan['kod'])}: {v or 'boş'}")
    return sorunlar


def ie_formu(calisma) -> Form | None:
    return next((f for f in calisma.formlar if f.kod == "IE" and f.durum != "taslak"), None)


def randomizasyon_engeli(g: Gonullu) -> str | None:
    """Randomizasyon oncesi IE denetimi; engel yoksa None. IE formu olmayan calismada denetim yapilmaz."""
    f = ie_formu(g.calisma)
    if f is None:
        return None
    kayitlar = [fk for fk in g.form_kayitlari if fk.form_id == f.id and fk.durum in ("tamamlandi", "sdv", "kilitli")]
    if not kayitlar:
        return "Uygunluk Kontrolü (IE) formu tamamlanmadan randomizasyon yapılamaz."
    sorunlar = uygunluk_sorunlari(f, max(kayitlar, key=lambda fk: fk.id).veriler)
    if sorunlar:
        return "Uygunluk Kontrolü formuna göre gönüllü uygun değil: " + "; ".join(sorunlar)
    return None
