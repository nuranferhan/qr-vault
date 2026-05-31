
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch  # noqa: F401

pytest.importorskip("testcontainers", reason="testcontainers not installed")

try:
    from testcontainers.postgres import PostgresContainer
    TESTCONTAINERS_AVAILABLE = True
except Exception:
    TESTCONTAINERS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not TESTCONTAINERS_AVAILABLE,
    reason="testcontainers.postgres not available",
)


@pytest.fixture(scope="module")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def pg_engine(postgres_container):
    from src.database import Base
    url = postgres_container.get_connection_url()
    eng = create_engine(url)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def pg_client(postgres_container):
    db_url = postgres_container.get_connection_url()
    with patch("src.database.DATABASE_URL", db_url), patch(
        "src.services.s3_service.boto3"
    ) as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_bucket.return_value = {}
        mock_client.put_object.return_value = {}
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"\x89PNGfake")
        }
        mock_client.delete_object.return_value = {}
        mock_client.list_objects_v2.return_value = {"Contents": []}

        import src.database as db_mod
        db_mod.engine = create_engine(db_url)
        db_mod.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=db_mod.engine
        )
        from src.database import Base
        Base.metadata.create_all(bind=db_mod.engine)

        from src.main import app
        with TestClient(app) as c:
            yield c


class TestIntegrationQRPersistence:
    def test_created_qr_is_retrievable(self, pg_client):
        resp = pg_client.post("/qr", json={"target_url": "https://integration-test.com"})
        assert resp.status_code == 201
        code = resp.json()["short_code"]
        get_resp = pg_client.get(f"/qr/{code}")
        assert get_resp.status_code == 200
        assert get_resp.json()["short_code"] == code

    def test_scan_count_persisted_across_requests(self, pg_client):
        r = pg_client.post("/qr", json={"target_url": "https://scan-persist.com"})
        code = r.json()["short_code"]
        pg_client.get(f"/qr/{code}/redirect", follow_redirects=False)
        pg_client.get(f"/qr/{code}/redirect", follow_redirects=False)
        updated = pg_client.get(f"/qr/{code}").json()
        assert updated["scan_count"] == 2

    def test_unique_short_codes_on_batch(self, pg_client):
        items = [{"target_url": f"https://batch-{i}.com"} for i in range(5)]
        resp = pg_client.post("/qr/batch", json={"items": items})
        assert resp.status_code == 201
        codes = [item["short_code"] for item in resp.json()]
        assert len(set(codes)) == 5

    def test_delete_removes_from_db(self, pg_client):
        r = pg_client.post("/qr", json={"target_url": "https://to-delete.com"})
        code = r.json()["short_code"]
        pg_client.delete(f"/qr/{code}")
        assert pg_client.get(f"/qr/{code}").status_code == 404

    def test_list_paginates_correctly(self, pg_client):
        for i in range(10):
            pg_client.post("/qr", json={"target_url": f"https://page-{i}.com"})
        page1 = pg_client.get("/qr?skip=0&limit=5").json()
        page2 = pg_client.get("/qr?skip=5&limit=5").json()
        codes1 = {item["short_code"] for item in page1}
        codes2 = {item["short_code"] for item in page2}
        assert codes1.isdisjoint(codes2)

    def test_utm_params_stored_and_returned(self, pg_client):
        r = pg_client.post(
            "/qr",
            json={
                "target_url": "https://utm-integration.com",
                "utm_source": "test_source",
                "utm_medium": "email",
            },
        )
        assert r.status_code == 201