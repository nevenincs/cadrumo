"""Privacy tests for declaración pdfplumber backend diagnostics."""

from __future__ import annotations

import logging

import pytest

from .._parsers.pdfplumber_backend import _extract_pages_text_with_pdfium_cached

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_pdfium_fallback_debug_log_does_not_expose_source_path(caplog: pytest.LogCaptureFixture) -> None:
    sensitive_path = "C:/private/12345678Z-declaracion.pdf"
    _extract_pages_text_with_pdfium_cached.cache_clear()

    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.inbound.declaracion.parsers._pdfplumber_backend"):
        result = _extract_pages_text_with_pdfium_cached(sensitive_path, 1, 1, "0" * 64)

    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert result is None
    assert sensitive_path not in rendered_logs
    assert "12345678Z-declaracion.pdf" not in rendered_logs
    assert "<input-pdf>" in rendered_logs


def test_extract_pages_text_from_bytes_fast_path() -> None:
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from .._parsers.pdfplumber_backend import _extract_pages_text_with_pdfium_from_bytes

    # 1. Canary matches -> returns page texts
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.drawString(100, 100, "NIF: 12345678Z 2024 1T")
    pdf.save()
    pdf_bytes = buf.getvalue()

    result = _extract_pages_text_with_pdfium_from_bytes(pdf_bytes)
    assert result is not None
    assert len(result) == 1
    assert "NIF: 12345678Z" in result[0]

    # 2. Canary does not match -> returns None (fast path bypass)
    buf2 = BytesIO()
    pdf2 = canvas.Canvas(buf2, pagesize=A4)
    pdf2.drawString(100, 100, "Unrelated text")
    pdf2.save()
    pdf_bytes2 = buf2.getvalue()

    result2 = _extract_pages_text_with_pdfium_from_bytes(pdf_bytes2)
    assert result2 is None


def test_extract_pages_text_from_bytes_fast_path_cache() -> None:
    from hashlib import sha256
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from .._parsers.pdfplumber_backend import _PDFIUM_BYTES_CACHE, _extract_pages_text_with_pdfium_from_bytes

    _PDFIUM_BYTES_CACHE.clear()

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.drawString(100, 100, "NIF: 12345678Z 2024 1T")
    pdf.save()
    pdf_bytes = buf.getvalue()
    digest = sha256(pdf_bytes).hexdigest()

    result1 = _extract_pages_text_with_pdfium_from_bytes(pdf_bytes)
    assert result1 is not None
    assert digest in _PDFIUM_BYTES_CACHE

    # Mutate cache entry directly to verify cache hit
    _PDFIUM_BYTES_CACHE[digest] = ("cached_value",)
    result2 = _extract_pages_text_with_pdfium_from_bytes(pdf_bytes)
    assert result2 == ("cached_value",)

    # Clean cache and verify it runs again
    _PDFIUM_BYTES_CACHE.clear()
    result3 = _extract_pages_text_with_pdfium_from_bytes(pdf_bytes)
    assert result3 == result1
