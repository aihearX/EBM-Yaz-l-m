# IQ-001 Kurulum Kalifikasyonu Protokolü ve Raporu

| | |
|---|---|
| Belge No | IQ-001 |
| Sistem | EBM SmartClinical v1.4.2 |
| Kurulum ortamı | Pilot Merkez 1 (Üniversite Hastanesi) – üretim ortamı, hastane veri merkezi |
| Sürüm | 1.0 |
| Protokol onayı | 2026-05-04 |
| Uygulama tarihi | 2026-05-12 – 2026-05-13 |
| Uygulayan | Kurulum Mühendisi (EBM), Hastane BT Sistem Yöneticisi |
| Gözden geçiren | Validasyon Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Amaç ve kapsam

Sistemin KUR-001'e göre doğru kurulduğunu, bileşen sürümlerinin sürüm paketiyle
uyuştuğunu ve altyapı ön koşullarının sağlandığını belgelemek. Kapsam: uygulama
sunucusu, veritabanı, ters vekil, BDM servisi, yedekleme.

## 2. Ön koşullar

- Sürüm paketi: `smartclinical-1.4.2-imajlar.tar.gz`, SHA-256: `3f1c…a92e` (teslim tutanağı TT-2026-017)
- Model paketi: `ebm-klinik-tr-7b-q4_k_m.gguf`, SHA-256: `9b4d…1c07`
- Hastane değişiklik talebi onayı: BT-DT-2026-088

## 3. Kontrol listesi

| No | Kontrol | Beklenen | Gözlenen | Sonuç | Kanıt |
|---|---|---|---|---|---|
| IQ-1 | Sunucu donanımı | ≥ 8 çekirdek, 32 GB RAM, 500 GB SSD RAID1 | 16 çekirdek, 64 GB, 960 GB RAID1 | Uygun | `lscpu`, `free -g`, `lsblk` çıktıları (EK-1) |
| IQ-2 | İşletim sistemi | Ubuntu 24.04 LTS, güncel yamalar | Ubuntu 24.04.2, son yama 2026-05-08 | Uygun | `lsb_release`, `apt list --upgradable` (EK-1) |
| IQ-3 | Docker / Compose | ≥ 24 / v2 | 27.1.1 / v2.29.2 | Uygun | `docker version` |
| IQ-4 | Zaman eşitleme | chrony aktif, kayma < 100 ms | chrony, hastane NTP sunucusu, kayma 4 ms | Uygun | `chronyc tracking` |
| IQ-5 | Disk şifreleme | Veri bölümü LUKS | /var/lib/docker LUKS2 | Uygun | `lsblk -f` |
| IQ-6 | TLS sertifikası | Hastane PKI, TLS 1.2/1.3, geçerlilik > 6 ay | smartclinical.hastane.local, 2027-04-30'a kadar; testssl: A | Uygun | testssl raporu (EK-2) |
| IQ-7 | Yedekleme | cron 02:00, geri yükleme provası başarılı | Kuruldu; test veritabanında geri yükleme 11 dk, özetler eşleşti | Uygun | yedek.log, prova kaydı (EK-3) |
| IQ-8 | İmaj bütünlüğü | SHA-256 eşleşir | Eşleşti | Uygun | `sha256sum -c` çıktısı |
| IQ-9 | Veritabanı yetkileri | denetim_kaydi/e_imza üzerinde UPDATE/DELETE engelli | `UPDATE denetim_kaydi` → insufficient_privilege; tetikleyici listede | Uygun | psql çıktısı (EK-4) |
| IQ-10 | Uygulama sürümü | 1.4.2 | /saglik → `"surum":"1.4.2"` | Uygun | curl çıktısı |
| IQ-11 | Veritabanı sürümü | PostgreSQL 16.x | 16.4 | Uygun | `SELECT version()` |
| IQ-12 | Şema | 23 tablo oluşturuldu | 23 tablo | Uygun | `\dt` |
| IQ-13 | BDM servisi | Model yüklü, yanıt < 5 sn (GPU) | ebm-klinik-tr-7b-q4, L40S, test istemi 1,3 sn | Uygun | Yönetim → BDM Durumu ekran görüntüsü |
| IQ-14 | BDM dış ağ erişimi | Yok | bdm konteynerinden dış adrese çıkış yok (iptables) | Uygun | `docker exec bdm curl` zaman aşımı |
| IQ-15 | Gömme servisi | Çalışıyor | 8081 yanıt veriyor | Uygun | curl |
| IQ-16 | HBYS FHIR bağlantısı | Metadata alınır, salt okunur hesap | CapabilityStatement alındı; POST → 403 | Uygun | Entegrasyon → Bağlantıyı sına (EK-5) |
| IQ-17 | Ortam değişkenleri | SC_ORTAM=uretim, SECRET_KEY üretilmiş, oturum 20 dk | Uygun | .env (parolalar maskeli) |
| IQ-18 | Log saklama | 1 yıl, JSON | logrotate 365 gün | Uygun | /etc/logrotate.d/smartclinical |
| IQ-19 | Sağlık kontrolü erişimi | Yalnızca iç ağ | Dış IP'den 403 | Uygun | curl |
| IQ-20 | İlk yönetici | Oluşturuldu, ilk girişte parola değişimi zorunlu | Uygun | Denetim izi kaydı #1–#3 |
| IQ-21 | Altın standart değerlendirmesi (kurulum sonrası) | Duyarlılık ≥ 0,90; halüsinasyon ≤ 0,02 | 0,93 / 0,00 (n=312) | Uygun | ml/ciktilar/20260513_101822.json (EK-6) |

## 4. Sapmalar

| No | Açıklama | Sınıf | Çözüm | Durum |
|---|---|---|---|---|
| SAP-IQ-01 | IQ-7 ilk provada geri yükleme betiği docker volume yolunu bulamadı (KUR-001 §8'de yol tanımı eksik) | Minör | KUR-001 1.4.1'de yol düzeltildi; prova tekrarlandı, başarılı | Kapalı |

## 5. Sonuç

21 kontrolün tamamı uygun. 1 minör sapma kapatıldı. Sistem OQ-001'e geçmeye uygundur.

## 6. Onaylar

| Rol | İmza | Tarih |
|---|---|---|
| Kurulum Mühendisi | e-imza | 2026-05-13 |
| Hastane BT Sistem Yöneticisi | ıslak imza | 2026-05-13 |
| Validasyon Sorumlusu | e-imza | 2026-05-15 |
| Kalite Güvence Yöneticisi | e-imza | 2026-05-18 |
