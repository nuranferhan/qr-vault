
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models import ScanEvent


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def record_scan(self, qr_id: uuid.UUID, ip: str, user_agent: str):
        event = ScanEvent(
            qr_id=qr_id,
            scanned_at=datetime.now(UTC),
            ip_address=ip,
            user_agent=user_agent,
        )
        self.db.add(event)


    def daily_scan_counts(self, qr_id: uuid.UUID) -> dict:
        events = (
            self.db.query(ScanEvent)
            .filter(ScanEvent.qr_id == str(qr_id))
            .all()
        )
        counts: dict[str, int] = defaultdict(int)
        for e in events:
            day = e.scanned_at.strftime("%Y-%m-%d") if e.scanned_at else "unknown"
            counts[day] += 1
        return dict(counts)