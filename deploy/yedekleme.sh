#!/usr/bin/env bash
# EBM SmartClinical yedekleme
# Günlük cron: 0 2 * * * /opt/smartclinical/deploy/yedekleme.sh >> /var/log/smartclinical/yedek.log 2>&1
#
# Saklama: günlük yedekler 7 gün, haftalık (pazar) yedekler 30 gün, aylık (ayın 1'i) yedekler 7 yıl.
# Klinik araştırma kayıtları için TMF saklama süresi (en az 25 yıl, İyi Klinik Uygulamaları
# Yönetmeliği) ayrıca arşiv prosedürüyle (SOP-ARS-02) karşılanır; bu betik operasyonel yedektir.
set -euo pipefail

YEDEK_DIZIN="${YEDEK_DIZIN:-/var/yedek/smartclinical}"
DOSYA_DIZIN="${SC_DOSYA_DIZINI:-/opt/smartclinical/yuklemeler}"
PG_URL="${SC_DB_URL:-}"
TARIH="$(date +%Y%m%d_%H%M%S)"
GUN="$(date +%u)"      # 7 = pazar
AY_GUNU="$(date +%d)"

mkdir -p "$YEDEK_DIZIN"/{gunluk,haftalik,aylik}

if [ -n "$PG_URL" ] && [[ "$PG_URL" == postgresql* ]]; then
  # SQLAlchemy URL'ini libpq biçimine çevir
  LIBPQ_URL="${PG_URL/postgresql+psycopg:/postgresql:}"
  DB_YEDEK="$YEDEK_DIZIN/gunluk/db_$TARIH.dump"
  pg_dump --format=custom --compress=6 --no-owner "$LIBPQ_URL" > "$DB_YEDEK"
else
  SQLITE_YOL="${PG_URL#sqlite:///}"
  DB_YEDEK="$YEDEK_DIZIN/gunluk/db_$TARIH.sqlite"
  sqlite3 "$SQLITE_YOL" ".backup '$DB_YEDEK'"
fi

DOSYA_YEDEK="$YEDEK_DIZIN/gunluk/dosyalar_$TARIH.tar.gz"
tar -czf "$DOSYA_YEDEK" -C "$(dirname "$DOSYA_DIZIN")" "$(basename "$DOSYA_DIZIN")"

# Bütünlük özeti – geri yükleme testinde (IQ-001 madde 7) karşılaştırılır
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
find "$YEDEK_DIZIN/aylik"    -type f -mtime +2557 -delete   # 7 yıl

# Uzak kopya (hastane yedek sunucusu) – tanımlıysa
if [ -n "${UZAK_YEDEK:-}" ]; then
  rsync -a --delete "$YEDEK_DIZIN/" "$UZAK_YEDEK/"
fi

echo "$(date -Is) yedek tamamlandı: $DB_YEDEK ($(du -h "$DB_YEDEK" | cut -f1)), $DOSYA_YEDEK ($(du -h "$DOSYA_YEDEK" | cut -f1))"
