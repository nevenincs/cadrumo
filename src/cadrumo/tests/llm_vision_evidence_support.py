"""Shared support for local-vision evidence tests."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from ..core.type_adapters import STR_KEYED_MAPPING_ADAPTER


def json_object(value: object) -> dict[str, object]:
    """Narrow one decoded JSON value to a string-keyed object for typed subscripting."""
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


def json_array(value: object) -> list[object]:
    assert isinstance(value, list)
    return list(value)


def png_image() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()
