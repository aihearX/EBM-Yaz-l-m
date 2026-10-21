"""TR-KlinikBench çalıştırıcı ve federe toplayıcı testleri."""
import json

import numpy as np
import pytest

from ml.federe import toplayici as T
from ml.tr_klinik_bench import GOREVLER
from ml.tr_klinik_bench import calistir as C


def _adaptor(rng, olcek=1.0):
    return {"lora_A.q_proj": rng.normal(0, olcek, (4, 8)).astype(np.float32),
            "lora_B.q_proj": rng.normal(0, olcek, (8, 4)).astype(np.float32)}


def test_fedavg_esit_agirlik():
    rng = np.random.default_rng(1)
    a, b = _adaptor(rng), _adaptor(rng)
    s = T.fedavg([a, b])
    for k in a:
        assert np.allclose(s[k], (a[k] + b[k]) / 2, atol=1e-6)
        assert s[k].dtype == np.float32


def test_fedavg_agirlikli_ve_dogrulama():
    rng = np.random.default_rng(2)
    a, b, c = _adaptor(rng), _adaptor(rng), _adaptor(rng)
    s = T.fedavg([a, b, c], [1000, 0, 3000])
    for k in a:
        assert np.allclose(s[k], 0.25 * a[k] + 0.75 * c[k], atol=1e-6)
    with pytest.raises(T.ToplamaHatasi):
        T.fedavg([a, {"lora_A.q_proj": a["lora_A.q_proj"]}])
    with pytest.raises(T.ToplamaHatasi):
        T.fedavg([a, b], [1, -1])
    bozuk = {k: v.copy() for k, v in b.items()}
    bozuk["lora_A.q_proj"][0, 0] = np.nan
    with pytest.raises(T.ToplamaHatasi):
        T.fedavg([a, bozuk])


def test_dp_gurultu_ve_kirpma():
    rng = np.random.default_rng(3)
    a = _adaptor(rng)
    g = T.dp_gurultu(a, sigma=0.05, seed=7)
    assert set(g) == set(a) and all(g[k].shape == a[k].shape for k in a)
    assert not np.allclose(g["lora_A.q_proj"], a["lora_A.q_proj"])
    fark = np.concatenate([(g[k] - a[k]).ravel() for k in a])
    assert abs(fark.std() - 0.05) < 0.02
    assert T.dp_gurultu(a, sigma=0) is a
    buyuk = _adaptor(rng, olcek=10)
    kirpik = T.kirp(buyuk, 1.0)
    norm = np.sqrt(sum(float(np.sum(v.astype(np.float64) ** 2)) for v in kirpik.values()))
    assert abs(norm - 1.0) < 1e-6


def test_toplayici_cli_npz(tmp_path):
    rng = np.random.default_rng(4)
    yollar = []
    for i in range(3):
        y = tmp_path / f"a{i}.npz"
        T.kaydet(_adaptor(rng), y)
        yollar.append(str(y))
    cikti = tmp_path / "kuresel.npz"
    kod = T.main(["--adaptorler", *yollar, "--agirliklar", "1", "1", "2", "--dp-sigma", "0.001", "--seed", "1", "--cikti", str(cikti)])
    assert kod == 0 and cikti.exists()
    s = T.yukle(cikti)
    assert set(s) == {"lora_A.q_proj", "lora_B.q_proj"} and len(T.ozet(cikti)) == 64


def test_bench_veri_semaya_uygun():
    for g in GOREVLER:
        kayitlar = C.oku(g)
        assert len(kayitlar) >= 10
        assert all(k["id"].startswith(g.upper() + "-") for k in kayitlar)
    # span ofsetleri yüklemede doğrulanır; burada en az bir kaydın span taşıdığını kontrol et
    assert any(k["kanit_span"] for k in C.oku("g2"))


def test_bench_g4_g5_kural():
    sonuc = C.calistir(["g4", "g5"], saglayici="kural")
    g4, g5 = sonuc["gorevler"]["g4"], sonuc["gorevler"]["g5"]
    assert 0.8 <= g4["duyarlilik"] <= 1.0 and g4["kesinlik"] >= 0.9 and g4["klinik_terim_koruma"] >= 0.9
    assert g5["f1"] >= 0.9
    md = C.markdown(sonuc, "test")
    assert "| G4 |" in md and "| G5 |" in md


def test_bench_g1_g3_kural_ve_cikti(tmp_path):
    kod = C.main(["--gorevler", "g1,g3", "--saglayici", "kural", "--cikti-dizini", str(tmp_path)])
    assert kod == 0
    dosyalar = list(tmp_path.glob("bench_*.json"))
    assert len(dosyalar) == 1
    s = json.loads(dosyalar[0].read_text(encoding="utf-8"))
    assert 0 <= s["gorevler"]["g1"]["duyarlilik"] <= 1 and s["gorevler"]["g3"]["tam_eslesme"] >= 0.8
    assert C.main(["--gorevler", "g9"]) == 2
