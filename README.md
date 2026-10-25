# EBM SmartClinical

Klinik araştırma yönetimi ve Türkçe klinik karar destek platformu.

SmartClinical, bir klinik araştırmanın tasarımından arşivine kadar tüm yaşam döngüsünü tek
platformda yönetir ve bunun üzerine hastane içinde çalışan bir Türkçe Klinik Büyük Dil Modeli
(BDM) ile üç karar destek işlevi ekler:

- **Protokol–hasta eşleştirme:** dahil etme / hariç tutma kriterlerini hesaplanabilir sorguya
  çevirir, HBYS'den gelen kimliksizleştirilmiş kayıtları tarar ve her öneriyi kaynak cümlesiyle
  birlikte araştırmacıya sunar.
- **Merkez zekâsı:** hiyerarşik Bayesçi kazanım tahmini, Weibull tabanlı aktivasyon gecikme
  riski ve açıklanabilir merkez sıralaması.
- **Risk bazlı izlem:** ICH E6(R3) ile uyumlu anahtar risk göstergeleri (KRI), kalite tolerans
  limitleri (QTL) ve merkezler arası anomali tespitine dayalı erken uyarı.

Platform ilaç, biyobenzer, tıbbi cihaz, in vitro tanı, gözlemsel, kayıt (RWE) ve araştırmacı
başlatımlı çalışmaların tamamını destekler. Hasta verisi kurum dışına çıkmaz; BDM dahil tüm
bileşenler hastane ağı içinde (on-premise) çalışır.

## Modüller

| Modül | Kapsam |
|---|---|
| Kullanım modu ve kurulum | Tekil araştırmacı, üniversite/hastane ve CRO modları; ilk açılışta kurulum ekranı; mod bazlı menü ve varsayılanlar |
| Çalışma sihirbazı | Dört adımda çalışma kurulumu: protokol bilgileri, kollar ve vizit şeması, merkez ve ekip, eCRF formları ve başvurular |
| Çalışma yönetimi | Protokol sürümleri, veriden hesaplanan aşama kontrol listesi, gerekçeli aşama geçişi, kayıt eğrisi |
| Çalışma tasarımı | Kollar, çalışma bazlı vizit şeması, kodsuz eCRF tasarımcısı (koşullu alanlar, bölüm başlıkları, çoklu seçim), kaydı olan formda sürümleme ve denetim izi, protokol metninden kural tabanlı/BDM destekli taslak (yalnızca öneri, uygulama insan onayıyla) |
| Çalışma ekibi | Kullanıcı × çalışma ataması; proje ekibi yalnızca atandığı çalışmaları görür, rol globaldir |
| Merkez ve araştırmacı | Merkez kayıt defteri, geçmiş performans, GCP eğitim takibi |
| Etik / TİTCK / KVKK | Başvuru ve karar takibi, süre analizi, merkez bazlı kurum izinleri |
| Hasta eşleştirme | Kriter yapılandırma, ICD ön filtre, yapısal + RAG değerlendirme, gölge mod |
| Gönüllü ve eCRF | Onam, tarama, randomizasyon, vizit takvimi, CDASH uyumlu formlar, edit-check, sorgular, SDV, veri kilidi |
| Güvenlik | AE/SAE kaydı, CTCAE derecesi, nedensellik, SUSAR tespiti, 7/15 gün bildirim takibi |
| Risk bazlı izlem | 15 varsayılan KRI, QTL, ısı haritası, uyarı yönetimi, izlem önerisi |
| Ziyaret ve sapmalar | SIV/IMV/COV/uzaktan ziyaret planı, bulgu takibi, protokol sapmaları |
| TMF | DIA TMF referans modeli bölgeleri, SHA-256 özet, e-imza ile onay, tamlık kontrolü |
| Kalite | Hash zincirli denetim izi, elektronik imza, rol bazlı erişim, hesap kilitleme |
| Genel bakış | Role göre üç görünüm: merkez (vizit, taslak form, sorgu, SAE), izlem (uyarı, geciken sorgu, SDV, ziyaret), portföy (takvim riski, en riskli merkez, fizibilite raporu; sponsor için kurum bazlı salt okunur) |
| Merkez performans endeksi | Çalışmalar arası anonim kıyaslama, yüzdelik dilimler, kurum tipi medyanları |
| Analiz | Değişken bazlı betimleyici özet, kural tabanlı test seçimi (Welch t / Mann-Whitney / ANOVA / Kruskal-Wallis / ki-kare / Fisher), gönüllü akışı, kol × SOC advers olay özeti, analiz veri seti CSV (denetim izine yazılır) |
| Entegrasyon | FHIR R4, CSV hasta havuzu yükleme, CDISC ODM/CSV ve OMOP dışa aktarım, REST API + API anahtarı, ICD-10 kodlama ve klinik özet uçları |

## Hızlı başlangıç

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python -m smartclinical.scripts.demo_veri --sifirla     # sentetik demo verisi
uvicorn smartclinical.main:app --reload
```

Tarayıcıda `http://localhost:8000` adresine gidin. Demo hesapları `admin / Demo2026!sc`
(diğer roller için `smartclinical/scripts/demo_veri.py` içindeki listeye bakın). API belgeleri
`/api/belgeler` altındadır. Demo verisi CRO modunda yüklenir.

## İlk kurulum

Boş veritabanında `/giris` sayfası otomatik olarak `/kurulum` ekranına yönlendirir: kullanım
modu (tekil araştırmacı, üniversite/hastane, CRO), kurum adı ve yönetici hesabı burada
tanımlanır. Komut satırı eşdeğeri:

```bash
python -m smartclinical.scripts.yonetici_olustur --kullanici admin --ad "Ad Soyad" --eposta a@b.c --mod tekil --kurum "Kurum Adı"
```

Mod sonradan Ayarlar (`/yonetim/sistem`) sayfasından değiştirilir; mod yalnızca menüyü,
sihirbaz varsayılanlarını ve yeni kayıtları etkiler.

Demo verisi tamamen sentetiktir; merkez adları kurgusaldır, gerçek hasta verisi içermez.

## Türkçe Klinik BDM

Varsayılan yapılandırmada (`SC_BDM_SAGLAYICI=kural`) sistem, BDM sunucusu olmadan
deterministik kural tabanlı ayrıştırıcı ve kanıt çıkarıcı ile çalışır. Hastane içi model
sunucusu için `.env` dosyasında `ollama`, `vllm` veya `llamacpp` sağlayıcılarından biri seçilir.
Sunucuya erişilemediğinde sistem otomatik olarak kural tabanlı moda düşer ve bunu denetim izine
yazar. Model eğitim ve değerlendirme altyapısı `ml/` dizinindedir.

## Dizin yapısı

```
smartclinical/        uygulama (FastAPI)
  models/             SQLAlchemy veri modeli
  services/           alan servisleri (bdm, kriter, eslestirme, merkez_zekasi, rbm, ecrf, protokol, analiz, kurulum, fhir, kimliksizlestirme, denetim, yetki)
  web/                Jinja2 şablonları ve sayfa rotaları
  api/                REST API v1
  scripts/            yönetim betikleri (demo veri, yönetici oluşturma, denetim doğrulama, OMOP aktarım)
ml/                   BDM veri hazırlama, eğitim (LoRA), değerlendirme, TR-KlinikBench, federe güncelleme, model/veri kartları
deploy/               Docker, nginx, systemd, PostgreSQL yetkileri, yedekleme, kurulum kılavuzu
docs/validasyon/      CSV dosyası (URS, FRS, risk analizi, IQ/OQ/PQ, izlenebilirlik, 21 CFR 11 / Annex 11, KVKK)
docs/tanitim/         ürün tanıtım dokümanı ve ekran görüntüleri
tests/                pytest
```

## Geliştirme

```bash
make test      # pytest
make lint      # ruff
```

Katkı kuralları ve sürüm politikası için `docs/gelistirme.md`, mimari için `docs/mimari.md`,
API için `docs/api.md` dosyalarına bakın.

## Lisans

Tescilli yazılım. Her hakkı saklıdır. Bkz. `LICENSE`.
