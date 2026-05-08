"""Pdfplumber-backed page text extraction for declaración PDFs.

Wraps :mod:`pdfplumber` behind a single
:func:`extract_pages_text` function that returns the per-page text as a
tuple. Errors from the underlying library and pathological inputs
(missing file, scan-only PDF without an OCR layer) are translated into
:exc:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`.
"""

from __future__ import annotations

from pathlib import Path

from ...pdf._pdfplumber import (
    extract_pages_text_from_bytes as _extract_pages_text_from_bytes_impl,
)
from ...pdf._pdfplumber import (
    extract_pages_text_from_path as _extract_pages_text_from_path_impl,
)
from .._errors import DeclaracionParseError


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
    return _extract_pages_text_from_path_impl(
        pdf_path,
        error_class=DeclaracionParseError,
        not_found_label="declaración PDF not found",
        pdf_label="the PDF",
    )


def extract_pages_text_from_bytes(pdf_bytes: bytes, *, source_label: str = "in-memory PDF") -> tuple[str, ...]:
    """Extract text from PDF bytes without materialising a plaintext file."""
    return _extract_pages_text_from_bytes_impl(
        pdf_bytes,
        error_class=DeclaracionParseError,
        pdf_label="the PDF",
        source_label=source_label,
    )
