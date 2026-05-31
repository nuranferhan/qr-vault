import contextlib
import os

import boto3
from botocore.exceptions import ClientError

BUCKET_NAME = os.getenv("S3_BUCKET", "qr-vault-bucket")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
LOCALSTACK = os.getenv("LOCALSTACK", "true").lower() == "true"
LOCALSTACK_URL = os.getenv("LOCALSTACK_URL", "http://localhost:4566")


def _make_client():
    kwargs = dict(
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )
    if LOCALSTACK:
        kwargs["endpoint_url"] = LOCALSTACK_URL
    return boto3.client("s3", **kwargs)


class S3Service:
    def __init__(self):
        self.client = _make_client()
        self.bucket = BUCKET_NAME

    def ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                if AWS_REGION == "us-east-1":
                    self.client.create_bucket(Bucket=self.bucket)
                else:
                    self.client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
                    )
            else:
                raise

    def upload_png(self, png_bytes: bytes, key: str) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=png_bytes,
            ContentType="image/png",
        )
        return key

    def download_png(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def delete_object(self, key: str):
        with contextlib.suppress(ClientError):
            self.client.delete_object(Bucket=self.bucket, Key=key)

    def get_public_url(self, key: str) -> str:
        if LOCALSTACK:
            return f"{LOCALSTACK_URL}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.{AWS_REGION}.amazonaws.com/{key}"

    def list_objects(self, prefix: str = "qr/") -> list[str]:
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj["Key"] for obj in resp.get("Contents", [])]
