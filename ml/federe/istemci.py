"""Hastane tarafı federe istemci: yerel LoRA eğitimi, adaptör dışa aktarımı ve toplayıcıya gönderim.

    python -m ml.federe.istemci --config ml/federe/config.yaml --katilimci H-ANK-01 --kuru

Yerel eğitim ml/egitim/lora_egit.py'ye delege edilir; torch yoksa açıklayıcı mesajla çıkılır.
Hasta metni bu modülden hiçbir koşulda dışarı çıkmaz; gönderilen yalnızca adaptör dosyası ve özetidir.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ..egitim._ortak import config_oku
from .toplayici import ozet


def yerel_egit(config: dict, katilimci: str, kuru: bool) -> Path:
    """LoRA eğitimini çalıştırır ve adaptör .npz yolunu döndürür."""
    cikti = Path("ml/modeller/federe") / f"{katilimci}_r{config['tur']['numara']}.npz"
    if kuru:
        print(f"[kuru] yerel eğitim atlandı; adaptör yolu {cikti}")
        return cikti
    try:
        import torch  # noqa: F401
    except ImportError:
        print("torch kurulu değil: yerel eğitim GPU sunucusunda `pip install -e '.[ml]' trl` ile kurulduktan sonra çalışır.",
              file=sys.stderr)
        sys.exit(2)
    komut = [sys.executable, "-m", "ml.egitim.lora_egit", "--config", config["yerel_egitim"]["config"]]
    subprocess.run(komut, check=True)
    # TODO(burak): lora_egit cikti dizinindeki adapter_model.safetensors -> npz donusumu (birlestir.py'ye ekle)
    return cikti


def gonder(url: str, katilimci: str, adaptor: Path, ornek_sayisi: int, kuru: bool) -> dict:
    paket = {"katilimci": katilimci, "dosya": adaptor.name, "sha256": ozet(adaptor) if adaptor.exists() else None,
             "ornek_sayisi": ornek_sayisi}
    if kuru:
        print(f"[kuru] gönderim atlandı: {json.dumps(paket, ensure_ascii=False)}")
        return paket
    import httpx

    with adaptor.open("rb") as f:
        r = httpx.post(url, data={k: str(v) for k, v in paket.items()}, files={"adaptor": (adaptor.name, f)}, timeout=120)
    r.raise_for_status()
    return r.json()


def main(argv=None):
    p = argparse.ArgumentParser(description="Federe LoRA hastane istemcisi")
    p.add_argument("--config", required=True)
    p.add_argument("--katilimci", required=True)
    p.add_argument("--ornek-sayisi", type=int, default=0, help="yerel eğitimde kullanılan kayıt sayısı (ağırlık)")
    p.add_argument("--kuru", action="store_true", help="eğitim ve gönderim yapılmaz, akış doğrulanır")
    a = p.parse_args(argv)
    cfg = config_oku(a.config)
    if a.katilimci not in {k["kod"] for k in cfg.get("katilimcilar", [])}:
        print(f"{a.katilimci} katılımcı listesinde yok; config.yaml'a eklenmeli.", file=sys.stderr)
        return 2
    if not a.kuru and a.ornek_sayisi < cfg["yerel_egitim"].get("minimum_ornek", 0):
        print(f"Yerel örnek sayısı minimumun altında ({cfg['yerel_egitim']['minimum_ornek']}); tur atlanıyor.", file=sys.stderr)
        return 3
    adaptor = yerel_egit(cfg, a.katilimci, a.kuru)
    sonuc = gonder(cfg["toplayici"]["url"], a.katilimci, adaptor, a.ornek_sayisi, a.kuru)
    print(json.dumps(sonuc, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
