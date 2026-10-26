# RA-001 Risk Analizi (FMEA)

| | |
|---|---|
| Belge No | RA-001 |
| Sistem | EBM SmartClinical |
| Hazırlayan | Validasyon Sorumlusu |
| Katılımcılar | Yazılım Geliştirme Yöneticisi, Klinik Operasyon Direktörü, Tıbbi Direktör, Veri Yönetimi Sorumlusu, Bilgi Güvenliği Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Yöntem

GAMP 5 Ek M3'e uygun fonksiyonel risk değerlendirmesi. Her hata modu için:

- **Ş** Şiddet (1 ihmal edilebilir … 5 hasta güvenliği / veri bütünlüğü kaybı)
- **O** Oluşma olasılığı (1 çok düşük … 5 sık)
- **T** Tespit edilebilirlik (1 kesin tespit … 5 tespit edilemez)
- **RÖS** = Ş × O × T. RÖS ≥ 40 ya da Ş = 5 ve T ≥ 3 → ek kontrol zorunlu, OQ'da olumsuz senaryo testi.

Kontroller uygulandıktan sonra artık RÖS hesaplanır. "Kontrol" sütunundaki her önlem kodda
vardır (FRS-001); "Test" sütunu OQ-001 senaryosu ve TM-001 üzerinden otomatik teste izlenir.

## 2. FMEA tablosu

| No | Fonksiyon | Hata modu | Etki | Ş | O | T | RÖS | Kontrol / azaltma | Ş' | O' | T' | RÖS' | Test |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R-01 | Eşleştirme motoru | Yanlış pozitif: uygun olmayan hasta "uygun" önerilir | Gereksiz tarama; hariç kriterinin atlanması halinde güvenlik riski | 4 | 3 | 2 | 24 | Öneri hiçbir kaydı değiştirmez; araştırmacı onayı zorunlu (FRS-37); her kriter için kanıt gösterimi; hariç kriter ihlali anında "uygun değil" | 4 | 2 | 1 | 8 | OQ-21, OQ-23, PQ |
| R-02 | Eşleştirme motoru | Yanlış negatif: uygun hasta gözden kaçar | Kazanım kaybı; hasta tedaviye erişemez | 3 | 3 | 4 | 36 | Belirsiz sonuçlar listelenir ve insan incelemesine düşer; altın standartta duyarlılık ≥ %90; gölge modda manuel taramayla karşılaştırma | 3 | 2 | 2 | 12 | OQ-22, PQ-M1 |
| R-03 | BDM kanıt çıkarma | Halüsinasyon: metinde olmayan kanıt cümlesi üretilir | Yanlış karara güven; dayanaksız tarama | 4 | 3 | 3 | 36 | Kanıt cümlesi kaynakta birebir doğrulanır, yoksa reddedilir (FRS-36); sıcaklık 0 | 4 | 1 | 1 | 4 | OQ-24, OQ-25 |
| R-04 | BDM | Model güveni düşükken kesin sonuç verir | Hatalı karar | 3 | 3 | 3 | 27 | Güven eşiği altı → belirsiz (FRS-43) | 3 | 2 | 2 | 12 | OQ-24 |
| R-05 | BDM | Model sürümü değişince davranış değişir, eski sonuçlar izlenemez | Tutarsız kararlar, denetimde açıklanamama | 3 | 3 | 3 | 27 | Model sürümü her sonuçla kaydedilir (FRS-45); model değişikliği değişiklik kontrolü + yeniden değerlendirme (VAL-001 §6) | 3 | 2 | 1 | 6 | OQ-25 |
| R-06 | BDM | Servis erişilemez; eşleştirme durur | Operasyon kesintisi | 2 | 3 | 1 | 6 | Kural tabanlı fallback + arayüz rozeti + log (FRS-44) | 2 | 3 | 1 | 6 | OQ-26 |
| R-07 | BDM / veri | Kimlik verisi istem yoluyla model servisine gider | KVKK ihlali | 4 | 2 | 3 | 24 | Kimliksizleştirme zorunlu (FRS-48); istem PHI kontrolü (FRS-46); uygulama ağı internal | 4 | 1 | 1 | 4 | OQ-27, OQ-28, IQ-10 |
| R-08 | Kimliksizleştirme | Ad/soyad veya TCKN tespit edilemez (kaçak) | Kimlik verisi sistemde kalır | 5 | 3 | 3 | 45 | Çok katmanlı tespit (sözlük + unvan + kalıp + checksum); ikinci geçiş doğrulama (FRS-49); yükleme sonucunda reddedilen satırların gözden geçirilmesi | 5 | 1 | 2 | 10 | OQ-28, OQ-29, PQ-M10 |
| R-09 | Kimliksizleştirme | Klinik terim yanlışlıkla maskelenir | Eşleştirme kalitesi düşer | 2 | 3 | 2 | 12 | Klinik terim listesi (`sozluk.py`) | 2 | 2 | 2 | 8 | OQ-29 |
| R-10 | HBYS entegrasyonu | Kimlik alanları FHIR kaynağından okunur | KVKK ihlali | 5 | 2 | 2 | 20 | Eşleme kodu bu alanları hiç okumaz (FRS-50); otomatik test | 5 | 1 | 1 | 5 | OQ-30 |
| R-11 | HBYS entegrasyonu | Takma ad çakışması ya da geri çözülmesi | Yanlış eşleştirme / yeniden kimliklendirme | 4 | 1 | 3 | 12 | HMAC-SHA256 + merkez bağlamı; anahtar kasada; yeniden anahtarlama betiği | 4 | 1 | 2 | 8 | OQ-30 |
| R-12 | Merkez zekâsı | Az veride aşırı güvenli tahmin | Yanlış merkez seçimi | 2 | 4 | 3 | 24 | Hiyerarşik model büzülmesi; güven aralığı ve açıklama; "öncül" etiketi; MAPE izlemi | 2 | 2 | 2 | 8 | OQ-31, PQ-M7 |
| R-13 | RBM | KRI yanlış hesaplanır (payda hatası) | Yanlış uyarı ya da uyarı kaçırma | 3 | 2 | 2 | 12 | Her gösterge için birim testi; aday merkez ve az veri hesaba girmez | 3 | 1 | 1 | 3 | OQ-15, OQ-16 |
| R-14 | RBM | Uyarı yorgunluğu | Gerçek uyarılar gözden kaçar | 3 | 3 | 3 | 27 | Açık uyarı tekilleştirme; otomatik kapanış; eşikler çalışma bazında | 3 | 2 | 2 | 12 | OQ-17, PQ-M9 |
| R-15 | Güvenlik | SAE bildirim süresi yanlış hesaplanır | Mevzuat ihlali | 5 | 2 | 2 | 20 | Kural birim testi (7/15 gün); gece işi sayımı; panelde geri sayım | 5 | 1 | 1 | 5 | OQ-12, OQ-13 |
| R-16 | Güvenlik | SUSAR tespiti atlanır | Hızlandırılmış bildirim yapılmaz | 5 | 2 | 2 | 20 | Türetilmiş alan; beklenirlik ve nedensellik zorunlu | 5 | 1 | 1 | 5 | OQ-13 |
| R-17 | EDC | Veri değişikliği denetim izine yazılmaz | Veri bütünlüğü kaybı | 5 | 2 | 3 | 30 | Her yazan rota `denetim.kaydet` çağırır; kural kod incelemesinde zorunlu (docs/gelistirme.md); aynı transaction içinde yazılır | 5 | 1 | 2 | 10 | OQ-05 |
| R-18 | Denetim izi | Kayıtlar veritabanından değiştirilir/silinir ya da yeniden özetlenir | Veri bütünlüğü kaybı | 5 | 1 | 4 | 20 | DB tetikleyicisi + yetki kısıtı; HMAC zinciri (anahtar veritabanında değil); doğrulama betiği | 5 | 1 | 1 | 5 | OQ-07, IQ-9 |
| R-19 | Denetim izi | Eşzamanlı yazımlar aynı önceki özeti alır | Zincir bozulur, sahte alarm | 3 | 3 | 2 | 18 | Zincir ucu satırı kilitlenir (FOR UPDATE / BEGIN IMMEDIATE) | 3 | 1 | 1 | 3 | OQ-06 |
| R-20 | E-imza | İmza sonrası kayıt değişir, imza geçerli görünür | Sahte onay | 5 | 2 | 3 | 30 | İçerik özeti karşılaştırması; "imza yenilenmeli"; toplu kilit bu kayıtları atlar; onaylı rapor değiştirilemez | 5 | 1 | 1 | 5 | OQ-08, OQ-09 |
| R-21 | E-imza | Başkasının oturumunda imza atılır | Kimlik sahteciliği | 5 | 2 | 3 | 30 | İmza anında parola; oturum süresi ≤ 30 dk; kilit | 5 | 1 | 2 | 10 | OQ-08 |
| R-22 | Yetki | Merkez kullanıcısı başka merkezin verisini görür | Gizlilik ihlali | 4 | 2 | 3 | 24 | Servis katmanında merkez filtresi (`gonullu_erisimi`, `_gorunur_cm`); olumsuz testler | 4 | 1 | 1 | 4 | OQ-02 |
| R-23 | Yetki | Sponsor kullanıcısı gönüllü/hasta verisine erişir | Amaç dışı erişim | 4 | 2 | 2 | 16 | Sponsor kurum filtresi; gönüllü ve veri sekmeleri kapalı; CSV uçları 403 | 4 | 1 | 1 | 4 | OQ-03, OQ-32 |
| R-24 | Vizit / EDC | Vizit penceresi yanlış hesaplanır | Sapma kaçırılır | 3 | 2 | 2 | 12 | Birim testi; şema tanımı | 3 | 1 | 1 | 3 | OQ-11 |
| R-25 | Altyapı | Yedek alınmaz / geri yüklenemez / yedek dosyası sızar | Veri kaybı, gizlilik ihlali | 5 | 2 | 2 | 20 | Günlük `age` şifreli yedek, özet dosyası, üç aylık geri yükleme provası | 5 | 1 | 1 | 5 | IQ-7 |
| R-26 | Altyapı | Zaman damgası yanlış (NTP yok) | Denetim izi güvenilmez | 4 | 2 | 3 | 24 | NTP kurulum ön koşulu | 4 | 1 | 1 | 4 | IQ-4 |
| R-27 | Altyapı | TLS zayıf; sürüm/ortam bilgisi anonim sızar | Veri dinlenir; saldırı yüzeyi | 4 | 2 | 2 | 16 | Sertleştirilmiş nginx; `/saglik` yalnızca durum; API belgeleri oturumlu; internal ağ | 4 | 1 | 1 | 4 | IQ-6, IQ-10, IQ-14 |
| R-28 | Kriter yapılandırma | Kriter yanlış yapılandırılır (ör. ≥ yerine >) | Sistematik yanlış eşleştirme | 4 | 3 | 2 | 24 | Yapı kullanıcıya gösterilir, onay zorunlu (FRS-04); onaysız kriter eşleştirmede kullanılmaz | 4 | 2 | 1 | 8 | OQ-19 |
| R-29 | Çalışma yaşam döngüsü | Etik onayı olmadan kayıt aşamasına geçilir | GCP ihlali | 5 | 2 | 2 | 20 | Kontrol listesi eksik gösterir; aşama değişimi gerekçeli ve denetim izinde; karar PY'de | 5 | 1 | 2 | 10 | OQ-01 |
| R-30 | TMF | Eski sürüm belge güncel sanılır; dosya diskte değiştirilir | Yanlış belgeyle çalışma | 4 | 2 | 3 | 24 | Sürüm zinciri ve "eskimiş" durumu; indirmede SHA-256 doğrulama; indirme denetim izinde | 4 | 1 | 1 | 4 | OQ-33 |
| R-31 | Veri yönetimi | Açık sorgulu ya da imzasız kayıt kilitlenir | Kilit sonrası değişiklik gereksinimi | 4 | 3 | 2 | 24 | Toplu kilit ön kontrolü (açık sorgu, SDV, PI imzası, taslak); geçemeyenler raporlanır | 4 | 1 | 1 | 4 | OQ-05 |
| R-32 | Hasta havuzu | Saklama süresi aşılır / veri sahibi talebi uygulanamaz | KVKK ihlali | 4 | 3 | 3 | 36 | Saklama betiği (kuru çalışma + gerçek), tekil silme/kısıtlama; denetim izinde | 4 | 1 | 1 | 4 | OQ-35 |
| R-33 | Kullanıcı | Yapay zekâ önerisine aşırı güven (otomasyon yanlılığı) | Kritik inceleme atlanır | 3 | 3 | 4 | 36 | Arayüzde "öneri" vurgusu, kanıtın her kriterde zorunlu görüntülenmesi; gölge mod kabul oranı izlemi | 3 | 2 | 2 | 12 | PQ-M11 |

## 3. Sonuç

Kontroller sonrası RÖS ≥ 40 kalan hata modu yoktur. Ş = 5 olan tüm modlar için T' ≤ 2
sağlanmıştır. En yüksek artık riskler R-02 (yanlış negatif), R-17 (denetim izi çağrısının
kodda unutulması) ve R-33 (otomasyon yanlılığı) olup kod incelemesi, PQ gölge mod sonuçları ve
kullanıcı davranışı izlemiyle takip edilir.

## 4. Onaylar

| Rol | İmza |
|---|---|
| Validasyon Sorumlusu | |
| Tıbbi Direktör | |
| Kalite Güvence Yöneticisi | |
