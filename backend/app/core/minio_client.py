import urllib3
from minio import Minio

from app.core.config import settings

retries = urllib3.util.Retry(total=1, backoff_factor=0.1, connect=1, read=1, status=1)
http_client = urllib3.PoolManager(timeout=urllib3.Timeout(connect=2.0, read=5.0), retries=retries)

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
    http_client=http_client,
)


def ensure_bucket(bucket: str = settings.minio_bucket) -> None:
    """Create the artifacts bucket if it does not exist."""
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)
