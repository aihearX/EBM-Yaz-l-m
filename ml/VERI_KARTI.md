# Veri kartı: Türkçe klinik araştırma derlemi ve TR-KlinikBench

Veri sorumlusu (EBM içi): Veri Yönetimi Birimi

## Kapsam

Bu kart iki veri varlığını tanımlar: (1) ebm-klinik-tr modelinin eğitimi için derlenecek
Türkçe tıbbi derlem, (2) TR-KlinikBench değerlendirme seti. Her ikisi için de mevcut durum
şudur: yalnızca sentetik ve kamuya açık bileşenler mevcuttur; hastane kaynaklı hiçbir kayıt
henüz toplanmamıştır.

## Kaynaklar ve durum

| Bileşen | Kaynak | Hacim (mevcut / hedef) | Hukuki dayanak | Durum |
|---|---|---|---|---|
| Sentetik epikriz ve rapor örnekleri | şablon ve klinisyen yazımı | ~300 metin / 2.000 | yok (gerçek kişi verisi değil) | mevcut |
| Kamuya açık klinik kılavuzlar | dernek ve bakanlık yayınları | derleme sürüyor | kamuya açık | kısmen |
| EBM protokol ve çalışma belgeleri | kurum içi | 40 çalışma | sözleşme, sponsor izni gerekir | izin süreci |
| Pilot hastane serbest metin raporları | 3 pilot hastane HBYS | 0 / 50.000 belge | etik kurul onayı, KVKK md. 6 ve 28 değerlendirmesi, veri işleme sözleşmesi | başvuru hazırlığı (Faz 1) |
| Altın standart etiketler | klinisyen etiketleme | 28 / 2.000 çift | etiketleme sözleşmesi | sentetik kısım mevcut |

## Kimliksizleştirme

Hastane kaynaklı her metin, hastane içinde SmartClinical kimliksizleştirme modülünden geçer;
ikinci geçiş doğrulamasında şüpheli kalıp içeren belgeler derleme alınmaz. Takma ad anahtarı
hastanede kalır; EBM'ye ulaşan veride hasta kimliği, tarih (kaydırılmış), kurum ve
klinisyen adı bulunmaz. Kimliksizleştirme kalitesi, G4 görevi ile her sürümde ölçülür ve
rastgele örneklem elle denetlenir (hedef: duyarlılık ≥ %98, klinik terim kaybı ≤ %1).

## Etik onaylar ve izinler

- Her pilot hastane için ayrı etik kurul başvurusu (girişimsel olmayan araştırma); onay
  numaraları bu kartta sürüm notu olarak yayımlanacaktır.
- Veri işleme sözleşmesi: hastane veri sorumlusu, EBM veri işleyen.
- Sponsor belgeleri için sponsor yazılı izni; izin verilmeyen belgeler derleme alınmaz.
- Etiketleyiciler için gizlilik ve telif sözleşmesi.

## Saklama ve erişim

- Derlem EBM'nin hastane dışı ortamında yalnızca kimliksizleştirilmiş biçimde, şifreli
  diskte ve erişim kaydıyla saklanır; proje sonunda hastane isteğine göre imha edilir veya
  sözleşme süresince saklanır.
- Federe eğitim senaryosunda ham veya kimliksizleştirilmiş metin hastaneden çıkmaz
  (bkz. `ml/federe/README.md`).
- TR-KlinikBench sentetik sürümü açık (CC BY-NC-SA 4.0 planı); gerçek rapor sürümü yalnızca
  erişim sözleşmesiyle, araştırma amaçlı ve kimliksizleştirilmiş olarak.

## Dengeli temsil

Derlemde ve değerlendirme setinde hedeflenen dağılım: üç kurum tipi (üniversite, eğitim ve
araştırma, şehir hastanesi), en az dört terapötik alan (onkoloji, endokrinoloji,
kardiyoloji, göğüs hastalıkları), her iki cinsiyet ve üç yaş grubu. Sentetik sette bu
dağılım kabaca sağlanmıştır; gerçek sette hastane kaynak dağılımı raporlanacaktır.

## Bilinen eksikler

- Çocuk hastalar ve nadir hastalıklar derlemde yoktur; pediatrik çalışmalar kapsam dışıdır.
- Bölgesel dil varyasyonu (Doğu ve Güneydoğu Anadolu kurumları) pilot seçiminde yetersiz
  temsil ediliyor olabilir; dördüncü pilot kurum değerlendiriliyor.
