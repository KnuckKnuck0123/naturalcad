from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import settings

Image.MAX_IMAGE_PIXELS = 25_000_000


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class SanitizedImage:
    data: bytes
    content_type: str
    width: int
    height: int
    checksum_sha256: str


class SupabaseImageStorage:
    def __init__(self) -> None:
        self.base = settings.supabase_url.rstrip("/")
        self.key = settings.supabase_service_role_key
        self.bucket = settings.source_image_bucket

    @property
    def configured(self) -> bool:
        return bool(self.base and self.key)

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": content_type}

    def create_signed_upload(self, storage_key: str) -> str:
        endpoint = f"{self.base}/storage/v1/object/upload/sign/{self.bucket}/{quote(storage_key, safe='/')}"
        with httpx.Client(timeout=20.0) as client:
            response = client.post(endpoint, headers=self._headers(), json={})
        if response.status_code >= 400:
            raise StorageError(f"Unable to reserve image upload ({response.status_code})")
        value = response.json().get("url") or response.json().get("signedURL") or response.json().get("signedUrl")
        if not value:
            raise StorageError("Storage did not return a signed upload URL")
        return value if value.startswith("http") else f"{self.base}/storage/v1{value}"

    def download(self, storage_key: str) -> bytes:
        endpoint = f"{self.base}/storage/v1/object/{self.bucket}/{quote(storage_key, safe='/')}"
        with httpx.Client(timeout=30.0) as client:
            response = client.get(endpoint, headers=self._headers("application/octet-stream"))
        if response.status_code >= 400:
            raise StorageError("Uploaded image was not found")
        return response.content

    def upload(self, storage_key: str, data: bytes, content_type: str) -> None:
        endpoint = f"{self.base}/storage/v1/object/{self.bucket}/{quote(storage_key, safe='/')}"
        headers = self._headers(content_type)
        headers["x-upsert"] = "true"
        with httpx.Client(timeout=30.0) as client:
            response = client.post(endpoint, headers=headers, content=data)
        if response.status_code >= 400:
            raise StorageError("Unable to store sanitized image")

    def delete(self, storage_keys: list[str]) -> None:
        if not storage_keys:
            return
        endpoint = f"{self.base}/storage/v1/object/{self.bucket}"
        with httpx.Client(timeout=20.0) as client:
            response = client.request("DELETE", endpoint, headers=self._headers(), json={"prefixes": storage_keys})
        if response.status_code >= 400:
            raise StorageError("Unable to delete image")

    def create_signed_read(self, storage_key: str, expires_in: int = 600) -> str:
        endpoint = f"{self.base}/storage/v1/object/sign/{self.bucket}/{quote(storage_key, safe='/')}"
        with httpx.Client(timeout=20.0) as client:
            response = client.post(endpoint, headers=self._headers(), json={"expiresIn": expires_in})
        if response.status_code >= 400:
            raise StorageError("Unable to create image preview")
        value = response.json().get("signedURL") or response.json().get("signedUrl")
        if not value:
            raise StorageError("Storage did not return a preview URL")
        return value if value.startswith("http") else f"{self.base}/storage/v1{value}"


def sanitize_image(data: bytes, declared_content_type: str) -> SanitizedImage:
    if len(data) > 8 * 1024 * 1024:
        raise StorageError("Image exceeds the 8 MB limit")
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise StorageError("Unsupported image encoding")
            expected = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[source.format]
            if expected != declared_content_type:
                raise StorageError("Image content does not match its declared type")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            clean = output.getvalue()
            return SanitizedImage(
                data=clean, content_type="image/jpeg", width=image.width, height=image.height,
                checksum_sha256=hashlib.sha256(clean).hexdigest(),
            )
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise StorageError("Malformed or unsafe image") from exc
