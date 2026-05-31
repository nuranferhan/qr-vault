FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        sqlalchemy \
        psycopg2-binary \
        alembic \
        "qrcode[pil]" \
        pillow \
        boto3 \
        prometheus-client \
        pydantic \
        python-multipart \
        httpx \
        --prefix=/install


FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="QR Vault"
LABEL org.opencontainers.image.description="QR Code Generator with S3 storage and analytics"
LABEL org.opencontainers.image.version="1.0.0"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /install /usr/local

COPY src/ ./src/

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
