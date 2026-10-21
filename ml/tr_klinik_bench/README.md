# TR-KlinikBench

Türkçe Klinik Araştırma NLP Değerlendirme Seti, sürüm 0.3 (taslak)

TR-KlinikBench, klinik araştırma operasyonlarında kullanılan Türkçe dil modellerini ve
kural tabanlı sistemleri karşılaştırmak için hazırlanan görev tabanlı bir değerlendirme
setidir. EBM SmartClinical içindeki Türkçe Klinik BDM'nin geliştirme sürecinde iç
değerlendirme aracı olarak doğmuş; proje sonunda kimliksizleştirilmiş ve sentetik
bileşenleriyle açık olarak yayımlanması planlanmıştır. Amaç, Türkçe klinik metin işleme
alanında ortak bir ölçüm zemini oluşturmak ve farklı kurumların geliştirdiği modellerin
aynı sorular üzerinde karşılaştırılabilmesini sağlamaktır.

Bu dizindeki veri **tamamen sentetiktir**; gerçek hasta kaydı içermez. Gerçek rapor
örneklemleriyle genişletilmiş sürüm, etik kurul ve KVKK onayları tamamlandıktan sonra
yalnızca kimliksizleştirilmiş biçimde ve erişim sözleşmesiyle dağıtılacaktır (bkz.
`ml/VERI_KARTI.md`).

## Görevler

| Kod | Görev | Girdi | Beklenen çıktı | Ana metrik |
|---|---|---|---|---|
| G1 | Kriter–hasta eşleştirme | kriter metni, kriter tipi, hasta metni | `saglandi` / `saglanmadi` / `belirsiz` | duyarlılık, özgüllük, makro F1, belirsiz oranı |
| G2 | Kanıt çıkarma | kriter metni, hasta metni | karara dayanak kaynak cümle | halüsinasyon oranı, kanıt-span Jaccard örtüşmesi |
| G3 | Kriter yapılandırma | kriter metni | hesaplanabilir sorgu (JSON) | tam eşleşme, alan bazlı eşleşme |
| G4 | Kimliksizleştirme | serbest metin | tespit edilen kimlik varlığı türleri | varlık türü bazında duyarlılık, kesinlik, F1 |
| G5 | ICD-10 kodlama | tanı ifadeleri içeren metin | ICD-10 ön ekleri | mikro duyarlılık, kesinlik, F1 |
| G6 | Çalışma odaklı özet | epikriz metni | 3–6 maddelik özet | anahtar bilgi kapsama oranı, madde sayısı uyumu |

G1 ve G2 aynı kayıt yapısını paylaşır; G2 yalnızca `kanit_span` alanı dolu kayıtlarda
puanlanır. Sistemler G1'de "belirsiz" diyerek yanlış karardan kaçınabilir; bu nedenle
belirsiz oranı ayrıca raporlanır ve skor tablosunda duyarlılığın yanında gösterilir.

## Veri biçimi

Her görev için bir JSONL dosyası (`veri/gN_*.jsonl`) ve bir JSON Schema (`sema/gN_*.schema.json`)
bulunur. Kayıtlar şemaya göre doğrulanır; şema dışı kayıt kabul edilmez. Ortak alanlar:

- `id`: görev kodu ile başlayan benzersiz kimlik (`G1-0001`).
- `etiketleyen`, `ikinci_etiketleyen`, `ikinci_etiket`, `uyum`, `hakem_karari`: etiketleme
  sürecinin izi. Sentetik örneklerde etiketleyen kodu `S` (şablon) ile başlar.
- `zorluk`: `kolay` / `orta` / `zor`; model sonuçları zorluğa göre kırılır.
- `notlar`: serbest metin.

Kanıt aralıkları (`kanit_span`) karakter ofsetiyle verilir (`baslangic` dahil, `bitis` hariç)
ve `metin` alanı aralığın birebir kopyasını taşır; yükleme sırasında ikisi karşılaştırılır.

## Etiketleme kuralları

1. Her kayıt birbirinden bağımsız iki etiketleyici tarafından etiketlenir. Etiketleyiciler
   klinik araştırma deneyimi olan hekim veya çalışma koordinatörüdür.
2. Uyuşmazlıkta üçüncü bir hakem karar verir; `hakem_karari` alanı dolar ve puanlamada
   bu alan esas alınır.
3. Her sürümde etiketleyiciler arası uyum Cohen κ ile raporlanır; κ < 0,70 olan görev
   setleri yayımlanmaz, kılavuz gözden geçirilir.
4. Etiketleme kılavuzu `ml/veri_hazirlama/etiketleme_kilavuzu.md` dosyasındadır; kılavuz
   değişiklikleri sürüm notuna yazılır ve etkilenen kayıtlar yeniden etiketlenir.

## Metrikler

Metrik fonksiyonları `ml/degerlendirme/metrikler.py` içindedir ve dış bağımlılık içermez.
Puanlama `calistir.py` ile yapılır:

```bash
python -m ml.tr_klinik_bench.calistir --gorevler g1,g2,g3,g4,g5,g6 --saglayici kural
python -m ml.tr_klinik_bench.calistir --gorevler g1,g2 --saglayici vllm --model ebm-klinik-tr-7b-q4
```

Çıktılar `ml/ciktilar/bench_<tarih>.json` ve aynı adlı `.md` dosyasına yazılır. Skor tablosuna
girecek bir sonuç için `--etiket` ile sistem adı verilir.

## Skor tablosu politikası

- Skor tablosu (`skor_tablosu.md`) yalnızca bu dizindeki `calistir.py` ile üretilmiş ve
  çıktı JSON'u eklenmiş sonuçları kabul eder.
- Değerlendirme seti eğitimde kullanılamaz; gönderen kurum bunu beyan eder. Veri
  sızıntısı tespitinde sonuç tablodan kaldırılır.
- Her satırda sistem adı, sürüm, sağlayıcı türü (kural / BDM / hibrit), donanım ve örnek
  başına ortalama süre bulunur.
- Sentetik set ile gerçek set sonuçları ayrı tablolarda tutulur; karıştırılmaz.

## Sürümleme ve lisans

Set sürümleri anlamsal numara taşır (`0.3`, `1.0`). Kayıt ekleme ve kılavuz değişikliği
minör, görev tanımı değişikliği majör sürüm artışıdır. Yayım lisansı olarak
CC BY-NC-SA 4.0 planlanmaktadır; ticari kullanım talepleri EBM ile ayrıca görüşülür.
Katkı için: yeni kayıtlar şemaya uygun JSONL olarak, iki etiketleyici imzasıyla gönderilir.

## Etik ve KVKK ilkeleri

- Gerçek hasta metni yalnızca etik kurul onayı ve KVKK uyum değerlendirmesi tamamlanmış
  kaynaklardan, kimliksizleştirme ve ikinci geçiş doğrulamasından sonra sete alınır.
- Sentetik kayıtlar gerçek kişi, kurum veya olay tanımlamaz; kimlik verisi içeren G4
  kayıtlarındaki tüm değerler uydurmadır (TC kimlik numaraları algoritma geçerli ama
  gerçek olmayan sayılardır).
- Set, modellerin hasta grupları arasında farklı davranıp davranmadığının ölçülebilmesi
  için cinsiyet, yaş grubu ve endikasyon alanlarında dengeli tutulmaya çalışılır; alt grup
  kırılımı skor tablosunda isteğe bağlı sütundur.
