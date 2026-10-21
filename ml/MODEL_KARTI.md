# Model kartı: ebm-klinik-tr

Sürüm: 0.2 (kavram kanıtı) · Son güncelleme: 21.10.2026 · Sorumlu: EBM Yazılım ve Veri Bilimi Ekibi

## Özet

ebm-klinik-tr, EBM SmartClinical platformunda klinik araştırma görevleri için kullanılmak
üzere geliştirilen Türkçe klinik büyük dil modelidir. Açık kaynak 7–8 milyar parametreli bir
temel modelin Türkçe tıbbi derlemle sürekli ön eğitimi ve klinik araştırma görevlerinde
talimat ince ayarı (LoRA/QLoRA) ile elde edilmesi planlanmıştır. Bu kart, modelin mevcut
durumunu ve amaçlanan kullanımını tanımlar; model ağırlıkları henüz yayımlanmamıştır.

Mevcut durum: laboratuvar ortamında, sentetik talimat seti ile yapılmış kavram kanıtı
denemeleri. Üretimdeki SmartClinical kurulumları, BDM sunucusu bağlanana kadar kural
tabanlı ayrıştırıcı ve kalıp tabanlı metin değerlendirmesiyle çalışır; bu kartta
raporlanan ölçümler o taban çizgisine aittir.

## Amaçlanan kullanım

- Protokol dahil etme / hariç tutma kriterlerinin hesaplanabilir sorguya dönüştürülmesi.
- Kimliksizleştirilmiş hasta metninden bir kriter için kanıt cümlesi ve karar çıkarılması.
- Çalışma odaklı klinik özet ve bağlam üzerinden soru-cevap.
- Serbest metinde tanı ifadeleri için ICD-10 kodlama önerisi.

Kullanıcılar klinik araştırma uzmanları, araştırmacılar ve çalışma koordinatörleridir. Model
çıktısı her zaman kaynak cümleyle birlikte sunulur ve bir insan kararına girdi oluşturur.

## Kullanım dışı

- Tanı, tedavi veya hasta yönetimi kararı vermek.
- Araştırmacı onayı olmadan hastayı bir çalışmaya dahil etmek veya hariç tutmak.
- Kimliksizleştirilmemiş metin üzerinde çalıştırmak (koruma katmanı kimlik kalıbı tespit
  ederse isteği engeller).
- Türkçe dışındaki dillerde klinik metin işleme; İngilizce protokol kriterleri sınırlı
  olarak desteklenir.
- Hasta ile doğrudan etkileşim.

## Eğitim verisi (planlanan)

| Kaynak | Tür | Durum |
|---|---|---|
| Pilot hastane epikriz, patoloji ve radyoloji raporları | kimliksizleştirilmiş serbest metin | etik/KVKK onayı bekleniyor (Faz 1) |
| Türkçe klinik kılavuzlar, tanı-tedavi rehberleri | kamuya açık metin | derleme sürüyor |
| EBM protokol ve çalışma belgeleri | kurum içi metin | kimliksizleştirme sonrası |
| Sentetik talimat seti | şablon ve altın standart türevi | mevcut (ml/veri_hazirlama) |
| Altın standart etiketler | klinisyen etiketli çiftler | 28 sentetik; hedef 2.000 |

Ayrıntılar `ml/VERI_KARTI.md` dosyasındadır.

## Değerlendirme

TR-KlinikBench 0.3 (sentetik) üzerinde kural tabanlı taban çizgisi ve Ar-Ge programı Faz 2 sonu hedefleri:

| Görev | Metrik | Taban çizgisi (kural) | Hedef (ebm-klinik-tr) |
|---|---|---|---|
| G1 kriter–hasta eşleştirme | duyarlılık / özgüllük | 0,750 / 0,875 | ≥ 0,90 / ≥ 0,90 |
| G2 kanıt çıkarma | halüsinasyon oranı / span örtüşme | 0,000 / 0,270 | ≤ 0,02 / ≥ 0,70 |
| G3 kriter yapılandırma | tam eşleşme | 0,938 | ≥ 0,85 |
| G4 kimliksizleştirme | F1 | 0,962 | ≥ 0,98 (duyarlılık) |
| G5 ICD-10 kodlama | F1 | 0,971 | ≥ 0,95 |
| G6 çalışma odaklı özet | anahtar bilgi kapsama | 0,575 | ≥ 0,85 |

Sentetik set sonuçları gerçek rapor setine genellenemez; gerçek set sonuçları yayımlandığında
bu tablo ayrı bir sütunla güncellenecektir. Model sürümleri arasındaki karşılaştırma
`ml/tr_klinik_bench/skor_tablosu.md` dosyasında tutulur.

## Sınırlılıklar

- Türkçe tıbbi dilde kısaltma, kurum jargonu ve yazım varyasyonu yüksektir; sözlük dışı
  ifadelerde duyarlılık düşer.
- Zaman penceresi gerektiren kriterlerde ("son 6 ay içinde") tarih bilgisi metinde yoksa
  model belirsiz der; bu bir sınırlılık değil tasarım tercihidir, ancak belirsiz oranını artırır.
- Laboratuvar birim dönüşümleri sözlükle sınırlıdır; referans aralığı (ULN) gerektiren
  kriterler yapısal veri olmadan değerlendirilemez.
- Uzun belgelerde (6.000 karakter üstü) metin parçalanır; parçalar arası bağlam kaybı olabilir.
- Model, eğitim derleminin kurum ve bölge dağılımını yansıtır; az temsil edilen kurum
  tiplerinde (özel hastane, ilçe hastanesi) performans farkı beklenir.

## Önyargı ve adalet

TR-KlinikBench kayıtlarında cinsiyet, yaş grubu, endikasyon ve kurum tipi alanları alt grup
kırılımı için tutulur. Her model sürümünde G1 duyarlılığı en az cinsiyet ve yaş grubu
(< 40, 40–65, > 65) kırılımında raporlanır; gruplar arası fark 5 puanı aşarsa sürüm
yayımlanmaz ve veri dengesi gözden geçirilir. Mevcut sentetik set bu analiz için küçüktür;
kırılım gerçek set ile başlayacaktır. Gebelik ve emzirme kriterlerinde modelin yalnızca
cinsiyet ve yaşa dayanarak karar vermemesi (metinsel kanıt araması) koruma katmanında
kuraldır.

## Güvenlik önlemleri

- Kanıt cümlesi kaynakta birebir bulunmuyorsa çıktı reddedilir (halüsinasyon kontrolü).
- Güven eşiği altındaki sonuçlar belirsiz olarak işaretlenir; isteğe bağlı çoğunluk oyu.
- JSON şema doğrulaması; başarısızlıkta kural tabanlı yola düşüş ve denetim izi kaydı.
- İstemde kimlik verisi kalıbı tespitinde istek engellenir.
- Model yalnızca hastane ağı içinde çalışır; dış ağa istek göndermez.
- Tüm çağrılar kullanıcı, zaman, görev ve süre ile denetim izine yazılır.

## Sürüm geçmişi

| Sürüm | Tarih | Not |
|---|---|---|
| 0.1 | 2026-05 | Sentetik talimat setiyle ilk LoRA denemesi; yalnızca iç değerlendirme |
| 0.2 | 2026-10 | TR-KlinikBench 0.3 ile taban çizgisi; koruma katmanı ve kalıp tabanlı metin değerlendirmesi üretimde |
| 1.0 (plan) | Faz 2 sonu | Gerçek derlemle sürekli ön eğitim, nicemlenmiş hastane içi sürüm, gerçek set değerlendirmesi |
