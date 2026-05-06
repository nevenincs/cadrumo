"""Pdfplumber-backed page text extraction for declaración PDFs.

Wraps :mod:`pdfplumber` behind a single
:func:`extract_pages_text` function that returns the per-page text as a
tuple. Errors from the underlying library and pathological inputs
(missing file, scan-only PDF without an OCR layer) are translated into
:exc:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pdfplumber

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
    if not pdf_path.is_file():
        raise DeclaracionParseError(f"declaración PDF not found: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = tuple((page.extract_text() or "").strip() for page in pdf.pages)
    except Exception as exc:  # pragma: no cover — defensive; pdfplumber surface
        raise DeclaracionParseError(f"pdfplumber could not open {pdf_path}: {exc}") from exc

    if not any(pages):
        raise DeclaracionParseError(f"no text extracted from {pdf_path}; the PDF may be scan-only or XFA")
    return pages


def extract_pages_text_from_bytes(pdf_bytes: bytes, *, source_label: str = "in-memory PDF") -> tuple[str, ...]:
    """Extract text from PDF bytes without materialising a plaintext file."""

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages = tuple((page.extract_text() or "").strip() for page in pdf.pages)
    except Exception as exc:  # pragma: no cover - defensive; pdfplumber surface
        raise DeclaracionParseError(f"pdfplumber could not open {source_label}: {exc}") from exc

    if not any(pages):
        raise DeclaracionParseError(f"no text extracted from {source_label}; the PDF may be scan-only or XFA")
    return pages
