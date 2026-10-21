# Altın Standart Etiketleme Kılavuzu (sürüm 1.2)

Bu kılavuz, protokol–hasta eşleştirme modelinin değerlendirme setini oluşturan
klinisyen ve klinik araştırma uzmanları içindir. Şema: `altin_standart_sema.json`.

## 1. Temel kural

Etiket, **yalnızca verilen metin parçasına** dayanır. Metinde olmayan bir bilgiyi
klinik tecrübenizle tamamlamayın; bilgi yoksa `belirsiz` yazın. Modelden de aynı
davranışı bekliyoruz; aksi hâlde halüsinasyon oranını ölçemeyiz.

## 2. Etiketler

| Etiket | Ne zaman |
|---|---|
| `saglandi` | Kriterdeki koşul metinde açıkça karşılanıyor |
| `saglanmadi` | Koşulun karşılanmadığı metinden açıkça anlaşılıyor |
| `belirsiz` | Bilgi yok, eksik, çelişkili ya da tarih/ölçüm kriteri değerlendirmeye yetmiyor |

Hariç tutma kriterlerinde de **koşulun kendisi** etiketlenir. Örnek: "Son 6 ayda
MI geçirmiş olmak" hariç kriteri; metinde 2 ay önce MI varsa etiket `saglandi`dır
(hasta hariç tutulur). Uygunluk kararını sistem verir, etiketleyici vermez.

## 3. Kanıt aralığı (kanit_span)

- `saglandi` ve `saglanmadi` için en az bir kanıt aralığı zorunludur.
- Aralık, kararı tek başına destekleyen **en kısa** cümle veya cümle parçasıdır.
- Birden fazla cümle gerekiyorsa (ör. tanı bir cümlede, tarih başka cümlede) hepsini ekleyin.
- Olumsuzlama ifadelerini ("saptanmadı", "öyküsü yok") aralığa dahil edin.

## 4. Sık karşılaşılan durumlar

- **Kısaltmalar**: "DM", "HT", "KAH" gibi kısaltmalar yeterli kanıttır; açılım aramayın.
- **Tarih kısıtı**: Kriterde "son 6 ay" gibi bir kısıt varsa metindeki rapor tarihi referans alınır. Rapor tarihi yoksa `belirsiz`.
- **Laboratuvar**: Birim yoksa ve değer tek bir yorumla açıklanamıyorsa `belirsiz`. Birim dönüşümü yapılabiliyorsa (mg/dL ↔ µmol/L) yapın, nota yazın.
- **Performans skoru**: ECOG yazmıyor ama "günlük işlerini yapabiliyor, yatağa bağımlı değil" gibi ifade varsa `belirsiz` (çıkarım gerektirir; `zorluk: zor` işaretleyin).
- **Gebelik**: Erkek hastada gebelik kriteri doğrudan `saglanmadi`.
- **Çelişki**: Aynı metinde çelişen iki ifade varsa `belirsiz`, notlara yazın.

## 5. Çift etiketleme ve hakem

Her kayıt iki bağımsız etiketleyici tarafından işaretlenir. Uyumsuzlukta üçüncü
değerlendirici karar verir (`hakem_karari`). Hedef: Cohen kappa ≥ 0,80. Kappa'nın
0,70'in altına düştüğü kriter türleri için kılavuz güncellenir ve set yeniden etiketlenir.

## 6. Yapılmaması gerekenler

- Kimlik bilgisi içeren metin görürseniz etiketlemeyin; `notlar` alanına "PHI" yazıp veri yöneticisine bildirin.
- Modelin önceki çıktısını görerek etiketleme yapılmaz (kör etiketleme).
- Aynı hastaya ait birden fazla kaydı aynı etiketleyiciye toplu vermeyin.
