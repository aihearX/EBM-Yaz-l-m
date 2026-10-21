# URS-001 Kullanıcı Gereksinimleri Spesifikasyonu

| | |
|---|---|
| Belge No | URS-001 |
| Sistem | EBM SmartClinical v1.4 |
| Sürüm | 2.1 |
| Yürürlük tarihi | 2026-02-17 |
| Hazırlayan | Klinik Operasyon Direktörü, Proje Yöneticisi (Ürün) |
| Gözden geçiren | Yazılım Geliştirme Yöneticisi, Veri Yönetimi Sorumlusu, Farmakovijilans Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## Revizyon geçmişi

| Sürüm | Tarih | Açıklama |
|---|---|---|
| 1.0 | 2025-03-21 | İlk yayın: çalışma yönetimi, EDC, güvenlik, denetim izi |
| 1.2 | 2025-08-11 | RBM (KRI/QTL), e-imza, TMF gereksinimleri eklendi |
| 2.0 | 2026-01-29 | Eşleştirme, BDM, merkez zekâsı, kimliksizleştirme gereksinimleri eklendi |
| 2.1 | 2026-02-17 | Gözden geçirme bulguları: URS-ES-06 (gölge mod), URS-BDM-05 (fallback) netleştirildi |

## 1. Giriş

Bu belge, EBM'nin klinik operasyon, veri yönetimi, farmakovijilans ve kalite
birimlerinin SmartClinical platformundan beklentilerini kullanıcı dilinde tanımlar.
Gereksinimler FRS-001'de fonksiyonel spesifikasyona, OQ-001/PQ-001'de test
senaryolarına izlenir (TM-001).

Kritiklik sınıfları: **GK** (GCP-kritik: hasta güvenliği, veri bütünlüğü, mevzuat),
**İK** (iş-kritik: operasyonel verimlilik), **D** (destekleyici).

Gereksinim kodları: `URS-<modül>-<no>`. Modüller: ÇY çalışma yönetimi, MZ merkez,
BŞ başvuru, EDC veri toplama, GV güvenlik (farmakovijilans), RBM risk bazlı izlem,
ES eşleştirme, BDM büyük dil model, KM kimliksizleştirme, TMF belge, Dİ denetim izi,
Eİ e-imza, YT yetki, ENT entegrasyon, SİS sistem/altyapı.

## 2. Çalışma yönetimi

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-ÇY-01 | Sistem; ilaç, biyobenzer, tıbbi cihaz, in vitro tanı kiti, gözlemsel, araştırmacı başlatımlı, biyoeşdeğerlik, ileri tedavi ve kayıt çalışmalarını ayrı tür olarak tanımlayabilmeli; tür, zorunlu alanları ve kontrol listesini belirlemeli. | İK |
| URS-ÇY-02 | Çalışma yaşam döngüsü tasarım → fizibilite → başvuru → aktivasyon → kayıt → izlem → kapanış → analiz → arşiv aşamalarından oluşmalı; aşama geçişleri tanımlı ön koşullara bağlı olmalı (ör. kayıt aşamasına geçiş için en az bir etik kurul onayı). | GK |
| URS-ÇY-03 | Protokol sürümleri tarih, değişiklik notu ve tam metinle saklanmalı; eski sürümler silinmemeli. | GK |
| URS-ÇY-04 | Dahil etme / hariç tutma kriterleri protokol sürümüne bağlı olarak listelenmeli; her kriter için hesaplanabilir yapı ve onay durumu tutulmalı. | GK |
| URS-ÇY-05 | Çalışma düzeyinde kilometre taşları (ilk merkez aktivasyonu, ilk hasta, son hasta, veritabanı kilidi) planlanan/gerçekleşen tarihlerle izlenmeli. | İK |
| URS-ÇY-06 | Kullanıcı rolüne göre özelleştirilmiş gösterge panelleri (sponsor, CRA, araştırmacı, koordinatör, veri yöneticisi) sunulmalı. | D |

## 3. Merkez yönetimi ve merkez zekâsı

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-MZ-01 | Merkez ve araştırmacı kayıtları (kurum tipi, terapötik alanlar, GCP eğitimi, CV tarihi, geçmiş çalışma sayısı) tutulmalı. | İK |
| URS-MZ-02 | Her çalışma-merkez için aday → fizibilite → seçildi → etik → sözleşme → başlatma → aktif → kayıt kapalı → kapalı durum akışı ve tarihleri izlenmeli. | İK |
| URS-MZ-03 | Sistem, geçmiş operasyon verisine dayanarak merkez başına aylık hasta kazanımını güven aralığıyla tahmin etmeli; tahmin gerekçesi (hangi verilere dayandığı, havuza ne kadar yaklaştırıldığı) kullanıcıya gösterilmeli. | İK |
| URS-MZ-04 | Sistem, merkez aktivasyonunun hedef tarihi aşma olasılığını (gecikme riski) hesaplamalı ve katkıda bulunan etkenleri listelemeli. | İK |
| URS-MZ-05 | Aday merkezler kazanım, gecikme riski, kalite geçmişi ve deneyim bileşenleriyle sıralanmalı; ağırlıklar çalışma bazında ayarlanabilmeli. | İK |
| URS-MZ-06 | Çalışma hedefine ulaşma tarihi için olasılık dağılımı (simülasyon) sunulmalı. | D |

## 4. Etik kurul ve TİTCK başvuruları

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-BŞ-01 | Etik kurul, TİTCK, kurum izni ve KVKK başvuruları; ilk başvuru, önemli değişiklik, yıllık bildirim, güvenlik bildirimi, sapma ve sonlandırma bildirimi türleriyle kayıt altına alınmalı. | GK |
| URS-BŞ-02 | Gönderim, eksik bildirimi ve karar tarihleri tutulmalı; geçen süre hesaplanmalı ve mevzuat süreleri (ör. TİTCK 30/60 gün) aşıldığında uyarı üretilmeli. | İK |
| URS-BŞ-03 | Başvuru belgeleri TMF ile ilişkilendirilmeli. | İK |

## 5. Elektronik veri toplama (EDC)

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-EDC-01 | eCRF formları CDASH uyumlu alan tanımlarıyla (tip, birim, aralık, zorunluluk, seçenek listesi) çalışma bazında tanımlanabilmeli. | GK |
| URS-EDC-02 | Veri girişinde aralık ve tutarlılık kontrolleri (edit check) anında çalışmalı; ihlal halinde otomatik sorgu açılmalı. | GK |
| URS-EDC-03 | Sorgu yaşam döngüsü (açık → cevaplandı → kapalı) ve açık kalma süresi izlenmeli. | GK |
| URS-EDC-04 | Form durumu taslak → tamamlandı → kaynak veri doğrulandı (SDV) → kilitli akışını izlemeli; kilitli form yalnızca yetkili rol tarafından gerekçe ile açılabilmeli. | GK |
| URS-EDC-05 | Her veri değişikliği eski/yeni değer, kullanıcı, zaman ve gerekçe ile denetim izine yazılmalı. | GK |
| URS-EDC-06 | Vizit takvimi protokol penceresine göre oluşturulmalı; pencere dışı ve kaçırılan vizitler işaretlenmeli. | GK |
| URS-EDC-07 | Veri CDISC SDTM'e dönüştürülebilir yapıda dışa aktarılabilmeli (CSV/XPT). | İK |

## 6. Güvenlik (farmakovijilans)

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-GV-01 | Advers olaylar terim, MedDRA kodu, başlangıç/bitiş, CTCAE derecesi, nedensellik, beklenirlik, ciddiyet ölçütü, sonuç ve alınan önlem ile kaydedilmeli. | GK |
| URS-GV-02 | Sistem SUSAR kriterlerini (ciddi + beklenmeyen + ilişkili) otomatik tespit etmeli. | GK |
| URS-GV-03 | Ciddi advers olaylarda farkındalık tarihinden itibaren TİTCK bildirim süresi (7/15 gün) geri sayılmalı; süre dolmadan uyarı verilmeli. | GK |
| URS-GV-04 | Sponsor, TİTCK ve etik kurul bildirim tarihleri ayrı ayrı tutulmalı; geç bildirimler RBM göstergesine yansımalı. | GK |

## 7. Risk bazlı izlem

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-RBM-01 | ICH E6(R3) ile uyumlu, en az 12 anahtar risk göstergesi (KRI) hazır tanımla gelmeli; çalışma bazında eşik, yön ve ağırlık düzenlenebilmeli. | GK |
| URS-RBM-02 | Çalışma düzeyinde kalite tolerans limitleri (QTL) tanımlanmalı, güncel değer ve aşım durumu izlenmeli. | GK |
| URS-RBM-03 | KRI değerleri merkezler arası istatistiksel olarak karşılaştırılmalı (aykırı merkez tespiti); küçük örneklemde güven sınırlılığı belirtilmeli. | İK |
| URS-RBM-04 | Erken uyarı motoru eşik ve aykırılık ihlallerinde uyarı üretmeli; uyarı neden tetiklendiğini açıklamalı; aynı konuda açık uyarı varsa yenisi üretilmemeli. | İK |
| URS-RBM-05 | Uyarılar atanabilmeli; açık → inceleniyor → kapandı / yanlış alarm akışı ve kapanış notu tutulmalı. | İK |
| URS-RBM-06 | Merkez başına bileşik risk puanı (0–100) hesaplanmalı ve izlem stratejisi önerisi (uzaktan, tetiklenmiş ziyaret, SDV oranı) sunulmalı. | İK |
| URS-RBM-07 | İzlem ziyaretleri (SIV, IMV, COV, uzaktan, tetiklenmiş) planlanmalı; bulgular ve rapor onayı kaydedilmeli. | İK |
| URS-RBM-08 | Protokol sapmaları kategori, önem, kök neden, düzeltici faaliyet ve etik bildirim tarihiyle kaydedilmeli. | GK |

## 8. Protokol–hasta eşleştirme

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-ES-01 | Sistem, protokol kriterlerini (Türkçe ve İngilizce) hesaplanabilir sorguya dönüştürmeli; dönüşüm kullanıcı tarafından görülebilir, düzenlenebilir ve onaylanabilir olmalı. | GK |
| URS-ES-02 | Kimliksizleştirilmiş hasta kayıtları (yapısal veri + serbest metin) kriterlerle eşleştirilerek uygun / olası / uygun değil / belirsiz kararı ve 0–1 skor üretilmeli. | İK |
| URS-ES-03 | Her kriter sonucu için dayanak (yapısal veri alanı ya da kaynak metinden birebir cümle) gösterilmeli; dayanak gösterilemeyen sonuç "belirsiz" olmalı. | GK |
| URS-ES-04 | Eşleştirme önerisi, araştırmacı onayı olmadan gönüllü kaydı oluşturmamalı; onay/red/beklet kararı ve notu kaydedilmeli. | GK |
| URS-ES-05 | Kriter eşleştirmede duyarlılık altın standart sette ≥ %90 olmalı. | İK |
| URS-ES-06 | Gölge mod: eşleştirme sonuçları manuel ön tarama kararlarıyla karşılaştırılarak duyarlılık, özgüllük, PPV raporlanabilmeli. | İK |
| URS-ES-07 | Hasta başına eşleştirme süresi GPU'lu kurulumda ≤ 5 sn, GPU'suz kurulumda ≤ 30 sn olmalı. | D |

## 9. Türkçe Klinik BDM

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-BDM-01 | Model hastane içi sunucuda çalışmalı; hiçbir hasta verisi kurum dışına gönderilmemeli. | GK |
| URS-BDM-02 | Model çıktıları deterministik olmalı (aynı girdi → aynı çıktı). | GK |
| URS-BDM-03 | Modelin ürettiği kanıt cümlesi kaynak metinde birebir bulunmuyorsa sonuç reddedilmeli (halüsinasyon kontrolü). | GK |
| URS-BDM-04 | Model güveni eşik altındaysa sonuç "belirsiz" olarak işaretlenmeli ve insan incelemesine düşmeli. | GK |
| URS-BDM-05 | Model servisi erişilemezse sistem kural tabanlı değerlendirmeye düşmeli, bunu kullanıcıya göstermeli ve loglamalı; eşleştirme durmamalı. | İK |
| URS-BDM-06 | Model sürümü her eşleştirme sonucuyla birlikte kaydedilmeli. | GK |
| URS-BDM-07 | İstemlere kimlik verisi (TCKN vb.) girmesi engellenmeli. | GK |

## 10. Kimliksizleştirme

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-KM-01 | Serbest metinlerde TCKN, ad-soyad, telefon, e-posta, adres, tarih, dosya/protokol numarası, kurum adı ve 89 üstü yaş tespit edilip maskelenmeli ya da takma adla değiştirilmeli. | GK |
| URS-KM-02 | Kimliksizleştirmeden geçmemiş serbest metin hasta tablosuna yazılamamalı. | GK |
| URS-KM-03 | İkinci geçiş doğrulaması şüpheli kalıpları raporlamalı. | İK |
| URS-KM-04 | HBYS'den kimlik alanları (ad, adres, iletişim, kimlik numarası) hiç alınmamalı; takma ad tek yönlü özetle üretilmeli. | GK |

## 11. TMF belge yönetimi

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-TMF-01 | Belgeler DIA TMF Referans Modeli bölgelerine göre sınıflandırılmalı. | İK |
| URS-TMF-02 | Her belge sürüm, durum (taslak/onaylı/eskimiş), yükleyen, zaman ve SHA-256 özeti ile saklanmalı. | GK |
| URS-TMF-03 | Belge yükleme 50 MB'a kadar PDF, DOCX, XLSX, JPG biçimlerini desteklemeli. | D |

## 12. Denetim izi ve elektronik imza

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-Dİ-01 | Tüm oluşturma, güncelleme, silme, giriş/çıkış, imza, dışa aktarma işlemleri kullanıcı, zaman (NTP eşitli), eski/yeni değer ve gerekçe ile kaydedilmeli. | GK |
| URS-Dİ-02 | Denetim izi uygulama ve veritabanı düzeyinde değiştirilemez ve silinemez olmalı. | GK |
| URS-Dİ-03 | Denetim izi kayıtları zincir özetiyle (önceki kaydın hash'i) bütünlük açısından doğrulanabilmeli. | GK |
| URS-Dİ-04 | Denetçi rolü denetim izini filtreleyip okunabilir biçimde dışa aktarabilmeli. | GK |
| URS-Eİ-01 | Elektronik imza; imzalayanın adı, tarih-saat, imza anlamı (onay, gözden geçirme, sorumluluk) ve imzalanan içeriğin özetini içermeli. | GK |
| URS-Eİ-02 | İmza anında kullanıcı kimliği (parola) yeniden doğrulanmalı. | GK |
| URS-Eİ-03 | İmzalanmış kayıt değiştirildiğinde imza geçersiz olarak işaretlenmeli ve yeniden imza gerekmeli. | GK |

## 13. Yetkilendirme ve güvenlik

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-YT-01 | Rol bazlı erişim: sistem yöneticisi, sponsor, proje yöneticisi, CRA, araştırmacı, koordinatör, veri yöneticisi, biyoistatistikçi, farmakovijilans, denetçi. | GK |
| URS-YT-02 | Merkez kullanıcıları yalnızca kendi merkezlerinin verisini görebilmeli; sponsor kullanıcıları kimliksizleştirilmiş hasta metinlerini görememeli. | GK |
| URS-YT-03 | Parola politikası (uzunluk, karmaşıklık, süre, tekrar, kilitleme) yapılandırılabilir olmalı; oturum süresi dolunca otomatik çıkış. | GK |
| URS-YT-04 | Kullanıcı hesapları silinmemeli, pasifleştirilmeli; geçmiş kayıtlardaki kullanıcı adı korunmalı. | GK |
| URS-YT-05 | Kurumsal dizin (LDAP/AD) ile kimlik doğrulama desteklenmeli. | D |

## 14. Entegrasyon

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-ENT-01 | HBYS'den FHIR R4 (Patient, Condition, Observation, MedicationStatement, DocumentReference) ile hasta verisi alınabilmeli. | İK |
| URS-ENT-02 | Çalışma ve gönüllü verisi FHIR ResearchStudy / ResearchSubject olarak dışa verilebilmeli. | D |
| URS-ENT-03 | Hasta verisi OMOP CDM v5.4 tablolarına dışa aktarılabilmeli. | D |
| URS-ENT-04 | FHIR desteği olmayan HBYS'ler için CSV içe aktarma sağlanmalı. | İK |
| URS-ENT-05 | REST API, token ile kimlik doğrulanarak üçüncü taraf EDC/CTMS sistemlerine açılabilmeli. | D |

## 15. Sistem ve altyapı

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-SİS-01 | Sistem hastane içinde (on-premise) ve EBM veri merkezinde (SaaS) kurulabilmeli. | İK |
| URS-SİS-02 | Günlük yedekleme ve belgelenmiş geri yükleme prosedürü olmalı; geri yükleme en az üç ayda bir test edilmeli. | GK |
| URS-SİS-03 | İletişim TLS 1.2+ ile şifrelenmeli; veritabanı diskte şifreli bölümde tutulmalı. | GK |
| URS-SİS-04 | 50 eşzamanlı kullanıcıda sayfa yanıt süresi ≤ 2 sn (BDM çağrıları hariç). | D |
| URS-SİS-05 | Arayüz Türkçe olmalı; İngilizce arayüz desteklenmeli (sponsor kullanıcıları). | D |
| URS-SİS-06 | Zaman damgaları UTC saklanmalı, Türkiye saatiyle gösterilmeli. | GK |
| URS-SİS-07 | Sistem, ISO/IEC 27001 kapsamındaki bilgi güvenliği kontrollerine (erişim kaydı, log saklama ≥ 1 yıl, sızma testi) uygun olmalı. | GK |

## 16. Onaylar

| Rol | Ad / Unvan | İmza | Tarih |
|---|---|---|---|
| Hazırlayan | Klinik Operasyon Direktörü | e-imza | 2026-02-12 |
| Gözden geçiren | Yazılım Geliştirme Yöneticisi | e-imza | 2026-02-14 |
| Onaylayan | Kalite Güvence Yöneticisi | e-imza | 2026-02-17 |
