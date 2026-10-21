# PQ-001 Performans Kalifikasyonu Protokolü – Gölge Mod Pilotu

| | |
|---|---|
| Belge No | PQ-001 |
| Sistem | EBM SmartClinical v1.4.x |
| Sürüm | 1.0 (protokol) |
| Protokol onayı | 2026-06-16 |
| Planlanan uygulama | 2026-07 – 2026-12 (pilot merkezler), rapor 2027-01 |
| Sorumlu | Klinik Operasyon Direktörü (sistem sahibi) |
| Gözden geçiren | Validasyon Sorumlusu, Tıbbi Direktör |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Amaç

Sistemin gerçek operasyon ortamında, gerçek kullanıcılar ve gerçek (kimliksizleştirilmiş)
verilerle kullanım amacını karşıladığını göstermek. Deterministik fonksiyonlar OQ'da
doğrulandığından PQ, yapay zekâ bileşenlerinin saha performansına ve uçtan uca iş
akışlarına odaklanır.

## 2. Pilot tasarımı

| Parametre | Değer |
|---|---|
| Merkezler | Pilot 1: Üniversite hastanesi (onkoloji); Pilot 2: Eğitim ve araştırma hastanesi (kardiyoloji, endokrinoloji); Pilot 3: Şehir hastanesi (göğüs hastalıkları) |
| Çalışmalar | EBM'nin yürüttüğü, kayıt aşamasındaki 4 çalışma (2 ilaç faz III, 1 tıbbi cihaz, 1 gözlemsel) |
| Süre | 6 ay |
| Mod | Gölge mod: platform önerileri araştırmacıdan körleştirilir; manuel ön tarama rutin şekilde yapılır; karşılaştırma aylık yapılır |
| Etik | Hastane etik kurulu bilgilendirme/onayı (retrospektif kimliksiz veri + prospektif kullanılabilirlik anketi) |
| Veri | HBYS FHIR senkronu, tanı koduna göre ön filtrelenmiş hastalar; tüm metinler kimliksizleştirilmiş |

## 3. Ölçütler ve kabul eşikleri

| No | Ölçüt | Tanım | Eşik | URS |
|---|---|---|---|---|
| PQ-M1 | Eşleştirme duyarlılığı | Manuel taramada uygun bulunanlar içinde platformun "uygun" veya "olası" dediği oran | ≥ %90 | ES-05 |
| PQ-M2 | Eşleştirme özgüllüğü | Manuel taramada uygun olmayanlar içinde platformun "uygun değil" dediği oran | ≥ %70 (raporlanır) | ES-06 |
| PQ-M3 | Pozitif öngörü değeri | Platform "uygun" dediklerinin manuelde uygun çıkma oranı | ≥ %60 | ES-06 |
| PQ-M4 | Ön tarama süresi | Hasta başına koordinatör ön tarama süresi: platform listesiyle vs. manuel (zaman etüdü, 2 ay ortalaması) | ≥ %50 azalma | Proje hedefi |
| PQ-M5 | Halüsinasyon | Rastgele 200 kanıt cümlesi klinisyen kontrolü: kaynakta yok oranı | ≤ %2 | BDM-03 |
| PQ-M6 | Belirsiz oranı | Kriter sonuçları içinde "belirsiz" | ≤ %25 (raporlanır; yüksekse veri kalitesi analizi) | – |
| PQ-M7 | Kazanım tahmini MAPE | Pilot merkezler için 3. ayda yapılan 3 aylık tahmin vs gerçekleşen | ≤ %25 | MZ-03 |
| PQ-M8 | Gecikme riski AUC | Pilot dönemde aktive olan 12+ merkez için hedef aşımı tahmini | ≥ 0,80 | MZ-04 |
| PQ-M9 | RBM uyarı kesinliği | Açılan uyarılar içinde CRA'nın "gerçek sorun" olarak kapattığı oran | ≥ %60 | RBM-04 |
| PQ-M10 | Kimliksizleştirme kaçak | Aylık 100 rastgele metin elle denetim | 0 kimlik verisi | KM-01 |
| PQ-M11 | Kullanılabilirlik | SUS anketi (araştırmacı, koordinatör, CRA; n ≥ 15) | Ortalama ≥ 68; kritik bulgu yok | ÇY-06 |
| PQ-M12 | Kullanılabilirlik (sistem) | p95 sayfa yanıtı (BDM hariç), kesinti süresi | ≤ 2 sn; ≤ %0,5 | SİS-04 |

## 4. Yöntem

1. **Körleştirme**: Gölge mod kayıtları `golge_mod=True` ile saklanır; araştırmacı arayüzünde görünmez. Manuel ön tarama kararı koordinatör tarafından sisteme bağımsız girilir (manuel karar formu).
2. **Karşılaştırma**: Ay sonunda validasyon sorumlusu `golge_mod_karsilastir` raporunu alır; uyumsuz vakalar tıbbi direktör tarafından incelenir ve kök neden sınıflandırılır (veri eksik / kriter yapılandırma / model hatası / manuel hata).
3. **Zaman etüdü**: 1. ve 2. ayda manuel, 4. ve 5. ayda platform destekli ön tarama süresi kronometre ile; koordinatör başına ≥ 30 hasta.
4. **Kalibrasyon**: 3. ay sonunda kriter yapılandırma ve eşikler gözden geçirilebilir; değişiklik DK kaydıyla yapılır ve sonraki aylar ayrı raporlanır.
5. **Güvenlik sinyali**: Pilot süresince platform kaynaklı herhangi bir hatalı kayıt/onam olayı derhal sapma olarak açılır ve pilot durdurma kriteri değerlendirilir.

## 5. Durdurma kriterleri

- Kimlik verisi sızıntısı (PQ-M10 ihlali) → pilot derhal durdurulur, KVKK prosedürü işletilir.
- İki ardışık ayda duyarlılık < %75 → eşleştirme bileşeni pilotta askıya alınır, kök neden analizi.

## 6. Raporlama

PQ raporu (PQ-001-R) ölçüt tablosunu, uyumsuz vaka analizini, kullanıcı anketi
sonuçlarını, açık sapmaları ve üretim kullanımı önerisini içerir. Sonuçlar ayrıca
Ar-Ge programı Faz 5 ilerleme raporuna girdi oluşturur.

## 7. Durum

PQ henüz yürütülmemiştir; pilot merkezlerle protokol imzalandığında ve etik kurul onayı alındığında başlatılacaktır. Bu bölüm, PQ tamamlandığında ölçüt tablosundaki gerçekleşen değerlerle doldurulacaktır.

## 8. Onaylar

| Rol | İmza | Tarih |
|---|---|---|
| Klinik Operasyon Direktörü | e-imza | 2026-06-12 |
| Tıbbi Direktör | e-imza | 2026-06-15 |
| Kalite Güvence Yöneticisi | e-imza | 2026-06-16 |
