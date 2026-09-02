"""Pdfplumber-backed page text extraction for declaración PDFs.

Wraps :mod:`pdfplumber` behind
:func:`~adapters.inbound.declaracion._parsers._pdfplumber_backend.extract_pages_text`
and
:func:`~adapters.inbound.declaracion._parsers._pdfplumber_backend.extract_pages_text_from_bytes`,
which return one stripped text string per page. Errors from the underlying
library and pathological inputs (missing file, scan-only PDF without an OCR
layer) are translated into
:class:`~adapters.inbound.declaracion.errors.DeclaracionParseError`.

A pypdfium2 fast path is consulted before the canonical pdfplumber primitive.
The fast path only commits its output when at least one declaration-content
canary (NIF row or declarant row) matches; this keeps unrelated PDFs out of the
fast lane and avoids cache poisoning. The bytes route follows the same canary
discipline without writing decrypted content to disk.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .....core.hashing import sha256_hex
from .....core.logging import get_logger
from .....core.paths import path_stat_fingerprint
from ...pdf.page_text_extraction import (
    extract_pages_text_from_bytes as _extract_pages_text_from_bytes_impl,
)
from ...pdf.page_text_extraction import (
    extract_pages_text_with_fast_path as _extract_pages_text_with_fast_path_impl,
)
from ...pdf.redaction import INPUT_PDF_SOURCE_LABEL as _INPUT_PDF_SOURCE_LABEL
from ...pdf.source_provenance import sha256_file
from ..errors import DeclaracionParseError

_logger = get_logger(__name__)
_TAX_ID_CANARY_RE = re.compile(
    r"\bNIF\s*[:\-]?\s*[A-Z0-9][A-Z0-9 .\-]{3,31}?(?=\s+(?:CSV|Fecha)\b|\s*$)",
    re.IGNORECASE,
)
_DECLARANT_ROW_CANARY_RE = re.compile(
    r"\b[XYZ]?[0-9]{7,8}[A-Z]\s+20[0-9]{2}\s+(?:[1-4]T|0A|[0-1][0-9])\b",
    re.IGNORECASE,
)


def _pdfium_pages_text(source: str | bytes, *, source_label: str) -> tuple[str, ...] | None:
    """Extract per-page text via pypdfium2, or ``None`` when unavailable.

    Shared document→pages core behind the path and bytes fast paths: import
    pypdfium2, open the document, and walk each page/textpage under
    ``try/finally``. Returns one stripped string per page, or ``None`` when
    pypdfium2 is missing or the document cannot be opened/read. ``source_label``
    feeds the debug-log message so the path (``"<input-pdf>"``) and bytes
    (``"bytes"``) routes stay distinguishable. Callers apply their own canary
    validation and caching.
    """
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(source)
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
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        _logger.debug(
            "pypdfium2 failed to extract declaración PDF text from %s: %s",
            source_label,
            type(exc).__name__,
            exc_info=True,
        )
        return None
    return tuple(pages)


def extract_pages_text(pdf_path: Path) -> tuple[str, ...]:
    """Extract the text of each page in order.

    The declaration backend first tries the pypdfium2 fast path and falls back
    to the shared pdfplumber primitive when the fast path is unavailable or its
    declaration canaries do not match.

    Args:
        pdf_path: Filesystem path of the PDF to read.

    Returns:
        Tuple with one stripped string per page in the source order.
        Empty pages preserve their slot as the empty string.

    Raises:
        DeclaracionParseError: When the PDF is missing or no extractable text
            can be read from any page.
    """
    return _extract_pages_text_with_fast_path_impl(
        pdf_path,
        error_class=DeclaracionParseError,
        not_found_label="declaración PDF not found",
        pdf_label="the PDF",
        fast_path_extractor=_extract_pages_text_with_pdfium,
    )


def _extract_pages_text_with_pdfium(pdf_path: Path) -> tuple[str, ...] | None:
    """Run the cached pypdfium2 path extraction for one filesystem PDF."""
    resolved = pdf_path.resolve()
    fingerprint = path_stat_fingerprint(resolved)
    content_digest = sha256_file(resolved)
    return _extract_pages_text_with_pdfium_cached(*fingerprint, content_digest)


@lru_cache(maxsize=256)
def _extract_pages_text_with_pdfium_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
    content_digest: str = "",
) -> tuple[str, ...] | None:
    """Return canary-validated PDFium text for one content-bound file revision."""
    # All three discriminators are intentionally part of the lru_cache key.
    # Size and mtime retain the cheap stable-file identity, while the digest is
    # load-bearing when a replacement preserves both metadata values.
    del byte_count, modified_ns, content_digest
    pages = _pdfium_pages_text(path, source_label=_INPUT_PDF_SOURCE_LABEL)
    if pages is None or not any(pages):
        return None
    text = "\n".join(pages)
    if not (_TAX_ID_CANARY_RE.search(text) or _DECLARANT_ROW_CANARY_RE.search(text)):
        return None
    return pages


_PDFIUM_BYTES_CACHE: dict[str, tuple[str, ...]] = {}


def _extract_pages_text_with_pdfium_from_bytes(pdf_bytes: bytes) -> tuple[str, ...] | None:
    """Return canary-validated pypdfium2 page text for in-memory PDF bytes."""
    digest = sha256_hex(pdf_bytes)
    if digest in _PDFIUM_BYTES_CACHE:
        return _PDFIUM_BYTES_CACHE[digest]

    pages = _pdfium_pages_text(pdf_bytes, source_label="bytes")
    if pages is None or not any(pages):
        return None
    text = "\n".join(pages)
    if not (_TAX_ID_CANARY_RE.search(text) or _DECLARANT_ROW_CANARY_RE.search(text)):
        return None

    result = pages
    if len(_PDFIUM_BYTES_CACHE) >= 256:
        first_key = next(iter(_PDFIUM_BYTES_CACHE))
        _PDFIUM_BYTES_CACHE.pop(first_key, None)
    _PDFIUM_BYTES_CACHE[digest] = result
    return result


def extract_pages_text_from_bytes(pdf_bytes: bytes, *, source_label: str = "in-memory PDF") -> tuple[str, ...]:
    """Extract text from PDF bytes without materialising a plaintext file.

    The bytes path mirrors ``extract_pages_text``: pypdfium2 gets the first
    chance to return canary-validated page text, then the shared pdfplumber
    bytes primitive handles the fallback while keeping the caller's decrypted
    bytes in memory.

    Raises:
        DeclaracionParseError: When no extractable text can be read from the
            supplied PDF bytes.
    """
    fast_pages = _extract_pages_text_with_pdfium_from_bytes(pdf_bytes)
    if fast_pages is not None:
        return fast_pages
    return _extract_pages_text_from_bytes_impl(
        pdf_bytes,
        error_class=DeclaracionParseError,
        pdf_label="the PDF",
        source_label=source_label,
    )
