# 21 CFR Part 11 ve EU GMP Annex 11 Uyum Değerlendirmesi

| | |
|---|---|
| Belge No | UYM-001 |
| Sistem | EBM SmartClinical |
| Hazırlayan | Validasyon Sorumlusu, Bilgi Güvenliği Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

Durum kodları: **U** uyumlu, **UK** uyumlu (kısmen prosedürel kontrol ile), **UY** uygulanamaz, **A** açık (eylem planı var).
"Sistem kontrolü" sütunundaki her teknik önlem FRS-001'de koda bağlıdır; prosedürel kontroller SOP ile sağlanır.

## 1. 21 CFR Part 11

### Subpart B – Elektronik kayıtlar

| Madde | Gereklilik | Sistem kontrolü | Durum |
|---|---|---|---|
| 11.10(a) | Sistem validasyonu | VAL-001 planı, IQ/OQ/PQ, otomatik testler, TM-001 kod eşlemesi | U |
| 11.10(b) | Doğru ve eksiksiz kopya üretimi | Denetim izi CSV; eCRF CSV paketi ve CDISC ODM (isteğe bağlı AuditRecord); liste CSV'leri; OMOP; her dışa aktarma kaydedilir (FRS-22, FRS-54, FRS-78) | U |
| 11.10(c) | Kayıtların saklama süresi boyunca korunması | PostgreSQL + günlük `age` şifreli yedek, aylık arşiv 25 yıl (FRS-66); TMF arşiv prosedürü | UK |
| 11.10(d) | Sistem erişiminin yetkili kişilerle sınırlanması | Rol bazlı yetki, merkez ve sponsor kapsaması, parola politikası, hesap kilidi (FRS-56, FRS-57) | U |
| 11.10(e) | Güvenli, bilgisayar üretimli, zaman damgalı denetim izi | Ekleme-yalnız denetim izi, DB tetikleyicisi, HMAC zinciri, kilitli zincir ucu, UTC; eski/yeni değer (FRS-53) | U |
| 11.10(f) | İşlem sırası kontrolü | Aşama kontrol listeleri, form durum makinesi, toplu kilit ön kontrolü, onaylı rapor kilidi (FRS-02, FRS-19, FRS-33) | U |
| 11.10(g) | Yetki kontrolleri (sistem, fonksiyon, kayıt düzeyinde) | `IZINLER` matrisi, `calisma_erisimi`, `gonullu_erisimi`, belge merkez filtresi | U |
| 11.10(h) | Cihaz kontrolleri (veri girişi kaynağı) | HBYS eşitlemesi yetkili kullanıcı ve API anahtarıyla; CSV içe aktarma kullanıcıya bağlı ve denetim izinde | U |
| 11.10(i) | Kullanıcıların eğitimi | Eğitim kayıtları SOP ile; sistem içi eğitim modülü yok | UK |
| 11.10(j) | E-imza sorumluluğuna ilişkin yazılı politika | E-imza politikası SOP | UK |
| 11.10(k) | Sistem dokümantasyonu kontrolü | Belgeler sürüm kontrollü (git); belge satırları koda test ile bağlı | U |
| 11.30 | Açık sistem kontrolleri | Hastane içi kurulumda kapalı ağ (internal docker ağı); TLS | U |
| 11.50 | İmza manifestosu (ad, tarih-saat, anlam) | `EImza` kaydı; ziyaret raporu, belge, kilit ve araştırmacı imzası sayfalarında görüntüleme | U |
| 11.70 | İmza-kayıt bağlantısı | `icerik_hash`; içerik değişince "imza yenilenmeli" (FRS-74) | U |

### Subpart C – Elektronik imzalar

| Madde | Gereklilik | Sistem kontrolü | Durum |
|---|---|---|---|
| 11.100(a) | İmzanın tek kişiye özgü olması | Benzersiz kullanıcı adı; hesaplar silinmez, pasifleştirilir (FRS-58) | U |
| 11.100(b) | Kimlik doğrulaması | Kullanıcı açma prosedürü (SOP): kimlik belgesi kontrolü | UK |
| 11.100(c) | FDA'ya e-imza kullanım bildirimi | Sponsor sorumluluğunda | UY |
| 11.200(a)(1) | En az iki bileşen (kimlik + parola) | Kullanıcı adı + parola; imzada parola yeniden | U |
| 11.200(a)(1)(i) | Oturumda ilk imzada tüm bileşenler | İmza her seferinde parola ister (FRS-55) | U |
| 11.200(a)(2) | Yalnızca sahibi kullanır | Parola paylaşım yasağı (SOP), kilitleme | UK |
| 11.200(a)(3) | Taklit için iki kişinin iş birliği gerekmesi | Yönetici parolayı göremez (PBKDF2 özeti) | U |
| 11.300(a) | Kimlik/parola kombinasyonunun benzersizliği | DB unique kısıtı | U |
| 11.300(b) | Periyodik parola değişimi | 90 gün, son 5 tekrar yasağı (FRS-57) | U |
| 11.300(c) | Kayıp/çalıntı token prosedürü | Yönetici parola sıfırlama, ilk girişte zorunlu değişim; denetim izi | U |
| 11.300(d) | Yetkisiz kullanım tespiti ve raporlama | 5 hatalı → süreli kilit, IP başına sınır; kilit olayı denetim izinde | U |
| 11.300(e) | Token cihaz testi | Donanım token kullanılmıyor | UY |

## 2. EU GMP Annex 11

| Madde | Konu | Sistem kontrolü | Durum |
|---|---|---|---|
| 1 | Risk yönetimi | RA-001 FMEA; yapay zekâ riskleri dahil | U |
| 2 | Personel | Roller tanımlı (VAL-001 §5), eğitim kayıtları | U |
| 3 | Tedarikçiler ve hizmet sağlayıcılar | EBM geliştirici; altyapı tedarikçileri kategori 1 | U |
| 4 | Validasyon (yaşam döngüsü, URS, veri transferi) | VAL-001, URS-001, OQ-30/36 (veri transferi) | U |
| 5 | Veri (giriş kontrolleri) | Edit check, sorgu; FHIR eşleme testi; CSV red listesi | U |
| 6 | Doğruluk kontrolleri (kritik veri elle giriş) | Çift giriş yok; SDV, otomatik kontrol ve araştırmacı imzası ile telafi | UK |
| 7.1 | Veri saklama – fiziksel ve elektronik koruma | Şifreli yedek, LUKS, erişim kontrolü | U |
| 7.2 | Yedekleme düzenliliği ve geri yükleme testi | Günlük; üç aylık prova (IQ-7) | U |
| 8.1 | Basılı kopya | CSV/ODM dışa aktarma; yazdırılabilir ziyaret raporu ve fizibilite raporu | U |
| 8.2 | Denetim izi dahil okunabilir çıktı | Denetim izi CSV; ODM AuditRecord | U |
| 9 | Denetim izi (değişiklik ve silmeler, gerekçe) | Gerekçe alanı (aşama değişimi, kilit açma, kaçırılan vizit); silme yerine pasifleştirme; görüntüleme kayıtları | U |
| 10 | Değişiklik ve yapılandırma yönetimi | Değişiklik kontrol prosedürü; model değişikliği dahil | U |
| 11 | Periyodik değerlendirme | Yıllık gözden geçirme | U (planlı) |
| 12.1 | Güvenlik – fiziksel ve mantıksal | Hastane veri merkezi; rol bazlı erişim; TLS; anonim uçlar bilgi vermez | U |
| 12.2 | Erişim verme/değiştirme/iptal kayıtları | Kullanıcı ve API anahtarı yönetimi denetim izinde | U |
| 12.3 | Veri ve belgelere erişimin yönetilmesi | Yetki matrisi; belge indirme kayıtları | U |
| 12.4 | Veri giriş/değişikliklerinin kaydı | Denetim izi | U |
| 13 | Olay yönetimi | Olay yönetimi SOP | U |
| 14 | Elektronik imza | Bkz. Part 11 Subpart C | U |
| 15 | Parti serbest bırakma | GMP üretim fonksiyonu yok | UY |
| 16 | İş sürekliliği | Şifreli yedek, geri yükleme prosedürü (KUR-001 §8) | U |
| 17 | Arşivleme | Aylık arşiv 25 yıl; okunabilirlik yıllık kontrol (SOP) | UK |

## 3. Açık maddeler ve eylem planı

| No | Madde | Eylem | Sorumlu |
|---|---|---|---|
| 1 | Annex 11 §6 | Kritik eCRF alanları için isteğe bağlı çift giriş modu | Yazılım |
| 2 | Part 11 11.10(i) | Sistem içi eğitim tamamlama kaydı | Yazılım / KGS |
| 3 | Annex 11 §17 | Uzun dönem arşiv paketi (PDF/A + CSV + denetim izi) | Yazılım |

Açık maddeler prosedürel kontrollerle karşılanmaktadır; üretim kullanımına engel değildir.

## 4. Onaylar

| Rol | İmza |
|---|---|
| Validasyon Sorumlusu | |
| Bilgi Güvenliği Sorumlusu | |
| Kalite Güvence Yöneticisi | |
