"""Anahtar Risk Gostergeleri (KRI). ICH E6(R3) 3.10 risk bazli kalite yonetimi.

Her gosterge icin `hesapla_<kod>` fonksiyonu merkez (CalismaMerkez) duzeyinde deger dondurur.
Veri yoksa None doner; None olan gostergeler uyari uretmez.
"""

from datetime import date
from statistics import median

from sqlalchemy import select

from ...models import (
    AdversOlay,
    FormKaydi,
    GonulluDurumu,
    IzlemZiyareti,
    ProtokolSapmasi,
    Sorgu,
    Vizit,
)

KAYITLI_DURUMLAR = (GonulluDurumu.RANDOMIZE, GonulluDurumu.TEDAVIDE, GonulluDurumu.TAKIPTE,
                    GonulluDurumu.TAMAMLADI, GonulluDurumu.AYRILDI)

# NOT: esikler EBM onkoloji/kardiyoloji calismalarindaki medyanlara gore belirlendi; calisma
# bazinda RiskGostergesi tablosundan ezilebilir.
VARSAYILAN_KRILER = [
    {"kod": "SORGU_ORANI", "ad": "Form basina sorgu", "hesaplama": "sorgu_orani", "birim": "sorgu/form",
     "yon": "yuksek", "esik_uyari": 0.25, "esik_aksiyon": 0.50, "agirlik": 1.0,
     "aciklama": "Acilan toplam sorgu sayisinin tamamlanan form sayisina orani. Veri kalitesi gostergesi."},
    {"kod": "SORGU_KAPANIS_GUN", "ad": "Sorgu kapanis suresi (medyan)", "hesaplama": "sorgu_kapanis_gun",
     "birim": "gun", "yon": "yuksek", "esik_uyari": 14, "esik_aksiyon": 30, "agirlik": 0.8,
     "aciklama": "Sorgularin acilistan kapanisa medyan suresi; acik sorgular bugune kadar sayilir."},
    {"kod": "SAPMA_ORANI", "ad": "Gonullu basina protokol sapmasi", "hesaplama": "sapma_orani",
     "birim": "sapma/gonullu", "yon": "yuksek", "esik_uyari": 0.30, "esik_aksiyon": 0.60, "agirlik": 1.2,
     "aciklama": "Tum protokol sapmalarinin kayitli gonullu sayisina orani."},
    {"kod": "MAJOR_SAPMA", "ad": "Major sapma sayisi", "hesaplama": "major_sapma", "birim": "adet",
     "yon": "yuksek", "esik_uyari": 1, "esik_aksiyon": 3, "agirlik": 1.5,
     "aciklama": "Gonullu guvenligini veya veri butunlugunu etkileyen sapmalar."},
    {"kod": "AE_ORANI", "ad": "Gonullu basina advers olay", "hesaplama": "ae_orani", "birim": "AE/gonullu",
     "yon": "dusuk", "esik_uyari": 0.5, "esik_aksiyon": 0.2, "agirlik": 1.2,
     "aciklama": "Dusuk AE bildirimi eksik raporlamaya isaret edebilir; diger merkezlerle karsilastirilir."},
    {"kod": "SAE_GEC_BILDIRIM", "ad": "SAE gec bildirim sayisi", "hesaplama": "sae_gec_bildirim", "birim": "adet",
     "yon": "yuksek", "esik_uyari": 1, "esik_aksiyon": 2, "agirlik": 2.0,
     "aciklama": "Farkindaliktan itibaren 24 saat icinde sponsora bildirilmeyen ciddi advers olaylar."},
    {"kod": "PENCERE_DISI_VIZIT", "ad": "Pencere disi vizit orani", "hesaplama": "pencere_disi_vizit", "birim": "%",
     "yon": "yuksek", "esik_uyari": 10, "esik_aksiyon": 20, "agirlik": 0.8,
     "aciklama": "Gerceklesen vizitler icinde protokol penceresi disinda yapilanlarin yuzdesi."},
    {"kod": "KACIRILAN_VIZIT", "ad": "Kacirilan vizit orani", "hesaplama": "kacirilan_vizit", "birim": "%",
     "yon": "yuksek", "esik_uyari": 5, "esik_aksiyon": 15, "agirlik": 1.0,
     "aciklama": "Planlanan tarihi gecmis ve yapilmamis vizitlerin yuzdesi."},
    {"kod": "TARAMA_BASARISIZ", "ad": "Tarama basarisizlik orani", "hesaplama": "tarama_basarisiz", "birim": "%",
     "yon": "yuksek", "esik_uyari": 40, "esik_aksiyon": 60, "agirlik": 0.7,
     "aciklama": "Taramaya alinan gonulluler icinde basarisiz olanlarin yuzdesi; kriter anlasilmasi sorununa isaret edebilir."},
    {"kod": "ERKEN_AYRILMA", "ad": "Erken ayrilma orani", "hesaplama": "erken_ayrilma", "birim": "%",
     "yon": "yuksek", "esik_uyari": 15, "esik_aksiyon": 25, "agirlik": 1.0,
     "aciklama": "Kayitli gonulluler icinde calismayi tamamlamadan ayrilanlarin yuzdesi."},
    {"kod": "VERI_GIRIS_GECIKME_GUN", "ad": "Veri giris gecikmesi (medyan)", "hesaplama": "veri_giris_gecikme_gun",
     "birim": "gun", "yon": "yuksek", "esik_uyari": 7, "esik_aksiyon": 14, "agirlik": 0.8,
     "aciklama": "Vizit tarihinden form kaydinin olusturulmasina kadar gecen medyan sure."},
    {"kod": "SDV_ORANI", "ad": "SDV tamamlanma orani", "hesaplama": "sdv_orani", "birim": "%",
     "yon": "dusuk", "esik_uyari": 60, "esik_aksiyon": 40, "agirlik": 0.5,
     "aciklama": "Tamamlanan formlar icinde kaynak veri dogrulamasi yapilmis olanlarin yuzdesi."},
    {"kod": "ONAM_HATASI", "ad": "Onam sapmasi sayisi", "hesaplama": "onam_hatasi", "birim": "adet",
     "yon": "yuksek", "esik_uyari": 1, "esik_aksiyon": 2, "agirlik": 2.0,
     "aciklama": "Bilgilendirilmis onam sureciyle ilgili sapmalar (eksik imza, eski versiyon, tarih hatasi)."},
    {"kod": "KAZANIM_HEDEF_SAPMA", "ad": "Kazanim hedef gerisi", "hesaplama": "kazanim_hedef_sapma", "birim": "%",
     "yon": "yuksek", "esik_uyari": 25, "esik_aksiyon": 50, "agirlik": 0.8,
     "aciklama": "Gecen sureye gore beklenen kazanimin yuzde kac gerisinde olundugu."},
    {"kod": "FORM_TAMAMLAMA", "ad": "Form tamamlama orani", "hesaplama": "form_tamamlama", "birim": "%",
     "yon": "dusuk", "esik_uyari": 80, "esik_aksiyon": 60, "agirlik": 0.6,
     "aciklama": "Olusturulan formlar icinde taslak durumunda kalmayanlarin yuzdesi."},
]

KRI_SOZLUK = {k["kod"]: k for k in VARSAYILAN_KRILER}


def _kayitli(cm):
    return [g for g in cm.gonulluler if g.durum in KAYITLI_DURUMLAR]


def _formlar(db, cm):
    gid = [g.id for g in cm.gonulluler]
    if not gid:
        return []
    return db.scalars(select(FormKaydi).where(FormKaydi.gonullu_id.in_(gid))).all()


def _vizitler(db, cm):
    gid = [g.id for g in cm.gonulluler]
    if not gid:
        return []
    return db.scalars(select(Vizit).where(Vizit.gonullu_id.in_(gid))).all()


def _sapmalar(db, cm):
    return db.scalars(select(ProtokolSapmasi).where(ProtokolSapmasi.calisma_merkez_id == cm.id)).all()


def _aeler(db, cm):
    gid = [g.id for g in cm.gonulluler]
    if not gid:
        return []
    return db.scalars(select(AdversOlay).where(AdversOlay.gonullu_id.in_(gid))).all()


def _pct(pay, payda):
    return None if not payda else round(100.0 * pay / payda, 1)


def hesapla_sorgu_orani(db, cm):
    formlar = [f for f in _formlar(db, cm) if f.durum != "taslak"]
    if not formlar:
        return None
    fid = [f.id for f in formlar]
    n_sorgu = len(db.scalars(select(Sorgu.id).where(Sorgu.form_kaydi_id.in_(fid))).all())
    return round(n_sorgu / len(formlar), 3)


def hesapla_sorgu_kapanis_gun(db, cm):
    formlar = _formlar(db, cm)
    if not formlar:
        return None
    fid = [f.id for f in formlar]
    sorgular = db.scalars(select(Sorgu).where(Sorgu.form_kaydi_id.in_(fid))).all()
    if not sorgular:
        return None
    return float(median(s.acik_gun for s in sorgular))


def hesapla_sapma_orani(db, cm):
    kayitli = _kayitli(cm)
    if not kayitli:
        return None
    return round(len(_sapmalar(db, cm)) / len(kayitli), 3)


def hesapla_major_sapma(db, cm):
    return float(sum(1 for s in _sapmalar(db, cm) if s.onem == "major"))


def hesapla_ae_orani(db, cm):
    kayitli = _kayitli(cm)
    if not kayitli:
        return None
    return round(len(_aeler(db, cm)) / len(kayitli), 3)


def hesapla_sae_gec_bildirim(db, cm):
    sayi = 0
    for ae in _aeler(db, cm):
        if not ae.ciddi or not ae.farkindalik_tarihi:
            continue
        son = ae.sponsor_bildirim or date.today()
        if (son - ae.farkindalik_tarihi).days > 1:
            sayi += 1
    return float(sayi)


def hesapla_pencere_disi_vizit(db, cm):
    yapilan = [v for v in _vizitler(db, cm) if v.gerceklesen]
    return _pct(sum(1 for v in yapilan if v.pencere_disi), len(yapilan))


def hesapla_kacirilan_vizit(db, cm):
    bugun = date.today()
    gecmis = [v for v in _vizitler(db, cm) if v.planlanan and v.planlanan + _gun(v.pencere_gun) < bugun]
    return _pct(sum(1 for v in gecmis if not v.gerceklesen or v.durum == "kacirildi"), len(gecmis))


def _gun(n):
    from datetime import timedelta
    return timedelta(days=n or 0)


def hesapla_tarama_basarisiz(db, cm):
    taranan = [g for g in cm.gonulluler if g.durum not in (GonulluDurumu.ADAY, GonulluDurumu.ON_TARAMA, GonulluDurumu.ONAM)]
    return _pct(sum(1 for g in taranan if g.durum == GonulluDurumu.TARAMA_BASARISIZ), len(taranan))


def hesapla_erken_ayrilma(db, cm):
    kayitli = _kayitli(cm)
    return _pct(sum(1 for g in kayitli if g.durum == GonulluDurumu.AYRILDI), len(kayitli))


def hesapla_veri_giris_gecikme_gun(db, cm):
    gecikmeler = []
    for f in _formlar(db, cm):
        if f.vizit and f.vizit.gerceklesen and f.olusturma:
            gecikmeler.append((f.olusturma.date() - f.vizit.gerceklesen).days)
    if not gecikmeler:
        return None
    return float(median(gecikmeler))


def hesapla_sdv_orani(db, cm):
    tamam = [f for f in _formlar(db, cm) if f.durum != "taslak"]
    return _pct(sum(1 for f in tamam if f.durum in ("sdv", "kilitli") or f.sdv_zamani), len(tamam))


def hesapla_onam_hatasi(db, cm):
    return float(sum(1 for s in _sapmalar(db, cm) if s.kategori == "onam"))


def hesapla_kazanim_hedef_sapma(db, cm):
    if not cm.hedef_hasta or not cm.aktivasyon_tarihi:
        return None
    calisma = cm.calisma
    bugun = date.today()
    if calisma.planlanan_bitis and calisma.planlanan_bitis > cm.aktivasyon_tarihi:
        toplam_gun = (calisma.planlanan_bitis - cm.aktivasyon_tarihi).days
    else:
        toplam_gun = 365
    gecen = min((bugun - cm.aktivasyon_tarihi).days, toplam_gun)
    if gecen <= 0:
        return None
    beklenen = cm.hedef_hasta * gecen / toplam_gun
    gercek = len(_kayitli(cm))
    if beklenen <= 0:
        return None
    return round(max(0.0, 100.0 * (beklenen - gercek) / beklenen), 1)


def hesapla_form_tamamlama(db, cm):
    formlar = _formlar(db, cm)
    return _pct(sum(1 for f in formlar if f.durum != "taslak"), len(formlar))


HESAPLAYICILAR = {
    "sorgu_orani": hesapla_sorgu_orani,
    "sorgu_kapanis_gun": hesapla_sorgu_kapanis_gun,
    "sapma_orani": hesapla_sapma_orani,
    "major_sapma": hesapla_major_sapma,
    "ae_orani": hesapla_ae_orani,
    "sae_gec_bildirim": hesapla_sae_gec_bildirim,
    "pencere_disi_vizit": hesapla_pencere_disi_vizit,
    "kacirilan_vizit": hesapla_kacirilan_vizit,
    "tarama_basarisiz": hesapla_tarama_basarisiz,
    "erken_ayrilma": hesapla_erken_ayrilma,
    "veri_giris_gecikme_gun": hesapla_veri_giris_gecikme_gun,
    "sdv_orani": hesapla_sdv_orani,
    "onam_hatasi": hesapla_onam_hatasi,
    "kazanim_hedef_sapma": hesapla_kazanim_hedef_sapma,
    "form_tamamlama": hesapla_form_tamamlama,
}


def kri_hesapla(db, calisma, kriler=None):
    """{calisma_merkez_id: {KOD: deger}}. kriler: dict listesi (VARSAYILAN_KRILER bicimi) ya da RiskGostergesi."""
    kriler = kriler if kriler is not None else VARSAYILAN_KRILER
    sonuc = {}
    for cm in calisma.merkezler:
        if cm.durum in ("aday", "fizibilite", "secildi"):
            continue  # henuz hasta yok
        degerler = {}
        for k in kriler:
            kod = k["kod"] if isinstance(k, dict) else k.kod
            hes = k["hesaplama"] if isinstance(k, dict) else k.hesaplama
            fn = HESAPLAYICILAR.get(hes)
            if fn is None:
                continue
            degerler[kod] = fn(db, cm)
        sonuc[cm.id] = degerler
    return sonuc


def izlem_ziyaret_sayisi(db, cm):
    return len(db.scalars(select(IzlemZiyareti.id).where(IzlemZiyareti.calisma_merkez_id == cm.id,
                                                          IzlemZiyareti.gerceklesen.is_not(None))).all())
