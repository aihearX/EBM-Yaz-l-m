# VAL-001 Bilgisayarlı Sistem Validasyon Planı

| | |
|---|---|
| Belge No | VAL-001 |
| Sistem | EBM SmartClinical v1.4 |
| Sürüm | 2.0 |
| Yürürlük tarihi | 2026-02-10 |
| Hazırlayan | Validasyon Sorumlusu (Yazılım Kalite) |
| Gözden geçiren | Yazılım Geliştirme Yöneticisi, Klinik Operasyon Direktörü |
| Onaylayan | Kalite Güvence Yöneticisi |

## Revizyon geçmişi

| Sürüm | Tarih | Açıklama |
|---|---|---|
| 1.0 | 2025-04-18 | İlk yayın (v1.2 için) |
| 1.1 | 2025-09-02 | RBM modülü ve e-imza kapsamı eklendi (v1.3) |
| 2.0 | 2026-02-10 | Yapay zekâ bileşenleri (BDM, eşleştirme, merkez zekâsı) kapsama alındı; gölge mod PQ yaklaşımı tanımlandı (v1.4) |

## 1. Amaç

Bu plan, EBM SmartClinical klinik araştırma yönetim ve karar destek platformunun
kullanım amacına uygunluğunun belgelenmiş kanıtla gösterilmesi için izlenecek
yaklaşımı, sorumlulukları, kapsamı ve kabul ölçütlerini tanımlar. Validasyon
yaklaşımı GAMP 5 (2. baskı, 2022), ICH E6(R3), 21 CFR Part 11, EU GMP Annex 11 ve
TİTCK İyi Klinik Uygulamaları Kılavuzu gereklilikleri temel alınarak oluşturulmuştur.

## 2. Kapsam

### 2.1 Kapsam içi

| Modül | GAMP kategorisi | Gerekçe |
|---|---|---|
| Çalışma yönetimi, merkez yönetimi, başvuru takibi | 5 (özel geliştirilmiş) | EBM tarafından geliştirilen uygulama kodu |
| Elektronik veri toplama (eCRF, sorgu, SDV, kilit) | 5 | GCP açısından kritik; kaynak veri bütünlüğü |
| Güvenlik (AE/SAE, SUSAR tespiti, bildirim süreleri) | 5 | Mevzuat bildirim sürelerini hesaplar |
| Risk bazlı izlem (KRI, QTL, uyarılar) | 5 | ICH E6(R3) izlem kararlarını yönlendirir |
| Denetim izi, elektronik imza, yetkilendirme | 5 | Part 11 / Annex 11 doğrudan kapsamı |
| Protokol–hasta eşleştirme motoru ve Türkçe Klinik BDM | 5 (+ yapay zekâ ek değerlendirmesi, bkz. bölüm 6) | Karar destek; insan onayı olmadan hasta kaydı yapmaz |
| Merkez zekâsı (kazanım ve gecikme tahmini) | 5 | Planlama kararlarını destekler; GCP verisine doğrudan yazmaz |
| Kimliksizleştirme aracı | 5 | KVKK uyumunun teknik tedbiri |
| TMF belge yönetimi | 5 | Temel belge bütünlüğü |
| PostgreSQL 16, nginx, Docker, Linux | 1 (altyapı) | Standart, yaygın kullanılan yazılımlar; kurulum kalifikasyonu ile doğrulanır |
| Ollama / llama.cpp çalışma zamanı | 1 | Model sunucu altyapısı |

### 2.2 Kapsam dışı

- HBYS'nin kendisi (hastane sorumluluğunda; yalnızca arayüz doğrulanır).
- EBM'nin iç proje muhasebe sistemi (SmartClinical'a yalnızca salt okunur bağlanır).
- Model eğitim boru hattı (`ml/`): üretim sistemi değildir; model sürümleri çıktı
  kalitesi üzerinden (bölüm 6) nitelendirilir.

## 3. Sistem tanımı

SmartClinical, klinik araştırmaların tasarımdan arşive kadar tüm yaşam döngüsünü tek
platformda yöneten web tabanlı bir uygulamadır. Hastane içinde ya da EBM veri merkezinde
çalışır. Mimari: Python/FastAPI uygulama katmanı, PostgreSQL veritabanı, nginx ters vekil,
hastane içi çalışan Türkçe klinik büyük dil modeli (BDM) servisi. Sistem tanımının ayrıntısı
için FRS-001 bölüm 2'ye bakınız.

Kullanım amacı: Sponsor, CRO ve araştırma merkezlerinin ICH-GCP ve ulusal mevzuata uygun
biçimde çalışma yürütmesini desteklemek; yapay zekâ bileşenleri aracılığıyla hasta ön
taramasını, merkez seçimini ve risk tespitini hızlandırmak. Yapay zekâ çıktıları her zaman
yetkili kullanıcı onayı gerektiren önerilerdir.

## 4. Validasyon yaklaşımı

Risk temelli V-model uygulanır:

```
URS-001 ─────────────────────────────── PQ-001
   FRS-001 ───────────────────────── OQ-001
      Tasarım (DS, kod) ────────── IQ-001
            Birim/entegrasyon testleri (CI)
```

- **Gereksinimler** URS-001'de tanımlanır, kritiklik (GCP-kritik / iş-kritik / destekleyici) atanır.
- **Risk analizi** RA-001'de FMEA ile yapılır; yüksek riskli fonksiyonlar için ek test derinliği (sınır değer, olumsuz senaryolar, veri bütünlüğü) uygulanır.
- **Tedarikçi değerlendirmesi**: EBM kendi geliştiricisi olduğundan tedarikçi denetimi yerine yazılım yaşam döngüsü prosedürü (SOP-YZ-01, IEC 62304 uyumlu) ve kod inceleme kayıtları dayanak alınır.
- **Otomatik testler**: Her sürümde CI üzerinde çalışan birim ve entegrasyon testleri (pytest, >%80 satır kapsamı hedefi) tasarım doğrulamasının parçasıdır; test çıktıları sürüm paketine eklenir.
- **Kalifikasyon**: IQ (kurulum), OQ (fonksiyonel, URS izlenebilir), PQ (gerçek operasyon verisiyle, gölge mod).
- **İzlenebilirlik** TM-001 ile sağlanır.

## 5. Roller ve sorumluluklar

| Rol | Sorumluluk |
|---|---|
| Sistem sahibi (Klinik Operasyon Direktörü) | URS onayı, PQ kabulü, kullanım politikası |
| Validasyon sorumlusu | Plan, protokoller, raporlar, izlenebilirlik |
| Yazılım geliştirme yöneticisi | FRS, tasarım, birim testleri, sapma düzeltmeleri |
| Kalite güvence | Bağımsız gözden geçirme ve onay, sapma kapatma |
| BT (hastane) | IQ'da altyapı adımları, yedekleme |
| Klinik uzman (tıbbi direktör) | Altın standart etiketleme, yapay zekâ çıktı kabulü |
| Test uygulayıcıları | OQ/PQ senaryolarını koşar; geliştirme ekibinden bağımsız olmalıdır |

## 6. Yapay zekâ bileşenlerine özel yaklaşım

Deterministik olmayan bileşenler (BDM, eşleştirme, tahmin modelleri) için klasik
senaryo testine ek olarak:

1. **Sabit değerlendirme seti**: Klinisyen etiketli altın standart (çift etiketleme, kappa ≥ 0,80). Her model sürümü aynı set üzerinde ölçülür.
2. **Kabul eşikleri**: Kriter eşleştirme duyarlılığı ≥ %90; halüsinasyon (kaynakta olmayan kanıt) oranı ≤ %2; kazanım tahmini MAPE ≤ %25; gecikme riski AUC ≥ 0,80.
3. **Deterministik çalıştırma**: Üretimde sıcaklık 0; aynı girdi aynı çıktıyı verir (OQ-23 ile doğrulanır).
4. **İnsan-döngüde kontrol**: Yapay zekâ çıktısı sistemde hiçbir GCP kaydını (gönüllü durumu, uygunluk) kullanıcı onayı olmadan değiştiremez (OQ-20).
5. **Gölge mod PQ**: Pilot merkezlerde platform önerileri, manuel ön tarama sonuçlarıyla körleştirilmiş biçimde karşılaştırılır (PQ-001).
6. **Model değişiklik kontrolü**: Yeni model sürümü = yazılım değişikliği; DK kaydı, altın standart yeniden değerlendirme ve kısaltılmış OQ gerekir.
7. **Sürekli izleme**: Üretimde belirsiz oranı, kullanıcı red oranı ve yanıt süresi aylık raporlanır; eşik dışına çıkınca sapma açılır.

## 7. Kabul ölçütleri

- IQ: Tüm kontrol adımları "uygun"; sapma varsa kapatılmış ya da gerekçeli kabul.
- OQ: GCP-kritik senaryoların %100'ü, diğer senaryoların ≥ %95'i geçmiş; başarısız senaryolar için düzeltme ve yeniden test tamamlanmış.
- PQ: Bölüm 6'daki eşikler sağlanmış; pilot kullanıcı kabul anketi ortalaması ≥ 4/5; kritik kullanılabilirlik bulgusu yok.
- Açık sapma yok ya da tümü risk değerlendirmesiyle kabul edilmiş.

## 8. Sapma yönetimi

Test sırasında beklenen sonuçtan sapmalar SAP-xxx numarasıyla kaydedilir; sınıflandırma:
kritik (GCP verisi etkilenir, veri bütünlüğü), majör (fonksiyon çalışmıyor), minör
(kozmetik, iş akışı). Kritik ve majör sapmalar kapatılmadan sistem üretime alınmaz.

## 9. Değişiklik kontrolü ve yeniden validasyon

Üretime alındıktan sonra her değişiklik SOP-DK-03'e göre değerlendirilir. Etki analizi
sonucuna göre: yama sürümü (1.4.x) → ilgili OQ senaryoları; küçük sürüm (1.x) → kısmi
OQ + izlenebilirlik güncellemesi; büyük sürüm → tam validasyon döngüsü. Periyodik
gözden geçirme yılda bir yapılır.

## 10. Çıktılar

VAL-001 (bu belge), URS-001, FRS-001, RA-001, IQ-001, OQ-001, PQ-001, TM-001,
21CFR11/Annex11 uyum değerlendirmesi, KVKK etki değerlendirmesi, Validasyon Özet Raporu (VSR-001).

## 11. Referanslar

ISPE GAMP 5 (2. baskı); ICH E6(R3) Good Clinical Practice (2025); 21 CFR Part 11;
EudraLex Vol. 4 Annex 11; TİTCK Klinik Araştırmalar Hakkında Yönetmelik; KVKK (6698);
IEC 62304:2006+A1:2015; ISO/IEC 27001:2022; EMA Guideline on computerised systems and
electronic data in clinical trials (2023).
