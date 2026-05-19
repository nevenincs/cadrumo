"""Pdfplumber-backed page text extraction for declaración PDFs.

Wraps :mod:`pdfplumber` behind a single :func:`extract_pages_text`
function that returns the per-page text as a tuple. Errors from the
underlying library and pathological inputs (missing file, scan-only PDF
without an OCR layer) are translated into
:exc:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`.

A pypdfium2 fast-path is consulted before the canonical pdfplumber
primitive. The fast-path only commits its output when at least one
declaration-content canary (NIF row or declarant row) matches; this
keeps unrelated PDFs out of the fast lane and avoids cache poisoning.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from aeat.core.logging import get_logger

from ...pdf._pdfplumber import (
    extract_pages_text_from_bytes as _extract_pages_text_from_bytes_impl,
)
from ...pdf._pdfplumber import (
    extract_pages_text_with_fast_path as _extract_pages_text_with_fast_path_impl,
)
from .._errors import DeclaracionParseError

_logger = get_logger(__name__)
_TAX_ID_CANARY_RE = re.compile(
    r"\bNIF\s*[:\-]?\s*[A-Z0-9][A-Z0-9 .\-]{3,31}?(?=\s+(?:CSV|Fecha)\b|\s*$)",
    re.IGNORECASE,
)
_DECLARANT_ROW_CANARY_RE = re.compile(
    r"\b[XYZ]?[0-9]{7,8}[A-Z]\s+20[0-9]{2}\s+(?:[1-4]T|0A|[0-1][0-9])\b",
    re.IGNORECASE,
)


def extract_pages_text(pdf_path: Path) -> tuple[str, ...]:
    """Extract the text of each page in order.

    Args:
        pdf_path: Filesystem path of the PDF to read.

    Returns:
        Tuple with one stripped string per page in the source order.
        Empty pages preserve their slot as the empty string.

    Raises:
        :exc:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`:
            When ``pdf_path`` does not exist, when pdfplumber cannot open
            the file, or when every page is empty (suggesting a
            scan-only / XFA PDF without an embedded text layer).
    """
    return _extract_pages_text_with_fast_path_impl(
        pdf_path,
        error_class=DeclaracionParseError,
        not_found_label="declaración PDF not found",
        pdf_label="the PDF",
        fast_path_extractor=_extract_pages_text_with_pdfium,
    )


def _extract_pages_text_with_pdfium(pdf_path: Path) -> tuple[str, ...] | None:
    resolved = pdf_path.resolve()
    stat = resolved.stat()
    return _extract_pages_text_with_pdfium_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _extract_pages_text_with_pdfium_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> tuple[str, ...] | None:
    del byte_count, modified_ns
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(path)
        try:
            pages: list[str] = []
            for page in document:
                text_page = page.get_textpage()
                try:
                    pages.append((text_page.get_text_range() or "").strip())
                finally:
                    text_page.close()
                    page.close()
        finally:
            document.close()
    except Exception:
        _logger.debug("pypdfium2 failed to extract declaración PDF text from %s", path, exc_info=True)
        return None
    if not any(pages):
        return None
    text = "\n".join(pages)
    if not (_TAX_ID_CANARY_RE.search(text) or _DECLARANT_ROW_CANARY_RE.search(text)):
        return None
    return tuple(pages)


def extract_pages_text_from_bytes(pdf_bytes: bytes, *, source_label: str = "in-memory PDF") -> tuple[str, ...]:
    """Extract text from PDF bytes without materialising a plaintext file."""
    return _extract_pages_text_from_bytes_impl(
        pdf_bytes,
        error_class=DeclaracionParseError,
        pdf_label="the PDF",
        source_label=source_label,
    )
