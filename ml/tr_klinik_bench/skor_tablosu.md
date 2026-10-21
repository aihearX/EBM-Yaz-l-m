# TR-KlinikBench skor tablosu

Set sürümü 0.3 (sentetik), son güncelleme 21.10.2026. Değerler `calistir.py` çıktısından
alınmıştır; ilgili JSON `ml/ciktilar/bench_20261021_094133.json`. Sentetik set üzerindeki
sonuçlar, gerçek rapor seti sonuçlarıyla aynı tabloda gösterilmez.

## Sentetik set, sürüm 0.3

| Sistem | Sağlayıcı | G1 duyarlılık | G1 özgüllük | G1 belirsiz | G2 halüsinasyon | G2 span örtüşme | G3 tam eşleşme | G4 F1 | G5 F1 | G6 kapsama | Süre / örnek |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SmartClinical kural tabanlı taban çizgisi v1.4.2 | kural, CPU | 0,750 | 0,875 | 0,278 | 0,000 | 0,270 | 0,938 | 0,962 | 0,971 | 0,575 | ~10 ms |
| ebm-klinik-tr (hedef, Faz 2 sonu) | BDM, GPU | ≥ 0,90 | ≥ 0,90 | ≤ 0,10 | ≤ 0,02 | ≥ 0,70 | ≥ 0,85 | ≥ 0,98 | ≥ 0,95 | ≥ 0,85 | ≤ 2 s |

Okuma notları:

- G1'de kural tabanlı yolun belirsiz oranı yüksektir (%27,8); bu, karar verememe
  durumunda güvenli tarafta kalma tasarımının sonucudur ve BDM ile düşürülmesi beklenir.
- G2'de halüsinasyon sıfırdır çünkü kural tabanlı yol yalnızca kaynaktan cümle döndürür;
  buna karşılık span örtüşmesi düşüktür (tüm cümle döner, klinisyenin işaretlediği kısa
  aralık değil). BDM hedefi kısa ve doğru aralık döndürmektir.
- G3 ve G5 sözlük tabanlı yolun güçlü olduğu görevlerdir; gerçek protokol metinlerinde
  sözlük dışı ifadeler nedeniyle düşüş beklenir.
- G6 kapsama değeri kural tabanlı cümle seçiminin sınırını gösterir; özetleme BDM görevidir.

## Gerçek rapor seti

Henüz yayımlanmadı. Etik kurul ve KVKK onayları sonrası, kimliksizleştirilmiş sürüm
üzerinde iki etiketleyici + hakem kuralıyla oluşturulacak; κ değerleri ile birlikte
burada raporlanacaktır.
