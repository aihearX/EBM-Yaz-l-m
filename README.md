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
| Kullanım modu ve kurulum | Tekil araştırmacı, üniversite/hastane ve CRO modları; ilk açılışta kurulum ekranı; mod bazlı menü ve varsayılanlar. Tekil ve üniversite modunda araştırmacı, CRO modunda proje yöneticisi çalışma kurar |
| Çalışma sihirbazı | Dört adımda çalışma kurulumu: protokol bilgileri, kollar ve vizit şeması, merkez ve ekip, eCRF formları ve başvurular; taslak veritabanında saklanır ve kaldığı yerden sürer; kurucu ekibe kendiliğinden eklenir |
| Çalışma yönetimi | Protokol sürümleri, veriden hesaplanan aşama kontrol listesi, gerekçeli aşama geçişi, kayıt eğrisi |
| Çalışma tasarımı | Kollar, çalışma bazlı vizit şeması, vizit × form matrisi, kodsuz eCRF tasarımcısı (koşullu alanlar, bölüm başlıkları, çoklu seçim, tekrarlayan formlar, canlı önizleme), kaydı olan formda sürümleme ve denetim izi, protokol metninden veya belgesinden (PDF/DOCX) kural tabanlı/BDM destekli taslak (yalnızca öneri, uygulama insan onayıyla), telifsiz ölçek paketi (PHQ-9, GAD-7, VAS) |
| Çalışma ekibi | Kullanıcı × çalışma ataması; proje ekibi yalnızca atandığı çalışmaları görür, rol globaldir. Rol × sekme ve rol × izin tablosu: `docs/roller.md` |
| Merkez ve araştırmacı | Merkez kayıt defteri, geçmiş performans, GCP eğitim takibi |
| Etik / TİTCK / KVKK | Başvuru ve karar takibi, süre analizi, merkez bazlı kurum izinleri |
| Hasta eşleştirme | Kriter yapılandırma, ICD ön filtre, yapısal + RAG değerlendirme, gölge mod |
| Gönüllü ve eCRF | Onam, tarama, randomizasyon, vizit takvimi, CDASH uyumlu formlar, edit-check, sorgular, SDV, veri kilidi; durum geçiş denetimi, tarama vizitleri onamla, dahili blok randomizasyon (e-imzalı liste, strata: merkez), tekrarlayan formlar, AE güncelleme ve SOC kodlama |
| Güvenlik | AE/SAE kaydı, CTCAE derecesi, nedensellik, SUSAR tespiti, 7/15 gün bildirim takibi |
| Risk bazlı izlem | 15 varsayılan KRI (kaçırılan vizit oranı dahil), QTL, ısı haritası, uyarı yönetimi, izlem önerisi |
| Ziyaret ve sapmalar | SIV/IMV/COV/uzaktan ziyaret planı, ziyaret raporu (gerçekleşen tarih, SDV oranı, kontrol listesi, bulgular), proje yöneticisi e-imzası, açık bulguların sonraki ziyarete taşınması, aksiyon uyarısından tek tıkla tetiklenmiş ziyaret, sapma kapatma (majörde etik bildirim zorunlu) |
| TMF | DIA TMF referans modeli bölgeleri, merkez dosyası (ISF) görünümü, sürüm zinciri (eskimiş belgeler), e-imzalı onay, özet doğrulamalı indirme, tamlık kontrolü; PDF/DOCX/XLSX/PNG/JPG, 25 MB |
| Veri yönetimi | Araştırmacı imzası, toplu kilit (tek e-imza, ön kontrol raporu), gerekçeli kilit açma, toplu sorgu kapatma, CSV listeleri |
| Kalite | HMAC zincirli denetim izi, elektronik imza, rol bazlı erişim (sponsor her yerde salt okunur), süreli hesap kilidi (15 dk, her kilitte iki katına çıkar), IP başına deneme sınırı, parola politikası (uzunluk, geçerlilik süresi, son beş parola) |
| Genel bakış | Role göre üç görünüm: merkez (vizit, taslak form, sorgu, SAE), izlem (uyarı, geciken sorgu, SDV, ziyaret), portföy (takvim riski, en riskli merkez, fizibilite raporu; sponsor için kurum bazlı salt okunur) |
| Merkez performans endeksi | Çalışmalar arası anonim kıyaslama, yüzdelik dilimler, kurum tipi medyanları |
| Analiz | Değişken bazlı betimleyici özet, kural tabanlı test seçimi (Welch t / Mann-Whitney / ANOVA / Kruskal-Wallis / ki-kare / Fisher), Tablo 1 (başlangıç özeti, kol bazında, CSV), vizitler arası değişim (eşleştirilmiş t / Wilcoxon), gönüllü akışı, kol × SOC advers olay özeti, analiz veri seti CSV (denetim izine yazılır) |
| Entegrasyon | FHIR R4, CSV hasta havuzu yükleme, CDISC ODM (vizit tanımları, merkezler, AE/dispozisyon, isteğe bağlı AuditRecord), CSV ve OMOP dışa aktarım, REST API + API anahtarı, ICD-10 kodlama ve klinik özet uçları |
| Zamanlanmış işler | `gece_isleri` (KRI, tahmin, SAE süre kontrolü), `hasta_saklama`, `denetim_dogrula` |

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

Parola politikası `SC_PAROLA_MIN` ve `SC_PAROLA_GUN`, hasta takma adı anahtarı
`SC_TAKMA_AD_ANAHTARI` ile ayarlanır (üretimde zorunlu). Protokol belgesi yükleme için
`pdfminer.six` ve `python-docx` `requirements.txt` ile gelir.

## Komut satırı araçları

| Betik | İş |
|---|---|
| `scripts/demo_veri.py` | Sentetik demo verisi (`--sifirla`) |
| `scripts/yonetici_olustur.py` | İlk yönetici ve kullanım modu |
| `scripts/kilit_ac.py` | Kilitli hesabı açar (`--kullanici`) |
| `scripts/yeniden_anahtarla.py` | Takma ad anahtarı değişince hasta kayıt numaralarını yeniler |
| `scripts/gece_isleri.py` | KRI, kazanım tahmini ve SAE bildirim süreleri (zamanlayıcı ile) |
| `scripts/hasta_saklama.py` | Saklama süresi dolan hasta havuzu kayıtlarını temizler (`--kuru-calisma`) |
| `scripts/denetim_dogrula.py` | Denetim izi zincirini doğrular |
| `scripts/onarim_tarama_vizitleri.py` | Vizite bağlı olmayan tarama formlarını bağlar |
| `scripts/omop_aktar.py` | OMOP CDM dışa aktarımı |

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
  services/           alan servisleri (bdm, kriter, eslestirme, merkez_zekasi, rbm, ecrf, protokol, analiz, gonullu, randomizasyon, kurulum, fhir, kimliksizlestirme, denetim, yetki)
  web/                Jinja2 şablonları ve sayfa rotaları
  api/                REST API v1
  scripts/            yönetim betikleri (bkz. Komut satırı araçları)
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
