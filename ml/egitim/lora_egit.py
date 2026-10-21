"""Talimat ince ayarı – QLoRA.

    python -m ml.egitim.lora_egit --config ml/configs/talimat_ince_ayar.yaml

Tek 24 GB kartta 7B model için 4-bit nf4 + LoRA r=16 yeterli. Daha büyük
toplu boyut için gradyan birikimini artırın, toplu boyutu değil.
"""

import argparse
import json
import sys
from pathlib import Path

from ._ortak import cihaz_bilgisi, config_oku, egitim_bagimliliklari


def _veri_yukle(datasets, yol: str):
    ds = datasets.load_dataset("json", data_files=yol, split="train")
    return ds


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--temel-model", help="config'teki temel_model'i ezer")
    p.add_argument("--kuru", action="store_true", help="Veriyi yükle, modeli yükleme (hızlı kontrol)")
    args = p.parse_args(argv)

    cfg = config_oku(args.config)
    if args.temel_model:
        cfg["temel_model"] = args.temel_model
    torch, transformers, peft, datasets = egitim_bagimliliklari()
    print("Cihaz:", cihaz_bilgisi(torch))

    egitim_ds = _veri_yukle(datasets, cfg["veri"]["egitim"])
    dogrulama_ds = _veri_yukle(datasets, cfg["veri"]["dogrulama"]) if Path(cfg["veri"]["dogrulama"]).exists() else None
    print(f"Eğitim örneği: {len(egitim_ds)}  doğrulama: {len(dogrulama_ds) if dogrulama_ds else 0}")
    if args.kuru:
        return 0

    try:
        from trl import SFTConfig, SFTTrainer
    except ImportError:
        print("trl kurulu değil: pip install trl", file=sys.stderr)
        return 2

    nic = cfg.get("nicemleme", {})
    bnb = None
    if nic.get("yukle_4bit"):
        bnb = transformers.BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=nic.get("tip", "nf4"),
            bnb_4bit_use_double_quant=nic.get("cift_nicemleme", True),
            bnb_4bit_compute_dtype=getattr(torch, nic.get("hesaplama_dtype", "bfloat16")),
        )

    tokenizer = transformers.AutoTokenizer.from_pretrained(cfg["temel_model"], use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = transformers.AutoModelForCausalLM.from_pretrained(
        cfg["temel_model"], quantization_config=bnb, device_map="auto",
        torch_dtype=torch.bfloat16 if bnb is None else None,
    )
    if bnb is not None:
        model = peft.prepare_model_for_kbit_training(model)

    lcfg = cfg["lora"]
    lora = peft.LoraConfig(
        r=lcfg["r"], lora_alpha=lcfg["alpha"], lora_dropout=lcfg.get("dropout", 0.05),
        target_modules=lcfg["hedef_moduller"], bias=lcfg.get("bias", "none"), task_type="CAUSAL_LM",
    )
    model = peft.get_peft_model(model, lora)
    model.print_trainable_parameters()

    e = cfg["egitim"]
    sft_cfg = SFTConfig(
        output_dir=cfg["cikti_dizini"],
        num_train_epochs=e["epoch"],
        learning_rate=float(e["ogrenme_orani"]),
        warmup_ratio=e.get("isinma_orani", 0.05),
        per_device_train_batch_size=e["toplu_boyut"],
        per_device_eval_batch_size=e["toplu_boyut"],
        gradient_accumulation_steps=e["gradyan_birikim"],
        lr_scheduler_type=e.get("lr_zamanlayici", "cosine"),
        bf16=e.get("karisik_hassasiyet") == "bf16",
        gradient_checkpointing=e.get("gradient_checkpointing", True),
        eval_strategy="steps" if dogrulama_ds else "no",
        eval_steps=e.get("degerlendirme_adimi", 200),
        save_steps=e.get("kaydetme_adimi", 200),
        save_total_limit=3,
        load_best_model_at_end=bool(dogrulama_ds) and e.get("en_iyi_modeli_yukle", True),
        logging_steps=20,
        max_length=cfg["veri"].get("maks_uzunluk", 4096),
        seed=cfg.get("tohum", 42),
        report_to="none",
    )
    callbacks = []
    if dogrulama_ds and e.get("erken_durdurma_sabri"):
        callbacks.append(transformers.EarlyStoppingCallback(early_stopping_patience=e["erken_durdurma_sabri"]))

    trainer = SFTTrainer(
        model=model, args=sft_cfg, train_dataset=egitim_ds, eval_dataset=dogrulama_ds,
        processing_class=tokenizer, callbacks=callbacks,
    )
    trainer.train()
    trainer.save_model(cfg["cikti_dizini"])
    tokenizer.save_pretrained(cfg["cikti_dizini"])

    # Eğitim özetini sürüm notları için yanına yaz
    ozet = {"temel_model": cfg["temel_model"], "lora": lcfg, "egitim": e,
            "ornek_sayisi": len(egitim_ds), "son_log": trainer.state.log_history[-1] if trainer.state.log_history else None}
    Path(cfg["cikti_dizini"], "egitim_ozeti.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Tamamlandı:", cfg["cikti_dizini"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
