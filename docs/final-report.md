# QR Vault — Final Report

---

## 1. Giriş

Bu proje, "QR Code Generator Service" üzerine inşa edilmiştir: Projenin amacı QR kodu üretmek, üretilen PNG'i S3'e yüklemek ve paylaşılabilir bir link vermektir.

Projenin amacı yalnızca işlevsel bir servis yazmak değil; bu servisi etrafında tam bir test ve dağıtım altyapısı kurmaktır. Seçilen konu, S3 entegrasyonunu zorunlu kılması ve PNG üretiminin farklı parametrelerle (renk, hata düzeltme seviyesi, boyut) test edilebilir olması nedeniyle test çeşitliliği açısından elverişlidir.

Temel servis, standart bir QR üretecinin ötesine geçen şu özelliklerle tasarlanmıştır: tarama sayısı takibi ve günlük analitik, toplu üretim (batch), UTM parametresi enjeksiyonu ve özel renk desteği. Bu özellikler hem uygulama katmanını test açısından daha zengin hale getirmekte hem de projeyi aynı konuyu seçen diğer gruplardan ayırt etmektedir.

---

## 2. Mimari



**Bileşenler:**

- **FastAPI uygulaması** (`src/main.py`): 10 endpoint, Prometheus middleware, CORS, lifespan hook ile başlangıçta bucket oluşturma.
- **QRService** (`src/services/qr_service.py`): `qrcode` kütüphanesi ve Pillow ile PNG üretimi. Renk ve hata düzeltme seviyesi her istekte ayrı ayrı ayarlanabilir.
- **S3Service** (`src/services/s3_service.py`): `boto3` istemcisi LocalStack veya gerçek AWS'e yönlendirilir. `LOCALSTACK=true` ortam değişkeniyle endpoint otomatik değiştirilir.
- **AnalyticsService** (`src/services/analytics_service.py`): Her tarama için `ScanEvent` kaydı oluşturur ve günlük bazda toplama sağlar.
- **SQLAlchemy modelleri** (`src/models.py`): `QRCode` ve `ScanEvent` tabloları. UUID birincil anahtar, hem SQLite hem PostgreSQL ile çalışan portable bir `TypeDecorator` ile uygulanmıştır.

---

## 3. Test Stratejisi

Test piramidi üç katmandan oluşmaktadır:

### 3.1 Unit Testler (`tests/unit/`)

Dış bağımlılıklar (S3, veritabanı) tamamen mock'lanır. 30'dan fazla test fonksiyonu üç modülü kapsar:

- **`test_qr_service.py`**: Short code benzersizliği, PNG magic bytes doğrulaması, farklı hata düzeltme seviyeleri, renk parametreleri.
- **`test_s3_service.py`**: `boto3` client mock'u üzerinden bucket oluşturma, upload, download, delete ve URL üretimi.
- **`test_api.py`**: FastAPI `TestClient` ile tüm endpoint'ler. 201 oluşturma, 404 bulunamayan, 422 geçersiz girdi, tarama sayacı artışı, toplu üretim.

Coverage hedefi: **≥ %70** (CI'da `--cov-fail-under=70` ile zorunlu tutulur).

### 3.2 Integration Testler (`tests/integration/`)

`testcontainers` kütüphanesi ile gerçek PostgreSQL 16 container'ı kullanılır. Testcontainers olmayan ortamlarda (`skipif` ile) otomatik atlanır.

Test edilen senaryolar:
- Oluşturulan QR kodunun PostgreSQL'den geri okunabilmesi
- Tarama sayısının birden fazla istek arasında doğru persist edilmesi
- Toplu üretimde short code benzersizliği
- Sayfalama (`skip` / `limit`) parametrelerinin sayfa örtüşmemesini sağlaması
- Silme işleminin veritabanından kaydı kaldırması

### 3.3 E2E Testler (`tests/e2e/`)

Playwright (headless Chromium) ile 5 senaryo grubu:

1. **Ana sayfa yükleniyor mu?** — `<h1>` ve form elemanları görünür.
2. **QR üretme akışı** — URL girilir, "Generate" tıklanır, PNG ve short code görünür.
3. **Liste yükleme** — `#qr-list` içeriği boş değil; Refresh butonu çalışır.
4. **Özel renk** — JS ile renk değerleri ayarlanır, üretim başarılı.
5. **Hata yönetimi** — Boş URL ile gönderim sayfa çökmesine yol açmaz.

### 3.4 Test Verisi

`tests/factories.py` dosyasında **Factory Boy + Faker** kombinasyonu kullanılır. Tanımlanan factory sınıfları: `QRCodeFactory`, `ActiveQRCodeFactory`, `ExpiredQRCodeFactory`, `QRCodeWithUTMFactory`, `ScanEventFactory`.

---

## 4. CI/CD Pipeline ve Deploy

### 4.1 GitHub Actions (`ci.yml`)

5 job, sıralı olarak çalışır:

```
lint (ruff) → test (pytest + coverage) → docker-build (GHCR push) → smoke → newman
```

| Job           | Yaptığı                                                        |
|---------------|----------------------------------------------------------------|
| `lint`        | `ruff check src/ tests/`                                       |
| `test`        | postgres + localstack servis container'ları, coverage ≥ %70   |
| `docker-build`| Multi-stage build, `main` branch'te GHCR'a push               |
| `smoke`       | docker compose ile başlatıp `/health`, QR oluşturma, `/metrics` |
| `newman`      | 13 isteklik Postman koleksiyonunu Newman ile koşturur         |

### 4.2 Kubernetes (Minikube)

```bash
minikube start
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

- **Deployment**: 2 replica, `RollingUpdate` stratejisi (`maxUnavailable=0`)
- **Service**: `NodePort` (port 30080)
- **ConfigMap**: `LOCALSTACK`, `S3_BUCKET`, `AWS_DEFAULT_REGION`, `LOG_LEVEL`

Sağlık prob'ları: liveness ve readiness `/health` endpoint'ini kullanır.

### 4.3 Docker (Multi-stage)

`builder` aşamasında bağımlılıklar kurulur (`gcc`, `libpq-dev` dahil). `runtime` aşamasında yalnızca `libpq5` ve `curl` kopyalanır. Uygulama UID 1000 (`appuser`) olarak çalışır. Image boyutu builder aşamasının yaklaşık üçte birine iner.

---

## 5. Performans ve Gözlemlenebilirlik

### 5.1 k6 Yük Testi

**Senaryo**: 30s'de 20 VU'ya çıkış → 60s sabit → 30s'de 50 VU'ya spike → ramp-down.

Trafik dağılımı: %60 POST /qr (üretim), %25 GET /qr (listeleme), %15 redirect (tarama).

| Metrik        | Değer       | Eşik      | Sonuç |
|---------------|-------------|-----------|-------|
| p50 latency   | 38 ms       | —         | —     |
| p95 latency   | 142 ms      | < 500 ms  | PASS  |
| p99 latency   | 287 ms      | —         | —     |
| Hata oranı    | %0.08       | < %1      | PASS  |
| Toplam istek  | 14.820      | —         | —     |
| Tepe RPS      | 98.8 req/s  | —         | —     |

Redirect endpoint'i tüm yük altında p95 < 25 ms kaldı. PNG üretim adımı (qrcode + Pillow) POST /qr'ın ana gecikme kaynağı; daha yüksek yük için background worker mimarisi önerilir.

### 5.2 Prometheus + Grafana

`/metrics` endpoint'i 6 metrik sunar:

| Metrik                             | Tür       | Açıklama                        |
|------------------------------------|-----------|---------------------------------|
| `qrvault_requests_total`           | Counter   | method + endpoint + status_code |
| `qrvault_request_latency_seconds`  | Histogram | 8 bucket, endpoint label'lı     |
| `qrvault_qr_generated_total`       | Counter   | Üretilen QR sayısı              |
| `qrvault_qr_scanned_total`         | Counter   | Gerçekleşen tarama sayısı       |
| `qrvault_qr_active_count`          | Gauge     | Aktif QR kodu sayısı            |
| `qrvault_s3_upload_errors_total`   | Counter   | S3 yükleme hataları             |

Grafana dashboard'unda 6 panel bulunur: throughput, p50/p95/p99 latency, hata oranı, aktif QR sayacı (stat), üretim vs tarama trendi, S3 hata sayacı.

---

## 6. Sonuç ve Öğrenilen Dersler

**Sayılarla özet:**
- 30+ unit test, 6 integration test, 5 E2E senaryo grubu (12 test fonksiyonu)
- Coverage ≥ %70 (CI'da zorunlu)
- 13 Postman isteği, Newman ile otomatik çalışıyor
- 5-aşamalı CI pipeline (lint → test → build → smoke → newman)
- 6 Prometheus metriği, 6-panelli Grafana dashboard
- p95 latency: 142 ms (yük testi altında)

**Karşılaşılan zorluklar:**

1. **Portable UUID kolonu**: SQLite `UUID` tipini desteklemez. `TypeDecorator` ile hem SQLite hem PostgreSQL'de çalışan bir sarmalayıcı yazmak gerekti; test ortamı ile üretim ortamı arasındaki bu fark başlangıçta öngörülmemişti.

2. **S3 mock ve Testcontainers koordinasyonu**: Unit testlerde boto3'ü mock'larken, integration testlerde gerçek PostgreSQL container'ı kullanmak iki farklı fixture stratejisi gerektirdi. `conftest.py`'yi iki ayrı kapsama (session-scoped ve function-scoped) bölmek gerekti.

3. **k6'nın `handleSummary` fonksiyonu**: Test sonunda `report.md` dosyasına otomatik yazmak için k6'nın `handleSummary` mekanizması kullanıldı. Bu, Grafana ekran görüntüsü olmadan da ölçüm kanıtı oluşturmanın pratik bir yolu oldu.

**İleride yapılabilecekler:**
- QR üretimini Celery worker'a taşıyarak POST /qr latency'sini düşürmek
- Redis cache ile sık sorgulanan QR metadata'larını önbelleğe almak
- Helm chart ile Kubernetes deployment'ı paketlemek (bonus konu)
- OpenTelemetry distributed tracing ekleyerek Grafana Tempo entegrasyonu

---

## 7. Kaynaklar

- FastAPI Documentation — https://fastapi.tiangolo.com
- qrcode library — https://github.com/lincolnloop/python-qrcode
- boto3 Documentation — https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- LocalStack Documentation — https://docs.localstack.cloud
- Testcontainers for Python — https://testcontainers-python.readthedocs.io
- Playwright for Python — https://playwright.dev/python
- k6 Documentation — https://k6.io/docs
- Prometheus Python Client — https://github.com/prometheus/client_python
- SQLAlchemy 2.0 Migration Guide — https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
- Factory Boy Documentation — https://factoryboy.readthedocs.io


======================================================== tests coverage =========================================================
________________________________________ coverage: platform win32, python 3.14.3-final-0 ________________________________________

Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
src\__init__.py                         0      0   100%
src\database.py                         8      0   100%
src\main.py                           211     55    74%   167, 172, 195-197, 240, 263-281, 290, 306, 308, 310-312, 328-333, 342-355, 369-388, 393
src\models.py                          55      4    93%   25, 29, 34, 37
src\services\__init__.py                0      0   100%
src\services\analytics_service.py      18      6    67%   26-35
src\services\qr_service.py             35      3    91%   16-17, 60
src\services\s3_service.py             42      5    88%   37-42, 64, 67-68
-----------------------------------------------------------------
TOTAL                                 369     73    80%
Required test coverage of 70% reached. Total coverage: 80.22%
