"""Sürekli ön eğitim (continued pre-training) – Türkçe tıbbi derlem üzerinde causal LM.

    python -m ml.egitim.on_egitim --config ml/configs/surekli_on_egitim.yaml

Derlem derlem_temizle.py'den geçmiş olmalı (kimliksiz). Ham veriyle çalıştırmayın.
"""

import argparse
import sys
from itertools import chain

from ._ortak import cihaz_bilgisi, config_oku, egitim_bagimliliklari


def _paketle(ornekler, maks_uzunluk: int):
    # Kısa belgeleri uç uca ekleyip sabit uzunlukta bloklara böler (packing)
    birlesik = {k: list(chain(*ornekler[k])) for k in ornekler.keys()}
    toplam = len(birlesik["input_ids"])
    toplam = (toplam // maks_uzunluk) * maks_uzunluk
    sonuc = {k: [t[i:i + maks_uzunluk] for i in range(0, toplam, maks_uzunluk)] for k, t in birlesik.items()}
    sonuc["labels"] = sonuc["input_ids"].copy()
    return sonuc


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    args = p.parse_args(argv)
    cfg = config_oku(args.config)
    torch, transformers, peft, datasets = egitim_bagimliliklari()
    print("Cihaz:", cihaz_bilgisi(torch))

    v = cfg["veri"]
    ds = datasets.load_dataset("json", data_files=v["dosyalar"], split="train")
    tokenizer = transformers.AutoTokenizer.from_pretrained(cfg["temel_model"], use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def tokenize(batch):
        return tokenizer([m + tokenizer.eos_token for m in batch[v.get("metin_alani", "metin")]])

    ds = ds.map(tokenize, batched=True, remove_columns=ds.column_names)
    if v.get("paketleme", True):
        ds = ds.map(lambda b: _paketle(b, v["maks_uzunluk"]), batched=True)
    print(f"Blok sayısı: {len(ds)}")

    model = transformers.AutoModelForCausalLM.from_pretrained(
        cfg["temel_model"], torch_dtype=torch.bfloat16, device_map="auto")
    if cfg.get("lora", {}).get("etkin"):
        lo = cfg["lora"]
        model = peft.get_peft_model(model, peft.LoraConfig(
            r=lo["r"], lora_alpha=lo["alpha"], lora_dropout=lo.get("dropout", 0.05),
            target_modules=lo["hedef_moduller"], task_type="CAUSAL_LM"))
        model.print_trainable_parameters()

    e = cfg["egitim"]
    targs = transformers.TrainingArguments(
        output_dir=cfg["cikti_dizini"],
        num_train_epochs=e["epoch"],
        learning_rate=float(e["ogrenme_orani"]),
        warmup_ratio=e.get("isinma_orani", 0.03),
        per_device_train_batch_size=e["toplu_boyut"],
        gradient_accumulation_steps=e["gradyan_birikim"],
        weight_decay=e.get("agirlik_cozulmesi", 0.0),
        lr_scheduler_type=e.get("lr_zamanlayici", "cosine"),
        bf16=e.get("karisik_hassasiyet") == "bf16",
        gradient_checkpointing=e.get("gradient_checkpointing", True),
        save_steps=e.get("kaydetme_adimi", 500),
        save_total_limit=2,
        logging_steps=e.get("log_adimi", 20),
        seed=cfg.get("tohum", 42),
        report_to="none",
    )
    trainer = transformers.Trainer(
        model=model, args=targs, train_dataset=ds,
        data_collator=transformers.DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    trainer.train()
    trainer.save_model(cfg["cikti_dizini"])
    tokenizer.save_pretrained(cfg["cikti_dizini"])
    print("Tamamlandı:", cfg["cikti_dizini"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
