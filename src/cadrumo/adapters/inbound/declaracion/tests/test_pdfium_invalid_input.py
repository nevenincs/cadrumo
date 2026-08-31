from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from .._parsers.pdfplumber_backend import _extract_pages_text_with_pdfium_cached

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_non_pdf_bytes_return_none(tmp_path: Path) -> None:
    bad_pdf = tmp_path / "not_a_pdf.pdf"
    payload = b"NOT A PDF"
    bad_pdf.write_bytes(payload)
    stat = bad_pdf.stat()

    result = _extract_pages_text_with_pdfium_cached(
        str(bad_pdf),
        stat.st_size,
        stat.st_mtime_ns,
        hashlib.sha256(payload).hexdigest(),
    )

    assert result is None
