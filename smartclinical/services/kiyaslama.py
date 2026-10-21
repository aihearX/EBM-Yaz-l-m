"""Merkez Performans Endeksi: calismalar arasi anonim kiyaslama.

Her merkezin aktivasyon suresi, kazanim hizi, tarama basarisizligi ve veri kalitesi gostergeleri,
ayni kurum tipindeki ve ayni terapotik alandaki merkez havuzuyla karsilastirilir ve yuzdelik dilim
olarak raporlanir. Sponsor gorunumunde merkez adlari gizlenir (M-01, M-02 ...). Veri biriktikce
(daha fazla calisma, daha fazla merkez) kiyaslama kuvvetlenir; bu, platformun kurumlar arasi
paylasilan deger uretme mekanizmasidir.
"""
from datetime import date
from statistics import median

from sqlalchemy import select

from ..models import GonulluDurumu, Merkez


def _yuzdelik(deger, havuz, yon="yuksek"):
    """Degerin havuz icindeki yuzdelik dilimi (0-100). yon='yuksek' -> buyuk deger iyi."""
    if deger is None or not havuz:
        return None
    if yon == "yuksek":
        alt = sum(1 for h in havuz if h < deger)
    else:
        alt = sum(1 for h in havuz if h > deger)
    return round(100 * alt / len(havuz))


def merkez_olcumleri(db, bugun: date | None = None) -> list[dict]:
    bugun = bugun or date.today()
    sonuc = []
    for m in db.scalars(select(Merkez).order_by(Merkez.ad)):
        cms = [cm for cm in m.calismalar if cm.aktivasyon_tarihi]
        if not cms:
            continue
        akt = [(cm.aktivasyon_tarihi - cm.secim_tarihi).days for cm in cms if cm.secim_tarihi]
        toplam_rand, toplam_ay, tarama, basarisiz, sorgu, form = 0, 0.0, 0, 0, 0, 0
        alanlar = set()
        for cm in cms:
            bitis = cm.calisma.planlanan_bitis if cm.durum == "kapali" and cm.calisma.planlanan_bitis else bugun
            toplam_ay += max(0.5, (min(bitis, bugun) - cm.aktivasyon_tarihi).days / 30.4)
            alanlar.add(cm.calisma.terapotik_alan)
            for g in cm.gonulluler:
                tarama += 1
                if g.randomizasyon_tarihi:
                    toplam_rand += 1
                if g.durum == GonulluDurumu.TARAMA_BASARISIZ:
                    basarisiz += 1
                for fk in g.form_kayitlari:
                    form += 1
                    sorgu += len(fk.sorgular)
        sonuc.append({
            "merkez": m, "calisma": len(cms), "alanlar": sorted(alanlar),
            "aktivasyon_gun": median(akt) if akt else None,
            "hasta_ay": toplam_rand / toplam_ay if toplam_ay else None,
            "tarama_basarisiz": (100 * basarisiz / tarama) if tarama else None,
            "sorgu_orani": (sorgu / form) if form else None,
            "randomize": toplam_rand,
        })
    return sonuc


def endeks(db, anonim: bool = False) -> dict:
    olcumler = merkez_olcumleri(db)
    gostergeler = [("aktivasyon_gun", "dusuk"), ("hasta_ay", "yuksek"), ("tarama_basarisiz", "dusuk"), ("sorgu_orani", "dusuk")]
    for o in olcumler:
        tip = o["merkez"].kurum_tipi
        for kod, yon in gostergeler:
            havuz = [x[kod] for x in olcumler if x[kod] is not None]
            tip_havuz = [x[kod] for x in olcumler if x[kod] is not None and x["merkez"].kurum_tipi == tip]
            o[f"{kod}_p"] = _yuzdelik(o[kod], havuz, yon)
            o[f"{kod}_tip_p"] = _yuzdelik(o[kod], tip_havuz, yon)
        puanlar = [o[f"{k}_p"] for k, _ in gostergeler if o.get(f"{k}_p") is not None]
        o["endeks"] = round(sum(puanlar) / len(puanlar)) if puanlar else None
    olcumler.sort(key=lambda o: -(o["endeks"] or 0))
    if anonim:
        for i, o in enumerate(olcumler, 1):
            o["etiket"] = f"M-{i:02d} ({o['merkez'].kurum_tipi.replace('_', ' ')}, {o['merkez'].sehir[:1]}…)"
    else:
        for o in olcumler:
            o["etiket"] = o["merkez"].ad
    # kurum tipi bazinda medyanlar
    tipler = {}
    for o in olcumler:
        t = tipler.setdefault(o["merkez"].kurum_tipi, {k: [] for k, _ in gostergeler})
        for k, _ in gostergeler:
            if o[k] is not None:
                t[k].append(o[k])
    tip_ozet = {tip: {k: (median(v) if v else None) for k, v in d.items()} | {"n": len(d["hasta_ay"])} for tip, d in tipler.items()}
    return {"merkezler": olcumler, "tip_ozet": tip_ozet, "n": len(olcumler)}
