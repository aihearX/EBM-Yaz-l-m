# FRS-001 Fonksiyonel Spesifikasyon

| | |
|---|---|
| Belge No | FRS-001 |
| Sistem | EBM SmartClinical |
| Hazırlayan | Yazılım Geliştirme Yöneticisi |
| Gözden geçiren | Validasyon Sorumlusu, Veri Yönetimi Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Amaç

URS-001'deki her gereksinimin sistemde nasıl karşılandığını, kodun gerçek dosya ve rota
adlarıyla tanımlar. Her fonksiyon FRS-xx kodu ile URS'ye, TM-001 ile de otomatik teste izlenir.
Burada adı geçen her modül, rota ve betik depoda vardır; numaralandırmadaki boşluklar
kaldırılmış fonksiyonlara aittir (TM-001 bölüm 11).

## 2. Sistem mimarisi

```
 Kullanıcı (tarayıcı) ──TLS──> nginx ──> FastAPI uygulaması (smartclinical/)
                                              ├── web/      (Jinja2 şablonları, sunucu tarafı render)
                                              ├── api/      (REST, /api/v1)
                                              ├── services/ (kimliksizlestirme, kriter, bdm, eslestirme,
                                              │              merkez_zekasi, rbm, fhir, ecrf, analiz, denetim, yetki)
                                              ├── scripts/  (gece_isleri, denetim_dogrula, hasta_saklama, ...)
                                              └── models/   (SQLAlchemy) ──> PostgreSQL 16 (geliştirmede SQLite)
                                                     BDM servisi (Ollama / llama.cpp, hastane içi; isteğe bağlı)
                                                     Gömme servisi (RAG; isteğe bağlı)
                                                     HBYS FHIR R4 uç noktası (salt okunur; isteğe bağlı)
```

Uygulama modüler monolit olarak paketlenir; BDM ve gömme servisleri ayrı konteynerlerdir.
Tüm bileşenler dış dünyaya kapalı `uygulama` docker ağında çalışır (`deploy/docker-compose.yml`).

## 3. Fonksiyonlar

### 3.1 Çalışma yönetimi

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-01 | `models/calisma.py`: `Calisma`, `CalismaTuru` (9 tür), `CalismaDurumu`; `web/calismalar.py` içinde `TITCK_GEREKEN` türleri başvuru kontrol listesini belirler. Yeni çalışma `GET/POST /calismalar/yeni`. | URS-ÇY-01 |
| FRS-02 | `web/calismalar.py::kontrol_listesi` her aşama için veriden hesaplanan maddeleri (etiket, tamam, bağlantı) üretir; `POST /calismalar/{calisma_id}/durum` gerekçe ister ve eski/yeni durumu denetim izine yazar. Kontrol listesi bilgilendiricidir; aşama kararını proje yöneticisi verir. | URS-ÇY-02 |
| FRS-03 | `ProtokolVersiyon` yalnızca eklenir (`POST /calismalar/{calisma_id}/protokol/versiyon`); silme rotası yoktur. | URS-ÇY-03 |
| FRS-04 | `Kriter`: tip, sıra, metin, `yapisal` (JSON), `guven`, `onaylandi`. Yapılandırma `services/kriter/ayristirici.py` (kural tabanlı; BDM varsa doğrulanıp kullanılır); onay `POST /calismalar/{calisma_id}/protokol/kriter/{kriter_id}/onayla`. | URS-ÇY-04, URS-ES-01 |
| FRS-05 | `CalismaMerkez.aktivasyon_tarihi`, `ilk_hasta_tarihi`; SIV gerçekleşmesi `IzlemZiyareti` (tip SIV, gerçekleşen tarih dolu) ile okunur ve `kontrol_listesi` aktivasyon maddesini tamamlar. Ayrı kilometre taşı tablosu yoktur. | URS-ÇY-05 |
| FRS-06 | `web/pano.py` (`GET /`): rol ve `yetki.calisma_filtresi` ile erişilebilen çalışmaların özetleri; sayılar çalışma listesiyle aynı tanımdan (`KAYITLI_DURUMLAR`) gelir. | URS-ÇY-06 |
| FRS-72 | `web/sihirbaz.py` (`/sihirbaz/1`…`/4`), `services/kurulum.py`: mod varsayılanları, protokol kodu önerisi ve benzersizlik; taslak veritabanında tutulur; CRO modunda ekip ve aday merkez seçimi. | URS-ÇY-07 |

### 3.2 Merkez yönetimi ve merkez zekâsı

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-07 | `models/merkez.py`: `Merkez`, `Arastirmaci` (GCP eğitim, CV tarihi, tamamlanan çalışma); `POST /merkezler`, `POST /merkezler/{mid}/arastirmaci`. | URS-MZ-01 |
| FRS-08 | `CalismaMerkez.durum` 9 durumlu akış (`CM_DURUMLAR`); `POST /calismalar/{calisma_id}/merkezler/{cm_id}/durum` seçim/aktivasyon tarihlerini doldurur. | URS-MZ-02 |
| FRS-09 | `services/merkez_zekasi/kazanim.py::kazanim_tahmini`: Gamma-Poisson hiyerarşik model, havuz parametreleri moment/MLE kestirimi, posterior ortalama ve %90 aralık, `aciklama` listesi; arayüzde `GET /calismalar/{calisma_id}/merkez-zekasi`. | URS-MZ-03 |
| FRS-10 | `services/merkez_zekasi/aktivasyon.py::GecikmeModeli`: Weibull AFT, sansürlü veri; eğitim verisi yoksa öncül parametreler ve "öncül" etiketi. | URS-MZ-04 |
| FRS-11 | `services/merkez_zekasi/siralama.py::merkez_sirala`: bileşen ağırlıkları parametre olarak ezilebilir; çıktı puan + katkı + gerekçe. | URS-MZ-05 |
| FRS-12 | `kazanim.py::calisma_kazanim_projeksiyonu`: Monte Carlo (sabit tohum) ile hedefe ulaşma ayı dağılımı. | URS-MZ-06 |
| FRS-73 | `scripts/gece_isleri.py`: aktif çalışmalarda `erken_uyari_calistir`, `qtl_guncelle`, `calisma_tahmin_guncelle` ve SAE süre sayımı; çalışma başına denetim izine `zamanlanmis` olayı; `--kuru-calisma`. Zamanlama `deploy/systemd/smartclinical-gece.timer`. | URS-MZ-07, URS-GV-03 |

### 3.3 Başvurular

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-13 | `models/basvuru.py`: kurum × tip; `POST /calismalar/{calisma_id}/basvurular`. | URS-BŞ-01 |
| FRS-14 | `Basvuru.sure_gun` türetilmiş alan; karar `POST /calismalar/{calisma_id}/basvurular/{basvuru_id}/karar`; onaysız karar kayıt aşaması kontrol listesinde eksik görünür. | URS-BŞ-02 |
| FRS-15 | Başvuru belgeleri TMF bölge 03/04'e yüklenir (`FRS-51`); başvuru kaydı ile belge arasında ayrı bir bağ alanı yoktur. | URS-BŞ-03 |

### 3.4 EDC

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-16 | `Form.alanlar` JSON şeması (`services/ecrf.py::ALAN_ANAHTARLARI`); standart form kütüphanesi ve vizit şablonları `services/ecrf.py`; tasarımcı `web/ecrf.py` (`/calismalar/{calisma_id}/tasarim/...`); kayıtlı formda alan silme reddedilir, sürüm artırılır. | URS-EDC-01 |
| FRS-17 | `services/ecrf.py` form doğrulama ve edit-check (tip, aralık, zorunluluk, koşul); ihlalde `Sorgu(kaynak="otomatik")` açılır, kayıt engellenmez (`web/gonulluler.py::form_kaydet`). | URS-EDC-02 |
| FRS-18 | `Sorgu` durum makinesi; `acik_gun` türetilmiş; `POST /gonulluler/{gid}/sorgu/{sid}` (cevapla/kapat), `POST /calismalar/{calisma_id}/veri/sorgu-toplu` seçili sorguları kapatır (sorgu.ac izni, merkez filtresi). | URS-EDC-03 |
| FRS-19 | `FormKaydi.durum` akışı; SDV `POST /gonulluler/{gid}/form-kaydi/{fk_id}/sdv`; tekil kilit e-imzalı; toplu kilit `web/veri_islem.py`: `GET /calismalar/{calisma_id}/veri/kilit` ön kontrol (açık sorgu, SDV yok, PI imzası yok/yenilenmeli, taslak), `POST .../veri/kilit` tek e-imza ile uygun kayıtları kilitler ve geçemeyenleri raporlar; `POST .../veri/kilit-ac/{fk_id}` gerekçe zorunlu, denetim izine `kilit_ac` (eski/yeni), durum `tamamlandi`. | URS-EDC-04 |
| FRS-20 | Değişiklikler `services/denetim.kaydet` ile açık çağrıyla yazılır (web/API katmanı); eski/yeni değer JSON. ORM olay dinleyicisi yoktur; kural: denetim izine yazılmayan değişiklik kabul edilmez (docs/gelistirme.md). | URS-EDC-05, URS-Dİ-01 |
| FRS-21 | `models/tasarim.py::VizitTanimi`; randomizasyonda `Vizit` kayıtları üretilir; `Vizit.pencere_disi` türetilmiş; kaçırılan vizit gerekçe ister (`POST /gonulluler/{gid}/vizit/{vid}`). | URS-EDC-06 |
| FRS-22 | `web/disa_aktar.py`: CSV paketi (noktalı virgül, UTF-8 BOM) ve CDISC ODM 1.3.2 (`GET /calismalar/{calisma_id}/veri/disa-aktar?bicim=csv|odm`); ODM'de `StudyEventDef` vizit tanımlarından (`SE.V{sira}`), ASCII ve benzersiz OID'ler, `AdminData/Location` + `SiteRef`, `IG.AE` ve `IG.DS` grupları, tekrarlayan formlarda `Repeating="Yes"`, `?denetim=1` ile `AuditRecord`. | URS-EDC-07 |
| FRS-74 | `web/veri_islem.py`: araştırmacı imzası `POST /calismalar/{calisma_id}/veri/imza/{gid}` (yalnızca araştırmacı rolü, parola); imzalanan içerik gönüllünün tüm form kayıtlarının özet sözlüğü; `imza_durumu` imzadan sonra değişen kayıt varsa `yenilenmeli` döner. | URS-EDC-08, URS-Eİ-03 |
| FRS-75 | `services/randomizasyon.py`, `web/randomizasyon.py` (`smartclinical/web/randomizasyon.py`): blok/strata listesi, e-imza zorunlu; kol ataması listeden. | URS-EDC-09 |

### 3.5 Güvenlik

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-23 | `models/guvenlik.py::AdversOlay`; MedDRA kodlama elle; `POST /gonulluler/{gid}/advers-olay`, güncelleme denetim izinde. | URS-GV-01 |
| FRS-24 | `AdversOlay.susar`: `ciddi and not beklenen and nedensellik in {olasi, muhtemel, kesin}`. | URS-GV-02 |
| FRS-25 | `AdversOlay.bildirim_suresi_gun`: ölüm/yaşamı tehdit → 7 gün, diğer ciddi → 15 gün; panelde geri sayım; gece işi süresi dolan ve 2 gün içinde dolacakları sayar. | URS-GV-03 |
| FRS-26 | Sponsor/TİTCK/etik bildirim tarihleri (`POST /gonulluler/{gid}/advers-olay/{aid}/bildirim`); `services/rbm/gostergeler.py::hesapla_sae_gec_bildirim`. | URS-GV-04 |

### 3.6 RBM ve izlem

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-27 | `services/rbm/gostergeler.py::VARSAYILAN_KRILER`; çalışma bazında `RiskGostergesi` kopyası genel şablonu ezer. | URS-RBM-01 |
| FRS-28 | `KaliteToleransLimiti`; `services/rbm/uyari.py::qtl_guncelle` istek üzerine ve gece işinde. | URS-RBM-02 |
| FRS-29 | `services/rbm/anomali.py::anomali_tespit`: medyan/MAD robust z-skor; az merkezde sınırlı güven notu; `cusum`. | URS-RBM-03 |
| FRS-30 | `uyari.py::erken_uyari_calistir`: eşik ve aykırılık → `RiskUyarisi` (açıklama alanı); açık uyarı güncellenir, normale dönen uyarı otomatik kapanır; `POST /calismalar/{calisma_id}/rbm/calistir`. | URS-RBM-04 |
| FRS-31 | Uyarı durum akışı `POST /calismalar/{calisma_id}/rbm/uyari/{uyari_id}`; aksiyon seviyesindeki uyarıdan `POST /calismalar/{calisma_id}/izlem/tetikle/{uyari_id}` tetiklenmiş ziyaret oluşturur (`tetikleyen_uyari_id`), uyarı "inceleniyor" olur. | URS-RBM-05 |
| FRS-32 | `CalismaMerkez.risk_puani` (`bilesik_risk_puani`), `izlem_onerisi`. | URS-RBM-06 |
| FRS-33 | `web/izlem.py`: ziyaret planlama (`POST /calismalar/{calisma_id}/izlem/ziyaret`), rapor sayfası `GET/POST .../izlem/ziyaret/{zid}` (gerçekleşen tarih, katılımcılar, SDV oranı, `ZIYARET_KONTROL` kontrol listesi, rapor metni), bulgu ekleme/kapatma, PY e-imzası `POST .../izlem/ziyaret/{zid}/onay` (rapor_onay, onaylayan_id, imza kaydı); onaylı rapor değiştirilemez; `onceki_acik_bulgular` aynı merkezin son ziyaretindeki açık bulguları yeni ziyarete taşır; sayfa yazdırılabilir. Tip ve durum etiketleri `models/izlem.py` sözlüklerinden. | URS-RBM-07 |
| FRS-34 | `ProtokolSapmasi`: kök neden, düzeltici faaliyet, sorumlu, hedef tarih, etik bildirim, kapanış tarihi; `POST /calismalar/{calisma_id}/izlem/sapma/{sid}` kapatmada kök neden ve düzeltici faaliyet, majörde etik bildirim tarihi zorunlu. | URS-RBM-08 |

### 3.7 Eşleştirme ve BDM

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-35 | `services/eslestirme/__init__.py`: her kriter için yapısal değerlendirme (`kriter/degerlendirici.py`), belirsizse metin (RAG + kanıt çıkarma); hariç kriter sağlandı → uygun değil; `POST /calismalar/{calisma_id}/eslestirme/calistir`. | URS-ES-02 |
| FRS-36 | `kriter_sonuclari[].kanit`; `services/bdm/korumalar.py::kanit_dogrula` kaynakta birebir (normalize) yoksa sonuç belirsiz. | URS-ES-03, URS-BDM-03 |
| FRS-37 | `EslestirmeSonucu.inceleme_karari` (onay/red/beklet) `POST /calismalar/{calisma_id}/eslestirme/{sonuc_id}/incele`; eşleştirme motoru `Gonullu` yazmaz; onay gönüllüyü aday durumunda oluşturur. | URS-ES-04 |
| FRS-38 | `ml/degerlendirme/degerlendir.py` altın standart ölçümü; metrikler `ml/degerlendirme/metrikler.py`. | URS-ES-05 |
| FRS-39 | `golge_mod_karsilastir`; `GET /calismalar/{calisma_id}/eslestirme-golge`: duyarlılık/özgüllük/PPV/NPV ve karışıklık matrisi. | URS-ES-06 |
| FRS-41 | `services/bdm/istemci.py`: sağlayıcılar (kural / ollama / vllm / llamacpp) yalnızca `SC_BDM_URL` ile konuşur; docker ağı `internal`. | URS-BDM-01 |
| FRS-42 | Üretimde sıcaklık 0; çoğunluk oyu yalnızca `oy_sayisi > 1` yapılandırıldığında. | URS-BDM-02 |
| FRS-43 | `korumalar.py` güven eşiği altı → belirsiz. | URS-BDM-04 |
| FRS-44 | `BDMIstemci` ağ hatasında kural tabanlı sağlayıcıya düşer; `yontem="kural"`, arayüz rozeti, WARNING log. | URS-BDM-05 |
| FRS-45 | `EslestirmeSonucu.model_surumu` sağlayıcı + model adı. | URS-BDM-06 |
| FRS-46 | `korumalar.py::phi_kontrol`: istemde TCKN/telefon kalıbı varsa çağrı engellenir. | URS-BDM-07 |

### 3.8 Kimliksizleştirme ve hasta havuzu

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-47 | `services/kimliksizlestirme/__init__.py::kimliksizlestir(metin, mod)`: maske / takma ad / tarih kaydırma; kurallar `kurallar.py`, klinik terim listesi `sozluk.py`; `POST /api/v1/yz/kimliksizlestir`, arayüz `GET /araclar/kimliksizlestirme`. | URS-KM-01 |
| FRS-48 | `api/hastalar.py` ve `POST /merkezler/{mid}/hasta-yukle` metinleri yazmadan önce kimliksizleştirir. | URS-KM-02 |
| FRS-49 | `metni_dogrula()` ikinci geçiş; şüpheli kalıp raporu. | URS-KM-03 |
| FRS-50 | `services/fhir/__init__.py::bundle_to_hasta`: name/address/telecom/identifier alanlarını okumaz; `kayit_no = HMAC-SHA256(SC_TAKMA_AD_ANAHTARI, merkez + kaynak id)`; anahtar değişiminde `scripts/yeniden_anahtarla.py`. | URS-KM-04 |
| FRS-76 | `scripts/hasta_saklama.py`: merkezin açık çalışması kalmamış ve son kapanış `--ay` ay önceyse gönüllüye bağlı olmayan `Hasta` kayıtları (ve eşleştirme sonuçları) silinir; `--kayit-no` ile tekil silme, gönüllüye bağlıysa ya da `--kisitla` ile klinik içerik boşaltılıp `kaynak="kisitli"`; `--kuru-calisma`; denetim izine `sil`/`kisitla` (takma ad yazılmaz). | URS-KM-05 |

### 3.9 TMF, denetim izi, e-imza, yetki

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-51 | `web/belgeler.py`: liste (`?merkez_id=` ISF görünümü, eskimiş belgeler katlanır, tamlık yüzdesi onaylı ve eskimemiş belgelere göre), yükleme (SHA-256; aynı bölge+ad+merkez için önceki belge `eskimis`, `Belge.onceki_id` zinciri), e-imzalı onay, indirme `GET /calismalar/{calisma_id}/belgeler/{belge_id}/indir` (özet doğrulanır, denetim izine `goruntule`; merkez rolleri yalnızca kendi merkezinin belgesi). | URS-TMF-01, 02, URS-BŞ-03 |
| FRS-52 | `belgeler.py::dosya_kontrol`: izinli uzantılar (`models/belge.py::IZINLI_UZANTILAR`), 25 MB sınırı, bildirilen tür ve ilk bayt (magic) kontrolü; nginx `client_max_body_size 26m`. | URS-TMF-03 |
| FRS-53 | `services/denetim.py`: `hash = HMAC-SHA256(anahtar, onceki_hash + zaman + kullanıcı + işlem + eski + yeni)`, anahtar `SC_SECRET_KEY`'den türetilir; zincir ucu `DenetimZincir` (id=1) PostgreSQL'de `SELECT ... FOR UPDATE`, SQLite'ta `BEGIN IMMEDIATE` ile kilitlenir; `zinciri_dogrula` aynı anahtarla yeniden hesaplar; `scripts/denetim_dogrula.py`; `deploy/postgres/yetkiler.sql` UPDATE/DELETE yasağı ve tetikleyici. | URS-Dİ-01, 02, 03 |
| FRS-54 | Denetim izi arayüzü `GET /yonetim/denetim` (filtre: kullanıcı, varlık, tarih; CSV) ve çalışma bazlı `GET /calismalar/{calisma_id}/denetim`; dışa aktarma kaydedilir. | URS-Dİ-04 |
| FRS-55 | `denetim.imzala`: parola yeniden doğrulama (`yetki.parola_dogrula`), anlam, `icerik_hash` (düz SHA-256, anahtardan bağımsız); imza her seferinde parola ister. | URS-Eİ-01, 02 |
| FRS-56 | `Rol` (10 rol); yetki matrisi `services/yetki.py::IZINLER`; çalışma görünürlüğü `calisma_erisimi` (yönetici/denetçi tümü, sponsor kurumu, merkez rolleri merkezi, atanabilir roller üyelik); `gonullu_erisimi`; sekme × rol kuralı `web/calismalar.py::sekme_gorunur` (docs/roller.md ile test edilir). | URS-YT-01, 02 |
| FRS-57 | `services/yetki.py`: PBKDF2-SHA256 (200 000 tur), `parola_politikasi` (min 12, harf+rakam), `PAROLA_GECMISI = 5`, 90 gün (`SC_PAROLA_GUN`), `kilit_suresi` 15 dk × 2^n, IP başına deneme sınırı (`web/giris.py`), ilk girişte değişim; oturum çerezi imzalı, süre `SC_OTURUM_SURESI_DK`. | URS-YT-03 |
| FRS-58 | Kullanıcı silme yok; `POST /yonetim/kullanicilar/{kid}/durum` pasifleştirir; `DenetimKaydi.kullanici_adi` kopyası. | URS-YT-04 |
| FRS-77 | `models/ekip.py::CalismaUyesi`, `web/ekip.py` (`POST /calismalar/{calisma_id}/ekip/ekle`); `yetki.kisit_aktif` ilk atamayla devreye girer. | URS-YT-05 |

### 3.10 Entegrasyon ve sistem

| Kod | Fonksiyon | URS |
|---|---|---|
| FRS-60 | `services/fhir/hbys.py::HBYSAdaptoru`: FHIR R4 arama, token; eşitleme `POST /api/v1/hbys/senkron?merkez_id=` (hasta.goruntule, merkez erişimi). Zamanlanmış eşitleme yoktur. | URS-ENT-01 |
| FRS-61 | `fhir.calisma_to_research_study`, `gonullu_to_research_subject`; `GET /api/v1/fhir/ResearchStudy/{cid}`, `GET /api/v1/fhir/ResearchSubject/{gid}`. | URS-ENT-02 |
| FRS-62 | `services/fhir/omop.py::omop_disa_aktar`; `scripts/omop_aktar.py`. | URS-ENT-03 |
| FRS-63 | CSV içe aktarma `GET/POST /merkezler/{mid}/hasta-yukle`: sütun düzeni sayfada, reddedilen satırlar sonuçta listelenir. | URS-ENT-04 |
| FRS-64 | REST API `/api/v1`; `X-SC-Anahtar` (SHA-256 özeti saklanır, iptal edilebilir, `POST /yonetim/api-anahtarlari`); API belgeleri `GET /api/belgeler` ve `GET /api/openapi.json` oturum ister (`main.py`). | URS-ENT-05 |
| FRS-78 | `web/disa_aktar.py`: `GET .../veri/sorgular.csv` (durum, merkez), `GET .../gonulluler.csv` (durum, merkez), `GET .../izlem/ziyaretler.csv`, `GET .../izlem/sapmalar.csv`; sekme yetkisi ve merkez filtresi; denetim izine `disa_aktar`. | URS-ENT-06 |
| FRS-65 | `deploy/docker-compose.yml` (sema → yetki → app sırası, internal ağ), `deploy/systemd/smartclinical.service`, `deploy/KURULUM.md`. | URS-SİS-01 |
| FRS-66 | `deploy/yedekleme.sh`: pg_dump/sqlite + TMF arşivi `age` ile şifrelenir; günlük 7 gün, haftalık 30 gün, aylık 25 yıl; geri yükleme KURULUM.md bölüm 8. | URS-SİS-02 |
| FRS-67 | `deploy/nginx/smartclinical.conf`: TLS 1.2/1.3, HSTS, CSP; uygulama katmanı `main.py` ek başlıklar; disk şifreleme kurulum ön koşulu (IQ). | URS-SİS-03 |
| FRS-70 | `models/_ortak.py::simdi` UTC (tz bilgisiz) döner; tüm `DateTime` alanlar bu değeri kullanır. | URS-SİS-04 |
| FRS-71 | `api/sistem.py`: `/saglik` yalnızca `{"durum":"ok"}`; `/surum` oturumlu; `main.py` `/docs` kapalı; loglarda yalnızca sayılar (docs/gelistirme.md). | URS-SİS-05 |
| FRS-79 | `services/analiz.py` + `web/analiz.py` (`/calismalar/{calisma_id}/analiz`, `/tablo1`, `/tablo1.csv`, `/advers-olaylar`, `/veri-seti.csv`); taslak kayıtlar dışlanır; sponsor ve CRA 403. | URS-SİS-06 |

## 4. Veri modeli

Varlık ilişki özeti (ayrıntı: `smartclinical/models/`):

Calisma 1—n ProtokolVersiyon, Kriter, Kol, CalismaMerkez, Basvuru, Form, Gonullu, VizitTanimi, KaliteToleransLimiti, RiskUyarisi, Belge, CalismaUyesi
Merkez 1—n Arastirmaci, CalismaMerkez, Hasta, Belge (merkez bazlı)
CalismaMerkez 1—n Gonullu, ProtokolSapmasi, IzlemZiyareti, RiskUyarisi
Gonullu 1—n Vizit, FormKaydi, AdversOlay; n—1 Hasta (opsiyonel), Kol
FormKaydi 1—n Sorgu
Hasta 1—n EslestirmeSonucu
Belge n—1 Belge (onceki_id sürüm zinciri)
Kullanici 1—n DenetimKaydi, EImza, ApiAnahtari; DenetimZincir tek satır (zincir ucu)

## 5. Arayüzler

| Arayüz | Protokol | Yön | Veri |
|---|---|---|---|
| HBYS | FHIR R4 REST, statik token | Giriş (elle tetiklenir) | Patient (kimliksiz), Condition, Observation, MedicationStatement, DocumentReference |
| BDM servisi | HTTP (Ollama / OpenAI-uyumlu / llama.cpp) | Çift yön | İstem (kimliksiz metin) / JSON çıktı |
| Gömme servisi | HTTP | Çift yön | Metin / vektör |
| Üçüncü taraf | REST /api/v1 | Çift yön | Çalışma, kriter, uyarı, hasta (kimliksiz), FHIR kaynakları |
| Dışa aktarım | HTTPS indirme | Çıkış | CSV paketi, ODM, liste CSV'leri, OMOP CSV'leri |

## 6. Onaylar

| Rol | Ad / Unvan | İmza |
|---|---|---|
| Hazırlayan | Yazılım Geliştirme Yöneticisi | |
| Gözden geçiren | Validasyon Sorumlusu | |
| Onaylayan | Kalite Güvence Yöneticisi | |
