# URS-001 Kullanıcı Gereksinimleri Spesifikasyonu

| | |
|---|---|
| Belge No | URS-001 |
| Sistem | EBM SmartClinical |
| Hazırlayan | Klinik Operasyon Direktörü, Proje Yöneticisi (Ürün) |
| Gözden geçiren | Yazılım Geliştirme Yöneticisi, Veri Yönetimi Sorumlusu, Farmakovijilans Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Giriş

Bu belge, klinik operasyon, veri yönetimi, farmakovijilans ve kalite birimlerinin SmartClinical
platformundan beklentilerini kullanıcı dilinde tanımlar. Gereksinimler FRS-001'de fonksiyonel
spesifikasyona, OQ-001/PQ-001'de kalifikasyon senaryolarına ve TM-001'de koda (rota, betik,
otomatik test) izlenir. Kodda karşılığı olmayan gereksinim bu belgede yer almaz; önceki
sürümlerden çıkarılan maddeler TM-001 bölüm 11'de listelenir.

Kritiklik sınıfları: **GK** (GCP-kritik: hasta güvenliği, veri bütünlüğü, mevzuat),
**İK** (iş-kritik: operasyonel verimlilik), **D** (destekleyici).

Gereksinim kodları: `URS-<modül>-<no>`. Modüller: ÇY çalışma yönetimi, MZ merkez, BŞ başvuru,
EDC veri toplama, GV güvenlik (farmakovijilans), RBM risk bazlı izlem, ES eşleştirme, BDM büyük
dil modeli, KM kimliksizleştirme, TMF belge, Dİ denetim izi, Eİ e-imza, YT yetki, ENT entegrasyon,
SİS sistem/altyapı.

Kullanım senaryoları: CRO modu (çok merkezli, proje ekibi atamalı), tekil araştırmacı modu
(tek merkez, sade sihirbaz) ve üniversite modu (anabilim dalı gruplaması). Aynı kod tabanı üç
senaryoda da kullanılır; mod kurulum ayarıyla seçilir.

## 2. Çalışma yönetimi

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-ÇY-01 | Sistem; ilaç, biyobenzer, tıbbi cihaz, in vitro tanı kiti, gözlemsel, araştırmacı başlatımlı, biyoeşdeğerlik, ileri tedavi ve kayıt çalışmalarını ayrı tür olarak tanımlayabilmeli; tür, zorunlu alanları (ör. TİTCK başvurusu gereken türler) belirlemeli. | İK |
| URS-ÇY-02 | Çalışma yaşam döngüsü tasarım → fizibilite → başvuru → aktivasyon → kayıt → izlem → kapanış → analiz → arşiv aşamalarından oluşmalı; her aşama için veriden hesaplanan kontrol listesi gösterilmeli, aşama değişimi gerekçe ile ve denetim izine yazılarak yapılmalı. | GK |
| URS-ÇY-03 | Protokol sürümleri tarih, özet ve değişiklik notuyla saklanmalı; eski sürümler silinmemeli. | GK |
| URS-ÇY-04 | Dahil etme / hariç tutma kriterleri listelenmeli; her kriter için hesaplanabilir yapı, güven değeri ve onay durumu tutulmalı; onaysız kriter eşleştirmede kullanılmamalı. | GK |
| URS-ÇY-05 | Merkez aktivasyon, ilk hasta ve başlatma ziyareti (SIV) tarihleri izlenmeli; SIV'in yapılması aktivasyon aşaması kontrol listesine yansımalı. | İK |
| URS-ÇY-06 | Genel bakış sayfası kullanıcının rolüne ve erişebildiği çalışmalara göre özet göstermeli. | D |
| URS-ÇY-07 | Yeni çalışma dört adımlı bir sihirbazla (temel bilgiler, tasarım, merkezler/ekip, özet) tek işlemde kurulabilmeli; tekil modda araştırmacı, CRO modunda proje yöneticisi kurmalı; protokol kodu benzersiz olmalı. | İK |

## 3. Merkez yönetimi ve merkez zekâsı

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-MZ-01 | Merkez ve araştırmacı kayıtları (kurum tipi, terapötik alanlar, GCP eğitimi, CV tarihi, geçmiş çalışma sayısı, FHIR uç noktası) tutulmalı. | İK |
| URS-MZ-02 | Her çalışma-merkez için aday → fizibilite → seçildi → etik → sözleşme → başlatma → aktif → kayıt kapalı → kapalı durum akışı ve tarihleri izlenmeli. | İK |
| URS-MZ-03 | Sistem, geçmiş operasyon verisine dayanarak merkez başına aylık hasta kazanımını güven aralığıyla tahmin etmeli; tahmin gerekçesi (veri miktarı, havuza büzülme, kovaryat düzeltmeleri) gösterilmeli. | İK |
| URS-MZ-04 | Sistem, merkez aktivasyonunun hedef tarihi aşma olasılığını (gecikme riski) hesaplamalı; eğitim verisi yoksa öncülle çalıştığını belirtmeli. | İK |
| URS-MZ-05 | Aday merkezler kazanım, gecikme riski, kalite geçmişi ve deneyim bileşenleriyle sıralanmalı; ağırlıklar ayarlanabilmeli. | İK |
| URS-MZ-06 | Çalışma hedefine ulaşma tarihi için olasılık dağılımı (simülasyon) sunulmalı. | D |
| URS-MZ-07 | Tahminler ve risk göstergeleri gece işiyle tüm aktif çalışmalarda güncellenmeli; çalıştırma denetim izine yazılmalı. | İK |

## 4. Etik kurul ve TİTCK başvuruları

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-BŞ-01 | Etik kurul, TİTCK, kurum izni ve KVKK başvuruları; ilk başvuru, önemli değişiklik, yıllık bildirim, güvenlik bildirimi, sapma ve sonlandırma bildirimi türleriyle kayıt altına alınmalı. | GK |
| URS-BŞ-02 | Gönderim ve karar tarihleri tutulmalı, geçen süre hesaplanmalı; karar onay olmadan kayıt aşamasına geçiş kontrol listesinde eksik görünmeli. | İK |
| URS-BŞ-03 | Başvuru belgeleri TMF'nin düzenleyici (03) ve etik kurul (04) bölgelerinde saklanmalı. | İK |

## 5. Elektronik veri toplama (EDC)

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-EDC-01 | eCRF formları CDASH uyumlu alan tanımlarıyla (tip, birim, aralık, zorunluluk, seçenek listesi, koşul) çalışma bazında tanımlanabilmeli; standart form kütüphanesi bulunmalı; veri girilmiş formda alan silme reddedilmeli ve sürüm artmalı. | GK |
| URS-EDC-02 | Veri girişinde aralık ve tutarlılık kontrolleri (edit check) anında çalışmalı; ihlal halinde otomatik sorgu açılmalı, kayıt engellenmemeli. | GK |
| URS-EDC-03 | Sorgu yaşam döngüsü (açık → cevaplandı → kapalı) ve açık kalma süresi izlenmeli; seçili sorgular toplu kapatılabilmeli. | GK |
| URS-EDC-04 | Form durumu taslak → tamamlandı → SDV → kilitli akışını izlemeli; veri yöneticisi çalışma/merkez/gönüllü kapsamında tek e-imza ile toplu kilit uygulayabilmeli; açık sorgulu, SDV'siz veya araştırmacı imzası olmayan kayıtlar kilitlenmemeli ve raporlanmalı; kilit yalnızca gerekçe ile açılabilmeli. | GK |
| URS-EDC-05 | Her veri değişikliği eski/yeni değer, kullanıcı, zaman ve gerekçe ile denetim izine yazılmalı. | GK |
| URS-EDC-06 | Vizit takvimi vizit şemasından randomizasyon tarihine göre oluşturulmalı; pencere dışı ve kaçırılan vizitler gerekçeyle işaretlenmeli. | GK |
| URS-EDC-07 | Veri CSV paketi ve CDISC ODM olarak dışa aktarılabilmeli; ODM'de vizit tanımları, merkezler, advers olay ve dispozisyon verisi bulunmalı; dışa aktarım denetim izine yazılmalı. | İK |
| URS-EDC-08 | Araştırmacı, gönüllü bazında tüm form kayıtlarını e-imza ile imzalayabilmeli; imzadan sonra değişen kayıt "imza yenilenmeli" olarak işaretlenmeli. | GK |
| URS-EDC-09 | Randomizasyon listesi blok ve strata ile üretilmeli, üretim e-imza istemeli; gönüllü kolu listeden atanmalı. | GK |

## 6. Güvenlik (farmakovijilans)

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-GV-01 | Advers olaylar terim, MedDRA kodu, başlangıç/bitiş, CTCAE derecesi, nedensellik, beklenirlik, ciddiyet ölçütü, sonuç ve alınan önlem ile kaydedilmeli; değişiklikler denetim izinde olmalı. | GK |
| URS-GV-02 | Sistem SUSAR kriterlerini (ciddi + beklenmeyen + ilişkili) otomatik tespit etmeli. | GK |
| URS-GV-03 | Ciddi advers olaylarda farkındalık tarihinden itibaren TİTCK bildirim süresi (7/15 gün) geri sayılmalı; süresi dolan ve 2 gün içinde dolacak bildirimler gece işinde sayılmalı. | GK |
| URS-GV-04 | Sponsor, TİTCK ve etik kurul bildirim tarihleri ayrı ayrı tutulmalı; geç bildirimler RBM göstergesine yansımalı. | GK |

## 7. Risk bazlı izlem

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-RBM-01 | ICH E6(R3) ile uyumlu hazır anahtar risk göstergesi (KRI) tanımları gelmeli; çalışma bazında eşik, yön ve ağırlık düzenlenebilmeli. | GK |
| URS-RBM-02 | Çalışma düzeyinde kalite tolerans limitleri (QTL) tanımlanmalı, güncel değer ve aşım durumu izlenmeli. | GK |
| URS-RBM-03 | KRI değerleri merkezler arası istatistiksel olarak karşılaştırılmalı (aykırı merkez tespiti); küçük örneklemde güven sınırlılığı belirtilmeli. | İK |
| URS-RBM-04 | Erken uyarı motoru eşik ve aykırılık ihlallerinde uyarı üretmeli; uyarı neden tetiklendiğini açıklamalı; aynı konuda açık uyarı varsa yenisi üretilmemeli; değer normale dönünce uyarı kapanmalı. | İK |
| URS-RBM-05 | Uyarılar atanabilmeli; açık → inceleniyor → kapandı / yanlış alarm akışı ve kapanış notu tutulmalı; aksiyon seviyesindeki uyarıdan tek tıkla tetiklenmiş ziyaret oluşturulabilmeli. | İK |
| URS-RBM-06 | Merkez başına bileşik risk puanı (0–100) hesaplanmalı ve izlem stratejisi önerisi sunulmalı. | İK |
| URS-RBM-07 | İzlem ziyaretleri (SIV, IMV, COV, uzaktan, tetiklenmiş) planlanmalı; ziyaret raporunda gerçekleşen tarih, katılımcılar, SDV oranı, kontrol listesi ve bulgular kaydedilmeli; rapor proje yöneticisi e-imzasıyla onaylanmalı ve onay sonrası değiştirilememeli; önceki ziyaretin açık bulguları yeni ziyarete taşınmalı; rapor yazdırılabilmeli. | İK |
| URS-RBM-08 | Protokol sapmaları kategori, önem, kök neden, düzeltici faaliyet, sorumlu, hedef tarih ve etik bildirim tarihiyle kaydedilmeli; majör sapma etik bildirim tarihi olmadan kapatılamamalı. | GK |

## 8. Protokol–hasta eşleştirme

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-ES-01 | Sistem, protokol kriterlerini (Türkçe ve İngilizce) hesaplanabilir sorguya dönüştürmeli; dönüşüm görülebilir, düzenlenebilir ve onaylanabilir olmalı. | GK |
| URS-ES-02 | Kimliksizleştirilmiş hasta kayıtları (yapısal veri + serbest metin) kriterlerle eşleştirilerek uygun / olası / uygun değil / belirsiz kararı ve 0–1 skor üretilmeli. | İK |
| URS-ES-03 | Her kriter sonucu için dayanak (yapısal veri alanı ya da kaynak metinden birebir cümle) gösterilmeli; dayanak gösterilemeyen sonuç "belirsiz" olmalı. | GK |
| URS-ES-04 | Eşleştirme önerisi, araştırmacı onayı olmadan gönüllü kaydı oluşturmamalı; onay/red/beklet kararı ve notu kaydedilmeli. | GK |
| URS-ES-05 | Kriter eşleştirmede duyarlılık altın standart sette ≥ %90 olmalı; ölçüm betiği sürüm paketine çıktı üretmeli. | İK |
| URS-ES-06 | Gölge mod: eşleştirme sonuçları manuel ön tarama kararlarıyla karşılaştırılarak duyarlılık, özgüllük, PPV raporlanabilmeli. | İK |

## 9. Türkçe Klinik BDM

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-BDM-01 | Model hastane içi sunucuda çalışmalı; uygulama ağı dış dünyaya kapalı olmalı. | GK |
| URS-BDM-02 | Model çıktıları deterministik olmalı (sıcaklık 0; aynı girdi → aynı çıktı). | GK |
| URS-BDM-03 | Modelin ürettiği kanıt cümlesi kaynak metinde birebir bulunmuyorsa sonuç reddedilmeli (halüsinasyon kontrolü). | GK |
| URS-BDM-04 | Model güveni eşik altındaysa sonuç "belirsiz" olarak işaretlenmeli ve insan incelemesine düşmeli. | GK |
| URS-BDM-05 | Model servisi erişilemezse sistem kural tabanlı değerlendirmeye düşmeli, bunu göstermeli ve loglamalı; eşleştirme durmamalı. | İK |
| URS-BDM-06 | Model sürümü her eşleştirme sonucuyla birlikte kaydedilmeli. | GK |
| URS-BDM-07 | İstemlere kimlik verisi (TCKN, telefon) girmesi engellenmeli. | GK |

## 10. Kimliksizleştirme ve hasta havuzu

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-KM-01 | Serbest metinlerde TCKN, ad-soyad, telefon, e-posta, adres, tarih, dosya/protokol numarası, kurum adı ve 89 üstü yaş tespit edilip maskelenmeli ya da takma adla değiştirilmeli; klinik terimler korunmalı. | GK |
| URS-KM-02 | Kimliksizleştirmeden geçmemiş serbest metin hasta tablosuna yazılamamalı (API ve CSV yükleme). | GK |
| URS-KM-03 | İkinci geçiş doğrulaması şüpheli kalıpları raporlamalı. | İK |
| URS-KM-04 | HBYS'den kimlik alanları (ad, adres, iletişim, kimlik numarası) hiç alınmamalı; takma ad anahtarlı tek yönlü özetle (HMAC-SHA256) üretilmeli; anahtar değişince takma adlar yeniden üretilebilmeli. | GK |
| URS-KM-05 | Çalışma kapanışından belirli bir süre sonra gönüllüye bağlanmamış hasta kayıtları silinmeli; veri sahibi talebinde tekil kayıt silinebilmeli ya da işleme kısıtlaması uygulanabilmeli; işlemler denetim izine yazılmalı. | GK |

## 11. TMF belge yönetimi

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-TMF-01 | Belgeler DIA TMF Referans Modeli bölgelerine göre sınıflandırılmalı; merkez bazlı (ISF) görünüm sunulmalı; tamlık onaylı ve eskimemiş belgelere göre hesaplanmalı. | İK |
| URS-TMF-02 | Her belge sürüm, durum (taslak/onaylı/eskimiş), yükleyen, zaman ve SHA-256 özeti ile saklanmalı; yeni sürüm yüklenince önceki belge eskimiş olmalı ve zincir tutulmalı; indirmede özet doğrulanmalı ve indirme denetim izine yazılmalı. | GK |
| URS-TMF-03 | Belge yükleme PDF, DOCX, XLSX, PNG, JPG biçimlerini 25 MB'a kadar desteklemeli; uzantı, bildirilen tür ve dosya içeriği birlikte kontrol edilmeli. | D |

## 12. Denetim izi ve elektronik imza

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-Dİ-01 | Tüm oluşturma, güncelleme, silme, giriş/çıkış, imza, dışa aktarma ve görüntüleme işlemleri kullanıcı, zaman, eski/yeni değer ve gerekçe ile kaydedilmeli. | GK |
| URS-Dİ-02 | Denetim izi uygulama ve veritabanı düzeyinde değiştirilemez ve silinemez olmalı. | GK |
| URS-Dİ-03 | Denetim izi kayıtları anahtarlı zincir özetiyle (HMAC, önceki kaydın özeti) bütünlük açısından doğrulanabilmeli; eşzamanlı kayıtlar zinciri bozmamalı; anahtar değişince doğrulama başarısız olmalı. | GK |
| URS-Dİ-04 | Denetçi rolü denetim izini filtreleyip CSV olarak dışa aktarabilmeli; dışa aktarma da kaydedilmeli. | GK |
| URS-Eİ-01 | Elektronik imza; imzalayanın adı, tarih-saat, imza anlamı ve imzalanan içeriğin özetini içermeli. | GK |
| URS-Eİ-02 | İmza anında kullanıcı kimliği (parola) yeniden doğrulanmalı. | GK |
| URS-Eİ-03 | İmzalanmış içerik değiştiğinde imza "yenilenmeli" olarak işaretlenmeli; imza içeriği özeti anahtardan bağımsız olmalı. | GK |

## 13. Yetkilendirme ve güvenlik

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-YT-01 | Rol bazlı erişim: sistem yöneticisi, sponsor, proje yöneticisi, CRA, araştırmacı, koordinatör, veri yöneticisi, biyoistatistikçi, farmakovijilans, denetçi; rol × sekme × rota matrisi belgeyle uyumlu olmalı (docs/roller.md). | GK |
| URS-YT-02 | Merkez kullanıcıları yalnızca kendi merkezlerinin verisini görebilmeli; sponsor kullanıcıları yalnızca kendi kurumunun çalışmalarını görmeli, gönüllü ve hasta verisine erişememeli. | GK |
| URS-YT-03 | Parola politikası: en az 12 karakter (harf ve rakam), 90 günde değişim, son 5 parola tekrar yasağı, 5 hatalı denemede 15 dakika süreli kilit (her yeni kilitte iki kat), IP başına deneme sınırı, ilk girişte parola değişimi, oturum süresi dolunca çıkış. | GK |
| URS-YT-04 | Kullanıcı hesapları silinmemeli, pasifleştirilmeli; geçmiş kayıtlardaki kullanıcı adı korunmalı. | GK |
| URS-YT-05 | CRO modunda proje ekibi çalışmaya atanabilmeli; ilk atama yapıldığında atanabilir roller yalnızca atandıkları çalışmaları görmeli. | İK |

## 14. Entegrasyon

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-ENT-01 | HBYS'den FHIR R4 (Patient, Condition, Observation, MedicationStatement, DocumentReference) ile hasta verisi alınabilmeli; eşitleme yetkili kullanıcı tarafından API üzerinden tetiklenmeli. | İK |
| URS-ENT-02 | Çalışma ve gönüllü verisi FHIR ResearchStudy / ResearchSubject olarak dışa verilebilmeli. | D |
| URS-ENT-03 | Hasta verisi OMOP CDM v5.4 tablolarına dışa aktarılabilmeli. | D |
| URS-ENT-04 | FHIR desteği olmayan HBYS'ler için CSV içe aktarma sağlanmalı; reddedilen satırlar sonuç ekranında listelenmeli. | İK |
| URS-ENT-05 | REST API, kullanıcıya bağlı ve iptal edilebilir anahtarla üçüncü taraf sistemlere açılabilmeli; API belgeleri ve OpenAPI şeması yalnızca oturumlu kullanıcıya sunulmalı. | D |
| URS-ENT-06 | Sorgu, gönüllü, ziyaret ve sapma listeleri mevcut filtrelerle CSV (noktalı virgül, UTF-8 BOM) olarak indirilebilmeli. | İK |

## 15. Sistem ve altyapı

| Kod | Gereksinim | Kritiklik |
|---|---|---|
| URS-SİS-01 | Sistem hastane içinde Docker Compose veya systemd ile kurulabilmeli; uygulama ağı dış dünyaya kapalı olmalı. | İK |
| URS-SİS-02 | Günlük şifreli yedekleme (age) ve belgelenmiş geri yükleme prosedürü olmalı; aylık arşiv 25 yıl saklanmalı; geri yükleme üç ayda bir prova edilmeli. | GK |
| URS-SİS-03 | İletişim TLS 1.2+ ile şifrelenmeli; güvenlik başlıkları uygulanmalı; veritabanı diskte şifreli bölümde tutulmalı. | GK |
| URS-SİS-04 | Zaman damgaları UTC saklanmalı. | GK |
| URS-SİS-05 | Anonim sağlık ucu sürüm/ortam bilgisi vermemeli; API belgeleri oturum istemeli; loglarda hasta verisi bulunmamalı. | GK |
| URS-SİS-06 | Ön analiz: betimleyici istatistik, kural tabanlı test seçimi, gönüllü akışı ve advers olay özeti; veri seti CSV; sponsor ve CRA erişemez. | İK |

## 16. Onaylar

| Rol | Ad / Unvan | İmza |
|---|---|---|
| Hazırlayan | Klinik Operasyon Direktörü | |
| Gözden geçiren | Yazılım Geliştirme Yöneticisi | |
| Onaylayan | Kalite Güvence Yöneticisi | |
