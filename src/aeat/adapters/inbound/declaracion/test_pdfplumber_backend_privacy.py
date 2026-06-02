"""Privacy tests for declaración pdfplumber backend diagnostics."""

from __future__ import annotations

import logging

import pytest

from ._parsers._pdfplumber_backend import _extract_pages_text_with_pdfium_cached

pytestmark = [pytest.mark.unit, pytest.mark.domain_inbound]


def test_pdfium_fallback_debug_log_does_not_expose_source_path(caplog: pytest.LogCaptureFixture) -> None:
    sensitive_path = "C:/private/12345678Z-declaracion.pdf"
    _extract_pages_text_with_pdfium_cached.cache_clear()

    with caplog.at_level(logging.DEBUG, logger="aeat.adapters.inbound.declaracion._parsers._pdfplumber_backend"):
        result = _extract_pages_text_with_pdfium_cached(sensitive_path, 1, 1)

    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert result is None
    assert sensitive_path not in rendered_logs
    assert "12345678Z-declaracion.pdf" not in rendered_logs
    assert "<input-pdf>" in rendered_logs
