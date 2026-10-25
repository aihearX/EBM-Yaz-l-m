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
  davranışlar için; harici kütüphane yok (kapalı ağ).
- `api/` – REST API v1, Pydantic şemaları. Oturum çerezi veya `X-SC-Anahtar` başlığı ile kimlik
  doğrulama (bkz. `docs/api.md`).

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
| Ön analiz | `services/analiz.py` | Betimleyici istatistik, kural tabanlı test seçimi; nihai analiz SAP'a göre |
| Kurulum ve mod | `services/kurulum.py` | Kullanım modu, mod varsayılanları, protokol kodu önerisi |
| Kimliksizleştirme | `services/kimliksizlestirme/` | Regex + sözlük; maske / takma ad / tarih kaydırma |

Karar ilkesi: hiçbir model çıktısı tek başına işlem yapmaz. Eşleştirme önerileri araştırmacı
onayı bekler, RBM uyarıları CRA tarafından kapatılır, kriter yapılandırmaları onaylanmadan
"ön tarama" niteliğindedir. Tüm bu kararlar denetim izine yazılır.

## Denetim izi

`services/denetim.py`: her kayıt bir önceki kaydın SHA-256 özetini taşır. Veritabanı
kullanıcısının `denetim_kaydi` ve `e_imza` tablolarında UPDATE/DELETE yetkisi yoktur
(`deploy/postgres/yetkiler.sql`). Zincir `scripts/denetim_dogrula.py` ile doğrulanır.

## Veri modeli ve standartlar

- Hasta kayıtları (`hasta`) yalnızca kimliksizleştirilmiş veri taşır; `kayit_no` HBYS
  kimliğinin SHA-256 ile türetilmiş takma adıdır.
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
- Randomizasyon (IWRS) dış sistemdir; kol ataması elle girilir.
- Kural tabanlı metin değerlendirme, BDM olmayan kurulumlar için güvenli bir taban sağlar ama
  BDM'nin yerini tutmaz; serbest metin kriterlerinde "belirsiz" oranı yüksektir.
