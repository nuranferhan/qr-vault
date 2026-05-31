
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator

from src.database import Base


class UUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except Exception:
            return value


class QRCodeStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


class QRCode(Base):
    __tablename__ = "qr_codes"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    short_code = Column(String(16), unique=True, nullable=False, index=True)
    target_url = Column(Text, nullable=False)
    label = Column(String(120), nullable=True)

  
    s3_key = Column(String(256), nullable=False)

   
    error_correction = Column(String(1), nullable=False, default="H")
    box_size = Column(Integer, nullable=False, default=10)
    border = Column(Integer, nullable=False, default=4)
    fill_color = Column(String(7), nullable=False, default="#000000")
    back_color = Column(String(7), nullable=False, default="#FFFFFF")

   
    utm_source = Column(String(64), nullable=True)
    utm_medium = Column(String(64), nullable=True)
    utm_campaign = Column(String(64), nullable=True)

   
    status = Column(String(16), nullable=False, default=QRCodeStatus.ACTIVE)
    scan_count = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_scanned_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ScanEvent(Base):
   

    __tablename__ = "scan_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    qr_id = Column(UUID, nullable=False, index=True)
    scanned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
