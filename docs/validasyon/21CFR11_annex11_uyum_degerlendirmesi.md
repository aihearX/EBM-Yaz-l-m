# 21 CFR Part 11 ve EU GMP Annex 11 Uyum Değerlendirmesi

| | |
|---|---|
| Belge No | UYM-001 |
| Sistem | EBM SmartClinical v1.4.2 |
| Sürüm | 2.0 |
| Tarih | 2026-06-12 |
| Hazırlayan | Validasyon Sorumlusu, Bilgi Güvenliği Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

Durum kodları: **U** uyumlu, **UK** uyumlu (kısmen prosedürel kontrol ile), **UY** uygulanamaz, **A** açık (eylem planı var).

## 1. 21 CFR Part 11

### Subpart B – Elektronik kayıtlar

| Madde | Gereklilik | Sistem kontrolü | Durum |
|---|---|---|---|
| 11.10(a) | Sistem validasyonu | VAL-001 planı, IQ/OQ/PQ, değişiklik kontrolü | U |
| 11.10(b) | Doğru ve eksiksiz kopya üretimi (okunabilir ve elektronik) | Denetim izi ve eCRF CSV/PDF dışa aktarma; OMOP/SDTM dışa aktarma; dışa aktarma kaydı | U |
| 11.10(c) | Kayıtların saklama süresi boyunca korunması | PostgreSQL + günlük yedek, 7 yıl aylık arşiv; TMF arşiv prosedürü SOP-ARS-02 (25 yıl) | UK |
| 11.10(d) | Sistem erişiminin yetkili kişilerle sınırlanması | Rol bazlı yetki, merkez kapsaması, parola politikası, hesap kilidi | U |
| 11.10(e) | Güvenli, bilgisayar üretimli, zaman damgalı denetim izi; kayıtların üzerine yazılmaması | Ekleme-yalnız denetim izi, DB tetikleyicisi, hash zinciri, NTP; eski/yeni değer | U |
| 11.10(f) | İşlem sırası kontrolü | Çalışma yaşam döngüsü ön koşulları, form durum makinesi, imza sırası | U |
| 11.10(g) | Yetki kontrolleri (sistem, fonksiyon, kayıt düzeyinde) | Yetki matrisi (rol × işlem), kayıt düzeyinde merkez filtresi | U |
| 11.10(h) | Cihaz kontrolleri (veri girişi kaynağı) | HBYS entegrasyonu token/IP kısıtlı; CSV içe aktarma kullanıcıya bağlı ve loglu | U |
| 11.10(i) | Kullanıcıların eğitimi | SOP-EG-05 eğitim kayıtları; sistem içi rol bazlı eğitim modülü yok | UK |
| 11.10(j) | E-imza sorumluluğuna ilişkin yazılı politika | SOP-Eİ-01 e-imza politikası; kullanıcı ilk girişte taahhüt onayı | U |
| 11.10(k) | Sistem dokümantasyonu kontrolü | Belgeler sürüm kontrollü (git + KYS) | U |
| 11.30 | Açık sistem kontrolleri | Hastane içi kurulumda kapalı sistem; SaaS kurulumda TLS, veri şifreleme, EBM ISO 27001 kapsamı | U |
| 11.50 | İmza manifestosu (ad, tarih-saat, anlam) | EImza kaydı ve arayüzde görüntüleme | U |
| 11.70 | İmza-kayıt bağlantısı | icerik_hash; kayıt değişince imza geçersiz | U |

### Subpart C – Elektronik imzalar

| Madde | Gereklilik | Sistem kontrolü | Durum |
|---|---|---|---|
| 11.100(a) | İmzanın tek kişiye özgü olması | Benzersiz kullanıcı adı; hesaplar yeniden kullanılmaz (pasifleştirme) | U |
| 11.100(b) | Kimlik doğrulaması | Kullanıcı açma prosedürü (SOP-YT-02): kimlik belgesi kontrolü | UK |
| 11.100(c) | FDA'ya e-imza kullanım bildirimi | Sponsor sorumluluğunda; şablon mektup sağlanır | UY (EBM için), sponsor tarafı |
| 11.200(a)(1) | En az iki bileşen (kimlik + parola) | Kullanıcı adı + parola; imzada parola yeniden | U |
| 11.200(a)(1)(i) | Oturumda ilk imzada tüm bileşenler | İmza her seferinde parola ister | U |
| 11.200(a)(2) | Yalnızca sahibi kullanır | Parola paylaşım yasağı (SOP-Eİ-01), kilitleme | UK |
| 11.200(a)(3) | Taklit için iki kişinin iş birliği gerekmesi | Yönetici kullanıcı parolasını göremez (hash) | U |
| 11.300(a) | Kimlik/parola kombinasyonunun benzersizliği | DB unique kısıtı | U |
| 11.300(b) | Periyodik parola değişimi | 90 gün, son 5 tekrar yasağı | U |
| 11.300(c) | Kayıp/çalıntı token prosedürü | Parola sıfırlama prosedürü, denetim izi | U |
| 11.300(d) | Yetkisiz kullanım tespiti ve raporlama | 5 hatalı → kilit + yöneticiye bildirim; log | U |
| 11.300(e) | Token cihaz testi | Donanım token kullanılmıyor | UY |

## 2. EU GMP Annex 11

| Madde | Konu | Sistem kontrolü | Durum |
|---|---|---|---|
| 1 | Risk yönetimi | RA-001 FMEA; yapay zekâ riskleri dahil | U |
| 2 | Personel | Roller tanımlı (VAL-001 §5), eğitim kayıtları | U |
| 3 | Tedarikçiler ve hizmet sağlayıcılar | EBM geliştirici; SaaS'ta EBM tedarikçi değerlendirmesi müşteri tarafından; altyapı tedarikçileri (PostgreSQL, Ollama) kategori 1 | U |
| 4.1–4.8 | Validasyon (yaşam döngüsü, URS, tedarikçi, veri transferi) | VAL-001, URS-001, OQ-30/36 (veri transferi) | U |
| 5 | Veri (giriş kontrolleri) | Edit check, sorgu; FHIR eşleme doğrulaması | U |
| 6 | Doğruluk kontrolleri (kritik veri elle giriş) | eCRF kritik alanlarda çift giriş yok; SDV ve otomatik kontrol ile telafi | UK |
| 7.1 | Veri saklama – fiziksel ve elektronik koruma | Yedekleme, LUKS, erişim kontrolü | U |
| 7.2 | Yedekleme düzenliliği ve geri yükleme testi | Günlük; üç aylık prova (IQ-7) | U |
| 8.1 | Basılı kopya | PDF/CSV dışa aktarma | U |
| 8.2 | Denetim izi dahil okunabilir çıktı | Denetim izi dışa aktarma | U |
| 9 | Denetim izi (GMP ile ilgili değişiklik ve silmeler, gerekçe) | Gerekçe alanı zorunlu (kritik alanlar), silme yerine pasifleştirme; düzenli gözden geçirme SOP-Dİ-03 | U |
| 10 | Değişiklik ve yapılandırma yönetimi | SOP-DK-03; model değişikliği dahil | U |
| 11 | Periyodik değerlendirme | Yıllık gözden geçirme (ilk: 2027-05) | U (planlı) |
| 12.1 | Güvenlik – fiziksel ve mantıksal | Hastane veri merkezi; rol bazlı erişim; TLS | U |
| 12.2 | Erişim verme/değiştirme/iptal kayıtları | Kullanıcı yönetimi denetim izinde | U |
| 12.3 | Veri ve belgelere erişimin yönetilmesi | Yetki matrisi | U |
| 12.4 | Yönetim sistemleri için veri giriş/değişikliklerinin kaydı | Denetim izi | U |
| 13 | Olay yönetimi | SOP-OY-01; kritik sistem hataları değerlendirilir | U |
| 14 | Elektronik imza | Bkz. Part 11 Subpart C | U |
| 15 | Parti serbest bırakma | GMP üretim fonksiyonu yok | UY |
| 16 | İş sürekliliği | Yedek sunucu, geri yükleme RTO 4 saat, RPO 24 saat (SaaS'ta 1 saat) | U |
| 17 | Arşivleme | Arşiv prosedürü; okunabilirlik yıllık kontrol | UK |

## 3. Açık maddeler ve eylem planı

| No | Madde | Eylem | Sorumlu | Hedef |
|---|---|---|---|---|
| 1 | Annex 11 §6 | Kritik eCRF alanları için opsiyonel çift giriş modu | Yazılım | v1.5 (2026-Q4) |
| 2 | Part 11 11.10(i) | Sistem içi eğitim modülü ve eğitim tamamlama kaydı | Yazılım / KGS | v1.6 |
| 3 | Annex 11 §17 | Uzun dönem arşiv formatı (PDF/A + CSV + denetim izi) dışa aktarıcı | Yazılım | v1.5 |

Açık maddeler prosedürel kontrollerle (SOP) karşılanmaktadır; üretim kullanımına engel değildir.

## 4. Onaylar

| Rol | İmza | Tarih |
|---|---|---|
| Validasyon Sorumlusu | e-imza | 2026-06-10 |
| Bilgi Güvenliği Sorumlusu | e-imza | 2026-06-11 |
| Kalite Güvence Yöneticisi | e-imza | 2026-06-12 |
