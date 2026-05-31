
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_qrvault.db")
os.environ.setdefault("LOCALSTACK", "true")
os.environ.setdefault("LOCALSTACK_URL", "http://localhost:4566")
os.environ.setdefault("S3_BUCKET", "test-qr-vault-bucket")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from src.database import Base

TEST_DB_URL = "sqlite:///./test_qrvault.db"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def mock_s3():
    
    with patch("src.services.s3_service.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_bucket.return_value = {}
        mock_client.put_object.return_value = {}
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"\x89PNG\r\n\x1a\nfake-png-bytes")
        }
        mock_client.delete_object.return_value = {}
        mock_client.list_objects_v2.return_value = {"Contents": []}
        yield mock_client


@pytest.fixture()
def client(mock_s3):
    """FastAPI TestClient with mocked S3."""
    from src.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sample_qr_payload():
    return {
        "target_url": "https://example.com/test",
        "label": "Test QR",
        "error_correction": "H",
        "box_size": 10,
        "border": 4,
        "fill_color": "#000000",
        "back_color": "#FFFFFF",
    }


@pytest.fixture()
def created_qr(client, sample_qr_payload):
  
    resp = client.post("/qr", json=sample_qr_payload)
    assert resp.status_code == 201
    return resp.json()
