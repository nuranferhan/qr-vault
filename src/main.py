"""
QR Vault — QR Code Generator & S3 Storage Service
Entry point for FastAPI application.
"""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import SessionLocal, engine
from src.models import Base, QRCode, QRCodeStatus
from src.services.analytics_service import AnalyticsService
from src.services.qr_service import QRService
from src.services.s3_service import S3Service

REQUEST_COUNT = Counter(
    "qrvault_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "qrvault_request_latency_seconds",
    "HTTP request latency",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
QR_GENERATED = Counter("qrvault_qr_generated_total", "Total QR codes generated")
QR_SCANNED = Counter("qrvault_qr_scanned_total", "Total QR code scans (redirects)")
QR_ACTIVE = Gauge("qrvault_qr_active_count", "Currently active QR codes")
S3_UPLOAD_ERRORS = Counter("qrvault_s3_upload_errors_total", "S3 upload failures")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    S3Service().ensure_bucket()
    yield


app = FastAPI(
    title="QR Vault",
    description=(
        "Production-grade QR Code Generator with S3 storage, "
        "analytics, batch generation, and custom branding."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    latency = time.time() - start
    endpoint = request.url.path
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
    return response


class QRCreateRequest(BaseModel):
    target_url: str = Field(..., description="Destination URL the QR code points to")
    label: str | None = Field(None, max_length=120, description="Human-readable label")
    error_correction: str = Field("H", pattern="^[LMQH]$", description="L / M / Q / H")
    box_size: int = Field(10, ge=2, le=30)
    border: int = Field(4, ge=1, le=10)
    fill_color: str = Field("#000000", description="Foreground hex color")
    back_color: str = Field("#FFFFFF", description="Background hex color")
    expires_at: datetime | None = Field(None, description="Optional expiry (UTC)")
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None


class BatchQRRequest(BaseModel):
    items: list[QRCreateRequest] = Field(..., min_length=1, max_length=50)


class QRResponse(BaseModel):
    id: str
    short_code: str
    target_url: str
    label: str | None
    s3_key: str
    public_url: str
    redirect_url: str
    scan_count: int
    status: str
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class QRUpdateRequest(BaseModel):
    target_url: str | None = None
    label: str | None = None
    status: str | None = None
    expires_at: datetime | None = None


class AnalyticsResponse(BaseModel):
    qr_id: str
    short_code: str
    label: str | None
    target_url: str
    scan_count: int
    status: str
    created_at: datetime
    last_scanned_at: datetime | None
    daily_scans: dict


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _qr_to_response(qr: QRCode, base_url: str = "http://localhost:8000") -> QRResponse:
    s3 = S3Service()
    return QRResponse(
        id=str(qr.id),
        short_code=qr.short_code,
        target_url=qr.target_url,
        label=qr.label,
        s3_key=qr.s3_key,
        public_url=s3.get_public_url(qr.s3_key),
        redirect_url=f"{base_url}/qr/{qr.short_code}/redirect",
        scan_count=qr.scan_count,
        status=qr.status,
        created_at=qr.created_at,
        expires_at=qr.expires_at,
    )


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "qr-vault", "version": "1.0.0"}


@app.get("/metrics", tags=["System"])
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/qr", response_model=QRResponse, status_code=201, tags=["QR Codes"])
def create_qr(body: QRCreateRequest, request: Request):
    db: Session = next(get_db())
    try:
        qr_svc = QRService()
        s3_svc = S3Service()

        short_code = qr_svc.make_short_code()
        png_bytes = qr_svc.generate_png(
            url=body.target_url,
            error_correction=body.error_correction,
            box_size=body.box_size,
            border=body.border,
            fill_color=body.fill_color,
            back_color=body.back_color,
        )

        s3_key = f"qr/{short_code}.png"
        try:
            s3_svc.upload_png(png_bytes, s3_key)
        except Exception as err:
            S3_UPLOAD_ERRORS.inc()
            raise HTTPException(status_code=502, detail="S3 upload failed") from err

        record = QRCode(
            id=uuid.uuid4(),
            short_code=short_code,
            target_url=body.target_url,
            label=body.label,
            s3_key=s3_key,
            error_correction=body.error_correction,
            box_size=body.box_size,
            border=body.border,
            fill_color=body.fill_color,
            back_color=body.back_color,
            expires_at=body.expires_at,
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
            status=QRCodeStatus.ACTIVE,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        QR_GENERATED.inc()
        QR_ACTIVE.set(db.query(QRCode).filter(QRCode.status == QRCodeStatus.ACTIVE).count())

        base_url = str(request.base_url).rstrip("/")
        return _qr_to_response(record, base_url)
    finally:
        db.close()


@app.get("/qr", response_model=list[QRResponse], tags=["QR Codes"])
def list_qr(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    request: Request = None,
):
    db: Session = next(get_db())
    try:
        q = db.query(QRCode)
        if status:
            q = q.filter(QRCode.status == status)
        records = q.order_by(QRCode.created_at.desc()).offset(skip).limit(limit).all()
        base_url = str(request.base_url).rstrip("/") if request else "http://localhost:8000"
        return [_qr_to_response(r, base_url) for r in records]
    finally:
        db.close()


@app.get("/qr/{short_code}", response_model=QRResponse, tags=["QR Codes"])
def get_qr(short_code: str, request: Request):
    db: Session = next(get_db())
    try:
        record = db.query(QRCode).filter(QRCode.short_code == short_code).first()
        if not record:
            raise HTTPException(status_code=404, detail="QR code not found")
        base_url = str(request.base_url).rstrip("/")
        return _qr_to_response(record, base_url)
    finally:
        db.close()


@app.patch("/qr/{short_code}", response_model=QRResponse, tags=["QR Codes"])
def update_qr(short_code: str, body: QRUpdateRequest, request: Request):
    db: Session = next(get_db())
    try:
        record = db.query(QRCode).filter(QRCode.short_code == short_code).first()
        if not record:
            raise HTTPException(status_code=404, detail="QR code not found")
        if body.target_url is not None:
            record.target_url = body.target_url
        if body.label is not None:
            record.label = body.label
        if body.status is not None:
            record.status = body.status
        if body.expires_at is not None:
            record.expires_at = body.expires_at
        db.commit()
        db.refresh(record)
        base_url = str(request.base_url).rstrip("/")
        return _qr_to_response(record, base_url)
    finally:
        db.close()


@app.delete("/qr/{short_code}", status_code=204, tags=["QR Codes"])
def delete_qr(short_code: str):
    db: Session = next(get_db())
    try:
        record = db.query(QRCode).filter(QRCode.short_code == short_code).first()
        if not record:
            raise HTTPException(status_code=404, detail="QR code not found")
        s3_svc = S3Service()
        s3_svc.delete_object(record.s3_key)
        db.delete(record)
        db.commit()
        QR_ACTIVE.set(db.query(QRCode).filter(QRCode.status == QRCodeStatus.ACTIVE).count())
    finally:
        db.close()


@app.get("/qr/{short_code}/redirect", tags=["QR Codes"])
def redirect_qr(short_code: str, request: Request):
    db: Session = next(get_db())
    try:
        record = db.query(QRCode).filter(QRCode.short_code == short_code).first()
        if not record:
            raise HTTPException(status_code=404, detail="QR code not found")
        if record.status != QRCodeStatus.ACTIVE:
            raise HTTPException(status_code=410, detail="QR code is inactive")
        if record.expires_at and record.expires_at < datetime.now(UTC):
            record.status = QRCodeStatus.EXPIRED
            db.commit()
            raise HTTPException(status_code=410, detail="QR code has expired")

        record.scan_count += 1
        record.last_scanned_at = datetime.now(UTC)

        analytics_svc = AnalyticsService(db)
        analytics_svc.record_scan(
            qr_id=record.id,
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", ""),
        )
        db.commit()
        QR_SCANNED.inc()

        target = record.target_url
        if record.utm_source:
            sep = "&" if "?" in target else "?"
            target += f"{sep}utm_source={record.utm_source}"
            if record.utm_medium:
                target += f"&utm_medium={record.utm_medium}"
            if record.utm_campaign:
                target += f"&utm_campaign={record.utm_campaign}"

        return RedirectResponse(url=target, status_code=302)
    finally:
        db.close()


@app.get("/qr/{short_code}/image", tags=["QR Codes"])
def download_qr_image(short_code: str):
    db: Session = next(get_db())
    try:
        record = db.query(QRCode).filter(QRCode.short_code == short_code).first()
        if not record:
            raise HTTPException(status_code=404, detail="QR code not found")
        s3_svc = S3Service()
        png_bytes = s3_svc.download_png(record.s3_key)
        return StreamingResponse(
            iter([png_bytes]),
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{short_code}.png"'},
        )
    finally:
        db.close()


@app.post("/qr/batch", response_model=list[QRResponse], status_code=201, tags=["QR Codes"])
def batch_create_qr(body: BatchQRRequest, request: Request):
    results = []
    for item in body.items:
        resp = create_qr(item, request)
        results.append(resp)
    return results


@app.get("/qr/{short_code}/analytics", response_model=AnalyticsResponse, tags=["Analytics"])
def get_analytics(short_code: str):
    db: Session = next(get_db())
    try:
        record = db.query(QRCode).filter(QRCode.short_code == short_code).first()
        if not record:
            raise HTTPException(status_code=404, detail="QR code not found")
        analytics_svc = AnalyticsService(db)
        daily = analytics_svc.daily_scan_counts(record.id)
        return AnalyticsResponse(
            qr_id=str(record.id),
            short_code=record.short_code,
            label=record.label,
            target_url=record.target_url,
            scan_count=record.scan_count,
            status=record.status,
            created_at=record.created_at,
            last_scanned_at=record.last_scanned_at,
            daily_scans=daily,
        )
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse, tags=["UI"])
def index():
    return HTMLResponse(content=open("src/templates/index.html", encoding="utf-8").read())