from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("LOCALSTACK", "true")
    monkeypatch.setenv("LOCALSTACK_URL", "http://localhost:4566")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")


def _make_service_with_mock():
    with patch("src.services.s3_service.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        import src.services.s3_service
        from src.services.s3_service import S3Service

        src.services.s3_service.BUCKET_NAME = "test-bucket"

        svc = S3Service()
        svc.client = mock_client
        return svc, mock_client


class TestS3ServiceEnsureBucket:
    def test_skips_creation_if_bucket_exists(self):
        svc, client = _make_service_with_mock()
        client.head_bucket.return_value = {}
        svc.ensure_bucket()
        client.create_bucket.assert_not_called()

    def test_creates_bucket_on_404(self):
        svc, client = _make_service_with_mock()
        error = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket"
        )
        client.head_bucket.side_effect = error
        svc.ensure_bucket()
        client.create_bucket.assert_called_once_with(Bucket="test-bucket")


class TestS3ServiceUpload:
    def test_upload_calls_put_object(self):
        svc, client = _make_service_with_mock()
        client.put_object.return_value = {}
        key = svc.upload_png(b"\x89PNGfake", "qr/abc.png")
        assert key == "qr/abc.png"
        client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="qr/abc.png",
            Body=b"\x89PNGfake",
            ContentType="image/png",
        )

    def test_upload_returns_key(self):
        svc, client = _make_service_with_mock()
        client.put_object.return_value = {}
        result = svc.upload_png(b"data", "qr/xyz.png")
        assert result == "qr/xyz.png"


class TestS3ServiceDownload:
    def test_download_returns_bytes(self):
        svc, client = _make_service_with_mock()
        client.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"\x89PNG")
        }
        result = svc.download_png("qr/abc.png")
        assert result == b"\x89PNG"


class TestS3ServiceDelete:
    def test_delete_calls_delete_object(self):
        svc, client = _make_service_with_mock()
        client.delete_object.return_value = {}
        svc.delete_object("qr/abc.png")
        client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="qr/abc.png"
        )

    def test_delete_swallows_client_error(self):
        svc, client = _make_service_with_mock()
        client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": ""}}, "DeleteObject"
        )
        svc.delete_object("qr/nonexistent.png")


class TestS3ServicePublicURL:
    def test_localstack_url(self):
        svc, _ = _make_service_with_mock()
        url = svc.get_public_url("qr/abc.png")
        assert "localstack" in url or "localhost" in url
        assert "qr/abc.png" in url

    def test_url_contains_key(self):
        svc, _ = _make_service_with_mock()
        url = svc.get_public_url("qr/mycode.png")
        assert "mycode.png" in url
