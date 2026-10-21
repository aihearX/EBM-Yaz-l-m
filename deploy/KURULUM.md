# EBM SmartClinical – Hastane İçi Kurulum Kılavuzu

Belge No: KUR-001 · Sürüm 1.4 · Son güncelleme: 2026-09 · Hedef platform sürümü: 1.4.x

Bu kılavuz SmartClinical'ın hastane veri merkezinde (on-premise), internet erişimi
olmayan ya da kısıtlı bir ağda kurulumunu anlatır. Platform tüm verileri kurum
içinde işler; dışarıya hiçbir veri aktarılmaz. SaaS (EBM barındırmalı) kurulum için
ayrı bir prosedür (KUR-002) vardır.

## 1. Gereksinimler

### 1.1 Donanım

| Bileşen | Asgari | Önerilen |
|---|---|---|
| Uygulama + veritabanı sunucusu | 4 çekirdek, 16 GB RAM, 200 GB SSD | 8 çekirdek, 32 GB RAM, 500 GB SSD (RAID 1) |
| BDM sunucusu (GPU) | NVIDIA 24 GB VRAM (RTX A5000 / L4), 64 GB RAM | NVIDIA 48 GB (L40S / A6000) |
| BDM sunucusu (GPU'suz, llama.cpp) | 16 çekirdek, 48 GB RAM | 32 çekirdek, 64 GB RAM |
| Yedek alanı | 2 × veritabanı boyutu + TMF dosyaları | NAS üzerinde ayrı bölüm |

BDM ve uygulama aynı makinede çalışabilir; 50'den az eşzamanlı kullanıcı için tek sunucu yeterlidir.
Eşleştirme motoru GPU olmadan da çalışır; 7B Q4 model CPU'da hasta başına 8–15 saniye sürer (GPU'da 1–2 saniye).

### 1.2 Yazılım

- Linux (Ubuntu 22.04 / 24.04 LTS, RHEL 9, Pardus 23 doğrulanmıştır)
- Docker Engine 24+ ve Docker Compose v2 **veya** Python 3.11+ ve PostgreSQL 15/16
- GPU kullanılacaksa: NVIDIA sürücü 535+ ve NVIDIA Container Toolkit
- Hastane PKI'sından alınmış TLS sertifikası (`smartclinical.<hastane>.local`)
- NTP ile zaman eşitlemesi (denetim izi zaman damgaları için zorunludur)

### 1.3 Ağ

| Yön | Kaynak → Hedef | Port | Amaç |
|---|---|---|---|
| Gelen | Kullanıcı istemcileri → nginx | 443 | Web arayüzü |
| Giden | app → HBYS FHIR sunucusu | HBYS tarafından belirlenir | Hasta verisi senkronizasyonu |
| Giden | app → SMTP | 25/587 | Uyarı e-postaları (opsiyonel) |
| İç | app → postgres, bdm, gomme | 5432, 11434, 8081 | Yalnızca docker ağı |

İnternet erişimi gerekmez. Güncellemeler imzalı paket olarak USB/aktarım sunucusu ile getirilir (bölüm 9).

## 2. Kapalı ağ için paketlerin hazırlanması

İnternet erişimi olan bir hazırlık makinesinde:

```bash
git clone <ebm-git-sunucusu>/smartclinical.git && cd smartclinical && git checkout v1.4.2
docker build -f deploy/Dockerfile -t smartclinical:1.4.2 .
docker pull postgres:16-alpine nginx:1.27-alpine ollama/ollama:0.6.5
docker save smartclinical:1.4.2 postgres:16-alpine nginx:1.27-alpine ollama/ollama:0.6.5 \
    | gzip > smartclinical-1.4.2-imajlar.tar.gz
sha256sum smartclinical-1.4.2-imajlar.tar.gz > smartclinical-1.4.2-imajlar.sha256
```

Model dosyaları (`ebm-klinik-tr-7b-q4_k_m.gguf`, ~4.4 GB; `ebm-klinik-tr-embed-v2/`, ~0.5 GB)
EBM tarafından imzalı olarak teslim edilir. Teslim tutanağındaki SHA-256 özeti ile karşılaştırın.

Hedef sunucuda:

```bash
sha256sum -c smartclinical-1.4.2-imajlar.sha256
docker load < smartclinical-1.4.2-imajlar.tar.gz
```

## 3. Kurulum (Docker Compose)

```bash
sudo mkdir -p /opt/smartclinical && cd /opt/smartclinical
# depo içeriğini (deploy/, ml/modeller/gguf/) buraya kopyalayın
cp .env.example .env
```

`.env` dosyasında en az şunları düzenleyin:

```
SC_ORTAM=uretim
SC_SECRET_KEY=<openssl rand -hex 32 çıktısı>
SC_OTURUM_SURESI_DK=20
SC_BDM_SAGLAYICI=ollama            # GPU'suz kurulumda: llamacpp
SC_BDM_MODEL=ebm-klinik-tr-7b-q4
POSTGRES_PASSWORD=<uygulama db parolası>
POSTGRES_ADMIN_PASSWORD=<db yönetici parolası>
TLS_SERTIFIKA_DIZINI=/etc/ssl/smartclinical
```

Sertifika dizininde `tam_zincir.pem` ve `anahtar.pem` bulunmalı (anahtar dosyası 600 izinli).

```bash
cd deploy
docker compose up -d postgres            # ilk açılışta yetkiler.sql çalışır
docker compose up -d app nginx
docker compose logs -f app               # "Uygulama hazir" satırını bekleyin
```

Şema uygulama ilk açılışta oluşturulur. Denetim izi tablosu oluştuktan sonra koruma
tetikleyicilerini kurmak için `yetkiler.sql` ikinci kez çalıştırılır:

```bash
docker compose exec -T postgres psql -U smartclinical_admin -d smartclinical < postgres/yetkiler.sql
# Beklenen çıktı: NOTICE: denetim_kaydi ve e_imza korumasi kuruldu
```

Doğrulama: `curl -k https://localhost/saglik` → `{"durum":"ok", ...}`.

## 4. Kurulum (Docker'sız, systemd)

```bash
sudo useradd -r -s /sbin/nologin -d /opt/smartclinical smartclinical
sudo mkdir -p /opt/smartclinical /var/log/smartclinical && sudo chown smartclinical: /opt/smartclinical /var/log/smartclinical
sudo -u smartclinical bash -c 'cd /opt/smartclinical && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt "psycopg[binary]" && .venv/bin/pip install .'
sudo -u postgres createdb smartclinical
sudo -u postgres psql -d smartclinical -v app_parola='<parola>' -f deploy/postgres/yetkiler.sql
sudo cp deploy/systemd/smartclinical.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now smartclinical
sudo -u postgres psql -d smartclinical -f deploy/postgres/yetkiler.sql    # tetikleyiciler
```

nginx yapılandırması `deploy/nginx/smartclinical.conf` dosyasındaki `upstream` bloğunda
`server 127.0.0.1:8000;` olacak şekilde `/etc/nginx/conf.d/` altına kopyalanır.

## 5. İlk yönetici ve roller

```bash
docker compose exec app python -m smartclinical.scripts.yonetici_olustur --kullanici admin --ad "Sistem Yöneticisi" --eposta bt@hastane.gov.tr
```

Betik geçici bir parola üretir; ilk girişte değiştirilmesi zorunludur. Diğer kullanıcılar
arayüzden (Yönetim → Kullanıcılar) açılır. Roller ve yetki matrisi için bkz. docs/validasyon/URS-001 bölüm 9.

Parola politikası (varsayılan, `.env` ile değiştirilebilir): en az 12 karakter, 90 günde
değişim, 5 hatalı denemede 15 dakika kilit, son 5 parola tekrar kullanılamaz.

## 6. Türkçe Klinik BDM'nin yüklenmesi

### 6.1 GPU'lu (Ollama)

```bash
cp ebm-klinik-tr-7b-q4_k_m.gguf /opt/smartclinical/ml/modeller/gguf/
docker compose --profile bdm up -d bdm gomme
docker compose exec bdm ollama create ebm-klinik-tr-7b-q4 -f /modeller/Modelfile
docker compose exec bdm ollama list              # modelin listelendiğini doğrulayın
```

### 6.2 GPU'suz (llama.cpp)

```bash
docker compose --profile bdm-cpu up -d bdm-cpu gomme
```

`.env` içinde `SC_BDM_SAGLAYICI=llamacpp` olmalı. İlk yüklemede model RAM'e alınır (1–2 dakika).

### 6.3 Doğrulama

Arayüzde Yönetim → BDM Durumu sayfasında model adı, sürümü ve yanıt süresi görünür.
Kurulum sonrası kalite kontrolü için altın standart değerlendirmesi çalıştırılır ve
çıktı IQ dosyasına eklenir:

```bash
docker compose exec app python -m ml.degerlendirme.degerlendir --saglayici ollama --model ebm-klinik-tr-7b-q4
```

BDM erişilemezse uygulama kural tabanlı sağlayıcıya düşer ve bunu uyarı olarak loglar;
eşleştirme çalışmaya devam eder ancak serbest metin kanıtı üretilmez.

## 7. HBYS entegrasyonu (FHIR)

1. HBYS sağlayıcısından FHIR R4 uç noktası ve servis hesabı (salt okunur; Patient, Condition,
   Observation, MedicationStatement, DocumentReference kaynakları) talep edin.
2. `.env`: `SC_FHIR_SUNUCU_URL=https://hbys.hastane.local/fhir`, `SC_FHIR_TOKEN=<token>`
3. Bağlantı testi: Yönetim → Entegrasyon → "Bağlantıyı sına".
4. Senkronizasyon zamanlaması (varsayılan gece 03:00) Yönetim → Entegrasyon ekranından ayarlanır.
   Senkronizasyon yalnızca aktif çalışmaların tanı kodlarına uyan hastaları çeker; kimlik alanları
   HBYS'den hiç alınmaz, takma ad (SHA-256) üretilir.

FHIR desteği olmayan HBYS'ler için CSV içe aktarma (Yönetim → Entegrasyon → CSV) kullanılabilir;
şablon `docs/entegrasyon/csv_sablonu.xlsx` dosyasındadır. HL7 v2 arayüzü yol haritasındadır (1.6).

## 8. Yedekleme ve geri yükleme

```bash
sudo crontab -e
0 2 * * * /opt/smartclinical/deploy/yedekleme.sh >> /var/log/smartclinical/yedek.log 2>&1
```

Geri yükleme (test ortamında üç ayda bir prova edilir, kayıt: IQ-001 madde 7):

```bash
docker compose stop app
docker compose exec -T postgres pg_restore -U smartclinical_admin -d smartclinical --clean --if-exists < /var/yedek/smartclinical/gunluk/db_<tarih>.dump
tar -xzf /var/yedek/smartclinical/gunluk/dosyalar_<tarih>.tar.gz -C /var/lib/docker/volumes/smartclinical_yuklemeler/_data/..
docker compose start app
```

## 9. Güncelleme

1. Yeni imaj paketi ve sürüm notları EBM'den imzalı olarak alınır; özet doğrulanır.
2. Yedek alınır (bölüm 8).
3. `docker load` → `.env` içinde gerekirse yeni değişkenler eklenir (sürüm notlarında belirtilir).
4. `docker compose up -d app` – şema migrasyonları açılışta otomatik uygulanır.
5. `yetkiler.sql` tekrar çalıştırılır (yeni tablolar için yetkiler).
6. Sürüm notlarındaki doğrulama senaryoları (genellikle OQ-001'den seçilmiş 5–8 senaryo) koşulur ve
   sonuç değişiklik kontrol kaydına (DK-xxx) eklenir.

Geri alma: önceki imaj etiketi ile `docker compose up -d app` ve yedekten veritabanı geri yükleme.

## 10. Sorun giderme

| Belirti | Olası neden | Çözüm |
|---|---|---|
| `/saglik` 503 döner | Veritabanı erişilemiyor | `docker compose logs postgres`; parola ve ağ kontrolü |
| Eşleştirme "kural tabanlı" uyarısı veriyor | BDM servisi kapalı ya da model yüklü değil | `ollama list`, `SC_BDM_URL` kontrolü |
| Giriş sonrası hemen çıkış | Ters vekil `X-Forwarded-Proto` göndermiyor | nginx yapılandırmasını kontrol edin |
| TMF yükleme 413 | Dosya 50 MB üzeri | nginx `client_max_body_size` |
| Denetim izi yazılamıyor (insufficient_privilege) | yetkiler.sql yanlış sırada çalıştı | INSERT yetkisini kontrol edin: `\dp denetim_kaydi` |
| Zaman damgaları yanlış | NTP yok / TZ farklı | `timedatectl`, konteyner `TZ=Europe/Istanbul` |

Destek: destek@ebm-cro.com · Hafta içi 09:00–18:00 · Kritik (sistem kapalı) için 7/24 nöbetçi hattı sözleşmede belirtilmiştir.
