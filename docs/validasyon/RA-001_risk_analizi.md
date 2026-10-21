# RA-001 Risk Analizi (FMEA)

| | |
|---|---|
| Belge No | RA-001 |
| Sistem | EBM SmartClinical v1.4 |
| Sürüm | 2.0 |
| Yürürlük tarihi | 2026-03-10 |
| Hazırlayan | Validasyon Sorumlusu |
| Katılımcılar | Yazılım Geliştirme Yöneticisi, Klinik Operasyon Direktörü, Tıbbi Direktör, Veri Yönetimi Sorumlusu, Bilgi Güvenliği Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## Revizyon geçmişi

| Sürüm | Tarih | Açıklama |
|---|---|---|
| 1.0 | 2025-04-09 | İlk analiz (v1.2) |
| 1.1 | 2025-09-05 | RBM ve e-imza riskleri |
| 2.0 | 2026-03-10 | Yapay zekâ bileşenleri (yanlış pozitif/negatif, halüsinasyon, model kayması), kimliksizleştirme ve HBYS entegrasyonu riskleri eklendi |

## 1. Yöntem

GAMP 5 Ek M3'e uygun fonksiyonel risk değerlendirmesi. Her hata modu için:

- **Ş** Şiddet (1 ihmal edilebilir … 5 hasta güvenliği / veri bütünlüğü kaybı)
- **O** Oluşma olasılığı (1 çok düşük … 5 sık)
- **T** Tespit edilebilirlik (1 kesin tespit … 5 tespit edilemez)
- **RÖS** = Ş × O × T. RÖS ≥ 40 ya da Ş = 5 ve T ≥ 3 → ek kontrol zorunlu, OQ'da olumsuz senaryo testi.

Kontroller uygulandıktan sonra artık RÖS hesaplanır.

## 2. FMEA tablosu

| No | Fonksiyon | Hata modu | Etki | Ş | O | T | RÖS | Kontrol / azaltma | Ş' | O' | T' | RÖS' | Test |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R-01 | Eşleştirme motoru | Yanlış pozitif: uygun olmayan hasta "uygun" önerilir | Gereksiz tarama, hariç kriterinin atlanması halinde güvenlik riski | 4 | 3 | 2 | 24 | Öneri hiçbir kaydı değiştirmez; araştırmacı onayı zorunlu (FRS-37); her kriter için kanıt gösterimi; hariç kriter ihlali anında "uygun değil" | 4 | 2 | 1 | 8 | OQ-20, OQ-21, PQ |
| R-02 | Eşleştirme motoru | Yanlış negatif: uygun hasta gözden kaçar | Kazanım kaybı; hasta tedaviye erişemez | 3 | 3 | 4 | 36 | Belirsiz sonuçlar listelenir ve insan incelemesine düşer; duyarlılık hedefi ≥ %90 altın standartta; gölge modda manuel taramayla karşılaştırma; "olası" sınıfı için düşük eşik | 3 | 2 | 2 | 12 | OQ-22, PQ |
| R-03 | BDM kanıt çıkarma | Halüsinasyon: metinde olmayan kanıt cümlesi üretilir | Yanlış karara güven; GCP açısından dayanaksız tarama | 4 | 3 | 3 | 36 | Kanıt cümlesi kaynakta birebir doğrulanır, yoksa reddedilir (FRS-36); sıcaklık 0; altın standartta halüsinasyon ≤ %2 | 4 | 1 | 1 | 4 | OQ-23, OQ-24 |
| R-04 | BDM | Model güveni düşükken kesin sonuç verir | Hatalı karar | 3 | 3 | 3 | 27 | Güven eşiği (0,70) altı → belirsiz; kalibrasyon ölçümü (ECE) sürüm kabulünde | 3 | 2 | 2 | 12 | OQ-24 |
| R-05 | BDM | Model sürümü değişince davranış değişir (model kayması), eski sonuçlar izlenemez | Tutarsız kararlar, denetimde açıklanamama | 3 | 3 | 3 | 27 | Model sürümü her sonuçla kaydedilir (FRS-45); model değişikliği değişiklik kontrolü + yeniden değerlendirme (VAL-001 §6) | 3 | 2 | 1 | 6 | OQ-25 |
| R-06 | BDM | Servis erişilemez; eşleştirme durur | Operasyon kesintisi | 2 | 3 | 1 | 6 | Kural tabanlı fallback + arayüz rozeti + log (FRS-44) | 2 | 3 | 1 | 6 | OQ-26 |
| R-07 | BDM / veri | Kimlik verisi istem yoluyla model servisine gider | KVKK ihlali (hastane içi olsa da amaç dışı işleme) | 4 | 2 | 3 | 24 | Kimliksizleştirme zorunlu (FRS-48); istem PHI kontrolü (FRS-46); model dış ağa kapalı | 4 | 1 | 1 | 4 | OQ-27, OQ-28 |
| R-08 | Kimliksizleştirme | Ad/soyad veya TCKN tespit edilemez (kaçak) | Kimlik verisi sistemde kalır | 5 | 3 | 3 | 45 | Çok katmanlı tespit (sözlük + unvan + kalıp + checksum); ikinci geçiş doğrulama (FRS-49); aylık rastgele örneklem elle denetimi; test seti kaçak oranı ≤ %1 | 5 | 1 | 2 | 10 | OQ-28, OQ-29 |
| R-09 | Kimliksizleştirme | Klinik terim yanlışlıkla maskelenir (aşırı maskeleme) | Eşleştirme kalitesi düşer | 2 | 3 | 2 | 12 | Klinik terim beyaz listesi; etiketli sette aşırı maskeleme oranı ölçümü | 2 | 2 | 2 | 8 | OQ-29 |
| R-10 | HBYS entegrasyonu | Kimlik alanları FHIR kaynağından okunur | KVKK ihlali | 5 | 2 | 2 | 20 | Eşleme kodu bu alanları hiç okumaz (FRS-50); kod incelemesi; entegrasyon testi | 5 | 1 | 1 | 5 | OQ-30 |
| R-11 | HBYS entegrasyonu | Yanlış hastanın verisi eşlenir (takma ad çakışması) | Yanlış eşleştirme | 4 | 1 | 3 | 12 | SHA-256 + kurum tuzu; çakışma kontrolü senkronda | 4 | 1 | 2 | 8 | OQ-30 |
| R-12 | Merkez zekâsı | Az veride aşırı güvenli tahmin | Yanlış merkez seçimi, planlama hatası | 2 | 4 | 3 | 24 | Hiyerarşik model büzülmesi; güven aralığı ve veri miktarı açıklamada; "öncül" etiketi; MAPE izlemi | 2 | 2 | 2 | 8 | OQ-31, PQ |
| R-13 | RBM | KRI yanlış hesaplanır (payda hatası, sıfır bölme) | Yanlış uyarı ya da uyarı kaçırma | 3 | 2 | 2 | 12 | Birim testleri her gösterge için; n küçükse hesaplama yapılmaz ("yetersiz veri") | 3 | 1 | 1 | 3 | OQ-15, OQ-16 |
| R-14 | RBM | Uyarı yorgunluğu: çok sayıda düşük değerli uyarı | Gerçek uyarılar gözden kaçar | 3 | 3 | 3 | 27 | Açık uyarı tekilleştirme; eşikler çalışma bazında; aylık yanlış alarm oranı izlemi | 3 | 2 | 2 | 12 | OQ-17 |
| R-15 | Güvenlik | SAE bildirim süresi yanlış hesaplanır | Mevzuat ihlali, hasta güvenliği sinyali gecikir | 5 | 2 | 2 | 20 | Kural birim testi (7/15 gün); farkındalık tarihi zorunlu; panelde geri sayım | 5 | 1 | 1 | 5 | OQ-12, OQ-13 |
| R-16 | Güvenlik | SUSAR tespiti atlanır | Hızlandırılmış bildirim yapılmaz | 5 | 2 | 2 | 20 | Türetilmiş alan; beklenirlik ve nedensellik zorunlu | 5 | 1 | 1 | 5 | OQ-13 |
| R-17 | EDC | Veri değişikliği denetim izine yazılmaz | Veri bütünlüğü kaybı (ALCOA+) | 5 | 2 | 3 | 30 | ORM olay dinleyicisi tüm modellerde; denetim izi yazılamazsa işlem geri alınır (aynı transaction) | 5 | 1 | 1 | 5 | OQ-05, OQ-06 |
| R-18 | Denetim izi | Kayıtlar veritabanından değiştirilir/silinir | Veri bütünlüğü kaybı | 5 | 1 | 4 | 20 | DB tetikleyicisi + yetki kısıtı; zincir özeti doğrulama betiği | 5 | 1 | 1 | 5 | OQ-07, IQ-9 |
| R-19 | E-imza | İmza sonrası kayıt değişir, imza geçerli görünür | Sahte onay | 5 | 2 | 3 | 30 | İçerik özeti karşılaştırması; "imza geçersiz" rozeti; yeniden imza zorunlu | 5 | 1 | 1 | 5 | OQ-09 |
| R-20 | E-imza | Başkasının oturumunda imza atılır | Kimlik sahteciliği | 5 | 2 | 3 | 30 | İmza anında parola; oturum süresi 20–30 dk; kilit | 5 | 1 | 2 | 10 | OQ-08 |
| R-21 | Yetki | Merkez kullanıcısı başka merkezin verisini görür | Gizlilik ihlali | 4 | 2 | 3 | 24 | Sorgu düzeyinde merkez filtresi (servis katmanı), arayüzde değil; olumsuz testler | 4 | 1 | 1 | 4 | OQ-02, OQ-03 |
| R-22 | Yetki | Sponsor kullanıcısı hasta serbest metnine erişir | Amaç dışı erişim | 4 | 2 | 2 | 16 | Rol bazlı alan maskeleme API ve arayüzde | 4 | 1 | 1 | 4 | OQ-03 |
| R-23 | Vizit / EDC | Vizit penceresi yanlış hesaplanır | Sapma kaçırılır | 3 | 2 | 2 | 12 | Birim testi; protokol şablonu doğrulama | 3 | 1 | 1 | 3 | OQ-11 |
| R-24 | Altyapı | Yedek alınmaz / geri yüklenemez | Veri kaybı | 5 | 2 | 2 | 20 | Günlük yedek, özet dosyası, üç aylık geri yükleme provası | 5 | 1 | 1 | 5 | IQ-7 |
| R-25 | Altyapı | Zaman damgası yanlış (NTP yok) | Denetim izi güvenilmez | 4 | 2 | 3 | 24 | NTP kurulum ön koşulu; sunucu saat kayması izlemi | 4 | 1 | 1 | 4 | IQ-4 |
| R-26 | Altyapı | TLS yapılandırması zayıf | Veri dinlenir | 4 | 2 | 2 | 16 | Sertleştirilmiş nginx yapılandırması; yıllık sızma testi | 4 | 1 | 1 | 4 | IQ-6 |
| R-27 | Kriter yapılandırma | Kriter yanlış yapılandırılır (ör. ≥ yerine >) | Sistematik yanlış eşleştirme | 4 | 3 | 2 | 24 | Yapı kullanıcıya gösterilir, onay zorunlu (FRS-04); onaylanmamış kriterle eşleştirme "taslak" etiketli | 4 | 2 | 1 | 8 | OQ-19 |
| R-28 | Çalışma yaşam döngüsü | Etik onayı olmadan kayıt aşamasına geçilir | GCP ihlali | 5 | 2 | 2 | 20 | Aşama geçiş ön koşulları (FRS-02) | 5 | 1 | 1 | 5 | OQ-01 |
| R-29 | Performans | BDM çağrıları arayüzü kilitler | Kullanılabilirlik | 2 | 3 | 1 | 6 | Arka plan iş kuyruğu; ilerleme göstergesi | 2 | 2 | 1 | 4 | OQ-32 |
| R-30 | Kullanıcı | Kullanıcı yapay zekâ önerisine aşırı güvenir (otomasyon yanlılığı) | Kritik inceleme atlanır | 3 | 3 | 4 | 36 | Arayüzde "öneri" vurgusu, kanıtın her kriterde zorunlu görüntülenmesi, onay öncesi kriter listesi; eğitim (SOP-EG-05); gölge mod kabul oranı izlemi | 3 | 2 | 2 | 12 | PQ anketi |

## 3. Sonuç

Kontroller sonrası RÖS ≥ 40 kalan hata modu yoktur. Ş = 5 olan tüm modlar için T' ≤ 2
sağlanmıştır. Yapay zekâ bileşenlerine ilişkin en yüksek artık riskler R-02 (yanlış
negatif) ve R-30 (otomasyon yanlılığı) olup PQ gölge mod sonuçları ve kullanıcı
davranışı izlemiyle takip edilir; sonuçlar yıllık periyodik gözden geçirmede
değerlendirilir.

## 4. Onaylar

| Rol | İmza | Tarih |
|---|---|---|
| Validasyon Sorumlusu | e-imza | 2026-03-06 |
| Tıbbi Direktör | e-imza | 2026-03-09 |
| Kalite Güvence Yöneticisi | e-imza | 2026-03-10 |
