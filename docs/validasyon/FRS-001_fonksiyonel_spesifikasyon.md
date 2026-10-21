# FRS-001 Fonksiyonel Spesifikasyon

| | |
|---|---|
| Belge No | FRS-001 |
| Sistem | EBM SmartClinical v1.4 |
| Sürüm | 2.0 |
| Yürürlük tarihi | 2026-03-03 |
| Hazırlayan | Yazılım Geliştirme Yöneticisi |
| Gözden geçiren | Validasyon Sorumlusu, Veri Yönetimi Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## Revizyon geçmişi

| Sürüm | Tarih | Açıklama |
|---|---|---|
| 1.0 | 2025-04-02 | İlk yayın (v1.2) |
| 1.1 | 2025-08-25 | RBM, e-imza (v1.3) |
| 2.0 | 2026-03-03 | Eşleştirme, BDM, merkez zekâsı, kimliksizleştirme, FHIR/OMOP (v1.4) |

## 1. Amaç

URS-001'deki her gereksinimin sistemde nasıl karşılandığını tanımlar. Her
fonksiyon FRS-xx kodu ile URS'ye izlenir (TM-001).

## 2. Sistem mimarisi

```
 Kullanıcı (tarayıcı) ──TLS──> nginx ──> FastAPI uygulaması (smartclinical/)
                                              ├── web/  (Jinja2 + HTMX arayüz)
                                              ├── api/  (REST, /api/v1)
                                              ├── services/
                                              │     ├── kimliksizlestirme
                                              │     ├── kriter, bdm, eslestirme
                                              │     ├── merkez_zekasi, rbm
                                              │     ├── fhir (HBYS adaptörü, OMOP)
                                              │     └── denetim, yetki
                                              └── models/ (SQLAlchemy) ──> PostgreSQL 16
                                                     BDM servisi (Ollama / llama.cpp, hastane içi GPU)
                                                     Gömme servisi (RAG)
                                                     HBYS FHIR R4 uç noktası (salt okunur)
```

Uygulama modüler monolit olarak paketlenir; BDM ve gömme servisleri ayrı
konteynerlerdir. Tüm bileşenler hastane ağında çalışır.

## 3. Fonksiyonlar

### 3.1 Çalışma yönetimi

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-01 | `Calisma` varlığı `CalismaTuru` numaralandırmasıyla (9 tür) tanımlanır; tür, arayüzde zorunlu alanları ve kontrol listesi şablonunu belirler (ör. tıbbi cihaz: cihaz sınıfı, UDI; ilaç: faz, EudraCT). | URS-ÇY-01 |
| FRS-02 | `CalismaDurumu` sıralı yaşam döngüsü; `services/calisma.durum_ilerlet()` ön koşulları kontrol eder (kayıt için ≥1 onaylı etik başvurusu ve ≥1 aktif merkez; kapanış için açık sorgu/uyarı olmaması), ihlalde kullanıcıya eksik listesi gösterilir. | URS-ÇY-02 |
| FRS-03 | `ProtokolVersiyon` ekleme-yalnız; silme yetkisi hiçbir role verilmez; yeni sürüm eklendiğinde kriterler kopyalanır ve "onay bekliyor" durumuna alınır. | URS-ÇY-03 |
| FRS-04 | `Kriter`: tip (dahil/hariç), sıra, metin, `yapisal` (JSON sorgu), `guven`, `onaylandi`, `onaylayan_id`. Yapılandırma `services/kriter.yapilandir` (kural) ya da `services/bdm.kriter_yapilandir` ile üretilir; arayüzde JSON düzenleyici ve "Onayla" düğmesi. | URS-ÇY-04, URS-ES-01 |
| FRS-05 | Çalışma kilometre taşları `KilometreTasi` (merkez bazlı) üzerinden türetilir; çalışma düzeyinde min/max ile ilk/son hasta hesaplanır. | URS-ÇY-05 |
| FRS-06 | Rol bazlı gösterge panelleri: `web/panel.py` rolü okuyup ilgili bileşenleri (sponsor: kazanım eğrisi, risk haritası; CRA: uyarılar, açık sorgular, planlı ziyaretler; araştırmacı: eşleştirme adayları, vizit takvimi, AE bildirim süreleri) yükler. | URS-ÇY-06 |

### 3.2 Merkez yönetimi ve merkez zekâsı

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-07 | `Merkez`, `Arastirmaci` varlıkları; GCP eğitim tarihi 2 yıldan eskiyse arayüzde uyarı. | URS-MZ-01 |
| FRS-08 | `CalismaMerkez.durum` 9 durumlu akış; her geçiş `KilometreTasi` gerçekleşen tarihini doldurur. | URS-MZ-02 |
| FRS-09 | `services/merkez_zekasi/kazanim.kazanim_tahmini`: Gamma-Poisson hiyerarşik model; havuz α,β ampirik Bayes; posterior ortalama ve %90 aralık; `aciklama` listesi (veri miktarı, büzülme oranı, kovaryat düzeltmeleri) arayüzde "Neden bu tahmin?" panelinde gösterilir. | URS-MZ-03 |
| FRS-10 | `services/merkez_zekasi/aktivasyon.GecikmeModeli`: Weibull AFT, sansürlü veri; `tahmin()` hedef gün için aşma olasılığı, medyan, kovaryat katkıları. Eğitim verisi yoksa öncül parametrelerle çalışır ve "öncül" etiketi gösterir. | URS-MZ-04 |
| FRS-11 | `services/merkez_zekasi/siralama.merkez_sirala`: bileşen ağırlıkları `Calisma` düzeyinde JSON olarak saklanır (varsayılan modül sabiti); çıktı puan + katkı + gerekçe metni. | URS-MZ-05 |
| FRS-12 | `calisma_kazanim_projeksiyonu`: Monte Carlo (2000 örnek, sabit tohum) ile hedefe ulaşma ayı dağılımı; arayüzde yelpaze grafiği. | URS-MZ-06 |

### 3.3 Başvurular

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-13 | `Basvuru` varlığı; kurum (5) × tip (6); `sure_gun` türetilmiş alan. | URS-BŞ-01 |
| FRS-14 | Mevzuat süre tablosu (`services/basvuru.SURELER`: TİTCK ilk başvuru 30 gün, değişiklik 30 gün, etik kurul 30 gün) ile karşılaştırılır; aşımda panelde ve günlük özet e-postasında uyarı. | URS-BŞ-02 |
| FRS-15 | Başvuru kaydı TMF bölge 03/04 belgelerine bağlanır (`Belge.basvuru_id`). | URS-BŞ-03 |

### 3.4 EDC

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-16 | `Form.alanlar` JSON şeması (kod, etiket, tip, birim, zorunlu, min, max, secenekler, cdash). Form tasarımcısı arayüzü; sürüm artırımı veri varsa zorunlu. | URS-EDC-01 |
| FRS-17 | `services/edc.kontrol_et()`: tip, aralık, zorunluluk ve formlar arası tutarlılık (ör. bitiş < başlangıç) kontrolleri; ihlalde `Sorgu(kaynak="otomatik")` açılır, kayıt engellenmez. | URS-EDC-02 |
| FRS-18 | `Sorgu` durum makinesi; `acik_gun` türetilmiş; CRA/veri yöneticisi kapatabilir, merkez cevaplar. | URS-EDC-03 |
| FRS-19 | `FormKaydi.durum` akışı; kilit açma yalnızca veri yöneticisi + gerekçe + e-imza; açma işlemi denetim izine "kilit_ac" olarak yazılır. | URS-EDC-04 |
| FRS-20 | Tüm model değişiklikleri SQLAlchemy olay dinleyicisi (`services/denetim.kaydet`) ile yakalanır; eski/yeni değer JSON. | URS-EDC-05, URS-Dİ-01 |
| FRS-21 | `Vizit` planı protokol şablonundan (`Form.vizit_adi` ve `Calisma.vizit_sablonu`) gönüllü randomizasyon tarihine göre üretilir; `pencere_disi` türetilmiş özellik. | URS-EDC-06 |
| FRS-22 | Dışa aktarma: CSV (ham), SDTM-benzeri alan eşlemesi (`cdash` → SDTM değişken), XPT yazımı `ml`siz saf Python (xport paketi opsiyonel). | URS-EDC-07 |

### 3.5 Güvenlik

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-23 | `AdversOlay` tüm alanlarla; MedDRA kodlama elle (lisans gereği sözlük gömülmez). | URS-GV-01 |
| FRS-24 | `AdversOlay.susar` türetilmiş: `ciddi and not beklenen and nedensellik in {olasi, muhtemel, kesin}`. | URS-GV-02 |
| FRS-25 | `bildirim_suresi_gun`: ölüm/yaşamı tehdit → 7 gün, diğer ciddi → 15 gün; ≤ 2 gün kaldığında panelde kırmızı, negatifse "gecikti". | URS-GV-03 |
| FRS-26 | Sponsor/TİTCK/etik bildirim tarihleri; `rbm.gostergeler.hesapla_sae_gec_bildirim` bunları okur. | URS-GV-04 |

### 3.6 RBM

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-27 | `rbm.gostergeler.VARSAYILAN_KRILER` (15 gösterge) ilk kurulumda `RiskGostergesi` tablosuna şablon olarak yüklenir; çalışma bazında kopyalanıp düzenlenir. | URS-RBM-01 |
| FRS-28 | `KaliteToleransLimiti`; `rbm.uyari.qtl_guncelle` gece işinde ve istek üzerine hesaplar. | URS-RBM-02 |
| FRS-29 | `rbm.anomali.anomali_tespit`: medyan/MAD robust z-skor, |z| > 3 aykırı; n < 5'te "sınırlı güven" notu. | URS-RBM-03 |
| FRS-30 | `rbm.uyari.erken_uyari_calistir`: eşik ve aykırılık → `RiskUyarisi`; `aciklama` alanı değer, eşik, merkezler arası konum; açık uyarı varsa güncelleme. | URS-RBM-04 |
| FRS-31 | Uyarı durum akışı ve atama; kapanış notu zorunlu. | URS-RBM-05 |
| FRS-32 | `CalismaMerkez.risk_puani` ağırlıklı bileşik (0–100); `rbm.uyari.izlem_onerisi`. | URS-RBM-06 |
| FRS-33 | `IzlemZiyareti` tipleri; tetiklenmiş ziyaret `tetikleyen_uyari_id` ile uyarıya bağlanır; rapor onayı e-imza ister. | URS-RBM-07 |
| FRS-34 | `ProtokolSapmasi`; major sapma kaydı etik bildirim alanı boşsa 7 gün sonra hatırlatma. | URS-RBM-08 |

### 3.7 Eşleştirme ve BDM

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-35 | `services/eslestirme.Eslestirici.hasta_degerlendir`: her kriter için önce yapısal değerlendirme (`kriter.degerlendir`), belirsizse RAG (`bdm.rag.HibritArama`) + `bdm.kanit_cikar`; hariç kriter sağlandı → uygun değil; karar eşikleri modül sabitleri. | URS-ES-02 |
| FRS-36 | `kriter_sonuclari[].kanit`: yapısal için alan adı ve değer, metin için kaynak cümle; `korumalar.kanit_dogrula` kaynakta birebir yoksa sonuç → belirsiz. | URS-ES-03, URS-BDM-03 |
| FRS-37 | `EslestirmeSonucu.inceleme_karari` (onay/red/beklet) yalnızca araştırmacı/koordinatör; "onay" gönüllü kaydını `aday` durumunda oluşturur; eşleştirme motoru hiçbir `Gonullu` kaydı yazmaz. | URS-ES-04 |
| FRS-38 | Altın standart değerlendirmesi `ml/degerlendirme/degerlendir.py`; sürüm paketinde metrik dosyası. | URS-ES-05 |
| FRS-39 | `golge_mod_karsilastir`: `EslestirmeSonucu.golge_mod=True` kayıtlar ile manuel karar tablosu; duyarlılık/özgüllük/PPV/NPV + karışıklık matrisi; arayüzde "Gölge Mod Raporu". | URS-ES-06 |
| FRS-40 | `EslestirmeSonucu.sure_ms` kaydedilir; aylık performans raporu. | URS-ES-07 |
| FRS-41 | `bdm.saglayicilar`: ollama / vllm / llamacpp yalnızca `SC_BDM_URL` (iç ağ) ile konuşur; dış adres yapılandırması başlangıçta reddedilir (`config` doğrulaması: yalnızca RFC1918 veya .local). | URS-BDM-01 |
| FRS-42 | Sıcaklık 0, sabit tohum; self-consistency yalnızca değerlendirme modunda. | URS-BDM-02 |
| FRS-43 | `korumalar.guven_esigi` (varsayılan 0,70) altı → belirsiz. | URS-BDM-04 |
| FRS-44 | `BDMIstemci` ağ hatasında `KuralTabanliSaglayici`'ya düşer; sonuç `yontem="kural"` ve arayüz rozeti "BDM erişilemedi – kural tabanlı"; `logging` WARNING. | URS-BDM-05 |
| FRS-45 | `EslestirmeSonucu.model_surumu` = sağlayıcı + model adı + model dosyası özeti (ilk 8 hex). | URS-BDM-06 |
| FRS-46 | `korumalar.phi_kontrol`: istem metninde TCKN/telefon kalıbı varsa çağrı engellenir, olay denetim izine yazılır. | URS-BDM-07 |

### 3.8 Kimliksizleştirme

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-47 | `kimliksizlestirme.kimliksizlestir(metin, mod)`: maske / takma ad / tarih kaydırma modları; tespit türleri URS-KM-01'deki gibi. | URS-KM-01 |
| FRS-48 | `Hasta.metinler` yazımı yalnızca `services/hasta.metin_ekle()` üzerinden; fonksiyon kimliksizleştirmeyi zorunlu çağırır ve bulgu sayısını `son_senkron` kaydına ekler. | URS-KM-02 |
| FRS-49 | `metni_dogrula()` ikinci geçiş; şüpheli kalıp varsa kayıt "inceleme bekliyor" olarak işaretlenir. | URS-KM-03 |
| FRS-50 | `fhir.bundle_to_hasta`: name/address/telecom/identifier alanlarını hiç okumaz; `kayit_no = sha256(kaynak_id + kurum_tuzu)[:16]`. | URS-KM-04 |

### 3.9 TMF, denetim izi, e-imza, yetki

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-51 | `Belge.tmf_bolge` (DIA TMF RM 11 bölge); yükleme sırasında SHA-256 hesaplanır ve indirmede doğrulanır. | URS-TMF-01, 02 |
| FRS-52 | Yükleme boyut/biçim kontrolü uygulama ve nginx düzeyinde. | URS-TMF-03 |
| FRS-53 | `DenetimKaydi` ekleme-yalnız; `yetkiler.sql` UPDATE/DELETE tetikleyicisi; `hash = sha256(onceki_hash + icerik)`; `scripts/denetim_dogrula.py` zinciri denetler. | URS-Dİ-01, 02, 03 |
| FRS-54 | Denetim izi arayüzü: filtre (kullanıcı, varlık, tarih), CSV/PDF dışa aktarma; dışa aktarma işlemi de kaydedilir. | URS-Dİ-04 |
| FRS-55 | `EImza`: parola yeniden doğrulama, anlam seçimi, `icerik_hash`; imzalı varlık değişince `services/imza.gecerli_mi()` false döner ve arayüzde "imza geçersiz" rozeti. | URS-Eİ-01, 02, 03 |
| FRS-56 | `Rol` numaralandırması (10 rol); yetki matrisi `services/yetki.YETKILER` (rol × işlem); merkez kapsaması `Kullanici.merkez_id`; sponsor rolü için `Hasta.metinler` alanı API ve arayüzde maskelenir. | URS-YT-01, 02 |
| FRS-57 | Parola politikası `config` değişkenleri; PBKDF2-SHA256 (600k tur); 5 hatalı → 15 dk kilit; oturum çerezi imzalı, süre `SC_OTURUM_SURESI_DK`. | URS-YT-03 |
| FRS-58 | Kullanıcı silme yok; `aktif=False`; `DenetimKaydi.kullanici_adi` kopyası. | URS-YT-04 |
| FRS-59 | LDAP bağlayıcısı (`services/yetki/ldap.py`, opsiyonel `ldap3`). | URS-YT-05 |

### 3.10 Entegrasyon ve sistem

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-60 | `fhir.hbys.HBYSAdaptoru`: FHIR R4 arama, sayfalama, token; gece senkronu `scripts/hbys_senkron.py`. | URS-ENT-01 |
| FRS-61 | `fhir.calisma_to_research_study`, `gonullu_to_research_subject`; `/api/v1/fhir/...` uç noktaları. | URS-ENT-02 |
| FRS-62 | `fhir.omop.omop_disa_aktar`: person, condition_occurrence, drug_exposure, measurement, note CSV'leri. | URS-ENT-03 |
| FRS-63 | CSV içe aktarma şablonu ve doğrulama raporu. | URS-ENT-04 |
| FRS-64 | REST API `/api/v1`, Bearer token (kullanıcıya bağlı, iptal edilebilir), OpenAPI belgesi. | URS-ENT-05 |
| FRS-65 | Docker Compose ve systemd kurulum yolları (deploy/KURULUM.md). | URS-SİS-01 |
| FRS-66 | `deploy/yedekleme.sh`; geri yükleme prosedürü KURULUM.md bölüm 8; IQ-001 madde 7 prova kaydı. | URS-SİS-02 |
| FRS-67 | nginx TLS 1.2/1.3; disk şifreleme kurulum ön koşulu (IQ kontrol). | URS-SİS-03 |
| FRS-68 | Performans testi `tests/performans/` (locust) – 50 kullanıcı, p95 ≤ 2 sn. | URS-SİS-04 |
| FRS-69 | Arayüz metinleri `web/ceviri/` (tr, en); kullanıcı tercihi. | URS-SİS-05 |
| FRS-70 | Tüm `DateTime` alanlar UTC; şablon filtresi `yerel_saat`. | URS-SİS-06 |
| FRS-71 | Uygulama logları JSON, 1 yıl saklama (logrotate); yıllık sızma testi (son: SC-PT-2025, kapatılmış bulgular). | URS-SİS-07 |

## 4. Veri modeli

Varlık ilişki özeti (ayrıntı: `smartclinical/models/`):

Calisma 1—n ProtokolVersiyon, Kriter, Kol, CalismaMerkez, Basvuru, Form, Gonullu, KaliteToleransLimiti
Merkez 1—n Arastirmaci, CalismaMerkez, Hasta
CalismaMerkez 1—n KilometreTasi, Gonullu, ProtokolSapmasi, IzlemZiyareti, RiskUyarisi
Gonullu 1—n Vizit, FormKaydi, AdversOlay; n—1 Hasta (opsiyonel), Kol
FormKaydi 1—n Sorgu
Hasta 1—n EslestirmeSonucu
Kullanici 1—n DenetimKaydi, EImza

## 5. Arayüzler

| Arayüz | Protokol | Yön | Veri |
|---|---|---|---|
| HBYS | FHIR R4 REST, OAuth2 client credentials ya da statik token | Giriş | Patient (kimliksiz), Condition, Observation, MedicationStatement, DocumentReference |
| BDM servisi | HTTP (Ollama / OpenAI-uyumlu / llama.cpp) | Çift yön | İstem (kimliksiz metin) / JSON çıktı |
| Gömme servisi | HTTP | Çift yön | Metin / vektör |
| SMTP | SMTP/TLS | Çıkış | Uyarı özetleri (hasta verisi içermez) |
| Üçüncü taraf | REST /api/v1 | Çift yön | Çalışma, merkez, gönüllü (kimliksiz), uyarı |

## 6. Onaylar

| Rol | Ad / Unvan | İmza | Tarih |
|---|---|---|---|
| Hazırlayan | Yazılım Geliştirme Yöneticisi | e-imza | 2026-02-26 |
| Gözden geçiren | Validasyon Sorumlusu | e-imza | 2026-03-02 |
| Onaylayan | Kalite Güvence Yöneticisi | e-imza | 2026-03-03 |
