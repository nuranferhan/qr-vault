
import uuid
from datetime import UTC, datetime, timedelta

import factory
from factory import Faker, LazyAttribute, LazyFunction
from factory.alchemy import SQLAlchemyModelFactory

from src.models import QRCode, QRCodeStatus, ScanEvent


class QRCodeFactory(SQLAlchemyModelFactory):
    class Meta:
        model = QRCode
        sqlalchemy_session = None 
        sqlalchemy_session_persistence = "commit"

    id = LazyFunction(uuid.uuid4)
    short_code = LazyFunction(lambda: factory.Faker("bothify", text="????????").generate())
    target_url = Faker("url")
    label = Faker("catch_phrase")
    s3_key = LazyAttribute(lambda o: f"qr/{o.short_code}.png")
    error_correction = "H"
    box_size = 10
    border = 4
    fill_color = "#000000"
    back_color = "#FFFFFF"
    utm_source = None
    utm_medium = None
    utm_campaign = None
    status = QRCodeStatus.ACTIVE
    scan_count = 0
    expires_at = None
    last_scanned_at = None
    created_at = LazyFunction(lambda: datetime.now(UTC))
    updated_at = LazyFunction(lambda: datetime.now(UTC))


class ActiveQRCodeFactory(QRCodeFactory):
    status = QRCodeStatus.ACTIVE
    scan_count = factory.Faker("random_int", min=0, max=500)


class ExpiredQRCodeFactory(QRCodeFactory):
    status = QRCodeStatus.EXPIRED
    expires_at = LazyFunction(lambda: datetime.now(UTC) - timedelta(days=1))


class QRCodeWithUTMFactory(QRCodeFactory):
    utm_source = Faker("word")
    utm_medium = factory.Iterator(["email", "social", "cpc", "organic"])
    utm_campaign = Faker("slug")


class ScanEventFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ScanEvent
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    qr_id = LazyFunction(uuid.uuid4)
    scanned_at = LazyFunction(lambda: datetime.now(UTC))
    ip_address = Faker("ipv4")
    user_agent = Faker("user_agent")
