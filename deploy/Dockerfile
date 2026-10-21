# EBM SmartClinical uygulama imajı
# Derleme (depo kökünden):  docker build -f deploy/Dockerfile -t smartclinical:1.4.2 .
FROM python:3.12-slim AS temel

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Istanbul

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r smartclinical && useradd -r -g smartclinical -d /app -s /sbin/nologin smartclinical
WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
RUN pip install -r requirements.txt "psycopg[binary]>=3.1"

COPY smartclinical ./smartclinical
COPY ml ./ml
RUN pip install --no-deps . \
    && mkdir -p /app/veri /app/yuklemeler \
    && chown -R smartclinical:smartclinical /app

USER smartclinical
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fs http://localhost:8000/saglik || exit 1

CMD ["uvicorn", "smartclinical.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
