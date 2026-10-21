import sys
from pathlib import Path


def config_oku(yol: str | Path) -> dict:
    try:
        import yaml
    except ImportError:
        print("PyYAML kurulu değil: pip install pyyaml", file=sys.stderr)
        sys.exit(2)
    with open(yol, encoding="utf-8") as f:
        return yaml.safe_load(f)


def egitim_bagimliliklari():
    """torch/transformers/peft yoksa anlaşılır mesajla çık. Uygulama sunucusunda bunlar kurulu değildir."""
    try:
        import datasets  # noqa: F401
        import peft  # noqa: F401
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as e:
        print(
            f"Eğitim bağımlılığı eksik ({e.name}). GPU sunucusunda şu komutla kurun:\n"
            "    pip install -e '.[ml]' trl\n"
            "Bu betik uygulama sunucusunda çalıştırılmak için değildir.",
            file=sys.stderr,
        )
        sys.exit(2)
    return torch, transformers, peft, datasets


def cihaz_bilgisi(torch) -> str:
    if torch.cuda.is_available():
        ad = torch.cuda.get_device_name(0)
        bellek = torch.cuda.get_device_properties(0).total_memory / 1e9
        return f"{ad} ({bellek:.0f} GB)"
    return "CPU (eğitim için uygun değil)"
