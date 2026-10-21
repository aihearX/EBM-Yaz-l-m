# REST API v1

Taban yol: `/api/v1`. Etkileşimli belgeler: `/api/belgeler` (OpenAPI).

Kimlik doğrulama: web oturumu çerezi (`sc_oturum`). Makine-makine entegrasyonlar için
API anahtarı başlığı (`X-SC-Anahtar`) 1.5 sürümünde planlanmıştır; şimdilik entegrasyon
kullanıcıları için ayrı hesap açılması önerilir.

Tüm yazma işlemleri denetim izine `"api": true` işaretiyle kaydedilir.

| Yöntem | Yol | Açıklama | Yetki |
|---|---|---|---|
| GET | `/saglik` | Servis durumu | – |
| GET | `/surum` | Sürüm bilgisi | – |
| GET | `/calismalar` | Çalışma listesi ve özet sayılar | oturum |
| GET | `/calismalar/{id}/kriterler` | Kriterler ve yapısal sorguları | oturum |
| POST | `/calismalar/{id}/kriterler` | Kriter ekle (BDM ile yapılandırılır) | calisma.duzenle |
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
| POST | `/yz/soru-cevap` | Bağlam üzerinden soru-cevap | bdm.kullan |
| GET | `/fhir/ResearchStudy/{id}` | Çalışma, FHIR ResearchStudy olarak | disa_aktar |
| GET | `/fhir/ResearchSubject/{id}` | Gönüllü, FHIR ResearchSubject olarak | disa_aktar |
| POST | `/fhir/Bundle?merkez_id=` | HBYS Bundle'ını kimliksizleştirip hasta havuzuna yaz | hasta.goruntule |
| POST | `/hbys/senkron?merkez_id=` | Merkezin FHIR uç noktasından tanı kodlarına göre hasta çek | hasta.goruntule |

Web üzerinden erişilen dışa aktarımlar (oturum gerektirir): `/calismalar/{id}/veri/disa-aktar?bicim=csv|odm`
(CSV paketi veya CDISC ODM 1.3.2) ve `/calismalar/{id}/merkez-zekasi/rapor` (sponsor fizibilite raporu, yazdırılabilir).

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
