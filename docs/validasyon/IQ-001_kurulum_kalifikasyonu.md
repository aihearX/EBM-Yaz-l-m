# IQ-001 Kurulum Kalifikasyonu Protokolü

| | |
|---|---|
| Belge No | IQ-001 |
| Sistem | EBM SmartClinical |
| Kurulum ortamı | Hastane veri merkezi (on-premise) |
| Uygulayan | Kurulum Mühendisi (EBM), Hastane BT Sistem Yöneticisi |
| Gözden geçiren | Validasyon Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Amaç ve kapsam

Sistemin KUR-001'e (deploy/KURULUM.md) göre doğru kurulduğunu, bileşenlerin sürüm paketiyle
uyuştuğunu ve altyapı ön koşullarının sağlandığını belgelemek. Kapsam: uygulama sunucusu,
veritabanı rolleri, ters vekil, BDM servisi, zamanlanmış işler, yedekleme.

## 2. Ön koşullar

- Sürüm paketi ve model dosyaları: teslim tutanağındaki SHA-256 özetleriyle doğrulanır.
- Hastane değişiklik talebi onayı.
- `.env` dosyasında `SC_SECRET_KEY` ve `SC_TAKMA_AD_ANAHTARI` üretilmiş ve anahtar kasasına kopyalanmış.

## 3. Kontrol listesi

Gözlenen ve Sonuç sütunları kurulum sırasında doldurulur; Kanıt sütununda komut çıktısı ya da ekran görüntüsü eki belirtilir.

| No | Kontrol | Beklenen | Kod / belge | Gözlenen | Sonuç | Kanıt |
|---|---|---|---|---|---|---|
| IQ-1 | Sunucu donanımı | KUR-001 §1.1 önerilen değerler | deploy/KURULUM.md | | | `lscpu`, `free -g`, `lsblk` |
| IQ-2 | İşletim sistemi ve yamalar | Desteklenen dağıtım, güncel yamalar | deploy/KURULUM.md §1.2 | | | `lsb_release`, yama listesi |
| IQ-3 | Docker / Compose | Engine ≥ 24, Compose v2 | deploy/docker-compose.yml | | | `docker version` |
| IQ-4 | Zaman eşitleme | chrony/ntp aktif, kayma < 100 ms | KUR-001 §1.2 | | | `chronyc tracking` |
| IQ-5 | Disk şifreleme | Veri bölümü LUKS | KUR-001 §1 | | | `lsblk -f` |
| IQ-6 | TLS | Hastane PKI sertifikası, TLS 1.2/1.3, HSTS | deploy/nginx/smartclinical.conf | | | testssl raporu |
| IQ-7 | Yedekleme | cron 02:00; `age` şifreli yedek; geri yükleme provası başarılı, özetler eşleşti | deploy/yedekleme.sh, KUR-001 §8 | | | yedek.log, prova kaydı |
| IQ-8 | İmaj bütünlüğü | SHA-256 eşleşir | KUR-001 §2 | | | `sha256sum -c` |
| IQ-9 | Veritabanı rolleri ve koruma | `smartclinical` rolünde CREATE yok; `UPDATE denetim_kaydi` → insufficient_privilege; tetikleyiciler listede | deploy/postgres/yetkiler.sql | | | psql `\dp denetim_kaydi`, `\dn+` |
| IQ-10 | Ağ yalıtımı | app/postgres/bdm konteynerlerinden dış adrese çıkış yok; yalnızca nginx 80/443 | deploy/docker-compose.yml (`uygulama` ağı internal) | | | `docker exec app curl` zaman aşımı |
| IQ-11 | Zamanlanmış işler | gece işleri timer'ı etkin ya da host cron tanımlı; ilk çalıştırma özeti ve denetim izinde `zamanlanmis` | deploy/systemd/smartclinical-gece.timer, `python -m smartclinical.scripts.gece_isleri --kuru-calisma` | | | `systemctl list-timers`, gece.log |
| IQ-12 | HBYS FHIR bağlantısı (varsa) | CapabilityStatement alınır; yazma isteği reddedilir; eşitleme API ile tetiklenir | `POST /api/v1/hbys/senkron` | | | API yanıtı |
| IQ-13 | BDM servisi ve altın standart (varsa) | Model yüklü; `ml/degerlendirme/degerlendir.py` çıktısı duyarlılık ≥ 0,90, halüsinasyon ≤ 0,02 | KUR-001 §6.3 | | | `ml/ciktilar/*.json` |
| IQ-14 | Anonim uçlar | `/saglik` yalnızca `{"durum":"ok"}`; `/api/belgeler` oturumsuz 303 | smartclinical/api/sistem.py, smartclinical/main.py | | | curl çıktısı |
| IQ-15 | Ortam değişkenleri | `SC_ORTAM=uretim`, anahtarlar üretilmiş, oturum süresi ≤ 30 dk | .env (parolalar maskeli) | | | .env dökümü |
| IQ-16 | Log saklama | Uygulama ve nginx logları ≥ 1 yıl; loglarda hasta verisi yok | logrotate yapılandırması | | | /etc/logrotate.d/smartclinical |
| IQ-17 | İlk yönetici | Oluşturuldu; ilk girişte parola değişimi zorunlu; kayıt denetim izinde | smartclinical/scripts/yonetici_olustur.py | | | Denetim izi kayıtları |
| IQ-18 | Denetim izi zinciri | `denetim_dogrula` çıkış kodu 0 | smartclinical/scripts/denetim_dogrula.py | | | komut çıktısı |

## 4. Sapmalar

| No | Açıklama | Sınıf | Çözüm | Durum |
|---|---|---|---|---|
| | | | | |

## 5. Sonuç

Tüm kontroller "uygun" olmadan ya da sapmalar gerekçeli kabul edilmeden OQ-001'e geçilmez.

## 6. Onaylar

| Rol | İmza |
|---|---|
| Kurulum Mühendisi | |
| Hastane BT Sistem Yöneticisi | |
| Validasyon Sorumlusu | |
| Kalite Güvence Yöneticisi | |
