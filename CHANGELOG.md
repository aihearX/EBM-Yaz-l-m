# Değişiklik Günlüğü

Biçim: Keep a Changelog. Sürümleme: anlamsal (major.minor.patch).

## Yayımlanmamış
### Eklendi
- Süreli hesap kilidi (15 dk, her kilitte iki katına çıkar) ve denetim izinde `kilit` kaydı; IP başına giriş deneme sınırı.
- `/hesap/parola` ile parola değişimi, ilk girişte zorunlu değişim, son beş parolanın reddi, `SC_PAROLA_MIN` / `SC_PAROLA_GUN`; `scripts/kilit_ac.py`.
- HMAC-SHA256 hasta takma adı (`SC_TAKMA_AD_ANAHTARI`, üretimde zorunlu) ve `scripts/yeniden_anahtarla.py`.
- Sihirbaz taslağı veritabanında (`CalismaTaslagi`); CRO modunda üçüncü adımda ekip seçimi; kurucu kendiliğinden ekip üyesi; tekil/üniversite modunda merkez kurulumla aktif.
- Denetim izinde tarih aralığı filtresi, okunur işlem cümleleri ve CSV indirme; kullanıcı ekleme formunda kurum alanı.
- Gruplu çalışma sekmeleri (Kurulum / Yürütme / İzlem / Kapanış); gönüllü ve veri listelerinde sayfalama; `docs/roller.md`.
- Gönüllü yaşam döngüsü: izinli durum geçişleri (400), onam ve taramada tarama vizitleri, randomizasyonda dahil/hariç denetimi ve kol zorunluluğu, tek kollu çalışmada "Çalışmaya alındı".
- Dahili blok randomizasyon modülü (e-imzalı liste, strata: yok / merkez, sıradaki tahsis); aşama kontrol listesinde randomizasyon maddesi.
- eCRF: tamamlama sonrası sorunlu alanda formda kalma ve "yine de tamamla", tekrarlayan form satırları, form sürümü kaydı, etiketli rozetler, görüntüleme denetim izi.
- Güvenlik: AE güncelleme sayfası (gerekçeli, eski/yeni), MedDRA SOC listesi, SAE yükseltmede farkındalık tarihi. Onarım betiği `onarim_tarama_vizitleri`.
- İzlem döngüsü: ziyaret raporu, kontrol listesi, proje yöneticisi e-imzası, açık bulguların sonraki ziyarete taşınması, uyarıdan tetiklenmiş ziyaret, sapma kapatma (majörde etik bildirim zorunlu).
- TMF: indirme, sürüm zinciri, ISF görünümü, yükleme kontrolleri (uzantı, tür, boyut).
- Veri yönetimi: araştırmacı imzası, toplu kilit (ön kontrol raporu, tek e-imza), gerekçeli kilit açma, toplu sorgu kapatma, CSV uçları; ODM yapısal düzeltmeleri (StudyEventDef, SiteRef, AE/DS, Repeating, isteğe bağlı AuditRecord).
- Denetim izi HMAC-SHA256 ve kilitli zincir ucu (`denetim_zincir`); `gece_isleri` ve `hasta_saklama` betikleri.
- eCRF tasarımcısı sadeleştirildi (altı sütun ve ayrıntı paneli, otomatik kod, hızlı ekleme, canlı önizleme); vizit × form matrisi; protokol taslağında kalıplar ve tanınmayan satırlar; PDF/DOCX yükleme (dosya saklanmaz, denetim kaydı `protokol_belge`); kriter cümlesi ve güven eşiği üstünde toplu onay.
- Analiz: başlangıç viziti ve tüm vizitler modu, vizitler arası değişim, Tablo 1, türetilmiş yaş, merkez sınırı. RBM: "Kaçırılan vizit oranı" KRI'si. BDM dış adres koruması ve `bdm_istem` denetim özeti; Ayarlar sayfasında BDM bloğu.
- Kullanım modu (tekil araştırmacı / üniversite-hastane / CRO), ilk kurulum ekranı ve mod bazlı menü, varsayılan merkez ve sponsor.
- Dört adımlı çalışma sihirbazı; `GET /calismalar/yeni` sihirbaza yönlendirir, hızlı oluşturma için `POST /calismalar/yeni` korundu.
- Çalışma tasarımı sekmesi: kollar, çalışma bazlı vizit şeması (`VizitTanimi`), kodsuz eCRF tasarımcısı (koşullu alanlar, bölüm başlıkları, çoklu seçim), kaydı olan formda sürümleme ve denetim izi, protokol metninden kural tabanlı/BDM destekli taslak (yalnızca öneri, uygulama insan onayıyla).
- Analiz sekmesi: değişken bazlı betimleyici özet, otomatik test seçimi (Welch t / Mann-Whitney / ANOVA / Kruskal-Wallis / ki-kare / Fisher), gönüllü akışı, kol × SOC advers olay özeti, analiz veri seti CSV (denetim izine yazılır).
- Çalışma ekibi sekmesi: kullanıcı × çalışma ataması; atama yapıldığında proje ekibi yalnızca atandığı çalışmaları görür. Yeni izinler: `ekip.yonet`, `analiz.goruntule`.
- Bölüm bazlı araştırmacı listesi (üniversite modu), merkez düzenleme, `Arastirmaci.bolum` alanı.
- Rol bazlı sekme görünürlüğü tek noktadan (`sekme_gorunur`); rotalarda aynı kural 403 üretir. Rol senaryo testleri.
### Değiştirildi
- Sponsor her yerde salt okunur (`calisma.olustur` / `calisma.duzenle` izinlerinden çıktı); araştırmacı yalnızca kendi kurduğu çalışmayı düzenler; CRA başvuruları izler; araştırmacı izlem ve TMF sekmelerini (merkez sınırlı), veri yöneticisi TMF'yi görür.
- Hasta havuzu, CSV yükleme, FHIR Bundle ve HBYS eşitleme merkez sınırlı; güvenlik sekmesi merkez rolleri için kendi merkeziyle sınırlı; CRA panosu yalnızca atandığı çalışmaları sayar, ziyaretler "bana atanan / çalışmalarımdaki diğer" olarak ayrıldı.
- Arşiv çalışmalarında takvim sütunları boş; merkez detayında çalışma geçmişi erişim filtreli; erişilemeyen sekmelere bağlantı verilmez.
- Kimliksizleştirme aracı yalnızca `kullanici.yonet` iznine açık ve Yönetim menüsüne taşındı; alt bilgideki sürüm damgası kaldırıldı.
- `/api/belgeler` oturumlu, `/saglik` anonim yanıtı yalnızca durum. 403 sayfasında gerçek kullanım modu.
- Mevcut veritabanlarında eski SHA-256 denetim kayıtları yeni anahtarla doğrulanmaz; geçişte zincir ilk kayıtta "bozuk" raporlar ve değişiklik kontrol kaydıyla kabul edilir. Deploy: şema/uygulama rolleri ayrımı, iç ağ, age şifreli yedek; belgelerden sürüm ve tarih damgaları kaldırıldı.
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
- `KilometreTasi` modeli ve tablosu; SIV ve aktivasyon bilgisi ziyaret ve merkez tarihlerinden okunur.

## [1.5.0]
### Eklendi
- Sponsor portalı: kurum bazlı salt okunur portföy görünümü, takvim riski, en riskli merkez, fizibilite raporu bağlantısı.
- Merkez Performans Endeksi: çalışmalar arası anonim kıyaslama (aktivasyon, hasta/ay, tarama başarısızlığı, sorgu oranı; yüzdelik dilimler, kurum tipi medyanları).
- CSV ile hasta havuzu yükleme (FHIR bağlantısı olmayan kurulumlar için); kimlik alanı yazılmaz, metinler kimliksizleştirilir, şüpheli satırlar reddedilir.
- API anahtarı ile makine-makine erişim (`X-SC-Anahtar`), yönetim sayfası, geçerlilik süresi ve iptal.
- Ar-Ge göstergeleri sayfası: altın standart, gölge mod, MAPE/AUC, ön tarama süresi, etki hesaplayıcı.
- CDISC ODM 1.3.2 ve CSV paketi dışa aktarımı; sponsor fizibilite raporu.
- Genel amaçlı klinik NLP uçları: ICD-10 kodlama, özet, soru-cevap.
- TR-KlinikBench değerlendirme seti, federe LoRA güncelleme iskeleti, model ve veri kartları (`ml/`).

## [1.4.2]
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

## [1.4.1]
### Eklendi
- Gölge mod raporu (model kararı ve araştırmacı kararı karşılaştırması; duyarlılık, özgüllük, PPV, NPV).
- RBM uyarılarında "neden tetiklendi" açıklaması ve otomatik kapanış.
- `/saglik` uç noktası (Docker healthcheck).
### Değiştirildi
- Oturum çerezi `SameSite=Strict`, üretimde `Secure` zorunlu.

## [1.4.0]
### Eklendi
- Merkez zekâsı: Gamma-Poisson hiyerarşik kazanım tahmini, Weibull AFT gecikme modeli, Monte Carlo projeksiyon.
- Risk bazlı izlem modülü: 15 varsayılan KRI, QTL, medyan/MAD anomali tespiti, bileşik risk puanı.
- OMOP CDM v5.4 CSV dışa aktarımı.
- BDM sağlayıcıları: Ollama, vLLM (OpenAI uyumlu), llama.cpp; ağ hatasında kural tabanlı moda düşme.

## [1.3.0]
### Eklendi
- Türkçe klinik metin kimliksizleştirme (TCKN algoritma doğrulaması, takma ad ve tarih kaydırma modları).
- FHIR R4 HBYS adaptörü (`_has:Condition` sorgusu, sayfalama, `$everything`).
- TMF modülü: DIA referans modeli bölgeleri, SHA-256, e-imza ile onay.
### Değiştirildi
- Denetim izi hash zincirli hale getirildi; `denetim_dogrula` betiği eklendi.

## [1.2.0]
### Eklendi
- Güvenlik modülü: AE/SAE, CTCAE, nedensellik, SUSAR tespiti, TİTCK 7/15 gün bildirim sayacı.
- Protokol sapmaları ve izlem ziyaretleri (SIV/IMV/COV/uzaktan/tetiklenmiş).
- Etik kurul / TİTCK / kurum izni / KVKK başvuru takibi.

## [1.1.0]
### Eklendi
- eCRF: CDASH uyumlu form tanımları, otomatik edit-check, sorgu yönetimi, SDV, veri kilidi (e-imza).
- Rol bazlı erişim denetimi (10 rol), hesap kilitleme, parola politikası.

## [1.0.0]
- İlk bütünleşik sürüm: çalışma, merkez, gönüllü yönetimi; denetim izi; REST API v1.
