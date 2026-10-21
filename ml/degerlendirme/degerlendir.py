"""Altın standart üzerinde model değerlendirmesi.

    python -m ml.degerlendirme.degerlendir --altin ml/degerlendirme/ornek_altin_standart.jsonl
    python -m ml.degerlendirme.degerlendir --saglayici ollama --model ebm-klinik-tr-7b-q4

Görevler:
  * kriter_eslestirme : etiket (saglandi/saglanmadi/belirsiz) duyarlılık, özgüllük, F1, makro F1
  * kanit_cikar       : kanıt cümlesi kaynakta var mı (halüsinasyon oranı), klinisyen span ile örtüşme
  * kriter_yapilandir : hesaplanabilir sorgu tam/alan bazlı eşleşme

Uygulamadaki BDM istemcisi (smartclinical.services.bdm) kullanılır; sağlayıcı "kural" ise ağ gerekmez
ve sonuç kural tabanlı referans değerdir. Sonuç ml/ciktilar/<tarih>.json'a yazılır.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from . import metrikler as M


def _altin_oku(yol: Path) -> list[dict]:
    kayitlar = []
    with yol.open(encoding="utf-8") as f:
        for satir in f:
            if satir.strip():
                kayitlar.append(json.loads(satir))
    return kayitlar


def _etiket(k: dict) -> str:
    return k.get("hakem_karari") or k["etiket"]


def _bdm_olustur(saglayici: str | None, model: str | None):
    if saglayici:
        os.environ["SC_BDM_SAGLAYICI"] = saglayici
    if model:
        os.environ["SC_BDM_MODEL"] = model
    try:
        from smartclinical.services.bdm import BDMIstemci
    except Exception as e:  # modül henüz yoksa
        print(f"BDM istemcisi yüklenemedi ({e}); değerlendirme yapılamıyor.", file=sys.stderr)
        return None
    try:
        return BDMIstemci.olustur()
    except Exception as e:
        print(f"BDM istemcisi başlatılamadı: {e}", file=sys.stderr)
        return None


def _kanit_cikar(bdm, kriter: str, tip: str, metin: str) -> tuple[str, str | None, float]:
    """Dönen: (sonuc, kanit, guven). İstemci arayüzü değişirse burayı güncelle."""
    s = bdm.kanit_cikar(kriter, [metin]) if tip is None else bdm.kanit_cikar(kriter, [metin])
    sonuc = getattr(s, "sonuc", None) or (s.get("sonuc") if isinstance(s, dict) else "belirsiz")
    kanit = getattr(s, "kanit_cumlesi", None) if not isinstance(s, dict) else s.get("kanit")
    guven = getattr(s, "guven", 0.0) if not isinstance(s, dict) else s.get("guven", 0.0)
    return sonuc or "belirsiz", kanit, float(guven or 0.0)


def _yapilandir(bdm, kriter: str, tip: str) -> dict | None:
    y = bdm.kriter_yapilandir(kriter, tip)
    if y is None:
        return None
    if hasattr(y, "to_dict"):
        y = y.to_dict()
    # KriterYapisi.to_dict() {"kategori", "sorgu", ...} döner; karşılaştırma sorgu üzerinden
    if isinstance(y, dict) and "sorgu" in y:
        return y["sorgu"]
    return y


def degerlendir(kayitlar: list[dict], bdm, gorevler: list[str]) -> dict:
    sonuc: dict = {"n": len(kayitlar)}
    gercek, tahmin, guvenler, dogru = [], [], [], []
    kanit_ciftleri, ortusmeler = [], []
    yap_tam, yap_alan = [], []
    sureler = []
    zorluk_dogru: dict[str, list[bool]] = {}

    for k in kayitlar:
        g = _etiket(k)
        t0 = time.perf_counter()
        s, kanit, guven = _kanit_cikar(bdm, k["kriter_metni"], k["kriter_tipi"], k["metin"])
        sureler.append((time.perf_counter() - t0) * 1000)
        gercek.append(g)
        tahmin.append(s)
        guvenler.append(guven)
        dogru.append(g == s)
        zorluk_dogru.setdefault(k.get("zorluk") or "bilinmiyor", []).append(g == s)
        if "kanit_cikar" in gorevler:
            kanit_ciftleri.append((kanit, k["metin"]))
            if k.get("kanit_span"):
                ortusmeler.append(M.kanit_ortusme(kanit, [sp.get("metin") or k["metin"][sp["baslangic"]:sp["bitis"]]
                                                          for sp in k["kanit_span"]]))
        if "kriter_yapilandir" in gorevler and k.get("yapisal") is not None:
            e = M.yapilandirma_eslesme(k["yapisal"], _yapilandir(bdm, k["kriter_metni"], k["kriter_tipi"]))
            yap_tam.append(e["tam"])
            yap_alan.append(e["alan_orani"])

    if "kriter_eslestirme" in gorevler:
        kar = M.karisiklik(gercek, tahmin, "saglandi")
        # "belirsiz" tahmini klinik açıdan güvenli taraftır; ayrıca raporla
        sonuc["kriter_eslestirme"] = {
            "duyarlilik": M.duyarlilik(kar), "ozgulluk": M.ozgulluk(kar), "kesinlik": M.kesinlik(kar),
            "f1": M.f1(kar), "makro_f1": M.makro_f1(gercek, tahmin), "dogruluk": M.dogruluk(gercek, tahmin),
            "belirsiz_orani": tahmin.count("belirsiz") / len(tahmin) if tahmin else 0.0,
            "karisiklik": kar,
            "zorluga_gore_dogruluk": {z: sum(v) / len(v) for z, v in zorluk_dogru.items()},
            "kalibrasyon": M.guven_kalibrasyonu(guvenler, dogru),
        }
    if "kanit_cikar" in gorevler:
        sonuc["kanit_cikar"] = {
            "halusinasyon_orani": M.halusinasyon_orani(kanit_ciftleri),
            "kanit_veren_oran": sum(1 for kn, _ in kanit_ciftleri if kn) / len(kanit_ciftleri) if kanit_ciftleri else 0.0,
            "span_ortusme_ort": sum(ortusmeler) / len(ortusmeler) if ortusmeler else 0.0,
        }
    if "kriter_yapilandir" in gorevler:
        sonuc["kriter_yapilandir"] = {
            "n": len(yap_tam),
            "tam_eslesme": sum(yap_tam) / len(yap_tam) if yap_tam else 0.0,
            "alan_eslesme_ort": sum(yap_alan) / len(yap_alan) if yap_alan else 0.0,
        }
    sonuc["sure_ms"] = {"ort": sum(sureler) / len(sureler) if sureler else 0.0, "maks": max(sureler) if sureler else 0.0}
    return sonuc


def markdown_tablo(sonuc: dict, hedefler: dict | None = None) -> str:
    h = hedefler or {}
    satirlar = ["| Metrik | Değer | Hedef | Durum |", "|---|---|---|---|"]

    def ekle(ad, deger, hedef=None, kucuk_iyi=False):
        if hedef is None:
            satirlar.append(f"| {ad} | {deger:.3f} | - | |")
            return
        ok = deger <= hedef if kucuk_iyi else deger >= hedef
        satirlar.append(f"| {ad} | {deger:.3f} | {'≤' if kucuk_iyi else '≥'} {hedef:.2f} | {'sağlandı' if ok else 'sağlanmadı'} |")

    ke = sonuc.get("kriter_eslestirme")
    if ke:
        ekle("Duyarlılık (saglandi)", ke["duyarlilik"], h.get("duyarlilik_min"))
        ekle("Özgüllük", ke["ozgulluk"])
        ekle("F1", ke["f1"])
        ekle("Makro F1", ke["makro_f1"])
        ekle("Belirsiz oranı", ke["belirsiz_orani"])
    kc = sonuc.get("kanit_cikar")
    if kc:
        ekle("Halüsinasyon oranı", kc["halusinasyon_orani"], h.get("halusinasyon_orani_maks"), kucuk_iyi=True)
        ekle("Kanıt-span örtüşmesi", kc["span_ortusme_ort"])
    ky = sonuc.get("kriter_yapilandir")
    if ky:
        ekle("Yapılandırma tam eşleşme", ky["tam_eslesme"], h.get("yapilandirma_dogrulugu_min"))
        ekle("Yapılandırma alan eşleşme", ky["alan_eslesme_ort"])
    satirlar.append(f"| Ortalama süre (ms) | {sonuc['sure_ms']['ort']:.1f} | - | |")
    return "\n".join(satirlar)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="ml/configs/degerlendirme.yaml")
    p.add_argument("--altin", type=Path)
    p.add_argument("--saglayici", help="kural | ollama | vllm | llamacpp")
    p.add_argument("--model")
    p.add_argument("--cikti-dizini", type=Path)
    args = p.parse_args(argv)

    cfg = {}
    if Path(args.config).exists():
        try:
            import yaml
            cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
        except ImportError:
            pass
    altin = args.altin or Path(cfg.get("altin_standart", "ml/degerlendirme/ornek_altin_standart.jsonl"))
    saglayici = args.saglayici or cfg.get("saglayici")
    model = args.model or cfg.get("model")
    cikti_dizini = args.cikti_dizini or Path(cfg.get("cikti_dizini", "ml/ciktilar"))
    gorevler = cfg.get("gorevler", ["kriter_eslestirme", "kanit_cikar", "kriter_yapilandir"])

    if not altin.exists():
        print(f"Altın standart bulunamadı: {altin}", file=sys.stderr)
        return 2
    bdm = _bdm_olustur(saglayici, model)
    if bdm is None:
        return 2

    kayitlar = _altin_oku(altin)
    sonuc = degerlendir(kayitlar, bdm, gorevler)
    sonuc["meta"] = {"tarih": datetime.now().isoformat(timespec="seconds"), "altin": str(altin),
                     "saglayici": saglayici or os.environ.get("SC_BDM_SAGLAYICI", "kural"),
                     "model": model or os.environ.get("SC_BDM_MODEL")}

    cikti_dizini.mkdir(parents=True, exist_ok=True)
    yol = cikti_dizini / f"{datetime.now():%Y%m%d_%H%M%S}.json"
    yol.write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Sağlayıcı: {sonuc['meta']['saglayici']}  model: {sonuc['meta']['model']}  n={sonuc['n']}")
    print(markdown_tablo(sonuc, cfg.get("hedefler")))
    print(f"\nKaydedildi: {yol}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
