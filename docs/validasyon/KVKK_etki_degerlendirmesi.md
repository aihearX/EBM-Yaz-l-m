# Kişisel Veri Koruma Etki Değerlendirmesi (KVKK)

| | |
|---|---|
| Belge No | KVK-001 |
| Sistem | EBM SmartClinical – hastane içi kurulum |
| Hazırlayan | KVKK Uyum Sorumlusu, Bilgi Güvenliği Sorumlusu |
| Görüş | Hukuk Müşaviri; hastane Veri Sorumlusu temsilcisi |
| Onaylayan | Genel Müdür |

## 1. Amaç ve dayanak

6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK), Kişisel Sağlık Verileri Hakkında Yönetmelik,
Klinik Araştırmalar Hakkında Yönetmelik ve KVKK Kurulu'nun özel nitelikli kişisel verilerin işlenmesinde
alınacak yeterli önlemlere ilişkin 2018/10 sayılı kararı çerçevesinde, SmartClinical ile yapılan işleme
faaliyetinin risklerini ve alınan tedbirleri değerlendirmek.

Sağlık verisi özel nitelikli kişisel veridir (KVKK m.6). Protokol–hasta eşleştirme işlevi, hasta henüz
çalışmaya onam vermeden önce HBYS kayıtlarını değerlendirdiği için en yüksek riskli işleme faaliyetidir
ve bu belgenin odağındadır. Teknik tedbirlerin her biri FRS-001'de koda bağlıdır.

## 2. Roller

| Rol | Taraf | Açıklama |
|---|---|---|
| Veri sorumlusu (HBYS verisi) | Hastane | HBYS'deki hasta verilerinin sahibi; ön tarama amacıyla kurum içi işlemeye karar verir |
| Veri sorumlusu (çalışma verisi) | Sponsor | Onam sonrası toplanan çalışma verisi |
| Veri işleyen | CRO | Sponsor adına çalışma verisini işler; hastane içi kurulumda HBYS verisine CRO personeli erişmez |
| Veri işleyen (altyapı) | Hastane BT | Sunucu, yedek ve anahtar kasası yönetimi |

Hastane içi kurulumda hiçbir hasta verisi hastane dışına çıkmaz; uygulama ağı dış dünyaya kapalıdır.
Sponsor rolü gönüllü ve hasta verisine erişemez; yalnızca kimliksiz operasyon özetlerini görür.

## 3. Veri envanteri

| Veri kategorisi | Kaynak | Alanlar | Kimlik durumu | Saklama | Hukuki dayanak |
|---|---|---|---|---|---|
| HBYS hasta kayıtları (ön tarama) | HBYS FHIR / CSV | Doğum yılı, cinsiyet, tanı kodları, ilaçlar, laboratuvar, vital, performans, serbest metin raporlar | Takma ad (HMAC-SHA256, anahtar kasada); serbest metin kimliksizleştirilmiş; ad, TCKN, adres, iletişim hiç alınmaz | Merkezin çalışması kapandıktan 6 ay sonra silinir (`hasta_saklama`) | KVKK m.6/3: sağlık verisi, sır saklama yükümlülüğü altındaki kişiler tarafından; Kişisel Sağlık Verileri Yönetmeliği m.5; hastane kurum içi işleme kararı |
| Takma ad anahtarı | Hastane | `SC_TAKMA_AD_ANAHTARI` | Gizli anahtar | Anahtar kasasında; değişimde yeniden anahtarlama | Hastane iç prosedürü |
| Gönüllü çalışma verisi (onam sonrası) | eCRF | Gönüllü no, vizit, klinik ölçümler, AE | Takma ad (gönüllü no) | Çalışma bitimi + 25 yıl (İKU Yönetmeliği) | Açık rıza (bilgilendirilmiş onam formu, KVKK bölümü) |
| Advers olay bildirimi | eCRF | Olay, tarihler, sonuç | Takma ad | 25 yıl | Mevzuat yükümlülüğü |
| Kullanıcı verileri | Sistem | Ad-soyad, e-posta, rol, giriş kayıtları | Kimlikli | Hesap + denetim izi süresi | Sözleşme / meşru menfaat; mevzuat (denetim izi) |
| Denetim izi | Sistem | Kullanıcı, işlem, zaman, eski/yeni değer | Kimlikli (kullanıcı), takma ad (gönüllü); hasta işlemlerinde takma ad yazılmaz | 25 yıl | Mevzuat yükümlülüğü |
| Araştırmacı bilgileri | TMF | CV, GCP sertifikası | Kimlikli | Çalışma + 25 yıl | Mevzuat yükümlülüğü |
| Model eğitim derlemi | Hastane arşivi | Kimliksizleştirilmiş serbest metin | Anonim hedefli (kimliksizleştirme + ikinci geçiş + örneklem) | Proje süresi | Hastane etik kurul kararı; bilimsel araştırma istisnası (KVKK m.28/1-c) için anonimleştirme |

## 4. İşleme akışı (ön tarama)

```
HBYS ──FHIR (salt okunur, elle tetiklenen eşitleme) / CSV yükleme──> fhir.bundle_to_hasta / hasta-yukle
        (ad/adres/iletişim/kimlik alanları okunmaz; kayit_no = HMAC(anahtar, merkez + hbys_id))
                                   │
                        kimliksizlestirme.kimliksizlestir (serbest metin)
                                   │  ikinci geçiş: metni_dogrula → şüpheli kalıp raporu
                                   ▼
                              Hasta tablosu (kimliksiz)
                                   │
                        eslestirme + BDM (hastane içi sunucu, internal ağ)
                                   │
                        Araştırmacı inceleme (kanıtlı öneri)  ──onay──> anahtar listesiyle hastaya ulaşım,
                                                                         bilgilendirilmiş onam süreci
```

Araştırmacı, platformun önerdiği takma adlı kaydı hastane tarafındaki anahtar listesiyle gerçek hastaya
eşler; bu adım SmartClinical dışında, hekim-hasta ilişkisi içinde kalır.

## 5. Risk değerlendirmesi

| No | Risk | Olasılık | Etki | Tedbir | Artık risk |
|---|---|---|---|---|---|
| K-1 | Serbest metinde kimlik verisi kalması | Orta | Yüksek | Çok katmanlı kimliksizleştirme, ikinci geçiş, yükleme sonucunda reddedilen satırların gözden geçirilmesi, kaçak = sapma | Düşük |
| K-2 | Takma adın geri çözülmesi | Düşük | Yüksek | HMAC-SHA256; anahtar hastane anahtar kasasında, veritabanında değil; anahtar listesi sistem dışında | Düşük |
| K-3 | Verinin kurum dışına çıkması | Düşük | Çok yüksek | Hastane içi kurulum; uygulama ağı internal; BDM dış ağ kapalı; e-posta gönderimi yok | Çok düşük |
| K-4 | Amaç dışı erişim (sponsor/CRO personeli hasta verisini görür) | Orta | Yüksek | Sponsor rolü gönüllü/hasta sayfalarına ve CSV uçlarına erişemez; merkez rolleri yalnızca kendi merkezi; CRO personeline hastane içi kurulumda hesap açılmaz | Düşük |
| K-5 | Onam öncesi işlemenin hukuki dayanağının tartışmalı olması | Orta | Yüksek | Hastane veri sorumlusu kararı ve etik kurul bilgilendirmesi; aydınlatma metinlerine "klinik araştırma uygunluk değerlendirmesi" amacı | Orta (izlenir) |
| K-6 | Saklama süresinin aşılması | Orta | Orta | `scripts/hasta_saklama.py` (kapanış + 6 ay); silme denetim izinde | Düşük |
| K-7 | Denetim izinde kimlikli kullanıcı verisi | Düşük | Düşük | Mevzuat yükümlülüğü; erişim denetçi/yönetici ile sınırlı | Düşük |
| K-8 | Model eğitim derleminde kimlik verisi | Orta | Yüksek | Kimliksizleştirme + ikinci geçiş + elle örneklem; eğitim kapalı ağda | Düşük |
| K-9 | Veri ihlali (sunucu ele geçirilmesi, yedek sızması) | Düşük | Çok yüksek | LUKS, TLS, sertleştirilmiş nginx, `age` şifreli yedek, anonim uçlarda bilgi yok, 72 saat içinde Kurul'a bildirim prosedürü | Düşük |

## 6. Teknik ve idari tedbirler (2018/10 sayılı Kurul kararı ile eşleme)

| Karar maddesi | Tedbir |
|---|---|
| Politika ve prosedür | KVKK politikası, özel nitelikli veri ve ihlal SOP'ları |
| Eğitim ve gizlilik taahhüdü | Tüm kullanıcılar için KVKK eğitimi, kullanıcı sözleşmesinde gizlilik |
| Yetki matrisi ve erişim kayıtları | Rol bazlı yetki; denetim izi (görüntüleme dahil); periyodik erişim gözden geçirme (6 ay) |
| Şifreleme (iletim ve saklama) | TLS 1.2+; LUKS; yedekler `age` ile şifreli |
| İki aşamalı doğrulama (uzaktan erişim) | Hastane VPN ve hastane MFA'sı; uygulama düzeyinde ikinci faktör yoktur |
| Güvenlik testleri | Sızma testi; sürüm öncesi statik analiz (ruff) ve otomatik testler |
| Yedekleme ve kurtarma | Günlük; üç aylık prova |
| Fiziksel güvenlik | Hastane veri merkezi (hastane sorumluluğu) |

## 7. Veri sahibi hakları

Takma adlı HBYS kayıtlarında veri sahibi başvurusu hastaneye yapılır; hastane anahtar listesi üzerinden kaydı
bulup silme/düzeltme talebini sistem yöneticisine iletir. Yönetici `python -m smartclinical.scripts.hasta_saklama --kayit-no <takma ad>`
ile bağlantısız kaydı siler; gönüllüye bağlı kayıtlarda mevzuat gereği silme yerine işleme kısıtlaması
(`--kisitla`: klinik içerik boşaltılır, kayıt eşleştirmeye girmez) uygulanır ve veri sahibi bilgilendirilir.
İşlem denetim izine yazılır; denetim kaydında takma ad bulunmaz.

## 8. Sonuç ve öneriler

İşleme faaliyeti, alınan teknik ve idari tedbirlerle KVKK'ya uygun şekilde yürütülebilir. K-5 için hastanelerin
hasta aydınlatma metinlerine klinik araştırma uygunluk değerlendirmesi amacının eklenmesi ve işlemenin hastane
iç kararı ile belgelenmesi şarttır. Bu değerlendirme her yeni kurulumda ve her büyük sürümde güncellenir.

## 9. Onaylar

| Rol | İmza |
|---|---|
| KVKK Uyum Sorumlusu | |
| Hukuk Müşaviri (görüş) | |
| Bilgi Güvenliği Sorumlusu | |
| Genel Müdür | |
