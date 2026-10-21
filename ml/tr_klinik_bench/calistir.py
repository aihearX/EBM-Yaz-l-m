"""TR-KlinikBench çalıştırıcı.

    python -m ml.tr_klinik_bench.calistir --gorevler g1,g4,g5 --saglayici kural
    python -m ml.tr_klinik_bench.calistir --gorevler g1,g2 --saglayici vllm --model ebm-klinik-tr-7b-q4 --etiket "ebm-klinik-tr v0.2"

Görevler smartclinical servisleriyle koşulur; sağlayıcı "kural" ise ağ gerekmez ve sonuç
kural tabanlı taban çizgisidir. Çıktı: ml/ciktilar/bench_<tarih>.json ve .md
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from ..degerlendirme import metrikler as M
from . import GOREVLER, SURUM

VERI_DIZINI = Path(__file__).parent / "veri"
DOSYALAR = {
    "g1": "g1_eslestirme.jsonl", "g2": "g2_kanit.jsonl", "g3": "g3_yapilandirma.jsonl",
    "g4": "g4_kimliksizlestirme.jsonl", "g5": "g5_icd.jsonl", "g6": "g6_ozet.jsonl",
}
# Proje başarı ölçütleri (BDM hedefleri); skor tablosunda "hedef" sütunu
HEDEFLER = {
    "g1": {"duyarlilik": 0.90, "ozgulluk": 0.90}, "g2": {"halusinasyon_orani": 0.02, "span_ortusme": 0.70},
    "g3": {"tam_eslesme": 0.85}, "g4": {"duyarlilik": 0.98, "kesinlik": 0.95},
    "g5": {"f1": 0.90}, "g6": {"kapsama": 0.85},
}


def oku(gorev: str) -> list[dict]:
    yol = VERI_DIZINI / DOSYALAR[gorev]
    kayitlar = []
    with yol.open(encoding="utf-8") as f:
        for satir in f:
            if satir.strip():
                k = json.loads(satir)
                # span tutarlılığı: ofset ile metin kopyası birbirini tutmalı
                for sp in k.get("kanit_span") or []:
                    if k["metin"][sp["baslangic"]:sp["bitis"]] != sp["metin"]:
                        raise ValueError(f"{k['id']}: kanit_span ofseti metinle uyuşmuyor")
                kayitlar.append(k)
    return kayitlar


def _etiket(k: dict) -> str:
    return k.get("hakem_karari") or k["etiket"]


# --------------------------------------------------------------------------- servisler
def _bdm(saglayici: str | None, model: str | None):
    if saglayici:
        os.environ["SC_BDM_SAGLAYICI"] = saglayici
    if model:
        os.environ["SC_BDM_MODEL"] = model
    try:
        from smartclinical.services.bdm import BDMIstemci
        return BDMIstemci.olustur()
    except Exception as e:  # uygulama paketi yoksa G1-G3, G6 koşulamaz
        print(f"BDM istemcisi yüklenemedi: {e}", file=sys.stderr)
        return None


def _kimliksizlestir():
    try:
        from smartclinical.services.kimliksizlestirme import kimliksizlestir
        return kimliksizlestir
    except Exception as e:
        print(f"Kimliksizleştirme servisi yüklenemedi: {e}", file=sys.stderr)
        return None


def _icd_kodla():
    """Sözlük tabanlı ICD-10 eşleme; API'deki /yz/icd-kodla ile aynı mantık."""
    try:
        from smartclinical.services.kriter import sozluk as S
    except Exception as e:
        print(f"Tanı sözlüğü yüklenemedi: {e}", file=sys.stderr)
        return None

    def kodla(metin: str) -> set[str]:
        m = S.sade(metin)
        kodlar: set[str] = set()
        for terim in S.TANI_TERIMLERI:
            if len(terim) < 4:
                continue
            if re.search(r"\b" + re.escape(S.sade(terim)) + r"\b", m):
                kodlar.update(S.TANI_SOZLUGU[terim])
        return kodlar

    return kodla


# --------------------------------------------------------------------------- görevler
def g1(kayitlar, bdm) -> dict:
    gercek, tahmin, guvenler, dogru, sureler = [], [], [], [], []
    zorluk: dict[str, list[bool]] = {}
    for k in kayitlar:
        t0 = time.perf_counter()
        s = bdm.kanit_cikar(k["kriter_metni"], [k["metin"]])
        sureler.append((time.perf_counter() - t0) * 1000)
        g = _etiket(k)
        gercek.append(g)
        tahmin.append(s.sonuc)
        guvenler.append(float(s.guven or 0))
        dogru.append(g == s.sonuc)
        zorluk.setdefault(k.get("zorluk", "orta"), []).append(g == s.sonuc)
    kar = M.karisiklik(gercek, tahmin, "saglandi")
    # belirsiz etiketli altın kayıtlar duyarlılık/özgüllük hesabının dışında tutulur
    kesin = [(g, t) for g, t in zip(gercek, tahmin) if g != "belirsiz"]
    kar_k = M.karisiklik([g for g, _ in kesin], [t for _, t in kesin], "saglandi")
    tn_k = M.karisiklik([g for g, _ in kesin], [t for _, t in kesin], "saglanmadi")
    return {
        "n": len(kayitlar), "duyarlilik": M.duyarlilik(kar_k), "ozgulluk": M.duyarlilik(tn_k),
        "kesinlik": M.kesinlik(kar_k), "f1": M.f1(kar_k), "makro_f1": M.makro_f1(gercek, tahmin),
        "dogruluk": M.dogruluk(gercek, tahmin), "belirsiz_orani": tahmin.count("belirsiz") / len(tahmin),
        "karisiklik": kar, "zorluga_gore_dogruluk": {z: sum(v) / len(v) for z, v in zorluk.items()},
        "kalibrasyon_ece": M.guven_kalibrasyonu(guvenler, dogru)["ece"],
        "sure_ms_ort": sum(sureler) / len(sureler),
    }


def g2(kayitlar, bdm) -> dict:
    ciftler, ortusmeler, dogru_karar = [], [], []
    for k in kayitlar:
        s = bdm.kanit_cikar(k["kriter_metni"], [k["metin"]])
        kanit = s.kanit_cumlesi
        ciftler.append((kanit, k["metin"]))
        ortusmeler.append(M.kanit_ortusme(kanit, [sp["metin"] for sp in k["kanit_span"]]))
        dogru_karar.append(s.sonuc == _etiket(k))
    return {
        "n": len(kayitlar), "halusinasyon_orani": M.halusinasyon_orani(ciftler),
        "kanit_veren_oran": sum(1 for kn, _ in ciftler if kn) / len(ciftler),
        "span_ortusme": sum(ortusmeler) / len(ortusmeler),
        "span_ortusme_0_5_ustu": sum(1 for o in ortusmeler if o >= 0.5) / len(ortusmeler),
        "karar_dogrulugu": sum(dogru_karar) / len(dogru_karar),
    }


def g3(kayitlar, bdm) -> dict:
    tam, alan, kategori = [], [], []
    for k in kayitlar:
        y = bdm.kriter_yapilandir(k["kriter_metni"], k["kriter_tipi"])
        d = y.to_dict()
        sorgu = d.get("sorgu") or {}
        if isinstance(sorgu, dict) and "degil" in sorgu and isinstance(sorgu["degil"], dict):
            sorgu = sorgu["degil"]
        e = M.yapilandirma_eslesme(k["yapisal"], sorgu)
        tam.append(e["tam"])
        alan.append(e["alan_orani"])
        kategori.append(d.get("kategori") == k["kategori"])
    return {"n": len(kayitlar), "tam_eslesme": sum(tam) / len(tam), "alan_eslesme": sum(alan) / len(alan),
            "kategori_dogrulugu": sum(kategori) / len(kategori)}


def g4(kayitlar, kimliksizlestir) -> dict:
    tp = fp = fn = 0
    terim_korundu = terim_toplam = 0
    for k in kayitlar:
        s = kimliksizlestir(k["metin"])
        bulunan = {b.tur for b in s.bulgular}
        beklenen = set(k["varliklar"])
        tp += len(bulunan & beklenen)
        fp += len(bulunan - beklenen)
        fn += len(beklenen - bulunan)
        for t in k.get("klinik_terimler", []):
            terim_toplam += 1
            terim_korundu += t.lower() in s.metin.lower()
    kar = {"tp": tp, "fp": fp, "fn": fn, "tn": 0}
    return {"n": len(kayitlar), "varlik_sayisi": tp + fn, "duyarlilik": M.duyarlilik(kar), "kesinlik": M.kesinlik(kar),
            "f1": M.f1(kar), "klinik_terim_koruma": (terim_korundu / terim_toplam) if terim_toplam else 1.0}


def g5(kayitlar, kodla) -> dict:
    tp = fp = fn = 0
    tam = 0
    for k in kayitlar:
        beklenen = set(k["icd10"])
        bulunan = kodla(k["metin"])
        tp += len(bulunan & beklenen)
        fp += len(bulunan - beklenen)
        fn += len(beklenen - bulunan)
        tam += bulunan == beklenen
    kar = {"tp": tp, "fp": fp, "fn": fn, "tn": 0}
    return {"n": len(kayitlar), "duyarlilik": M.duyarlilik(kar), "kesinlik": M.kesinlik(kar), "f1": M.f1(kar),
            "tam_eslesme": tam / len(kayitlar)}


def g6(kayitlar, bdm) -> dict:
    kapsama, madde_uyum = [], []
    for k in kayitlar:
        maddeler = bdm.klinik_ozet(k["metin"])
        birlesik = M.normalize(" ".join(maddeler))
        bulunan = sum(1 for a in k["anahtar_bilgiler"] if M.normalize(a) in birlesik)
        kapsama.append(bulunan / len(k["anahtar_bilgiler"]))
        madde_uyum.append(1 <= len(maddeler) <= k.get("maks_madde", 6))
    return {"n": len(kayitlar), "kapsama": sum(kapsama) / len(kapsama), "madde_sayisi_uyumu": sum(madde_uyum) / len(madde_uyum)}


# --------------------------------------------------------------------------- koşu
def calistir(gorevler: list[str], saglayici: str | None = None, model: str | None = None) -> dict:
    sonuc: dict = {"bench_surumu": SURUM, "saglayici": saglayici or os.environ.get("SC_BDM_SAGLAYICI", "kural"),
                   "model": model or os.environ.get("SC_BDM_MODEL"), "zaman": datetime.now().isoformat(timespec="seconds"),
                   "gorevler": {}}
    bdm = _bdm(saglayici, model) if any(g in gorevler for g in ("g1", "g2", "g3", "g6")) else None
    for g in gorevler:
        kayitlar = oku(g)
        if g in ("g1", "g2", "g3", "g6"):
            if bdm is None:
                sonuc["gorevler"][g] = {"hata": "BDM istemcisi yok"}
                continue
            sonuc["gorevler"][g] = {"g1": g1, "g2": g2, "g3": g3, "g6": g6}[g](kayitlar, bdm)
        elif g == "g4":
            fn = _kimliksizlestir()
            sonuc["gorevler"][g] = g4(kayitlar, fn) if fn else {"hata": "servis yok"}
        elif g == "g5":
            fn = _icd_kodla()
            sonuc["gorevler"][g] = g5(kayitlar, fn) if fn else {"hata": "servis yok"}
    if bdm is not None:
        sonuc["model"] = getattr(bdm, "model_adi", sonuc["model"])
    return sonuc


ANA_METRIK = {"g1": ("duyarlilik", "ozgulluk", "makro_f1", "belirsiz_orani"), "g2": ("halusinasyon_orani", "span_ortusme", "karar_dogrulugu"),
              "g3": ("tam_eslesme", "alan_eslesme", "kategori_dogrulugu"), "g4": ("duyarlilik", "kesinlik", "f1", "klinik_terim_koruma"),
              "g5": ("duyarlilik", "kesinlik", "f1"), "g6": ("kapsama", "madde_sayisi_uyumu")}
KUCUK_IYI = {"halusinasyon_orani", "belirsiz_orani"}


def markdown(sonuc: dict, etiket: str) -> str:
    satirlar = [f"Sistem: **{etiket}** · sağlayıcı: {sonuc['saglayici']} · model: {sonuc.get('model')} · bench {sonuc['bench_surumu']} · {sonuc['zaman']}", "",
                "| Görev | n | Metrik | Değer | Hedef (BDM) |", "|---|---|---|---|---|"]
    for g, r in sonuc["gorevler"].items():
        if "hata" in r:
            satirlar.append(f"| {g.upper()} | – | – | {r['hata']} | |")
            continue
        for m in ANA_METRIK[g]:
            hedef = HEDEFLER[g].get(m)
            h = "" if hedef is None else (f"≤ {hedef:.2f}" if m in KUCUK_IYI else f"≥ {hedef:.2f}")
            satirlar.append(f"| {g.upper()} | {r['n']} | {m} | {r[m]:.3f} | {h} |")
    return "\n".join(satirlar)


def main(argv=None):
    p = argparse.ArgumentParser(description="TR-KlinikBench çalıştırıcı")
    p.add_argument("--gorevler", default=",".join(GOREVLER))
    p.add_argument("--saglayici", help="kural | ollama | vllm | llamacpp")
    p.add_argument("--model")
    p.add_argument("--etiket", default="kural tabanlı taban çizgisi")
    p.add_argument("--cikti-dizini", default="ml/ciktilar")
    a = p.parse_args(argv)
    gorevler = [g.strip().lower() for g in a.gorevler.split(",") if g.strip()]
    bilinmeyen = [g for g in gorevler if g not in GOREVLER]
    if bilinmeyen:
        print(f"Bilinmeyen görev: {bilinmeyen}", file=sys.stderr)
        return 2
    sonuc = calistir(gorevler, a.saglayici, a.model)
    sonuc["etiket"] = a.etiket
    md = markdown(sonuc, a.etiket)
    print(md)
    dizin = Path(a.cikti_dizini)
    dizin.mkdir(parents=True, exist_ok=True)
    ad = f"bench_{datetime.now():%Y%m%d_%H%M%S}"
    (dizin / f"{ad}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
    (dizin / f"{ad}.md").write_text(md + "\n", encoding="utf-8")
    print(f"\nKaydedildi: {dizin / ad}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
