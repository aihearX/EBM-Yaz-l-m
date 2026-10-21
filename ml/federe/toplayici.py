"""Federe toplayıcı: LoRA adaptörlerini ağırlıklı ortalama ile birleştirir.

Adaptör biçimi: {parametre_adi: numpy dizisi}. Dosya olarak .npz (safetensors kuruluysa
.safetensors de okunur). Torch gerekmez; toplayıcı uygulama sunucusunda çalışabilir.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


class ToplamaHatasi(ValueError):
    pass


def yukle(yol: str | Path) -> dict[str, np.ndarray]:
    yol = Path(yol)
    if yol.suffix == ".npz":
        with np.load(yol) as z:
            return {k: z[k] for k in z.files}
    if yol.suffix == ".safetensors":
        try:
            from safetensors.numpy import load_file
        except ImportError:
            raise ToplamaHatasi("safetensors kurulu değil; .npz kullanın")
        return load_file(str(yol))
    raise ToplamaHatasi(f"desteklenmeyen biçim: {yol.suffix}")


def kaydet(adaptor: dict[str, np.ndarray], yol: str | Path) -> str:
    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)
    np.savez(yol, **adaptor)
    return ozet(yol)


def ozet(yol: str | Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def _dogrula(adaptorler: list[dict[str, np.ndarray]]) -> None:
    if not adaptorler:
        raise ToplamaHatasi("adaptör listesi boş")
    anahtarlar = set(adaptorler[0])
    for i, a in enumerate(adaptorler[1:], 1):
        if set(a) != anahtarlar:
            eksik = anahtarlar ^ set(a)
            raise ToplamaHatasi(f"adaptör {i} parametre adları uyuşmuyor: {sorted(eksik)[:5]}")
        for k in anahtarlar:
            if a[k].shape != adaptorler[0][k].shape:
                raise ToplamaHatasi(f"{k}: şekil uyuşmazlığı {a[k].shape} != {adaptorler[0][k].shape}")
            if not np.all(np.isfinite(a[k])):
                raise ToplamaHatasi(f"adaptör {i}, {k}: sonlu olmayan değer")


def kirp(guncelleme: dict[str, np.ndarray], norm: float) -> dict[str, np.ndarray]:
    """İstemci güncellemesini (adaptör - küresel) toplam L2 normuna göre kırpar (DP öncesi)."""
    toplam = float(np.sqrt(sum(float(np.sum(v.astype(np.float64) ** 2)) for v in guncelleme.values())))
    if toplam <= norm or toplam == 0:
        return guncelleme
    olcek = norm / toplam
    return {k: v * olcek for k, v in guncelleme.items()}


def fedavg(adaptorler: list[dict[str, np.ndarray]], agirliklar: list[float] | None = None) -> dict[str, np.ndarray]:
    """Örnek sayısıyla ağırlıklı ortalama (McMahan ve ark., 2017). Ağırlık verilmezse eşit."""
    _dogrula(adaptorler)
    n = len(adaptorler)
    w = np.ones(n, dtype=np.float64) if agirliklar is None else np.asarray(agirliklar, dtype=np.float64)
    if w.shape != (n,) or np.any(w < 0) or w.sum() == 0:
        raise ToplamaHatasi("ağırlıklar adaptör sayısıyla eşleşmeli, negatif olmamalı ve toplamı sıfır olmamalı")
    w = w / w.sum()
    sonuc = {}
    for k in adaptorler[0]:
        yigin = np.stack([a[k].astype(np.float64) for a in adaptorler])
        sonuc[k] = np.tensordot(w, yigin, axes=1).astype(adaptorler[0][k].dtype)
    return sonuc


def fedprox_duzelt(kuresel: dict[str, np.ndarray], birlesik: dict[str, np.ndarray], mu: float) -> dict[str, np.ndarray]:
    """Toplayıcı tarafı yakınlık düzeltmesi: heterojen verilerde küresel modele doğru çeker.
    Gerçek FedProx yakınlık terimi istemci kaybındadır; burada basit bir sunucu tarafı eşdeğeri."""
    return {k: (birlesik[k] + mu * kuresel[k]) / (1 + mu) for k in birlesik}


def dp_gurultu(adaptor: dict[str, np.ndarray], sigma: float, seed: int | None = None) -> dict[str, np.ndarray]:
    """Gauss mekanizması: her parametreye N(0, sigma^2). Kırpma normu ile birlikte (epsilon, delta) bütçesi
    tur bazında raporlanır; hesap `ml/federe/README.md`."""
    if sigma <= 0:
        return adaptor
    rng = np.random.default_rng(seed)
    return {k: (v + rng.normal(0.0, sigma, size=v.shape)).astype(v.dtype) for k, v in adaptor.items()}


def birlestir(yollar: list[str], agirliklar: list[float] | None, dp_sigma: float = 0.0,
              kuresel_yol: str | None = None, fedprox_mu: float = 0.0, kirpma_normu: float | None = None,
              seed: int | None = None) -> dict[str, np.ndarray]:
    adaptorler = [yukle(y) for y in yollar]
    kuresel = yukle(kuresel_yol) if kuresel_yol else None
    if kuresel is not None and kirpma_normu:
        # güncellemeleri kırpıp küresele geri ekle
        adaptorler = [{k: kuresel[k] + v for k, v in kirp({k: a[k] - kuresel[k] for k in a}, kirpma_normu).items()}
                      for a in adaptorler]
    sonuc = fedavg(adaptorler, agirliklar)
    if kuresel is not None and fedprox_mu > 0:
        sonuc = fedprox_duzelt(kuresel, sonuc, fedprox_mu)
    return dp_gurultu(sonuc, dp_sigma, seed)


def main(argv=None):
    p = argparse.ArgumentParser(description="Federe LoRA toplayıcı")
    p.add_argument("--adaptorler", nargs="+", required=True)
    p.add_argument("--agirliklar", nargs="*", type=float, help="katılımcı başına örnek sayısı")
    p.add_argument("--kuresel", help="önceki tur küresel adaptörü (kırpma / FedProx için)")
    p.add_argument("--fedprox-mu", type=float, default=0.0)
    p.add_argument("--kirpma-normu", type=float)
    p.add_argument("--dp-sigma", type=float, default=0.0)
    p.add_argument("--seed", type=int)
    p.add_argument("--cikti", required=True)
    a = p.parse_args(argv)
    if a.agirliklar and len(a.agirliklar) != len(a.adaptorler):
        print("ağırlık sayısı adaptör sayısına eşit olmalı", file=sys.stderr)
        return 2
    try:
        sonuc = birlestir(a.adaptorler, a.agirliklar or None, a.dp_sigma, a.kuresel, a.fedprox_mu, a.kirpma_normu, a.seed)
    except ToplamaHatasi as e:
        print(f"Toplama hatası: {e}", file=sys.stderr)
        return 1
    oz = kaydet(sonuc, a.cikti)
    print(json.dumps({"cikti": a.cikti, "sha256": oz, "katilimci": len(a.adaptorler), "parametre": len(sonuc),
                      "dp_sigma": a.dp_sigma}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
