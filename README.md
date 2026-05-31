# QR Vault

FastAPI ile geliştirilmiş, canlı ortama (production-grade) hazır bir QR Kod Oluşturma servisidir. QR kodlarını PNG formatında üretir, S3 üzerinde (LocalStack aracılığıyla) saklar, tarama verilerini günlük analizlerle takip eder, toplu (batch) üretimi destekler, özel markalama (renkler, hata düzeltme seviyeleri) ve UTM parametresi ekleme gibi gelişmiş özellikler sunar.

**Bu projeyi sıradan bir QR oluşturucudan ayıran özellikler:**
- Günlük kırılımlar ve son tarama zaman damgası (timestamp) ile tarama seviyesinde analizler
- Kaydedilen QR imajını değiştirmeden, yönlendirme (redirect) esnasında dinamik UTM parametresi ekleme
- Her QR kodu için özel dolgu (fill) ve arka plan rengi desteği
- Toplu üretim uç noktası (endpoint) ile tek istekte 50 adede kadar QR kodu oluşturabilme
- Her QR kodu için seçilebilir dört farklı hata düzeltme (error correction) seviyesi (L / M / Q / H)
- `/metrics` üzerinde etiketlenmiş altı adet sayaç (counter) ve histogram içeren Prometheus metrik dışa aktarıcısı (exporter)
- Root yetkisi olmayan (non-root) konteyner kullanıcısı, çok aşamalı (multi-stage) Dockerfile ve yapılandırılmış sağlık kontrolleri (health probes)

---

## Mimari (Architecture)



Görsel diyagram için `docs/architecture.png` dosyasına göz atabilirsiniz.

---

## Hızlı Başlangıç (Quick Start)

### Gereksinimler

- Docker + Docker Compose
- Python 3.11+

### Docker Compose ile Çalıştırma

```bash
git clone [https://github.com/KULLANICI_ADINIZ/qr-vault](https://github.com/KULLANICI_ADINIZ/qr-vault)
cd qr-vault
docker compose up -d

```

Servisler:

| Servis | URL |
| --- | --- |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

Grafana giriş bilgileri: `admin` / `admin`

### Yerelde Çalıştırma (Docker Olmadan)

```bash
pip install -e ".[dev]"
export DATABASE_URL="sqlite:///./qrvault.db"
export LOCALSTACK=true
export LOCALSTACK_URL=http://localhost:4566   # LocalStack'i ayrıca çalıştırmanız gerekir
uvicorn src.main:app --reload --port 8000

```

---

## API Referansı (API Reference)

| Metot | Uç Nokta (Endpoint) | Açıklama |
| --- | --- | --- |
| GET | `/health` | Sağlık kontrolü (Liveness probe) |
| GET | `/metrics` | Prometheus metrikleri |
| POST | `/qr` | QR kodu oluşturur |
| GET | `/qr` | QR kodlarını listeler (sayfalamalı) |
| GET | `/qr/{code}` | QR kodu meta verilerini getirir |
| PATCH | `/qr/{code}` | Etiket / hedef URL / durum günceller |
| DELETE | `/qr/{code}` | QR kodunu ve S3 nesnesini siler |
| GET | `/qr/{code}/redirect` | Tarama takipli yönlendirme (sayacı artırır) |
| GET | `/qr/{code}/image` | S3 üzerinden PNG indirir |
| GET | `/qr/{code}/analytics` | Günlük tarama kırılımı |
| POST | `/qr/batch` | Tek seferde 50 adede kadar toplu QR üretir |

Tüm interaktif dokümantasyona `/docs` (Swagger UI) veya `/redoc` adreslerinden ulaşabilirsiniz.

### Örnek: QR Kodu Oluşturma

```bash
curl -X POST http://localhost:8000/qr \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "[https://example.com](https://example.com)",
    "label": "Kampanyam",
    "error_correction": "H",
    "fill_color": "#1a1a2e",
    "back_color": "#FFFFFF",
    "utm_source": "readme",
    "utm_medium": "doc"
  }'

```

### Örnek: Toplu (Batch) Üretim

```bash
curl -X POST http://localhost:8000/qr/batch \
  -H "Content-Type: application/json" \
  -d '{"items": [
    {"target_url": "[https://urun-a.com](https://urun-a.com)"},
    {"target_url": "[https://urun-b.com](https://urun-b.com)"},
    {"target_url": "[https://urun-c.com](https://urun-c.com)"}
  ]}'

```

---

## Testleri Çalıştırma

```bash
# Sadece Birim (Unit) testleri (Docker gerektirmez)
pytest tests/unit/ -v --cov=src --cov-report=term-missing

# Entegrasyon (Integration) testleri (Testcontainers için Docker gerekir)
pytest tests/integration/ -v

# Uçtan Uca (E2E) testler (Uygulamanın localhost:8000'de çalışıyor olması gerekir)
pytest tests/e2e/ -v

# Kod kapsamı (coverage) ile birlikte tüm testler
pytest -v

```

### Yük Testi (Load Test)

```bash
# k6'nın kurulu olması gerekir: [https://k6.io/docs/get-started/installation/](https://k6.io/docs/get-started/installation/)
k6 run perf/load-test.js

```

### Postman / Newman

```bash
npm install -g newman
newman run postman/collection.json --env-var "baseUrl=http://localhost:8000"

```

---

## Kubernetes (Minikube)

```bash
minikube start
minikube image load qr-vault:latest

kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

kubectl rollout status deployment/qr-vault
minikube service qr-vault --url

```

---

## Proje Yapısı (Project Structure)

```
qr-vault/
├── src/
│   ├── main.py            # FastAPI uygulaması, rotalar (routes), Prometheus metrikleri
│   ├── models.py          # SQLAlchemy ORM modelleri (QRCode, ScanEvent)
│   ├── database.py        # Engine ve oturum (session) yapılandırması
│   ├── templates/
│   │   └── index.html     # Minimal kullanıcı arayüzü (E2E test hedefi)
│   └── services/
│       ├── qr_service.py       # PNG üretimi (qrcode + Pillow)
│       ├── s3_service.py       # S3 / LocalStack entegrasyonu
│       └── analytics_service.py # Tarama olaylarının kaydedilmesi ve kümelenmesi
├── tests/
│   ├── unit/              # 30+ harici bağımlılığı olmayan birim testi
│   ├── integration/       # Testcontainers + gerçek PostgreSQL entegrasyon testleri
│   ├── e2e/               # Playwright tarayıcı testleri (5 farklı senaryo)
│   ├── factories.py       # Factory Boy + Faker model fabrikaları
│   └── conftest.py        # Ortak pytest fikstürleri (fixtures)
├── postman/               # 13 farklı istek içeren Postman koleksiyonu
├── k8s/                   # Deployment, Service, ConfigMap dosyaları
├── perf/                  # k6 yük testi scriptleri ve raporları
├── monitoring/            # Prometheus + Grafana kurulum ayarları (provisioning)
├── .github/workflows/     # 5 aşamalı CI/CD hattı (pipeline)
├── Dockerfile             # Çok aşamalı (builder + runtime) Docker dosyası
├── docker-compose.yml     # Yerel altyapının tamamı (full local stack)
└── docs/                  # Mimari diyagramı, sonuç raporu ve sunum slaytları

```

---

## Fark Yaratan Özellikler (Differentiating Features)

Temel gereksinimlerin ötesinde, bu mimari şunları içerir:

* **Yönlendirme Esnasında UTM Ekleme** — UTM parametreleri, saklanan QR imajı değiştirilmeden yönlendirme anında hedef URL'e eklenir. Böylece tek bir QR kodu ile farklı kampanyalar takip edilebilir.
* **Toplu Üretim** — `/qr/batch` uç noktası tek seferde 50 adede kadar istek kabul eder ve hepsini tek bir ağ turunda (round trip) dönerek kampanya kurulumlarını hızlandırır.
* **Günlük Tarama Analizleri** — `/qr/{code}/analytics` uç noktası, tarih bazlı bir `daily_scans` haritası döner. Bu sayede harici bir analiz servisine ihtiyaç duymadan zaman serisi grafikleri çizdirilebilir.
* **Özel QR Markalama** — Sadece siyah-beyaz değil, her QR kodu için istenilen hex renk kodu kombinasyonunda dolgu/arka plan rengi desteklenir.
* **Altı Farklı Prometheus Metriği** — Metot/uç nokta/durum koduna göre etiketlenmiş istek sayısı, istek gecikme (latency) histogramı, aktif QR göstergesi (gauge), üretilen QR sayacı, taranan QR sayacı ve S3 hata sayacı ile tam operasyonel görünürlük sağlanır.
* **Root Yetkisi Olmayan Konteyner** — Çalışma zamanı (runtime) imajı UID 1000 (`appuser`) olarak çalışır ve Kubernetes `runAsNonRoot: true` güvenlik politikasını doğrudan karşılar.

---

## Teknoloji Yığını (Tech Stack)

| Katman | Teknoloji |
| --- | --- |
| Framework | FastAPI 0.111 + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Veritabanı | PostgreSQL 16 (canlı) / SQLite (test) |
| QR Üretimi | qrcode 7.4 + Pillow 10 |
| Nesne Depolama | LocalStack S3 (boto3) |
| İzleme | Prometheus + Grafana |
| Test | pytest, Factory Boy, Faker, Testcontainers, Playwright |
| Yük Testi | k6 |
| CI/CD | GitHub Actions |
| Konteyner | Docker (multi-stage) + Docker Compose |
| Orkestrasyon | Kubernetes (Minikube) |

---

## Lisans (License)

MIT — Detaylar için [LICENSE](https://www.google.com/search?q=LICENSE) dosyasına bakabilirsiniz.
