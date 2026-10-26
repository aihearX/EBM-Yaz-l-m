#!/bin/sh
# Uygulama konteyneri giris noktasi. X-Forwarded-* basliklarina yalnizca ters vekil konteynerinden guvenilir:
# PROXY_HOST (varsayilan "nginx") acilista cozumlenir ve --forwarded-allow-ips bu adresle sinirlanir.
set -eu

PROXY_HOST="${PROXY_HOST:-nginx}"
PROXY_IP="$(getent hosts "$PROXY_HOST" | awk '{print $1}' | paste -sd, -)"
if [ -z "$PROXY_IP" ]; then
  echo "uyari: $PROXY_HOST cozumlenemedi, yalnizca 127.0.0.1 kabul edilecek" >&2
  PROXY_IP="127.0.0.1"
fi

exec uvicorn smartclinical.main:app --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-2}" \
  --proxy-headers --forwarded-allow-ips "$PROXY_IP" "$@"
