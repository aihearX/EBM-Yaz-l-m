# Mimari Notları

## Genel yaklaşım

SmartClinical, "modüler monolit" olarak geliştirilmiştir: tek bir FastAPI süreci, alan
servisleri (`smartclinical/services/*`) arasında açık arayüzlerle konuşur. Mikroservis
ayrıştırması (BDM sunucusu, gömme sunucusu) yalnızca ağır hesaplama gerektiren ve farklı
donanımda (GPU) çalışması gereken bileşenler için yapılmıştır. Hastane BT ekiplerinin işletmesi
gereken bileşen sayısını düşük tutmak bilinçli bir tercihtir.

```
tarayıcı ──HTTPS──▶ nginx ──▶ uvicorn/FastAPI ──▶ PostgreSQL
                                   │ ├──▶ dosya deposu (TMF)
                                   │ ├──▶ BDM sunucusu (vLLM / llama.cpp / Ollama, GPU)
                                   │ └──▶ gömme sunucusu (isteğe bağlı)
                                   └──▶ HBYS FHIR R4 uç noktası (salt okunur)
```

## Katmanlar

- `models/` – SQLAlchemy 2.0 tip açıklamalı modeller. Enum'lar Türkçe etiket sözlükleriyle birlikte
  tanımlanır (`DURUM_ETIKET` vb.); şablonlar bu sözlükleri kullanır.
- `services/` – alan mantığı. Web ve API katmanları servisleri çağırır; servisler `commit` etmez
  (çağıran eder). İstisna: `eslestirme.calisma_icin_tara` uzun sürebildiği için kendi commit'ini yapar.
- `web/` – Jinja2 şablonları, sunucu tarafı render. JavaScript yalnızca grafik çizimi ve küçük
  davranışlar için; harici kütüphane yok (kapalı ağ). Çalışma sekmeleri ayrı modüllerde yaşar
  (`calismalar`, `ecrf`, `izlem`, `belgeler`, `veri_islem`, `randomizasyon`, `ekip`, `analiz`) ve
  `web/__init__.py` içinde `calismalar`'dan sonra kaydedilir. Sekme görünürlüğü ve rota koruması tek
  kuraldan gelir (`calismalar.sekme_gorunur` / `sekme_kontrol`); kurallar `docs/roller.md` ile birlikte
  test edilir.
- `api/` – REST API v1, Pydantic şemaları. Oturum çerezi veya `X-SC-Anahtar` başlığı ile kimlik
  doğrulama (bkz. `docs/api.md`).

## Kullanım modları ve çalışma sihirbazı

Kurulum (`services/kurulum.py`) üç mod tanır: tekil araştırmacı, üniversite/hastane, CRO. Mod
menüyü, sihirbaz varsayılanlarını ve yeni kayıtları etkiler; veri modeli ortaktır. Sihirbaz
(`web/sihirbaz.py`) dört adımda çalışma kurar; taslak `CalismaTaslagi` tablosunda kullanıcı başına tek
kayıt olarak tutulur ve kullanıcı kaldığı adımdan sürer. Tekil ve üniversite modunda merkez kurulumla
aktif olur; CRO modunda merkezler aday olarak eklenir ve üçüncü adımda proje ekibi seçilir. Kuran
kullanıcı atanabilir roldeyse ekibe kendiliğinden eklenir; sponsor çalışma kuramaz ve düzenleyemez.

## eCRF tasarımcısı ve gönüllü akışı

Form tanımları (`Form.alanlar`) JSON olarak saklanır; tasarımcı (`web/ecrf.py`, `static/js/ecrf.js`)
sunucu tarafı doğrulama ile çalışır, kaydı olan formda değişiklik yeni sürüm açar. Gönüllü durum
geçişleri `services/gonullu.py` içindeki `GECISLER` tablosuyla sınırlıdır; onamla tarama vizitleri,
randomizasyonla şema vizitleri üretilir. Birden fazla kollu çalışmada kol ataması
`services/randomizasyon.py` üzerinden permüte blok listesinden yapılır (liste e-imza ile üretilir,
tahsis yapılmış liste yeniden üretilemez). Tekrarlayan formlar (`Form.tekrarlayan`) aynı vizitte
birden fazla satır (`FormKaydi.tekrar_no`) tutar.

## Yapay zekâ katmanı

| Bileşen | Dosya | Not |
|---|---|---|
| Kriter ayrıştırıcı | `services/kriter/ayristirici.py` | Kural tabanlı; BDM mevcutsa BDM çıktısı doğrulanıp kullanılır, aksi halde bu |
| Kriter değerlendirici | `services/kriter/degerlendirici.py` | Yapısal hasta verisi üzerinde |
| BDM istemcisi | `services/bdm/istemci.py` | Sağlayıcı soyutlaması, görev şablonları, koruma katmanı |
| Metin kuralları | `services/bdm/metin_kurallari.py` | BDM yokken/belirsizken metinden sayısal ve kalıp tabanlı kanıt |
| RAG | `services/bdm/rag.py` | Cümle tabanlı parçalama, BM25 (saf Python), isteğe bağlı gömme |
| Korumalar | `services/bdm/korumalar.py` | Kanıt doğrulama, güven eşiği, çoğunluk oyu, JSON şema, PHI kontrolü |
| Eşleştirici | `services/eslestirme/__init__.py` | Yapısal → metin → karar; gölge mod |
| Merkez zekâsı | `services/merkez_zekasi/` | Gamma-Poisson, Weibull AFT, sıralama |
| RBM | `services/rbm/` | KRI hesaplama, anomali, uyarı, QTL |
| Kıyaslama | `services/kiyaslama.py` | Merkez performans endeksi; çalışmalar arası yüzdelik dilimler |
| eCRF ve vizit şeması | `services/ecrf.py` | Standart form kütüphanesi, vizit şablonları, form doğrulama ve sürümleme, edit-check |
| Protokol taslağı | `services/protokol.py` | Protokol metninden kriter/vizit/form önerisi; kural tabanlı, BDM varsa BDM |
| Ön analiz | `services/analiz.py` | Betimleyici istatistik, kural tabanlı test seçimi, Tablo 1, vizitler arası değişim; nihai analiz SAP'a göre |
| Gönüllü akışı | `services/gonullu.py` | Durum geçişleri, vizit üretimi, dahil/hariç denetimi |
| Randomizasyon | `services/randomizasyon.py` | Permüte blok liste, strata (merkez), sıradaki tahsis |
| Yetki | `services/yetki.py` | İzin tablosu, çalışma/merkez/gönüllü erişimi, parola politikası, süreli kilit |
| Kurulum ve mod | `services/kurulum.py` | Kullanım modu, mod varsayılanları, protokol kodu önerisi |
| Kimliksizleştirme | `services/kimliksizlestirme/` | Regex + sözlük; maske / takma ad / tarih kaydırma |

Karar ilkesi: hiçbir model çıktısı tek başına işlem yapmaz. Eşleştirme önerileri araştırmacı
onayı bekler, RBM uyarıları CRA tarafından kapatılır, kriter yapılandırmaları onaylanmadan
"ön tarama" niteliğindedir. Tüm bu kararlar denetim izine yazılır.

## Denetim izi

`services/denetim.py`: her kayıt bir önceki kaydın HMAC-SHA256 özetini taşır (anahtar
`SC_SECRET_KEY`); zincirin ucu `denetim_zincir` tablosunda kilitli tutulur. Veritabanı
kullanıcısının `denetim_kaydi` ve `e_imza` tablolarında UPDATE/DELETE yetkisi yoktur
(`deploy/postgres/yetkiler.sql`). Zincir `scripts/denetim_dogrula.py` ile doğrulanır; anahtar
değişirse eski kayıtlar doğrulanmaz, geçiş değişiklik kontrol kaydıyla belgelenir.

## Veri modeli ve standartlar

- Hasta kayıtları (`hasta`) yalnızca kimliksizleştirilmiş veri taşır; `kayit_no` HBYS
  kimliğinden HMAC-SHA256 ile türetilmiş takma adıdır (`SC_TAKMA_AD_ANAHTARI`, üretimde zorunlu;
  anahtar değişince `scripts/yeniden_anahtarla.py`).
- eCRF alanları CDASH değişken adlarıyla eşlenir; SDTM dışa aktarımı veri yöneticisinin
  kilit sonrası işlemidir.
- FHIR R4 eşlemeleri `services/fhir/__init__.py`, OMOP CDM v5.4 `services/fhir/omop.py`.

## Bilinen sınırlar / yol haritası

- Çalışma görünürlüğü üyelik tabanlıdır (`yetki.calisma_erisimi`): yönetici ve denetçi her
  çalışmayı, sponsor kurumunun, araştırmacı/koordinatör merkezinin çalışmalarını görür; proje
  ekibi rolleri atama yapıldıysa yalnızca atandıkları çalışmaları görür. Rol globaldir;
  çalışma bazlı rol (kullanıcı × çalışma × rol) yoktur.
- Var olan gönüllülerin vizitleri şema değişince güncellenmez; şema yalnızca vizit kaydı olmayan
  çalışmalarda değiştirilebilir.
- Dahili randomizasyon körleme yapmaz; kör çalışmalarda dış IWRS kullanılır. Liste tükenince
  uzatma yoktur; eş zamanlı tahsiste satır kilidi yalnızca PostgreSQL'de uygulanır.
- IP başına giriş sınırı bellek içidir; çok işçili uvicorn'da işçi başına sayılır.
- Kural tabanlı metin değerlendirme, BDM olmayan kurulumlar için güvenli bir taban sağlar ama
  BDM'nin yerini tutmaz; serbest metin kriterlerinde "belirsiz" oranı yüksektir.
