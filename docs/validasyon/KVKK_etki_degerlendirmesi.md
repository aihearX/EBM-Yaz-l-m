# Kişisel Veri Koruma Etki Değerlendirmesi (KVKK / Veri Koruma Etki Analizi)

| | |
|---|---|
| Belge No | KVK-001 |
| Sistem | EBM SmartClinical v1.4 – hastane içi kurulum |
| Sürüm | 2.0 |
| Tarih | 2026-04-07 |
| Hazırlayan | KVKK Uyum Sorumlusu (EBM), Bilgi Güvenliği Sorumlusu |
| Görüş | Hukuk Müşaviri; Pilot hastane Veri Sorumlusu temsilcisi |
| Onaylayan | Genel Müdür |

## Revizyon geçmişi

| Sürüm | Tarih | Açıklama |
|---|---|---|
| 1.0 | 2025-05-20 | EDC ve çalışma yönetimi kapsamı |
| 2.0 | 2026-04-07 | HBYS entegrasyonu, kimliksizleştirme, BDM ile serbest metin işleme ve eşleştirme kapsamı |

## 1. Amaç ve dayanak

6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK), Kişisel Sağlık Verileri Hakkında
Yönetmelik, Klinik Araştırmalar Hakkında Yönetmelik ve KVKK Kurulu'nun özel nitelikli
kişisel verilerin işlenmesinde alınacak yeterli önlemlere ilişkin 2018/10 sayılı kararı
çerçevesinde, SmartClinical ile yapılan işleme faaliyetinin risklerini ve alınan
tedbirleri değerlendirmek.

Sağlık verisi özel nitelikli kişisel veridir (KVKK m.6). Protokol–hasta eşleştirme
işlevi, hasta henüz çalışmaya onam vermeden önce HBYS kayıtlarını değerlendirdiği için
en yüksek riskli işleme faaliyetidir ve bu belgenin odağındadır.

## 2. Roller

| Rol | Taraf | Açıklama |
|---|---|---|
| Veri sorumlusu (HBYS verisi) | Hastane | HBYS'deki hasta verilerinin sahibi; ön tarama amacıyla kurum içi işlemeye karar verir |
| Veri sorumlusu (çalışma verisi) | Sponsor | Onam sonrası toplanan çalışma verisi |
| Veri işleyen | EBM (CRO) | Sponsor adına çalışma verisini işler; hastane içi kurulumda HBYS verisine EBM personeli erişmez |
| Veri işleyen (altyapı) | Hastane BT | Sunucu ve yedek yönetimi |

Hastane içi kurulumda **hiçbir hasta verisi hastane dışına çıkmaz**; EBM yalnızca
kimliksiz, toplulaştırılmış operasyon metriklerine (merkez başına kazanım sayısı, KRI
değerleri) erişir. SaaS kurulumunda yalnızca onam sonrası, gönüllü numarasıyla
takma adlandırılmış çalışma verisi EBM veri merkezinde işlenir; HBYS entegrasyonu ve
eşleştirme SaaS modelinde sunulmaz.

## 3. Veri envanteri

| Veri kategorisi | Kaynak | Alanlar | Kimlik durumu | Saklama | Hukuki dayanak |
|---|---|---|---|---|---|
| HBYS hasta kayıtları (ön tarama) | HBYS FHIR | Doğum yılı, cinsiyet, tanı kodları, ilaçlar, laboratuvar, vital, performans, serbest metin raporlar | Takma ad (SHA-256 + kurum tuzu); serbest metin kimliksizleştirilmiş; ad, TCKN, adres, iletişim hiç alınmaz | Çalışma kayıt dönemi + 6 ay; sonra silinir | KVKK m.6/3: sağlık verisi, sır saklama yükümlülüğü altındaki kişiler (hastane hekimleri) tarafından tedavi ve sağlık hizmetlerinin planlanması amacıyla; Kişisel Sağlık Verileri Yönetmeliği m.5; hastane kurum içi işleme kararı |
| Takma ad anahtar listesi | Hastane | kayit_no ↔ HBYS hasta no | Kimlikli | Hastane tarafında, SmartClinical dışında, yalnızca araştırmacı erişimi | Hastane iç prosedürü |
| Gönüllü çalışma verisi (onam sonrası) | eCRF | Gönüllü no, vizit, klinik ölçümler, AE | Takma ad (gönüllü no) | Çalışma bitimi + 25 yıl (İKU Yönetmeliği) | Açık rıza (bilgilendirilmiş onam formu, KVKK bölümü) |
| Advers olay bildirimi | eCRF | Olay, tarihler, sonuç | Takma ad | 25 yıl | Mevzuat yükümlülüğü (Klinik Araştırmalar Yönetmeliği) |
| Kullanıcı verileri | Sistem | Ad-soyad, e-posta, rol, giriş kayıtları | Kimlikli | Hesap + 10 yıl (denetim izi) | Sözleşme / meşru menfaat; mevzuat (denetim izi) |
| Denetim izi | Sistem | Kullanıcı, işlem, zaman, eski/yeni değer | Kimlikli (kullanıcı), takma ad (gönüllü) | 25 yıl | Mevzuat yükümlülüğü |
| Araştırmacı bilgileri | TMF | CV, GCP sertifikası | Kimlikli | Çalışma + 25 yıl | Mevzuat yükümlülüğü |
| Model eğitim derlemi | Hastane arşivi | Kimliksizleştirilmiş serbest metin | Anonim hedefli (kimliksizleştirme + ikinci geçiş + elle örneklem) | Proje süresi | Hastane etik kurul kararı; bilimsel araştırma istisnası (KVKK m.28/1-c) için anonimleştirme |

## 4. İşleme akışı (ön tarama)

```
HBYS ──FHIR (salt okunur, tanı koduna göre süzülmüş)──> fhir.bundle_to_hasta
        (ad/adres/iletişim/kimlik alanları okunmaz; kayit_no = sha256(hbys_id + tuz))
                                   │
                        kimliksizlestirme.kimliksizlestir (serbest metin)
                                   │  ikinci geçiş: metni_dogrula → şüpheli ise inceleme kuyruğu
                                   ▼
                              Hasta tablosu (kimliksiz)
                                   │
                        eslestirme + BDM (hastane içi sunucu, dış ağ kapalı)
                                   │
                        Araştırmacı inceleme (kanıtlı öneri)  ──onay──> anahtar listesiyle hastaya ulaşım,
                                                                         bilgilendirilmiş onam süreci
```

Araştırmacı, platformun önerdiği takma adlı kaydı hastane tarafındaki anahtar listesiyle
gerçek hastaya eşler; bu adım SmartClinical dışında, hastanenin mevcut ön tarama
pratiğinin parçasıdır ve hekim-hasta ilişkisi içinde kalır.

## 5. Risk değerlendirmesi

| No | Risk | Olasılık | Etki | Tedbir | Artık risk |
|---|---|---|---|---|---|
| K-1 | Serbest metinde kimlik verisi kalması | Orta | Yüksek | Çok katmanlı kimliksizleştirme, ikinci geçiş, aylık 100 metin elle denetim, kaçak = sapma | Düşük |
| K-2 | Takma adın geri çözülmesi | Düşük | Yüksek | SHA-256 + kurum tuzu (hastane HSM/anahtar kasasında); anahtar listesi sistem dışında | Düşük |
| K-3 | Verinin kurum dışına çıkması | Düşük | Çok yüksek | Hastane içi kurulum; BDM dış ağ kapalı; dış adres yapılandırması reddedilir; SMTP bildirimleri hasta verisi içermez | Çok düşük |
| K-4 | Amaç dışı erişim (sponsor/EBM personeli hasta metnini görür) | Orta | Yüksek | Rol bazlı alan maskeleme; sponsor rolü metin göremez; EBM personeline hastane içi kurulumda hesap açılmaz (yalnızca destek, geçici, loglu) | Düşük |
| K-5 | Onam öncesi işlemenin hukuki dayanağının tartışmalı olması | Orta | Yüksek | Hastane veri sorumlusu kararı ve etik kurul bilgilendirmesi; işleme hastanenin kendi hekimleri adına; aydınlatma metinlerine "klinik araştırma uygunluk değerlendirmesi" amacı eklenmesi önerisi | Orta (hukuki görüş alındı, izlenecek) |
| K-6 | Saklama süresinin aşılması | Orta | Orta | Otomatik silme işi (çalışma kayıt kapanışı + 6 ay); silme denetim izinde | Düşük |
| K-7 | Denetim izinde kimlikli kullanıcı verisi | Düşük | Düşük | Mevzuat yükümlülüğü; erişim denetçi/yönetici ile sınırlı | Düşük |
| K-8 | Model eğitim derleminde kimlik verisi | Orta | Yüksek | Kimliksizleştirme + ikinci geçiş + %5 elle örneklem; eğitim kapalı ağda; model ağırlıkları ezberleme testi (membership inference, kanarya dizileri) | Düşük |
| K-9 | Veri ihlali (sunucu ele geçirilmesi) | Düşük | Çok yüksek | LUKS, TLS, sertleştirilmiş nginx, yıllık sızma testi, log izleme, 72 saat içinde Kurul'a bildirim prosedürü (SOP-OY-02) | Düşük |

## 6. Teknik ve idari tedbirler (2018/10 sayılı Kurul kararı ile eşleme)

| Karar maddesi | Tedbir |
|---|---|
| Politika ve prosedür | KVKK politikası, SOP-KV-01 (özel nitelikli veri), SOP-OY-02 (ihlal) |
| Eğitim ve gizlilik taahhüdü | Tüm kullanıcılar için KVKK eğitimi, kullanıcı sözleşmesinde gizlilik |
| Yetki matrisi ve erişim kayıtları | Rol bazlı yetki; denetim izi; periyodik erişim gözden geçirme (6 ay) |
| Şifreleme (iletim ve saklama) | TLS 1.2+; LUKS; yedekler şifreli |
| İki aşamalı doğrulama (uzaktan erişim) | VPN + hastane MFA (SaaS kurulumunda uygulama düzeyinde TOTP, v1.5) |
| Güvenlik testleri | Yıllık sızma testi; sürüm öncesi SAST/DAST |
| Yedekleme ve kurtarma | Günlük; üç aylık prova |
| Fiziksel güvenlik | Hastane veri merkezi (hastane sorumluluğu) |

## 7. Veri sahibi hakları

Takma adlı HBYS kayıtlarında veri sahibi başvurusu hastaneye yapılır; hastane anahtar
listesi üzerinden kaydı bulup silme/düzeltme talebini SmartClinical yöneticisine iletir.
Silme işlemi denetim izine yazılır; gönüllü kayıtlarında mevzuat gereği silme yerine
işleme kısıtlaması uygulanır ve veri sahibi bilgilendirilir.

## 8. Sonuç ve öneriler

İşleme faaliyeti, alınan teknik ve idari tedbirlerle KVKK'ya uygun şekilde
yürütülebilir. K-5 için hastanelerin hasta aydınlatma metinlerine klinik araştırma
uygunluk değerlendirmesi amacının eklenmesi ve işlemenin hastane iç kararı ile
belgelenmesi şarttır; pilot sözleşmelerine bu madde eklenmiştir. Bu değerlendirme her
yeni pilot merkez ve her büyük sürümde güncellenir.

## 9. Onaylar

| Rol | İmza | Tarih |
|---|---|---|
| KVKK Uyum Sorumlusu | e-imza | 2026-04-01 |
| Hukuk Müşaviri (görüş) | e-imza | 2026-04-03 |
| Bilgi Güvenliği Sorumlusu | e-imza | 2026-04-03 |
| Genel Müdür | e-imza | 2026-04-07 |
