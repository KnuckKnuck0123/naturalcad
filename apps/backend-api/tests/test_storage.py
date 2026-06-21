from __future__ import annotations

import io

import pytest
from PIL import Image

from app.storage import StorageError, sanitize_image


def image_bytes(format_name: str = "PNG") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), "white").save(output, format=format_name)
    return output.getvalue()


def test_sanitizer_reencodes_and_hashes_image() -> None:
    result = sanitize_image(image_bytes(), "image/png")
    assert result.content_type == "image/jpeg"
    assert (result.width, result.height) == (32, 24)
    assert len(result.checksum_sha256) == 64


def test_sanitizer_rejects_mime_spoofing() -> None:
    with pytest.raises(StorageError, match="does not match"):
        sanitize_image(image_bytes("PNG"), "image/jpeg")


def test_sanitizer_rejects_malformed_input() -> None:
    with pytest.raises(StorageError, match="Malformed"):
        sanitize_image(b"not an image", "image/png")
