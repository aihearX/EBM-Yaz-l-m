# Değişiklik Günlüğü

Biçim: Keep a Changelog. Sürümleme: anlamsal (major.minor.patch).

## Yayınlanmamış
### Eklendi
- Kullanım modu (tekil araştırmacı / üniversite-hastane / CRO), ilk kurulum ekranı ve mod bazlı menü, varsayılan merkez ve sponsor.
- Dört adımlı çalışma sihirbazı; `GET /calismalar/yeni` sihirbaza yönlendirir, hızlı oluşturma için `POST /calismalar/yeni` korundu.
- Çalışma tasarımı sekmesi: kollar, çalışma bazlı vizit şeması (`VizitTanimi`), kodsuz eCRF tasarımcısı (koşullu alanlar, bölüm başlıkları, çoklu seçim), kaydı olan formda sürümleme ve denetim izi, protokol metninden kural tabanlı/BDM destekli taslak (yalnızca öneri, uygulama insan onayıyla).
- Analiz sekmesi: değişken bazlı betimleyici özet, otomatik test seçimi (Welch t / Mann-Whitney / ANOVA / Kruskal-Wallis / ki-kare / Fisher), gönüllü akışı, kol × SOC advers olay özeti, analiz veri seti CSV (denetim izine yazılır).
- Çalışma ekibi sekmesi: kullanıcı × çalışma ataması; atama yapıldığında proje ekibi yalnızca atandığı çalışmaları görür. Yeni izinler: `ekip.yonet`, `analiz.goruntule`.
- Bölüm bazlı araştırmacı listesi (üniversite modu), merkez düzenleme, `Arastirmaci.bolum` alanı.
- Rol bazlı sekme görünürlüğü tek noktadan (`sekme_gorunur`); rotalarda aynı kural 403 üretir. Rol senaryo testleri.
### Değiştirildi
- Genel bakış role göre üç görünüme ayrıldı (merkez, izlem, portföy); sponsor portföy özeti (takvim riski, en riskli merkez, fizibilite raporu) buraya taşındı. Boş kurulumda ilk çalışma kartı.
- Aşama kontrol listesi statik metin yerine veriden hesaplanır; aşama değişikliğinde gerekçe zorunlu.
- Vizit şeması ve edit-check iş mantığı `services/ecrf.py` altına taşındı; veri girişinde yalnızca yayındaki formlar görünür.
- Gönüllü sayfaları, çalışma listesi ve API uçları çalışma erişim kuralına (`yetki.calisma_erisimi`) bağlandı.
- Veri giriş formunda CDASH değişken adı ve ham durum değerleri gösterilmez.
### Kaldırıldı
- Ar-Ge göstergeleri sayfası ve servisi; model değerlendirme `ml/degerlendirme` altında komut satırından yapılır.
- Türkçe Klinik BDM Konsolu sayfası ve `POST /yz/soru-cevap` ucu (ICD kodlama ve özet uçları kalır).
- Ayrı Sponsor Portalı sayfası; menüden "Yapay Zekâ Araçları" grubu ve üst düzey "Merkez Performans Endeksi" maddesi (endeks Merkezler sayfasından açılır); API belgeleri bağlantısı yalnızca yöneticide.
- Tek sayfalık "Yeni çalışma" formu.

## [1.5.0] - 2026-10-22
### Eklendi
- Sponsor portalı: kurum bazlı salt okunur portföy görünümü, takvim riski, en riskli merkez, fizibilite raporu bağlantısı.
- Merkez Performans Endeksi: çalışmalar arası anonim kıyaslama (aktivasyon, hasta/ay, tarama başarısızlığı, sorgu oranı; yüzdelik dilimler, kurum tipi medyanları).
- CSV ile hasta havuzu yükleme (FHIR bağlantısı olmayan kurulumlar için); kimlik alanı yazılmaz, metinler kimliksizleştirilir, şüpheli satırlar reddedilir.
- API anahtarı ile makine-makine erişim (`X-SC-Anahtar`), yönetim sayfası, geçerlilik süresi ve iptal.
- Ar-Ge göstergeleri sayfası: altın standart, gölge mod, MAPE/AUC, ön tarama süresi, etki hesaplayıcı.
- CDISC ODM 1.3.2 ve CSV paketi dışa aktarımı; sponsor fizibilite raporu.
- Genel amaçlı klinik NLP uçları: ICD-10 kodlama, özet, soru-cevap.
- TR-KlinikBench değerlendirme seti, federe LoRA güncelleme iskeleti, model ve veri kartları (`ml/`).

## [1.4.2] - 2026-10-21
### Düzeltildi
- Kriter yapısal sorgusu `KriterYapisi.to_dict()` ile sarmalanmış kaydedildiğinde eşleştirme
  motorunun tüm kriterleri "belirsiz" döndürmesi (#171).
- "Daha önce ... tedavi almış" kalıbı tanı kriteri olarak yorumlanıyordu; artık tedavi geçmişi (#167).
- HER2-negatif / ER negatif gibi biyobelirteç ifadeleri kriterin olumsuzlanması sayılmıyor.
- "ms" kısaltması multipl skleroz olarak eşleniyordu; kaldırıldı, QTc ve LVEF laboratuvar sözlüğüne eklendi.
- Tip 1 / tip 2 diyabet terimlerinin birbirine karışması.
### Eklendi
- Kural tabanlı metin değerlendirme: laboratuvar değeri, yaş, ECOG/NYHA, TNM evre, reseptör durumu,
  gebelik, tedavi geçmişi ve zaman penceresi için sayısal/kalıp karşılaştırma (`bdm/metin_kurallari`).
- Eşleştirmede ICD-10 ön filtresi: dahil kriterlerinde tanı kodu varsa yalnızca ilgili hastalar taranır.
- Web katmanı ve denetim izi için duman testleri.

## [1.4.1] - 2026-09-30
### Eklendi
- Gölge mod raporu (model kararı ve araştırmacı kararı karşılaştırması; duyarlılık, özgüllük, PPV, NPV).
- RBM uyarılarında "neden tetiklendi" açıklaması ve otomatik kapanış.
- `/saglik` uç noktası (Docker healthcheck).
### Değiştirildi
- Oturum çerezi `SameSite=Strict`, üretimde `Secure` zorunlu.

## [1.4.0] - 2026-09-08
### Eklendi
- Merkez zekâsı: Gamma-Poisson hiyerarşik kazanım tahmini, Weibull AFT gecikme modeli, Monte Carlo projeksiyon.
- Risk bazlı izlem modülü: 15 varsayılan KRI, QTL, medyan/MAD anomali tespiti, bileşik risk puanı.
- OMOP CDM v5.4 CSV dışa aktarımı.
- BDM sağlayıcıları: Ollama, vLLM (OpenAI uyumlu), llama.cpp; ağ hatasında kural tabanlı moda düşme.

## [1.3.0] - 2026-06-16
### Eklendi
- Türkçe klinik metin kimliksizleştirme (TCKN algoritma doğrulaması, takma ad ve tarih kaydırma modları).
- FHIR R4 HBYS adaptörü (`_has:Condition` sorgusu, sayfalama, `$everything`).
- TMF modülü: DIA referans modeli bölgeleri, SHA-256, e-imza ile onay.
### Değiştirildi
- Denetim izi hash zincirli hale getirildi; `denetim_dogrula` betiği eklendi.

## [1.2.0] - 2026-03-04
### Eklendi
- Güvenlik modülü: AE/SAE, CTCAE, nedensellik, SUSAR tespiti, TİTCK 7/15 gün bildirim sayacı.
- Protokol sapmaları ve izlem ziyaretleri (SIV/IMV/COV/uzaktan/tetiklenmiş).
- Etik kurul / TİTCK / kurum izni / KVKK başvuru takibi.

## [1.1.0] - 2025-12-10
### Eklendi
- eCRF: CDASH uyumlu form tanımları, otomatik edit-check, sorgu yönetimi, SDV, veri kilidi (e-imza).
- Rol bazlı erişim denetimi (10 rol), hesap kilitleme, parola politikası.

## [1.0.0] - 2025-09-22
- İlk bütünleşik sürüm: çalışma, merkez, gönüllü yönetimi; denetim izi; REST API v1.
