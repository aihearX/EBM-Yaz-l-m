# Türkçe Klinik BDM – Geliştirme Altyapısı

Bu dizin EBM SmartClinical içinde kullanılan Türkçe klinik büyük dil modelinin
(kısaca BDM) veri hazırlama, eğitim, değerlendirme ve nicemleme adımlarını içerir.
Uygulama tarafı (`smartclinical/services/bdm`) burada üretilen modeli hastane içi
sunucuda (Ollama / vLLM / llama.cpp) çalıştırır; model dosyaları depoya eklenmez
(`ml/modeller/` ve `ml/ciktilar/` .gitignore'dadır).

## Akış

```
 Türkçe tıbbi derlem ──> derlem_temizle.py ──> sürekli ön eğitim (on_egitim.py)
                                                        │
 altın standart etiketler ──> talimat_seti_olustur.py ──> talimat ince ayarı (lora_egit.py, QLoRA)
                                                        │
                                                  birlestir.py (LoRA merge)
                                                        │
                                          degerlendir.py (duyarlılık / halüsinasyon)
                                                        │
                                              nicemle.sh (GGUF, Q4_K_M)
                                                        │
                                          hastane içi dağıtım (deploy/docker-compose.yml, profil: bdm)
```

## Komutlar

```bash
# 1. Derlemi temizle ve kimliksizleştir (girdi: her satır bir belge olan .jsonl veya .txt dosyaları)
python -m ml.veri_hazirlama.derlem_temizle --girdi veri/ham --cikti veri/temiz/derlem.jsonl

# 2. Talimat setini üret (altın standart + şablonlar)
python -m ml.veri_hazirlama.talimat_seti_olustur \
    --altin ml/degerlendirme/ornek_altin_standart.jsonl --cikti veri/talimat/egitim.jsonl

# 3. Sürekli ön eğitim (GPU gerekir)
python -m ml.egitim.on_egitim --config ml/configs/surekli_on_egitim.yaml

# 4. Talimat ince ayarı (QLoRA, tek 24GB GPU yeterli)
python -m ml.egitim.lora_egit --config ml/configs/talimat_ince_ayar.yaml

# 5. LoRA ağırlıklarını temel modelle birleştir
python -m ml.egitim.birlestir --temel Qwen/Qwen2.5-7B-Instruct --lora ml/ciktilar/lora --cikti ml/modeller/ebm-klinik-tr-7b

# 6. Değerlendirme (model yoksa kural tabanlı sağlayıcıyla çalışır, referans değer verir)
python -m ml.degerlendirme.degerlendir --altin ml/degerlendirme/ornek_altin_standart.jsonl

# 7. Nicemleme ve dağıtım
bash ml/egitim/nicemle.sh ml/modeller/ebm-klinik-tr-7b
```

## Dizinler

| Dizin | İçerik |
|---|---|
| `configs/` | Eğitim, nicemleme ve değerlendirme yapılandırmaları |
| `veri_hazirlama/` | Derlem temizleme, talimat seti üretimi, etiketleme şeması ve kılavuzu |
| `egitim/` | Sürekli ön eğitim, QLoRA, LoRA birleştirme, nicemleme betiği |
| `degerlendirme/` | Metrikler, değerlendirme koşucusu, örnek altın standart |

## Notlar

- Eğitim verisi hastane dışına çıkmaz. Ön eğitim ve ince ayar hastane içindeki GPU
  sunucusunda ya da EBM'nin kapalı ağ eğitim kümesinde yapılır.
- Altın standart setteki her örnek en az iki klinisyen tarafından etiketlenmiştir;
  uyumsuz örnekler üçüncü değerlendirici ile çözülür (bkz. `etiketleme_kilavuzu.md`).
- Değerlendirme çıktıları `ml/ciktilar/<tarih>.json` olarak saklanır; sürüm notlarına
  eklenen metrikler bu dosyalardan alınır.
