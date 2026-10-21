"""Türkçe tıbbi derlem temizleme.

Girdi: .txt (her dosya bir belge) veya .jsonl ("metin" alanı) dosyaları içeren dizin.
Çıktı: temizlenmiş, tekilleştirilmiş, kimliksizleştirilmiş JSONL.

Kullanım:
    python -m ml.veri_hazirlama.derlem_temizle --girdi veri/ham --cikti veri/temiz/derlem.jsonl
"""

import argparse
import hashlib
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from smartclinical.services.kimliksizlestirme import kimliksizlestir
except Exception:  # modül henüz yoksa ya da bağımlılık eksikse
    kimliksizlestir = None

MIN_KARAKTER = 200          # çok kısa belgeler (başlık, boş rapor) atılır
MAKS_TEKRAR_ORANI = 0.4     # satırların %40'ından fazlası tekrarsa şablon çıktısıdır, at

_BOSLUK = re.compile(r"[ \t ]+")
_COK_SATIR = re.compile(r"\n{3,}")
_KONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# HBYS çıktılarında sık görülen sayfa altlığı / başlık kalıpları
_GURULTU = re.compile(
    r"^(sayfa\s*\d+(\s*/\s*\d+)?|tarih\s*:\s*[\d./]+|yazdıran\s*:.*|rapor no\s*:.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def normalize(metin: str) -> str:
    metin = unicodedata.normalize("NFC", metin)
    metin = _KONTROL.sub("", metin)
    metin = metin.replace("\r\n", "\n").replace("\r", "\n")
    metin = _GURULTU.sub("", metin)
    metin = _BOSLUK.sub(" ", metin)
    metin = "\n".join(s.strip() for s in metin.split("\n"))
    metin = _COK_SATIR.sub("\n\n", metin)
    return metin.strip()


def tekrar_orani(metin: str) -> float:
    satirlar = [s for s in metin.split("\n") if s.strip()]
    if len(satirlar) < 5:
        return 0.0
    return 1.0 - len(set(satirlar)) / len(satirlar)


def icerik_hash(metin: str) -> str:
    # Noktalama ve büyük/küçük harf farkını yok sayan yakın-tekil anahtar.
    # NOT: MinHash kadar güçlü değil ama HBYS kopyaları için yeterli oldu.
    anahtar = re.sub(r"[^0-9a-zçğıöşü]+", " ", metin.lower()).strip()
    return hashlib.sha1(anahtar.encode("utf-8")).hexdigest()


def belgeleri_oku(dizin: Path):
    for yol in sorted(dizin.rglob("*")):
        if yol.suffix == ".txt":
            yield {"kaynak": str(yol), "metin": yol.read_text(encoding="utf-8", errors="replace")}
        elif yol.suffix == ".jsonl":
            with yol.open(encoding="utf-8") as f:
                for i, satir in enumerate(f):
                    satir = satir.strip()
                    if not satir:
                        continue
                    try:
                        kayit = json.loads(satir)
                    except json.JSONDecodeError:
                        log.warning("%s:%d okunamadı, atlandı", yol, i + 1)
                        continue
                    kayit.setdefault("kaynak", f"{yol}:{i + 1}")
                    yield kayit


def temizle(dizin: Path, cikti: Path, kimliksizlestirme: bool = True) -> dict:
    gorulen: set[str] = set()
    sayac = {"okunan": 0, "kisa": 0, "tekrar": 0, "sablon": 0, "yazilan": 0, "phi_bulgu": 0}
    cikti.parent.mkdir(parents=True, exist_ok=True)

    if kimliksizlestirme and kimliksizlestir is None:
        log.warning("kimliksizleştirme modülü yüklenemedi; derlem HAM yazılıyor, eğitimde kullanmayın")

    with cikti.open("w", encoding="utf-8") as f:
        for kayit in belgeleri_oku(dizin):
            sayac["okunan"] += 1
            metin = normalize(kayit.get("metin", ""))
            if len(metin) < MIN_KARAKTER:
                sayac["kisa"] += 1
                continue
            if tekrar_orani(metin) > MAKS_TEKRAR_ORANI:
                sayac["sablon"] += 1
                continue
            h = icerik_hash(metin)
            if h in gorulen:
                sayac["tekrar"] += 1
                continue
            gorulen.add(h)

            if kimliksizlestirme and kimliksizlestir is not None:
                sonuc = kimliksizlestir(metin, mod="maske")
                metin = sonuc.metin
                sayac["phi_bulgu"] += len(sonuc.bulgular)

            f.write(json.dumps({
                "id": h[:16],
                "tur": kayit.get("tur", "bilinmiyor"),   # epikriz | patoloji | radyoloji | ...
                "metin": metin,
                "karakter": len(metin),
            }, ensure_ascii=False) + "\n")
            sayac["yazilan"] += 1
    return sayac


def main(argv=None):
    p = argparse.ArgumentParser(description="Türkçe tıbbi derlem temizleme")
    p.add_argument("--girdi", required=True, type=Path)
    p.add_argument("--cikti", required=True, type=Path)
    p.add_argument("--kimliksizlestirme-yok", action="store_true",
                   help="Sadece zaten kimliksiz veri için. Üretim derleminde kullanılmaz.")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.girdi.is_dir():
        print(f"Girdi dizini bulunamadı: {args.girdi}", file=sys.stderr)
        return 2
    sayac = temizle(args.girdi, args.cikti, kimliksizlestirme=not args.kimliksizlestirme_yok)
    for k, v in sayac.items():
        print(f"{k:>10}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
