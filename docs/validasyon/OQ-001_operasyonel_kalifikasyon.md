# OQ-001 Operasyonel Kalifikasyon Protokolü ve Raporu

| | |
|---|---|
| Belge No | OQ-001 |
| Sistem | EBM SmartClinical v1.4.2 |
| Ortam | Pilot Merkez 1 – validasyon ortamı (üretim kopyası, sentetik veri) |
| Sürüm | 1.0 |
| Protokol onayı | 2026-05-19 |
| Uygulama tarihi | 2026-05-25 – 2026-06-05 |
| Test uygulayıcıları | Klinik Kalite Uzmanı (T1), Veri Yönetimi Uzmanı (T2), CRA (T3) – geliştirme ekibinden bağımsız |
| Gözden geçiren | Validasyon Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Amaç

FRS-001'de tanımlanan fonksiyonların, URS-001 gereksinimlerini belirlenen sınırlar
içinde ve olumsuz koşullarda karşıladığını belgelemek. GK sınıfı gereksinimlerin tamamı
en az bir senaryo ile kapsanır (TM-001).

## 2. Test ortamı ve veri

Validasyon ortamı üretim imajının kopyasıdır; veritabanı `demo_veri --sifirla` ile
sentetik veriyle doldurulmuştur (3 çalışma, 6 merkez, 48 sentetik hasta kaydı, 41 gönüllü).
Hiçbir gerçek hasta verisi kullanılmamıştır. Test kullanıcıları: `oq_yonetici`,
`oq_cra`, `oq_arastirmaci_m01`, `oq_sponsor`, `oq_veri`, `oq_denetci`.

## 3. Test senaryoları

Sonuç sütunu: G (geçti), K (kaldı), G* (sapma sonrası tekrar testte geçti).

| No | Senaryo | Adımlar (özet) | Beklenen sonuç | URS | Uyg. | Sonuç |
|---|---|---|---|---|---|---|
| OQ-01 | Yaşam döngüsü ön koşulu | Etik onayı olmayan çalışmayı "Hasta Kaydı" aşamasına taşımaya çalış | Geçiş reddedilir, eksik listesi "onaylı etik kurul başvurusu yok" gösterir | ÇY-02 | T1 | G |
| OQ-02 | Merkez kapsaması | `oq_arastirmaci_m01` ile Merkez 02 gönüllü sayfasına doğrudan URL ile git | 403; denetim izinde "yetkisiz erişim denemesi" | YT-02 | T1 | G |
| OQ-03 | Sponsor alan maskeleme | `oq_sponsor` ile hasta kaydı API'sini çağır | `metinler` alanı yanıt içinde yok; arayüzde "yetkiniz yok" | YT-02 | T1 | G |
| OQ-04 | Parola politikası ve kilit | 5 hatalı giriş; 11 karakter parola dene; 20 dk hareketsizlik | Kilit 15 dk; parola reddedilir; oturum düşer | YT-03 | T1 | G |
| OQ-05 | Denetim izi – veri değişikliği | eCRF alanını 120 → 125 değiştir, gerekçe gir | Kayıt: kullanıcı, UTC zaman, eski 120, yeni 125, gerekçe | EDC-05, Dİ-01 | T2 | G |
| OQ-06 | Denetim izi – transaction | Denetim izi yazımını geçici olarak engelle (DB yetkisi kaldır), veri değiştir | Değişiklik geri alınır, hata mesajı; yetki geri verilince normal | Dİ-01 | T2 | G* (bkz. SAP-OQ-01) |
| OQ-07 | Denetim izi bütünlüğü | Doğrudan SQL ile UPDATE/DELETE dene; `denetim_dogrula.py` çalıştır | İşlemler reddedilir; zincir doğrulaması "bütün" | Dİ-02, Dİ-03 | T2 | G |
| OQ-08 | E-imza kimlik doğrulama | İzlem raporunu imzala: yanlış parola, sonra doğru parola | Yanlış parola reddedilir; imza kaydı ad, zaman, anlam, özet içerir | Eİ-01, Eİ-02 | T3 | G |
| OQ-09 | E-imza geçersizleşme | İmzalı raporu düzenle | "İmza geçersiz" rozeti; yeniden imza istenir | Eİ-03 | T3 | G |
| OQ-10 | eCRF edit check | Sistolik KB alanına 400 ve boş zorunlu alan gir | Otomatik sorgu açılır (aralık), zorunlu alan uyarısı; kayıt taslak kalır | EDC-01, EDC-02 | T2 | G |
| OQ-11 | Vizit penceresi | V2 planlanan 2026-05-01, pencere ±3; gerçekleşen 2026-05-06 gir | Vizit "pencere dışı" işaretlenir; KRI PENCERE_DISI_VIZIT artar | EDC-06 | T2 | G |
| OQ-12 | SAE bildirim süresi | Ciddi AE, ölçüt "hastaneye yatış", farkındalık bugün-13 | Kalan süre 2 gün, panelde kırmızı | GV-03 | T3 | G |
| OQ-13 | SUSAR tespiti | AE: ciddi, beklenmeyen, nedensellik "muhtemel" | SUSAR rozeti; farmakovijilans paneline düşer | GV-02 | T3 | G |
| OQ-14 | Başvuru süre uyarısı | TİTCK ilk başvuru gönderim 35 gün önce, karar yok | "Mevzuat süresi aşıldı (30 gün)" uyarısı | BŞ-02 | T1 | G |
| OQ-15 | KRI hesaplama | Merkez 01: 40 form, 12 sorgu → SORGU_ORANI | 0,30; eşik 0,25 → uyarı seviyesi | RBM-01 | T3 | G |
| OQ-16 | KRI yetersiz veri | Merkez 06: 2 gönüllü | KRI "yetersiz veri", uyarı üretilmez | RBM-03 | T3 | G |
| OQ-17 | Uyarı tekilleştirme | Erken uyarıyı iki kez çalıştır | Aynı (merkez, KRI) için tek açık uyarı; değer güncellenir | RBM-04 | T3 | G |
| OQ-18 | QTL aşımı | Erken ayrılma %'sini limit üstüne çıkar | QTL "aşıldı"; çalışma panelinde kırmızı | RBM-02 | T3 | G |
| OQ-19 | Kriter yapılandırma ve onay | "Hemoglobin ≥ 9 g/dL" kriterini yapılandır; `>=` → `>` olarak düzenle; onayla | Yapı görüntülenir, düzenleme denetim izine düşer; onaysız kriterle eşleştirme "taslak" etiketli | ES-01, ÇY-04 | T2 | G |
| OQ-20 | İnsan-döngüde kontrol | Eşleştirme çalıştır; "uygun" sonucu olan hasta için Gonullu tablosunu kontrol et | Gönüllü kaydı oluşmaz; "Onayla" sonrası `aday` durumunda oluşur | ES-04 | T2 | G |
| OQ-21 | Hariç kriter ihlali | Hastaya "son 3 ay MI" metni ekle; EXC "son 6 ay MI" | Karar "uygun değil", kanıt cümlesi gösterilir | ES-02, ES-03 | T2 | G |
| OQ-22 | Belirsiz sonuç | ECOG bilgisi olmayan hasta | İlgili kriter "belirsiz", hasta "belirsiz/olası" listesinde | ES-02 | T2 | G |
| OQ-23 | Determinizm | Aynı hastayı 3 kez eşleştir | Skor ve kriter sonuçları birebir aynı | BDM-02 | T2 | G |
| OQ-24 | Halüsinasyon koruması | Test sağlayıcısı ile kaynakta olmayan kanıt döndür (mock) | Sonuç "belirsiz"e düşer; log WARNING | BDM-03, BDM-04 | T2 | G |
| OQ-25 | Model sürümü kaydı | Eşleştirme sonucunu incele | `model_surumu` = "ollama/ebm-klinik-tr-7b-q4/9b4d1c07" | BDM-06 | T2 | G |
| OQ-26 | BDM fallback | BDM konteynerini durdur; eşleştir | Sonuçlar `yontem=kural`, arayüz rozeti, log WARNING; servis açılınca normal | BDM-05 | T2 | G |
| OQ-27 | İstem PHI kontrolü | Kimliksizleştirmeyi atlayarak TCKN içeren metinle `kanit_cikar` çağır (test kancası) | Çağrı engellenir, denetim izinde "phi_engellendi" | BDM-07 | T2 | G |
| OQ-28 | Kimliksizleştirme kapsamı | 60 örnekli test metni seti (TCKN, ad, telefon, adres, tarih, dosya no, kurum, 92 yaş) | Kaçak oranı ≤ %1 (gözlenen: 0/412 varlık) | KM-01, KM-03 | T2 | G |
| OQ-29 | Aşırı maskeleme | Klinik terim içeren 30 metin (ör. "Ca", "Herceptin", "Ankara Üniversitesi" kurum vs "Ankara" il) | Klinik terimler korunur; kurum adı maskelenir; aşırı maskeleme ≤ %3 | KM-01 | T2 | G* (SAP-OQ-02) |
| OQ-30 | FHIR eşleme – kimlik alanları | Ad, adres, telefon içeren test Bundle'ı içe aktar | Hasta kaydında bu alanlar yok; kayit_no 16 hex | KM-04, ENT-01 | T2 | G |
| OQ-31 | Kazanım tahmini açıklanabilirlik | Geçmişi olmayan yeni merkez için tahmin | Havuz öncülü, "veri yok, havuza %100 büzüldü" açıklaması, geniş aralık | MZ-03 | T3 | G |
| OQ-32 | Toplu eşleştirme arka plan | 48 hasta için tara | Arayüz kilitlenmez, ilerleme çubuğu, tamamlanınca bildirim | ES-07 | T2 | G |
| OQ-33 | TMF bütünlük | PDF yükle, dosyayı diskte değiştir, indir | İndirmede "özet uyuşmuyor" hatası | TMF-02 | T1 | G |
| OQ-34 | Denetim izi dışa aktarma | `oq_denetci` ile tarih filtreli CSV al | Dosya oluşur; dışa aktarma işlemi de denetim izinde | Dİ-04 | T1 | G |
| OQ-35 | Kullanıcı pasifleştirme | Kullanıcıyı pasifleştir; eski kayıtları görüntüle | Giriş engellenir; kayıtlarda kullanıcı adı korunur | YT-04 | T1 | G |
| OQ-36 | OMOP dışa aktarma | 10 hasta için dışa aktar | 5 CSV; person satır sayısı 10; bilinmeyen kodlar concept_id 0 + source_value | ENT-03 | T2 | G |
| OQ-37 | Zaman damgası | Kayıt oluştur; DB ve arayüz zamanını karşılaştır | DB UTC, arayüz +03:00 | SİS-06 | T1 | G |
| OQ-38 | Gölge mod raporu | 20 hasta: manuel karar gir, eşleştir | Duyarlılık/özgüllük/PPV/NPV ve karışıklık matrisi gösterilir | ES-06 | T3 | G |

## 4. Sapmalar

| No | Senaryo | Açıklama | Sınıf | Düzeltme | Tekrar test | Durum |
|---|---|---|---|---|---|---|
| SAP-OQ-01 | OQ-06 | Denetim izi yazılamadığında hata mesajı İngilizce ve teknik ("IntegrityError") görüntülendi; işlem doğru şekilde geri alındı | Minör | v1.4.2-hf1: kullanıcı dostu Türkçe mesaj | 2026-06-02 G | Kapalı |
| SAP-OQ-02 | OQ-29 | "Eğitim ve Araştırma Hastanesi" kalıbı öncesindeki il adı bazı cümlelerde iki kez maskelenerek cümle bütünlüğü bozuldu (aşırı maskeleme %4,1) | Minör | Kurum kalıbı tek bulgu olarak birleştirildi; aşırı maskeleme %1,8 | 2026-06-03 G | Kapalı |

## 5. Sonuç

38 senaryonun 36'sı ilk koşuda geçti; 2 minör sapma düzeltilip tekrar testte geçti.
GK sınıfı gereksinimlerin %100'ü kapsandı ve geçti. Sistem PQ-001'e geçmeye uygundur.

## 6. Onaylar

| Rol | İmza | Tarih |
|---|---|---|
| Test uygulayıcıları (T1, T2, T3) | e-imza | 2026-06-05 |
| Validasyon Sorumlusu | e-imza | 2026-06-08 |
| Kalite Güvence Yöneticisi | e-imza | 2026-06-10 |
