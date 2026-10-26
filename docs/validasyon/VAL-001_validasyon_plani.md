# VAL-001 Bilgisayarlı Sistem Validasyon Planı

| | |
|---|---|
| Belge No | VAL-001 |
| Sistem | EBM SmartClinical |
| Hazırlayan | Validasyon Sorumlusu (Yazılım Kalite) |
| Gözden geçiren | Yazılım Geliştirme Yöneticisi, Klinik Operasyon Direktörü |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Amaç

Bu plan, EBM SmartClinical klinik araştırma yönetim ve karar destek platformunun kullanım amacına
uygunluğunun belgelenmiş kanıtla gösterilmesi için izlenecek yaklaşımı, sorumlulukları, kapsamı ve
kabul ölçütlerini tanımlar. Yaklaşım GAMP 5, ICH E6(R3), 21 CFR Part 11, EU GMP Annex 11 ve TİTCK
İyi Klinik Uygulamaları Kılavuzu gereklilikleri temel alınarak oluşturulmuştur.

## 2. Kapsam

### 2.1 Kapsam içi

| Modül | GAMP kategorisi | Gerekçe |
|---|---|---|
| Çalışma yönetimi, kurulum sihirbazı, merkez yönetimi, başvuru takibi, ekip | 5 (özel geliştirilmiş) | Uygulama kodu |
| Elektronik veri toplama (eCRF, sorgu, SDV, araştırmacı imzası, toplu kilit, randomizasyon) | 5 | GCP açısından kritik; kaynak veri bütünlüğü |
| Güvenlik (AE/SAE, SUSAR tespiti, bildirim süreleri) | 5 | Mevzuat bildirim sürelerini hesaplar |
| Risk bazlı izlem (KRI, QTL, uyarılar, ziyaret raporu, sapma kapatma) | 5 | İzlem kararlarını yönlendirir |
| Denetim izi, elektronik imza, yetkilendirme | 5 | Part 11 / Annex 11 doğrudan kapsamı |
| Protokol–hasta eşleştirme motoru ve Türkçe Klinik BDM | 5 (+ yapay zekâ ek değerlendirmesi, bölüm 6) | Karar destek; insan onayı olmadan hasta kaydı yapmaz |
| Merkez zekâsı (kazanım ve gecikme tahmini), gece işleri | 5 | Planlama kararlarını destekler |
| Kimliksizleştirme, hasta havuzu saklama | 5 | KVKK uyumunun teknik tedbiri |
| TMF belge yönetimi, dışa aktarımlar (CSV, ODM, OMOP) | 5 | Temel belge ve veri bütünlüğü |
| PostgreSQL 16, nginx, Docker, Linux, age | 1 (altyapı) | Standart yazılımlar; kurulum kalifikasyonu ile doğrulanır |
| Ollama / llama.cpp çalışma zamanı | 1 | Model sunucu altyapısı |

### 2.2 Kapsam dışı

- HBYS'nin kendisi (hastane sorumluluğunda; yalnızca arayüz doğrulanır).
- Model eğitim boru hattı (`ml/`): üretim sistemi değildir; model sürümleri çıktı kalitesi üzerinden (bölüm 6) nitelendirilir.

## 3. Sistem tanımı

SmartClinical, klinik araştırmaların tasarımdan arşive kadar yaşam döngüsünü tek platformda yöneten
web tabanlı bir uygulamadır; CRO, tekil araştırmacı ve üniversite kullanım modlarını aynı kodla destekler.
Mimari: Python/FastAPI uygulama katmanı, PostgreSQL veritabanı, nginx ters vekil, isteğe bağlı hastane içi
Türkçe klinik büyük dil modeli (BDM) servisi. Ayrıntı: FRS-001 bölüm 2 ve docs/mimari.md.

Kullanım amacı: Sponsor, CRO ve araştırma merkezlerinin ICH-GCP ve ulusal mevzuata uygun biçimde çalışma
yürütmesini desteklemek; yapay zekâ bileşenleri aracılığıyla hasta ön taramasını, merkez seçimini ve risk
tespitini hızlandırmak. Yapay zekâ çıktıları her zaman yetkili kullanıcı onayı gerektiren önerilerdir.

## 4. Validasyon yaklaşımı

Risk temelli V-model uygulanır:

```
URS-001 ─────────────────────────────── PQ-001
   FRS-001 ───────────────────────── OQ-001
      Tasarım (kod, docs/mimari.md) ─ IQ-001
            Otomatik testler (tests/, CI)
```

- **Gereksinimler** URS-001'de tanımlanır, kritiklik atanır.
- **Risk analizi** RA-001'de FMEA ile yapılır; yüksek riskli fonksiyonlar için olumsuz senaryo testi uygulanır.
- **Tedarikçi değerlendirmesi**: EBM kendi geliştiricisi olduğundan yazılım yaşam döngüsü prosedürü ve kod inceleme kayıtları dayanak alınır.
- **Otomatik testler**: `python -m pytest` ve `ruff` her değişiklikte çalışır; TM-001'deki her satır bir test ya da rotaya bağlıdır ve `tests/test_P3.py::test_izlenebilirlik_matrisi_kodla_eslesir` belgeyle kodu karşılaştırır.
- **Kalifikasyon**: IQ (kurulum), OQ (fonksiyonel, URS izlenebilir), PQ (gerçek operasyon verisiyle, gölge mod).

## 5. Roller ve sorumluluklar

| Rol | Sorumluluk |
|---|---|
| Sistem sahibi (Klinik Operasyon Direktörü) | URS onayı, PQ kabulü, kullanım politikası |
| Validasyon sorumlusu | Plan, protokoller, raporlar, izlenebilirlik |
| Yazılım geliştirme yöneticisi | FRS, tasarım, otomatik testler, sapma düzeltmeleri |
| Kalite güvence | Bağımsız gözden geçirme ve onay, sapma kapatma |
| BT (hastane) | IQ'da altyapı adımları, yedekleme, anahtar kasası |
| Klinik uzman (tıbbi direktör) | Altın standart etiketleme, yapay zekâ çıktı kabulü |
| Test uygulayıcıları | OQ/PQ senaryolarını koşar; geliştirme ekibinden bağımsızdır |

## 6. Yapay zekâ bileşenlerine özel yaklaşım

1. **Sabit değerlendirme seti**: Klinisyen etiketli altın standart (`ml/degerlendirme/`); her model sürümü aynı set üzerinde ölçülür.
2. **Kabul eşikleri**: Kriter eşleştirme duyarlılığı ≥ %90; halüsinasyon oranı ≤ %2; kazanım tahmini MAPE ≤ %25; gecikme riski AUC ≥ 0,80.
3. **Deterministik çalıştırma**: Üretimde sıcaklık 0 (OQ-25).
4. **İnsan-döngüde kontrol**: Yapay zekâ çıktısı hiçbir GCP kaydını kullanıcı onayı olmadan değiştiremez (OQ-23).
5. **Gölge mod PQ**: Platform önerileri manuel ön tarama sonuçlarıyla körleştirilmiş biçimde karşılaştırılır (PQ-001).
6. **Model değişiklik kontrolü**: Yeni model sürümü = yazılım değişikliği; değişiklik kaydı, altın standart yeniden değerlendirme ve kısaltılmış OQ.
7. **Sürekli izleme**: Üretimde belirsiz oranı, kullanıcı red oranı ve yanıt süresi aylık raporlanır.

## 7. Kabul ölçütleri

- IQ: Tüm kontrol adımları "uygun"; sapma varsa kapatılmış ya da gerekçeli kabul.
- OQ: GCP-kritik senaryoların %100'ü, diğer senaryoların ≥ %95'i geçmiş; başarısız senaryolar için düzeltme ve yeniden test tamamlanmış.
- PQ: Bölüm 6'daki eşikler sağlanmış; kullanıcı anketi ortalaması ≥ 68 (SUS); kritik kullanılabilirlik bulgusu yok.
- Açık sapma yok ya da tümü risk değerlendirmesiyle kabul edilmiş.

## 8. Sapma yönetimi

Test sırasında beklenen sonuçtan sapmalar SAP-xxx numarasıyla kaydedilir; sınıflandırma: kritik (GCP verisi
etkilenir), majör (fonksiyon çalışmıyor), minör (kozmetik, iş akışı). Kritik ve majör sapmalar kapatılmadan
sistem üretime alınmaz.

## 9. Değişiklik kontrolü ve yeniden validasyon

Üretime alındıktan sonra her değişiklik değişiklik kontrol prosedürüne göre değerlendirilir. Etki analizine göre:
yama → ilgili OQ senaryoları; küçük sürüm → kısmi OQ + TM-001 güncellemesi; büyük sürüm → tam döngü.
Şema değişiklikleri otomatik uygulanmaz; sürüm notlarındaki SQL ve `sema` adımıyla uygulanır (KUR-001 §9).
Periyodik gözden geçirme yılda bir yapılır.

## 10. Çıktılar

VAL-001 (bu belge), URS-001, FRS-001, RA-001, IQ-001, OQ-001, PQ-001, TM-001, 21 CFR Part 11 / Annex 11 uyum
değerlendirmesi, KVKK etki değerlendirmesi, Validasyon Özet Raporu.

## 11. Referanslar

ISPE GAMP 5 (2. baskı); ICH E6(R3) Good Clinical Practice; 21 CFR Part 11; EudraLex Vol. 4 Annex 11;
TİTCK Klinik Araştırmalar Hakkında Yönetmelik; KVKK (6698); IEC 62304; ISO/IEC 27001; EMA Guideline on
computerised systems and electronic data in clinical trials.
