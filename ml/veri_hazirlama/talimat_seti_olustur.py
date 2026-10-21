"""Klinik araştırma görevleri için talimat (instruction) veri seti üretici.

Kaynaklar:
  * Altın standart JSONL (klinisyen etiketli hasta-kriter çiftleri) -> kanıt çıkarma, kriter yapılandırma
  * Şablon tabanlı sentetik örnekler -> kriter yapılandırma (sayısal eşik, yaş, tanı)
  * Kimliksiz epikriz derlemi (opsiyonel) -> özet ve soru-cevap örnekleri (öğretmen çıktısı gerekir)

Çıktı: ChatML uyumlu JSONL; her satır {"gorev": ..., "messages": [...]}.

Kullanım:
    python -m ml.veri_hazirlama.talimat_seti_olustur --altin ml/degerlendirme/ornek_altin_standart.jsonl \
        --cikti veri/talimat/egitim.jsonl --dogrulama-orani 0.1
"""

import argparse
import json
import random
import sys
from pathlib import Path

SISTEM = (
    "Klinik araştırma uzmanlarına yardımcı olan bir asistansın. Yalnızca verilen metne dayanarak "
    "cevap verirsin. Metinde bilgi yoksa 'belirsiz' dersin ve uydurmazsın. Çıktıyı istenen JSON "
    "biçiminde verirsin."
)

KANIT_SABLONU = (
    "Aşağıdaki hasta metnine göre kriterin durumunu değerlendir.\n\n"
    "Kriter ({tip}): {kriter}\n\nHasta metni:\n\"\"\"\n{metin}\n\"\"\"\n\n"
    "JSON olarak dön: {{\"sonuc\": \"saglandi|saglanmadi|belirsiz\", \"kanit\": \"metinden birebir cümle veya null\", "
    "\"guven\": 0-1}}"
)

YAPILANDIR_SABLONU = (
    "Aşağıdaki {tip} kriterini hesaplanabilir sorguya dönüştür. Sorgu alanları: yas, cinsiyet, tani (icd10), "
    "lab (loinc, op, deger, birim), ilac (atc), performans, gebelik, zaman. Emin olamadığın alanı boş bırak.\n\n"
    "Kriter: {kriter}\n\nJSON olarak dön."
)

# Şablon tabanlı sentetik kriterler. Çeşitlilik için birkaç yazım biçimi.
_LAB = [
    ("hemoglobin", "718-7", "g/dL", (8, 12)),
    ("trombosit", "777-3", "10^9/L", (75, 150)),
    ("mutlak nötrofil sayısı", "751-8", "10^9/L", (1.0, 2.0)),
    ("kreatinin", "2160-0", "mg/dL", (1.2, 2.0)),
    ("eGFR", "62238-1", "mL/dk/1.73m2", (30, 60)),
    ("AST", "1920-8", "x ÜNS", (2.5, 5)),
    ("ALT", "1742-6", "x ÜNS", (2.5, 5)),
    ("total bilirubin", "1975-2", "x ÜNS", (1.5, 3)),
    ("HbA1c", "4548-4", "%", (7, 10)),
]
_TANI = [
    ("tip 2 diabetes mellitus", "E11"), ("küçük hücreli dışı akciğer kanseri", "C34"),
    ("meme kanseri", "C50"), ("kolorektal kanser", "C18"), ("kronik obstrüktif akciğer hastalığı", "J44"),
    ("kalp yetersizliği", "I50"), ("atriyal fibrilasyon", "I48"), ("romatoid artrit", "M06"),
    ("kronik böbrek hastalığı", "N18"), ("multipl skleroz", "G35"), ("hipertansiyon", "I10"),
]


def _lab_ornegi(rng: random.Random) -> dict:
    ad, loinc, birim, (alt, ust) = rng.choice(_LAB)
    deger = round(rng.uniform(alt, ust), 1)
    op = rng.choice([">=", "<=", ">", "<"])
    op_metin = {">=": rng.choice(["≥", ">=", "ve üzeri"]), "<=": rng.choice(["≤", "<=", "ve altı"]),
                ">": ">", "<": "<"}[op]
    if op_metin in ("ve üzeri", "ve altı"):
        kriter = f"{ad.capitalize()} {deger} {birim} {op_metin}"
    else:
        kriter = f"{ad.capitalize()} {op_metin} {deger} {birim}"
    if rng.random() < 0.3:
        kriter += " (tarama öncesi son 14 gün içinde)"
        son_gun = 14
    else:
        son_gun = None
    yapisal = {"alan": "lab", "loinc": loinc, "ad": ad, "op": op, "deger": deger, "birim": birim, "son_gun": son_gun}
    return {"kriter": kriter, "tip": "dahil", "yapisal": yapisal}


def _yas_ornegi(rng: random.Random) -> dict:
    alt = rng.choice([18, 18, 18, 40, 50, 65])
    ust = rng.choice([None, None, 65, 70, 75, 80])
    bicim = rng.random()
    if ust is None:
        kriter = rng.choice([f"{alt} yaş ve üzeri", f"≥{alt} yaş", f"{alt} yaşından büyük hastalar",
                             f"Patients aged {alt} years or older"])
        yapisal = {"alan": "yas", "op": ">=", "deger": alt}
    elif bicim < 0.5:
        kriter = f"{alt}-{ust} yaş arası (sınırlar dahil)"
        yapisal = {"ve": [{"alan": "yas", "op": ">=", "deger": alt}, {"alan": "yas", "op": "<=", "deger": ust}]}
    else:
        kriter = f"Aged {alt} to {ust} years at screening"
        yapisal = {"ve": [{"alan": "yas", "op": ">=", "deger": alt}, {"alan": "yas", "op": "<=", "deger": ust}]}
    return {"kriter": kriter, "tip": "dahil", "yapisal": yapisal}


def _tani_ornegi(rng: random.Random) -> dict:
    ad, icd = rng.choice(_TANI)
    on_ek = rng.choice(["Histolojik olarak doğrulanmış ", "Tanısı konmuş ", "Belgelenmiş ", ""])
    tip = "dahil"
    son_ay = None
    if rng.random() < 0.3:
        tip = "haric"
        son_ay = rng.choice([3, 6, 12])
        kriter = f"Son {son_ay} ay içinde {ad} öyküsü"
    else:
        kriter = f"{on_ek}{ad}"
    yapisal = {"alan": "tani", "icd10": [icd], "terimler": [ad], "son_ay": son_ay}
    return {"kriter": kriter, "tip": tip, "yapisal": yapisal}


def sentetik_yapilandirma(n: int, rng: random.Random) -> list[dict]:
    uretici = [_lab_ornegi, _yas_ornegi, _tani_ornegi]
    ornekler = []
    for _ in range(n):
        o = rng.choice(uretici)(rng)
        ornekler.append({
            "gorev": "kriter_yapilandir",
            "messages": [
                {"role": "system", "content": SISTEM},
                {"role": "user", "content": YAPILANDIR_SABLONU.format(tip=o["tip"], kriter=o["kriter"])},
                {"role": "assistant", "content": json.dumps(o["yapisal"], ensure_ascii=False)},
            ],
        })
    return ornekler


def altin_standarttan(altin: Path) -> list[dict]:
    ornekler = []
    with altin.open(encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir:
                continue
            k = json.loads(satir)
            # uyumsuz ve hakem kararı olmayan kayıtlar eğitime girmez
            if k.get("uyum") is False and not k.get("hakem_karari"):
                continue
            etiket = k.get("hakem_karari") or k["etiket"]
            kanit = None
            if k.get("kanit_span"):
                kanit = k["kanit_span"][0].get("metin") or k["metin"][k["kanit_span"][0]["baslangic"]:k["kanit_span"][0]["bitis"]]
            cevap = {"sonuc": etiket, "kanit": kanit, "guven": 0.95 if etiket != "belirsiz" else 0.5}
            ornekler.append({
                "gorev": "kanit_cikar",
                "messages": [
                    {"role": "system", "content": SISTEM},
                    {"role": "user", "content": KANIT_SABLONU.format(tip=k["kriter_tipi"], kriter=k["kriter_metni"],
                                                                     metin=k["metin"])},
                    {"role": "assistant", "content": json.dumps(cevap, ensure_ascii=False)},
                ],
            })
            if k.get("yapisal"):
                ornekler.append({
                    "gorev": "kriter_yapilandir",
                    "messages": [
                        {"role": "system", "content": SISTEM},
                        {"role": "user", "content": YAPILANDIR_SABLONU.format(tip=k["kriter_tipi"], kriter=k["kriter_metni"])},
                        {"role": "assistant", "content": json.dumps(k["yapisal"], ensure_ascii=False)},
                    ],
                })
    return ornekler


def ogretmen_ciktilarindan(dosya: Path) -> list[dict]:
    """Özet ve soru-cevap örnekleri: {"gorev", "girdi", "cikti"} satırlarından.

    Bu örnekler büyük bir öğretmen modelle (kapalı ağda) üretilip klinisyen tarafından
    gözden geçirilmiş olmalı. Gözden geçirilmemiş satırlar ("onay": false) atlanır.
    """
    ornekler = []
    with dosya.open(encoding="utf-8") as f:
        for satir in f:
            if not satir.strip():
                continue
            k = json.loads(satir)
            if not k.get("onay", False):
                continue
            ornekler.append({
                "gorev": k["gorev"],
                "messages": [
                    {"role": "system", "content": SISTEM},
                    {"role": "user", "content": k["girdi"]},
                    {"role": "assistant", "content": k["cikti"]},
                ],
            })
    return ornekler


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--altin", type=Path, required=True)
    p.add_argument("--ogretmen", type=Path, default=None, help="Gözden geçirilmiş özet/soru-cevap örnekleri")
    p.add_argument("--cikti", type=Path, required=True)
    p.add_argument("--sentetik", type=int, default=400)
    p.add_argument("--dogrulama-orani", type=float, default=0.1)
    p.add_argument("--tohum", type=int, default=42)
    args = p.parse_args(argv)

    rng = random.Random(args.tohum)
    ornekler = altin_standarttan(args.altin) + sentetik_yapilandirma(args.sentetik, rng)
    if args.ogretmen and args.ogretmen.exists():
        ornekler += ogretmen_ciktilarindan(args.ogretmen)
    rng.shuffle(ornekler)

    n_dog = int(len(ornekler) * args.dogrulama_orani)
    dogrulama, egitim = ornekler[:n_dog], ornekler[n_dog:]

    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    dog_yol = args.cikti.with_name(args.cikti.stem.replace("egitim", "dogrulama") + ".jsonl")
    if dog_yol == args.cikti:
        dog_yol = args.cikti.with_name(args.cikti.stem + "_dogrulama.jsonl")
    for yol, veri in ((args.cikti, egitim), (dog_yol, dogrulama)):
        with yol.open("w", encoding="utf-8") as f:
            for o in veri:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")

    sayim = {}
    for o in ornekler:
        sayim[o["gorev"]] = sayim.get(o["gorev"], 0) + 1
    print(f"eğitim: {len(egitim)}  doğrulama: {len(dogrulama)}")
    for g, n in sorted(sayim.items()):
        print(f"  {g:<20} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
