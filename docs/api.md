# REST API v1

Taban yol: `/api/v1`. Etkileşimli belgeler: `/api/belgeler` (oturum gerektirir; dış kaynak yüklemeyen kısa
liste), tam şema `/api/openapi.json` (oturum gerektirir).

Kimlik doğrulama: web oturumu çerezi (`sc_oturum`) veya makine-makine entegrasyonlar için `X-SC-Anahtar`
başlığı. Anahtarlar Yönetim › API Anahtarları sayfasından, belirli bir kullanıcı adına ve geçerlilik süresiyle
üretilir; anahtar sahibinin rol izinleri geçerlidir. Entegrasyonlar için en az yetkili ayrı bir hesap açılması
önerilir.

Tüm yazma işlemleri denetim izine kaydedilir.

| Yöntem | Yol | Açıklama | Yetki |
|---|---|---|---|
| GET | `/saglik` | Servis durumu (`{"durum":"ok"}`; sürüm/ortam vermez) | – |
| GET | `/surum` | Sürüm ve ortam bilgisi | oturum |
| GET | `/calismalar` | Çalışma listesi ve özet sayılar | oturum |
| GET | `/calismalar/{id}/kriterler` | Kriterler ve yapısal sorguları | oturum |
| POST | `/calismalar/{id}/kriterler` | Kriter ekle (yapılandırılır) | calisma.duzenle |
| POST | `/calismalar/{id}/eslestirme` | Ön taramayı çalıştır | eslestirme.calistir |
| GET | `/calismalar/{id}/uyarilar` | RBM uyarıları | rbm.goruntule |
| POST | `/calismalar/{id}/rbm/calistir` | KRI/QTL hesapla, uyarı üret | rbm.yonet |
| POST | `/hastalar` | Kimliksizleştirilmiş hasta kaydı ekle/güncelle | hasta.goruntule |
| GET | `/hastalar/{id}` | Hasta kaydı (görüntüleme denetim izine yazılır) | hasta.goruntule |
| POST | `/yz/kimliksizlestir` | Metin kimliksizleştirme | oturum |
| POST | `/yz/kriter-yapilandir` | Kriteri hesaplanabilir sorguya çevir | bdm.kullan |
| GET | `/yz/bdm/durum` | BDM sunucu durumu | oturum |
| POST | `/yz/icd-kodla` | Serbest metindeki tanı ifadelerini ICD-10 ile eşle | bdm.kullan |
| POST | `/yz/ozet` | Klinik metni çalışma odaklı özetle (girdi önce kimliksizleştirilir) | bdm.kullan |
| GET | `/fhir/ResearchStudy/{id}` | Çalışma, FHIR ResearchStudy olarak | disa_aktar |
| GET | `/fhir/ResearchSubject/{id}` | Gönüllü, FHIR ResearchSubject olarak | disa_aktar |
| POST | `/fhir/Bundle?merkez_id=` | HBYS Bundle'ını kimliksizleştirip hasta havuzuna yaz | hasta.goruntule |
| POST | `/hbys/senkron?merkez_id=` | Merkezin FHIR uç noktasından tanı kodlarına göre hasta çek | hasta.goruntule |

## Web üzerinden dışa aktarımlar (oturum gerektirir)

| Yol | İçerik | Yetki |
|---|---|---|
| `/calismalar/{id}/veri/disa-aktar?bicim=csv` | CSV paketi (form başına dosya, dispozisyon, AE; noktalı virgül, UTF-8 BOM) | disa_aktar |
| `/calismalar/{id}/veri/disa-aktar?bicim=odm[&denetim=1]` | CDISC ODM 1.3.2 Snapshot: vizit tanımları (StudyEventDef), merkezler (Location/SiteRef), AE ve dispozisyon grupları; `denetim=1` ile AuditRecord | disa_aktar |
| `/calismalar/{id}/veri/sorgular.csv?durum=acik|cevaplandi|kapali|hepsi&merkez_id=` | Sorgu listesi | veri sekmesi (sponsor hariç) |
| `/calismalar/{id}/gonulluler.csv?durum=&merkez_id=` | Gönüllü listesi | gönüllü sekmesi |
| `/calismalar/{id}/izlem/ziyaretler.csv?merkez_id=` | İzlem ziyaretleri | izlem sekmesi |
| `/calismalar/{id}/izlem/sapmalar.csv?durum=acik|kapali|hepsi&merkez_id=` | Protokol sapmaları | izlem sekmesi |
| `/calismalar/{id}/belgeler/{belge_id}/indir` | TMF belgesi (özet doğrulanır, görüntüleme denetim izine yazılır) | belge sekmesi; merkez rolleri kendi merkezi |
| `/calismalar/{id}/merkez-zekasi/rapor` | Sponsor fizibilite raporu (yazdırılabilir) | rbm.goruntule |
| `/calismalar/{id}/analiz/tablo1.csv`, `/calismalar/{id}/analiz/veri-seti.csv` | Ön analiz çıktıları | analiz.goruntule |
| `/yonetim/denetim?bicim=csv&...` | Denetim izi (filtreli) | denetim.goruntule |

Merkez rolleri (araştırmacı, koordinatör) listelerde yalnızca kendi merkezinin kayıtlarını alır; her dışa aktarım
denetim izine `disa_aktar` olarak yazılır.

## Örnek: kriter yapılandırma

```http
POST /api/v1/yz/kriter-yapilandir
{"metin": "Hemoglobin ≥ 9 g/dL", "tip": "dahil"}
```

```json
{"kategori": "lab", "sorgu": {"alan": "lab", "loinc": "718-7", "ad": "hemoglobin", "birim": "g/dL", "op": ">=", "deger": 9.0},
 "guven": 0.85, "yontem": "kural", "notlar": []}
```

## Hata biçimi

```json
{"hata": "Bu işlem için yetkiniz yok (rbm.yonet)"}
```

Oturumsuz istekler `/api/` altında 401 JSON döner; `/api/belgeler` tarayıcı sayfası olduğu için giriş sayfasına yönlenir.
