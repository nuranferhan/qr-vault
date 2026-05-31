import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Adım: Tüm environment variable'ları en başta güvenli moda alıyoruz
os.environ["DATABASE_URL"] = "sqlite:///./test_qrvault.db"
os.environ["LOCALSTACK"] = "true"
os.environ["LOCALSTACK_URL"] = "http://localhost:4566"
os.environ["S3_BUCKET"] = "test-qr-vault-bucket"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# NOT: Import'ları engine ezme mantığından önce yapıyoruz ki uygulama ayağa kalkabilsin
from src.database import Base
import src.database

TEST_DB_URL = "sqlite:///./test_qrvault.db"

@pytest.fixture(scope="session", autouse=True)
def engine():
    """Test oturumu boyunca kullanılacak SQLite engine."""
    eng = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    
    # 2. Adım: FastAPI'nin lifespan'de çağıracağı gerçek engine nesnesini 
    # test oturumu boyunca bizim test engine'imizle (eng) zorla değiştiriyoruz (Monkeypatching)
    src.database.engine = eng
    
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    
    # Test bittiğinde test veritabanı dosyasını temizle
    if os.path.exists("./test_qrvault.db"):
        try:
            os.remove("./test_qrvault.db")
        except:
            pass

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
def client(mock_s3, engine):
    """FastAPI TestClient'ı fixture'ların düzgün sırada kurulmasını garanti ederek başlatır."""
    from src.main import app
    with TestClient(app) as c:
        yield c

@pytest.fixture()
def created_qr(client, sample_qr_payload):
    response = client.post("/qr", json=sample_qr_payload)
    assert response.status_code == 201
    return response.json()

@pytest.fixture()
def sample_qr_payload():
    return {
        "target_url": "https://example.com/test",
        "label": "Test QR",
        "error_correction": "L",
        "box_size": 10,
        "border": 4,
        "fill_color": "black",
        "back_color": "white",
        "utm_source": "newsletter",
        "utm_medium": "email",
        "utm_campaign": "spring_2026"
    }
