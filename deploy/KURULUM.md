# EBM SmartClinical – Hastane İçi Kurulum Kılavuzu

Belge No: KUR-001

Bu kılavuz SmartClinical'ın hastane veri merkezinde (on-premise), internet erişimi
olmayan ya da kısıtlı bir ağda kurulumunu anlatır. Platform tüm verileri kurum
içinde işler; dışarıya hiçbir veri aktarılmaz. Kurulumdaki her adımın kodda bir
karşılığı vardır; karşılığı olmayan hiçbir özellik bu belgede yer almaz.

## 1. Gereksinimler

### 1.1 Donanım

| Bileşen | Asgari | Önerilen |
|---|---|---|
| Uygulama + veritabanı sunucusu | 4 çekirdek, 16 GB RAM, 200 GB SSD | 8 çekirdek, 32 GB RAM, 500 GB SSD (RAID 1) |
| BDM sunucusu (GPU) | NVIDIA 24 GB VRAM, 64 GB RAM | NVIDIA 48 GB |
| BDM sunucusu (GPU'suz, llama.cpp) | 16 çekirdek, 48 GB RAM | 32 çekirdek, 64 GB RAM |
| Yedek alanı | 2 × veritabanı boyutu + TMF dosyaları | NAS üzerinde ayrı bölüm |

BDM ve uygulama aynı makinede çalışabilir; 50'den az eşzamanlı kullanıcı için tek sunucu yeterlidir.
Eşleştirme motoru BDM olmadan da (kural tabanlı) çalışır.

### 1.2 Yazılım

- Linux (Ubuntu 22.04 / 24.04 LTS, RHEL 9, Pardus 23)
- Docker Engine 24+ ve Docker Compose v2 **veya** Python 3.11+ ve PostgreSQL 15/16
- GPU kullanılacaksa: NVIDIA sürücü 535+ ve NVIDIA Container Toolkit
- `age` (yedek şifreleme) ve `sqlite3` (yalnızca SQLite kurulumunda)
- Hastane PKI'sından alınmış TLS sertifikası (`smartclinical.<hastane>.local`)
- NTP ile zaman eşitlemesi (denetim izi zaman damgaları için zorunludur)

### 1.3 Ağ

| Yön | Kaynak → Hedef | Port | Amaç |
|---|---|---|---|
| Gelen | Kullanıcı istemcileri → nginx | 443 | Web arayüzü |
| Giden | app → HBYS FHIR sunucusu | HBYS tarafından belirlenir | Hasta verisi eşitleme (isteğe bağlı) |
| İç | app → postgres, bdm, gomme | 5432, 11434, 8081 | Yalnızca `uygulama` docker ağı (internal) |

İnternet erişimi gerekmez. Uygulama e-posta göndermez; uyarılar arayüzde ve gece işi çıktısında görünür.
Güncellemeler imzalı paket olarak USB/aktarım sunucusu ile getirilir (bölüm 9).

## 2. Kapalı ağ için paketlerin hazırlanması

İnternet erişimi olan bir hazırlık makinesinde (etiket olarak teslim edilen sürüm etiketi kullanılır):

```bash
git clone <ebm-git-sunucusu>/smartclinical.git && cd smartclinical && git checkout <etiket>
docker build -f deploy/Dockerfile -t smartclinical:yerel .
docker pull postgres:16-alpine nginx:1.27-alpine ollama/ollama:0.6.5
docker save smartclinical:yerel postgres:16-alpine nginx:1.27-alpine ollama/ollama:0.6.5 | gzip > smartclinical-imajlar.tar.gz
sha256sum smartclinical-imajlar.tar.gz > smartclinical-imajlar.sha256
```

Model dosyaları (`ebm-klinik-tr-7b-q4_k_m.gguf`, `ebm-klinik-tr-embed-v2/`) teslim tutanağındaki SHA-256
özeti ile karşılaştırılır. Hedef sunucuda: `sha256sum -c smartclinical-imajlar.sha256 && docker load < smartclinical-imajlar.tar.gz`.

## 3. Kurulum (Docker Compose)

```bash
sudo mkdir -p /opt/smartclinical && cd /opt/smartclinical
# depo içeriğini (deploy/, ml/modeller/gguf/) buraya kopyalayın
cp .env.example .env
```

`.env` dosyasında en az şunları düzenleyin:

```
SC_ORTAM=uretim
SC_SECRET_KEY=<openssl rand -hex 32 çıktısı>      # oturum çerezi ve denetim izi HMAC anahtarı; değişirse zincir doğrulaması ilk kayıtta durur
SC_TAKMA_AD_ANAHTARI=<openssl rand -hex 32 çıktısı>   # HBYS takma adı (HMAC); anahtar kasasında da saklayın
SC_OTURUM_SURESI_DK=20
SC_BDM_SAGLAYICI=ollama            # GPU'suz kurulumda: llamacpp; BDM yoksa: kural
SC_BDM_MODEL=ebm-klinik-tr-7b-q4
POSTGRES_PASSWORD=<uygulama rolü (smartclinical) parolası>
POSTGRES_SEMA_PASSWORD=<şema sahibi rol (smartclinical_sema) parolası>
POSTGRES_ADMIN_PASSWORD=<db yönetici parolası>
TLS_SERTIFIKA_DIZINI=/etc/ssl/smartclinical
```

Sertifika dizininde `tam_zincir.pem` ve `anahtar.pem` bulunmalı (anahtar dosyası 600 izinli).

Compose dosyası üç aşamalı bir açılış uygular:

1. `postgres` – ilk kurulumda `yetkiler.sql` rolleri oluşturur (şema sahibi `smartclinical_sema`, uygulama rolü `smartclinical`, salt okunur `smartclinical_okuyucu`).
2. `sema` – tabloları **şema sahibi** rolle oluşturur (`smartclinical.db.tablolari_olustur`); mevcut tablolara dokunmaz.
3. `yetki` – tablolar oluştuktan sonra `yetkiler.sql`'i yeniden çalıştırır: uygulama rolüne yalnızca DML, `denetim_kaydi` / `e_imza` üzerinde UPDATE/DELETE yasağı ve koruma tetikleyicileri.
4. `app` ve `nginx` – uygulama yalnızca DML yetkili rolle çalışır; `X-Forwarded-*` başlıkları yalnızca `nginx` konteynerinden kabul edilir (`deploy/entrypoint.sh`).

```bash
cd deploy
docker compose up -d
docker compose logs yetki            # Beklenen: NOTICE: denetim_kaydi ve e_imza korumasi kuruldu
docker compose logs -f app           # "SmartClinical ... baslatildi" satırını bekleyin
```

Doğrulama: `curl -k https://localhost/saglik` → `{"durum":"ok"}` (anonim yanıt sürüm/ortam bilgisi içermez; sürüm için oturumlu `/api/v1/surum`).

Ağ yalıtımı: `uygulama` ağı `internal: true` olduğundan app, postgres ve BDM konteynerleri dışarı çıkamaz; yalnızca nginx `dis` ağında 80/443 açar.

## 4. Kurulum (Docker'sız, systemd)

```bash
sudo useradd -r -s /sbin/nologin -d /opt/smartclinical smartclinical
sudo mkdir -p /opt/smartclinical /var/log/smartclinical && sudo chown smartclinical: /opt/smartclinical /var/log/smartclinical
sudo -u smartclinical bash -c 'cd /opt/smartclinical && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt "psycopg[binary]" && .venv/bin/pip install .'
sudo -u postgres createdb smartclinical
sudo -u postgres psql -d smartclinical -v app_parola='<parola>' -v sema_parola='<parola>' -f deploy/postgres/yetkiler.sql
# şemayı şema sahibi rolle oluştur
sudo -u smartclinical SC_DB_URL='postgresql+psycopg://smartclinical_sema:<parola>@localhost/smartclinical' \
    /opt/smartclinical/.venv/bin/python -c "from smartclinical.db import tablolari_olustur; tablolari_olustur()"
sudo -u postgres psql -d smartclinical -f deploy/postgres/yetkiler.sql    # tablo yetkileri + tetikleyiciler
sudo cp deploy/systemd/smartclinical.service deploy/systemd/smartclinical-gece.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now smartclinical smartclinical-gece.timer
```

`.env` içindeki `SC_DB_URL` uygulama rolünü (`smartclinical`) kullanır. nginx yapılandırması
`deploy/nginx/smartclinical.conf` dosyasındaki `upstream` bloğunda `server 127.0.0.1:8000;` olacak şekilde
`/etc/nginx/conf.d/` altına kopyalanır.

## 5. İlk yönetici, roller ve zamanlanmış işler

```bash
docker compose exec app python -m smartclinical.scripts.yonetici_olustur --kullanici admin --ad "Sistem Yöneticisi" --eposta bt@hastane.gov.tr --mod cro --kurum "Kurum adı"
```

Parola komut satırından istenir; parola politikası uygulanır. Diğer kullanıcılar arayüzden
(Yönetim › Kullanıcılar) açılır; yöneticinin belirlediği geçici parola ilk girişte değiştirilir.
Roller ve yetki matrisi için bkz. docs/roller.md ve docs/validasyon/URS-001 bölüm 13.

Parola politikası (`services/yetki.py`; `.env` ile `SC_PAROLA_MIN`, `SC_PAROLA_GUN`): en az 12 karakter, harf ve rakam,
90 günde değişim, son 5 parola tekrar kullanılamaz, 5 hatalı denemede 15 dakika süreli kilit (her yeni kilitte süre iki katına çıkar).

Zamanlanmış işler (ikisi de denetim izine yazar):

| İş | Komut | Zamanlama |
|---|---|---|
| Gece işleri: aktif çalışmalarda KRI/QTL, erken uyarı, merkez zekâsı tahmini, SAE bildirim süresi kontrolü | `python -m smartclinical.scripts.gece_isleri` | systemd: `smartclinical-gece.timer` (02:00); docker: `docker compose --profile gece run --rm gece` (host cron) |
| Denetim izi zincir doğrulama | `python -m smartclinical.scripts.denetim_dogrula` | günlük cron; çıkış kodu 2 → zincir bozuk |
| Hasta havuzu saklama süresi | `python -m smartclinical.scripts.hasta_saklama --ay 6` | aylık cron; `--kuru-calisma` ile önce liste |
| Yedekleme | `deploy/yedekleme.sh` | günlük cron 02:00 (bölüm 8) |

Veri sahibi talebi (KVKK): `python -m smartclinical.scripts.hasta_saklama --kayit-no <takma ad>` bağlantısız kaydı siler;
gönüllüye bağlı kayıtta ya da `--kisitla` ile klinik içerik boşaltılıp kayıt işleme kısıtlamasına alınır.

## 6. Türkçe Klinik BDM'nin yüklenmesi

### 6.1 GPU'lu (Ollama)

```bash
cp ebm-klinik-tr-7b-q4_k_m.gguf /opt/smartclinical/ml/modeller/gguf/
docker compose --profile bdm up -d bdm gomme
docker compose exec bdm ollama create ebm-klinik-tr-7b-q4 -f /modeller/Modelfile
docker compose exec bdm ollama list
```

### 6.2 GPU'suz (llama.cpp)

```bash
docker compose --profile bdm-cpu up -d bdm-cpu gomme
```

`.env` içinde `SC_BDM_SAGLAYICI=llamacpp` olmalı. İlk yüklemede model RAM'e alınır (1–2 dakika).

### 6.3 Doğrulama

Arayüzde Yönetim › Sistem sayfasında sağlayıcı ve model adı görünür; `/api/v1/yz/bdm/durum` sunucu durumunu döner.
Kurulum sonrası kalite kontrolü için altın standart değerlendirmesi çalıştırılır ve çıktı IQ dosyasına eklenir:

```bash
docker compose exec app python -m ml.degerlendirme.degerlendir --saglayici ollama --model ebm-klinik-tr-7b-q4
```

BDM erişilemezse uygulama kural tabanlı sağlayıcıya düşer ve bunu uyarı olarak loglar;
eşleştirme çalışmaya devam eder ancak serbest metin kanıtı üretilmez.

## 7. HBYS entegrasyonu (FHIR) ve CSV içe aktarma

1. HBYS sağlayıcısından FHIR R4 uç noktası ve salt okunur servis hesabı (Patient, Condition, Observation,
   MedicationStatement, DocumentReference) talep edin.
2. `.env`: `SC_FHIR_SUNUCU_URL=https://hbys.hastane.local/fhir`, `SC_FHIR_TOKEN=<token>`; merkez kaydında
   FHIR uç noktası alanı doldurulur (Merkezler › Merkez › Düzenle).
3. Eşitleme isteğe bağlıdır ve elle tetiklenir: `POST /api/v1/hbys/senkron?merkez_id=` (hasta.goruntule yetkisi)
   yalnızca aktif çalışmaların tanı kodlarına uyan hastaları çeker; kimlik alanları HBYS'den hiç alınmaz,
   takma ad HMAC-SHA256 (`SC_TAKMA_AD_ANAHTARI`) ile üretilir. Anahtar değişirse
   `python -m smartclinical.scripts.yeniden_anahtarla` mevcut takma adları yeniler.

FHIR desteği olmayan HBYS'ler için CSV içe aktarma merkez sayfasından yapılır (Merkezler › Merkez › Hasta yükle);
sütun düzeni ve reddedilen satırlar aynı sayfada gösterilir. Yükleme sonucunda reddedilen satırlar gözden geçirilir.

## 8. Yedekleme ve geri yükleme

```bash
sudo apt install age
age-keygen -o /root/kasa/yedek_age.key            # özel anahtar: anahtar kasasında saklanır, yedek sunucusunda tutulmaz
grep public /root/kasa/yedek_age.key | cut -d: -f2 | tr -d ' ' > /etc/smartclinical/yedek_age.pub
sudo crontab -e
0 2 * * * YEDEK_AGE_ALICI=/etc/smartclinical/yedek_age.pub /opt/smartclinical/deploy/yedekleme.sh >> /var/log/smartclinical/yedek.log 2>&1
```

Yedekler `age` ile şifrelenir (`*.age`); saklama: günlük 7 gün, haftalık 30 gün, aylık 25 yıl. Geri yükleme
(test ortamında üç ayda bir prova edilir, kayıt: IQ-001 madde IQ-7):

```bash
docker compose stop app
age -d -i /root/kasa/yedek_age.key /var/yedek/smartclinical/gunluk/db_<tarih>.dump.age \
  | docker compose exec -T postgres pg_restore -U smartclinical_admin -d smartclinical --clean --if-exists
age -d -i /root/kasa/yedek_age.key /var/yedek/smartclinical/gunluk/dosyalar_<tarih>.tar.gz.age \
  | tar -xzf - -C /var/lib/docker/volumes/smartclinical_yuklemeler/_data/..
docker compose start app
python -m smartclinical.scripts.denetim_dogrula     # geri yükleme sonrası zincir kontrolü
```

## 9. Güncelleme

Şema migrasyonu otomatik değildir: yeni tablolar şema sahibi rolle oluşturulur, mevcut tablolara sütun
eklenmesi sürüm notlarındaki SQL ile yapılır.

1. Yeni imaj paketi ve sürüm notları imzalı olarak alınır; özet doğrulanır.
2. Yedek alınır (bölüm 8).
3. `docker load`; `.env` içinde gerekirse yeni değişkenler eklenir (sürüm notlarında belirtilir).
4. Sürüm notlarındaki şema SQL'i (sütun eklemeleri) `psql -U smartclinical_sema` ile uygulanır.
5. `docker compose up -d` – `sema` servisi yeni tabloları oluşturur, `yetki` servisi yetkileri ve tetikleyicileri yeniler, ardından `app` açılır.
6. `python -m smartclinical.scripts.denetim_dogrula` çalıştırılır; sürüm notlarındaki doğrulama senaryoları
   (OQ-001'den seçilmiş senaryolar) koşulur ve sonuç değişiklik kontrol kaydına eklenir.

Geri alma: önceki imaj etiketi ile `docker compose up -d app` ve yedekten veritabanı geri yükleme.

## 10. Sorun giderme

| Belirti | Olası neden | Çözüm |
|---|---|---|
| `/saglik` 503 döner | Veritabanı erişilemiyor | `docker compose logs postgres`; parola ve ağ kontrolü |
| Eşleştirme "kural tabanlı" uyarısı veriyor | BDM servisi kapalı ya da model yüklü değil | `ollama list`, `SC_BDM_URL` kontrolü |
| Giriş sonrası hemen çıkış | Ters vekil `X-Forwarded-Proto` göndermiyor ya da `PROXY_HOST` yanlış | nginx yapılandırması ve `docker compose logs app` ("cozumlenemedi" uyarısı) |
| TMF yükleme reddedildi | Uzantı/içerik uyuşmuyor ya da 25 MB üstü | Arayüzdeki mesaj; nginx `client_max_body_size 26m` |
| Denetim izi yazılamıyor (insufficient_privilege) | `yetki` adımı çalışmadı | `docker compose logs yetki`; `\dp denetim_kaydi` |
| `denetim_dogrula` ilk kayıtta "bozuk" | `SC_SECRET_KEY` değişti | Eski anahtarla doğrulayın; anahtar değişikliği değişiklik kontrol kaydıyla yapılır |
| "relation does not exist" | Yeni tablo şema adımından önce istendi | `docker compose up -d sema yetki app` |
| Zaman damgaları yanlış | NTP yok / TZ farklı | `timedatectl`, konteyner `TZ=Europe/Istanbul` |

Destek: destek@ebm-cro.com · Hafta içi 09:00–18:00.
