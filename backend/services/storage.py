"""Storage de imagenes. Supabase Storage (gratis) por defecto; S3/R2 si esta configurado."""
import mimetypes
from functools import lru_cache

import httpx

import config


# ---------- descarga ----------

def download(url: str) -> tuple[bytes, str]:
    with httpx.Client(timeout=120, follow_redirects=True) as http:
        response = http.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type") or mimetypes.guess_type(url)[0] or "image/jpeg"
        return response.content, content_type.split(";")[0]


# ---------- Supabase Storage ----------

@lru_cache(maxsize=1)
def _supabase():
    from supabase import create_client

    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


def ensure_supabase_bucket() -> None:
    storage = _supabase().storage
    names = {b.name for b in storage.list_buckets()}
    if config.SUPABASE_BUCKET not in names:
        storage.create_bucket(config.SUPABASE_BUCKET, options={"public": True})


def _supabase_upload(key: str, data: bytes, content_type: str) -> str:
    bucket = _supabase().storage.from_(config.SUPABASE_BUCKET)
    bucket.upload(path=key, file=data, file_options={"content-type": content_type, "upsert": "true"})
    return bucket.get_public_url(key).rstrip("?")


# ---------- S3 / R2 ----------

@lru_cache(maxsize=1)
def _s3():
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=config.S3_ENDPOINT_URL,
        aws_access_key_id=config.S3_ACCESS_KEY_ID,
        aws_secret_access_key=config.S3_SECRET_ACCESS_KEY,
        region_name=config.S3_REGION,
        config=BotoConfig(signature_version="s3v4"),
    )


def _s3_upload(key: str, data: bytes, content_type: str) -> str:
    _s3().put_object(Bucket=config.S3_BUCKET, Key=key, Body=data, ContentType=content_type)
    return f"{config.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"


# ---------- API publica ----------

def upload_bytes(key: str, data: bytes, content_type: str = "image/jpeg") -> str | None:
    """Sube bytes y devuelve URL publica. None si no hay storage configurado."""
    if config.s3_enabled():
        return _s3_upload(key, data, content_type)
    if config.db_enabled():
        return _supabase_upload(key, data, content_type)
    return None


def mirror_url(key_prefix: str, source_url: str) -> str:
    """Copia una imagen remota al storage. Sin storage, devuelve la URL original."""
    if not config.storage_enabled():
        return source_url
    data, content_type = download(source_url)
    extension = "png" if "png" in content_type else "jpg"
    return upload_bytes(f"{key_prefix}.{extension}", data, content_type) or source_url
