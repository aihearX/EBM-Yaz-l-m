# Federe LoRA güncellemesi

Türkçe Klinik BDM'nin birden fazla hastanenin verisiyle, veri kurum dışına çıkmadan
iyileştirilmesi için tasarlanmış federe öğrenme düzeni. Mevcut durumda tasarım ve
çalışan iskelet (toplayıcı, istemci, yapılandırma) vardır; gerçek hastane turu henüz
yapılmamıştır. İlk çok merkezli tur, Ar-Ge programının 2–5. fazlarında pilot hastanelerle
planlanmaktadır.

## Neden federe

Türkçe tıbbi derlem tek bir kurumda yeterli hacme ulaşmaz; buna karşılık hiçbir hastane
ham hasta metnini kurum dışına veremez. Federe düzende her hastane, kendi
kimliksizleştirilmiş verisiyle modelin yalnızca LoRA adaptör katmanlarını yerelde eğitir;
EBM toplayıcısına giden tek şey adaptör ağırlıklarıdır (temel model 7–8B için adaptör
boyutu onlarca MB). Toplayıcı adaptörleri birleştirir, yeni küresel adaptörü hastanelere
dağıtır ve TR-KlinikBench ile değerlendirir.

```
 Hastane A ──(LoRA_A, sha256)──┐
 Hastane B ──(LoRA_B, sha256)──┼──▶ EBM toplayıcı: FedAvg / FedProx (+ DP gürültüsü) ──▶ LoRA_kuresel
 Hastane C ──(LoRA_C, sha256)──┘             │
                                             └──▶ TR-KlinikBench değerlendirmesi ──▶ kabul / ret
 LoRA_kuresel ──▶ hastanelere dağıtım ──▶ bir sonraki tur
```

## Tur protokolü

1. Toplayıcı turu açar: küresel adaptör sürümü, katılımcı listesi, yerel eğitim
   parametreleri (epoch, öğrenme hızı, maksimum adım) `config.yaml` ile duyurulur.
2. Her hastane `istemci.py` ile yerel eğitim yapar (`ml/egitim/lora_egit.py`), adaptörü
   `.npz` olarak dışa aktarır, SHA-256 özetini hesaplar ve toplayıcıya gönderir.
   Gönderim öncesi yerel değerlendirme eşiği (ör. G1 duyarlılık ≥ önceki tur) sağlanmalıdır.
3. Toplayıcı, özetleri doğrular, katılımcı başına örnek sayısına göre ağırlıklı ortalama
   alır (FedAvg); heterojen verilerde FedProx yakınlık terimi kullanılır.
4. Birleştirilen adaptör TR-KlinikBench üzerinde değerlendirilir; önceki turdan kötüyse
   tur reddedilir ve hastanelere bildirilir.
5. Kabul edilen adaptör sürümlenir, model kartı güncellenir ve dağıtılır.

Toplam tur sayısı ve katılımcı listesi `config.yaml` içindedir. Hastane katılımı için
yazılı veri işleme sözleşmesi ve etik kurul onayı önkoşuldur.

## Gizlilik ve güvenlik

- **Ne çıkar, ne çıkmaz:** hasta metni, kimliksizleştirilmiş metin, gömme vektörleri ve
  gradyan geçmişi hastaneden çıkmaz. Yalnızca adaptör ağırlıkları ve toplam örnek sayısı çıkar.
- **Ağırlık sızıntısı riski:** adaptör ağırlıklarından eğitim örneklerinin kısmen geri
  çıkarılabildiği literatürde gösterilmiştir. Azaltımlar: (a) yerelde yalnızca
  kimliksizleştirilmiş veri; (b) toplayıcıda Gauss gürültüsü ile diferansiyel gizlilik
  (`dp_gurultu`, varsayılan σ = 0,01, bütçe ε tur bazında raporlanır); (c) en az üç
  katılımcı olmadan birleştirme yapılmaz; (d) güvenli toplama (eşik şifreleme) ikinci
  aşama hedefidir.
- **Üyelik çıkarımı:** kabul edilen adaptör, bilinen örneklerle üyelik çıkarım testine
  tabi tutulur; başarı oranı rastgele tahminden anlamlı ölçüde yüksekse tur reddedilir.
- **Bütünlük:** her gönderim SHA-256 özeti ve katılımcı anahtarıyla imzalanır; toplayıcı
  yalnızca listedeki katılımcıları kabul eder.
- **KVKK:** hastane veri sorumlusu, EBM veri işleyen olarak kalır; adaptör ağırlıkları
  kişisel veri sayılmasa da ihtiyatlı yaklaşımla aynı saklama ve erişim kurallarına tabidir.

## Komutlar

```bash
# Toplayıcı: üç adaptörü ağırlıklı ortalamayla birleştir, gürültü ekle
python -m ml.federe.toplayici --adaptorler a.npz b.npz c.npz --agirliklar 1200 800 1500 \
    --dp-sigma 0.01 --cikti kuresel_r3.npz

# Hastane istemcisi: kuru çalışma (eğitim yok, akış doğrulanır)
python -m ml.federe.istemci --config ml/federe/config.yaml --katilimci H-ANK-01 --kuru
```
