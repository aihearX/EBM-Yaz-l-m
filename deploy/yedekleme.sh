#!/usr/bin/env bash
# EBM SmartClinical yedekleme
# Günlük cron: 0 2 * * * /opt/smartclinical/deploy/yedekleme.sh >> /var/log/smartclinical/yedek.log 2>&1
#
# Yedekler age ile şifrelenir (alıcı açık anahtarı YEDEK_AGE_ALICI dosyasında; özel anahtar yedek sunucusunda değil,
# anahtar kasasında tutulur). Saklama: günlük 7 gün, haftalık (pazar) 30 gün, aylık (ayın 1'i) 25 yıl
# (İyi Klinik Uygulamaları Yönetmeliği'ndeki temel belge saklama süresiyle aynı).
set -euo pipefail

YEDEK_DIZIN="${YEDEK_DIZIN:-/var/yedek/smartclinical}"
DOSYA_DIZIN="${SC_DOSYA_DIZINI:-/opt/smartclinical/yuklemeler}"
PG_URL="${SC_DB_URL:-}"
AGE_ALICI="${YEDEK_AGE_ALICI:-/etc/smartclinical/yedek_age.pub}"   # age alıcı (açık anahtar) dosyası
TARIH="$(date +%Y%m%d_%H%M%S)"
GUN="$(date +%u)"      # 7 = pazar
AY_GUNU="$(date +%d)"

if ! command -v age >/dev/null 2>&1; then
  echo "age bulunamadı; yedek şifrelenemez (apt install age)" >&2
  exit 1
fi
if [ ! -s "$AGE_ALICI" ]; then
  echo "age alıcı dosyası yok: $AGE_ALICI (age-keygen ile üretin, özel anahtarı kasada saklayın)" >&2
  exit 1
fi

mkdir -p "$YEDEK_DIZIN"/{gunluk,haftalik,aylik}
umask 077

if [ -n "$PG_URL" ] && [[ "$PG_URL" == postgresql* ]]; then
  # SQLAlchemy URL'ini libpq biçimine çevir
  LIBPQ_URL="${PG_URL/postgresql+psycopg:/postgresql:}"
  DB_YEDEK="$YEDEK_DIZIN/gunluk/db_$TARIH.dump.age"
  pg_dump --format=custom --compress=6 --no-owner "$LIBPQ_URL" | age -R "$AGE_ALICI" -o "$DB_YEDEK"
else
  SQLITE_YOL="${PG_URL#sqlite:///}"
  GECICI="$(mktemp)"
  sqlite3 "$SQLITE_YOL" ".backup '$GECICI'"
  DB_YEDEK="$YEDEK_DIZIN/gunluk/db_$TARIH.sqlite.age"
  age -R "$AGE_ALICI" -o "$DB_YEDEK" "$GECICI"
  rm -f "$GECICI"
fi

DOSYA_YEDEK="$YEDEK_DIZIN/gunluk/dosyalar_$TARIH.tar.gz.age"
tar -czf - -C "$(dirname "$DOSYA_DIZIN")" "$(basename "$DOSYA_DIZIN")" | age -R "$AGE_ALICI" -o "$DOSYA_YEDEK"

# Bütünlük özeti – geri yükleme provasında karşılaştırılır
sha256sum "$DB_YEDEK" "$DOSYA_YEDEK" > "$YEDEK_DIZIN/gunluk/ozet_$TARIH.sha256"

if [ "$GUN" = "7" ]; then
  cp "$DB_YEDEK" "$DOSYA_YEDEK" "$YEDEK_DIZIN/haftalik/"
fi
if [ "$AY_GUNU" = "01" ]; then
  cp "$DB_YEDEK" "$DOSYA_YEDEK" "$YEDEK_DIZIN/aylik/"
fi

# Saklama
find "$YEDEK_DIZIN/gunluk"   -type f -mtime +7    -delete
find "$YEDEK_DIZIN/haftalik" -type f -mtime +30   -delete
find "$YEDEK_DIZIN/aylik"    -type f -mtime +9131 -delete   # 25 yıl

# Uzak kopya (hastane yedek sunucusu) – tanımlıysa; dosyalar zaten şifreli
if [ -n "${UZAK_YEDEK:-}" ]; then
  rsync -a --delete "$YEDEK_DIZIN/" "$UZAK_YEDEK/"
fi

echo "$(date -Is) yedek tamamlandı: $DB_YEDEK ($(du -h "$DB_YEDEK" | cut -f1)), $DOSYA_YEDEK ($(du -h "$DOSYA_YEDEK" | cut -f1))"
# Geri yükleme: age -d -i /kasadan/yedek_age.key db_<tarih>.dump.age | pg_restore -U smartclinical_admin -d smartclinical --clean --if-exists
