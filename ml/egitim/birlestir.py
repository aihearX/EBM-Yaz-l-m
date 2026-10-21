"""LoRA ağırlıklarını temel modelle birleştirir (merge). Nicemleme öncesi gerekir.

    python -m ml.egitim.birlestir --temel Qwen/Qwen2.5-7B-Instruct --lora ml/ciktilar/lora --cikti ml/modeller/ebm-klinik-tr-7b
"""

import argparse
import sys

from ._ortak import egitim_bagimliliklari


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--temel", required=True)
    p.add_argument("--lora", required=True)
    p.add_argument("--cikti", required=True)
    args = p.parse_args(argv)
    torch, transformers, peft, _ = egitim_bagimliliklari()

    tokenizer = transformers.AutoTokenizer.from_pretrained(args.lora)
    model = transformers.AutoModelForCausalLM.from_pretrained(args.temel, torch_dtype=torch.bfloat16, device_map="cpu")
    model = peft.PeftModel.from_pretrained(model, args.lora)
    model = model.merge_and_unload()
    model.save_pretrained(args.cikti, safe_serialization=True)
    tokenizer.save_pretrained(args.cikti)
    print("Birleştirildi:", args.cikti)
    return 0


if __name__ == "__main__":
    sys.exit(main())
