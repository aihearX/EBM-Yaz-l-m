# PQ-001 Performans Kalifikasyonu Protokolü – Gölge Mod Pilotu

| | |
|---|---|
| Belge No | PQ-001 |
| Sistem | EBM SmartClinical |
| Sorumlu | Klinik Operasyon Direktörü (sistem sahibi) |
| Gözden geçiren | Validasyon Sorumlusu, Tıbbi Direktör |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Amaç

Sistemin gerçek operasyon ortamında, gerçek kullanıcılar ve gerçek (kimliksizleştirilmiş)
verilerle kullanım amacını karşıladığını göstermek. Deterministik fonksiyonlar OQ'da
doğrulandığından PQ, yapay zekâ bileşenlerinin saha performansına ve uçtan uca iş
akışlarına odaklanır. Bu belge bir protokoldür; pilot merkezler, çalışmalar ve süre
pilot sözleşmesi imzalandığında bölüm 2'ye işlenir.

## 2. Pilot tasarımı

| Parametre | Değer |
|---|---|
| Merkezler | Pilot sözleşmesiyle belirlenir (en az iki farklı kurum tipi önerilir) |
| Çalışmalar | Kayıt aşamasındaki çalışmalar |
| Süre | 6 ay |
| Mod | Gölge mod: platform önerileri araştırmacıdan körleştirilir; manuel ön tarama rutin şekilde yapılır; karşılaştırma aylık yapılır |
| Etik | Hastane etik kurulu bilgilendirme/onayı |
| Veri | HBYS verisi tanı koduna göre ön filtrelenmiş; tüm metinler kimliksizleştirilmiş |

## 3. Ölçütler ve kabul eşikleri

| No | Ölçüt | Tanım | Eşik | URS | Kod |
|---|---|---|---|---|---|
| PQ-M1 | Eşleştirme duyarlılığı | Manuel taramada uygun bulunanlar içinde platformun "uygun" veya "olası" dediği oran | ≥ %90 | ES-05 | `ml/degerlendirme/degerlendir.py` |
| PQ-M2 | Eşleştirme özgüllüğü | Manuel taramada uygun olmayanlar içinde platformun "uygun değil" dediği oran | ≥ %70 (raporlanır) | ES-06 | `GET /calismalar/{calisma_id}/eslestirme-golge` |
| PQ-M3 | Pozitif öngörü değeri | Platform "uygun" dediklerinin manuelde uygun çıkma oranı | ≥ %60 | ES-06 | `GET /calismalar/{calisma_id}/eslestirme-golge` |
| PQ-M4 | Ön tarama süresi | Hasta başına koordinatör ön tarama süresi: platform listesiyle vs. manuel (zaman etüdü) | ≥ %50 azalma | Proje hedefi | zaman etüdü formu |
| PQ-M5 | Halüsinasyon | Rastgele 200 kanıt cümlesi klinisyen kontrolü: kaynakta yok oranı | ≤ %2 | BDM-03 | `services/bdm/korumalar.py` |
| PQ-M6 | Belirsiz oranı | Kriter sonuçları içinde "belirsiz" | ≤ %25 (raporlanır) | – | eşleştirme sonuçları |
| PQ-M7 | Kazanım tahmini MAPE | 3. ayda yapılan 3 aylık tahmin vs gerçekleşen | ≤ %25 | MZ-03 | `services/merkez_zekasi/kazanim.py` (`mape`) |
| PQ-M8 | Gecikme riski AUC | Pilot dönemde aktive olan merkezler için hedef aşımı tahmini | ≥ 0,80 | MZ-04 | `services/merkez_zekasi/aktivasyon.py` (`auc`) |
| PQ-M9 | RBM uyarı kesinliği | Açılan uyarılar içinde CRA'nın "gerçek sorun" olarak kapattığı oran | ≥ %60 | RBM-04 | `POST /calismalar/{calisma_id}/rbm/uyari/{uyari_id}` |
| PQ-M10 | Kimliksizleştirme kaçak | Yükleme sonucunda reddedilen satırların ve ikinci geçiş raporunun gözden geçirilmesi | 0 kimlik verisi | KM-01, KM-03 | `metni_dogrula`, `POST /merkezler/{mid}/hasta-yukle` |
| PQ-M11 | Kullanılabilirlik | SUS anketi (araştırmacı, koordinatör, CRA; n ≥ 15) | Ortalama ≥ 68; kritik bulgu yok | ÇY-06 | anket |

## 4. Yöntem

1. **Körleştirme**: Gölge mod kayıtları `golge_mod=True` ile saklanır; araştırmacı arayüzünde görünmez. Manuel ön tarama kararı koordinatör tarafından bağımsız girilir.
2. **Karşılaştırma**: Ay sonunda validasyon sorumlusu gölge mod raporunu alır; uyumsuz vakalar tıbbi direktör tarafından incelenir ve kök neden sınıflandırılır (veri eksik / kriter yapılandırma / model hatası / manuel hata).
3. **Zaman etüdü**: 1. ve 2. ayda manuel, 4. ve 5. ayda platform destekli ön tarama süresi; koordinatör başına ≥ 30 hasta.
4. **Kalibrasyon**: 3. ay sonunda kriter yapılandırma ve eşikler gözden geçirilebilir; değişiklik değişiklik kontrol kaydıyla yapılır ve sonraki aylar ayrı raporlanır.
5. **Güvenlik sinyali**: Platform kaynaklı herhangi bir hatalı kayıt/onam olayı derhal sapma olarak açılır ve pilot durdurma kriteri değerlendirilir.

## 5. Durdurma kriterleri

- Kimlik verisi sızıntısı (PQ-M10 ihlali) → pilot derhal durdurulur, KVKK prosedürü işletilir.
- İki ardışık ayda duyarlılık < %75 → eşleştirme bileşeni pilotta askıya alınır, kök neden analizi.

## 6. Raporlama

PQ raporu ölçüt tablosunu, uyumsuz vaka analizini, kullanıcı anketi sonuçlarını, açık sapmaları ve
üretim kullanımı önerisini içerir.

## 7. Durum

PQ yürütülmemiştir; pilot merkezlerle protokol imzalandığında ve etik kurul onayı alındığında
başlatılır. Gerçekleşen değerler bu bölüme işlenir.

## 8. Onaylar

| Rol | İmza |
|---|---|
| Klinik Operasyon Direktörü | |
| Tıbbi Direktör | |
| Kalite Güvence Yöneticisi | |
