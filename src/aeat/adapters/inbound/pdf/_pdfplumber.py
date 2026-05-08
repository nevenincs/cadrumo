"""Shared pdfplumber-backed page-text extraction.

Backs the per-format ``extract_pages_text`` / ``extract_pages_text_from_bytes``
public surfaces (borrador, declaracion). Each per-format backend remains
the public entry point and is responsible for binding its own format
identity to the primitive: it injects the format-specific error class
plus the diagnostic phrasing that error messages must carry.

Justificante uses a categorically different shape (``str`` return,
content concatenation, no empty-page guard) and is intentionally NOT
backed by this primitive.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pdfplumber


def extract_pages_text_from_path(
    pdf_path: Path,
    *,
    error_class: type[Exception],
    not_found_label: str,
    pdf_label: str,
) -> tuple[str, ...]:
    """Read ``pdf_path`` page-by-page and return one stripped string per page.

    Args:
        pdf_path: Filesystem path of the PDF to read.
        error_class: Format-specific exception class to raise on every
            failure mode (missing file, pdfplumber failure, empty PDF).
            Each per-format backend injects its own (e.g.
            ``BorradorParseError``, ``DeclaracionParseError``) so callers
            can ``except`` by their familiar concrete type.
        not_found_label: Prefix the file-not-found message uses (e.g.
            ``"Modelo 100 PDF not found"``, ``"declaración PDF not found"``).
        pdf_label: Article-prefixed phrase the empty-PDF message uses
            (e.g. ``"PDF"``, ``"the PDF"``) so the diagnostic reads
            naturally per format.

    Returns:
        Tuple of stripped per-page text in page order. Empty pages
        preserve their slot as the empty string.

    Raises:
        ``error_class``: When the file does not exist, when pdfplumber
            cannot open it, or when every page is empty (suggesting a
            scan-only / XFA PDF without an embedded text layer).
    """

    if not pdf_path.is_file():
        raise error_class(f"{not_found_label}: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = tuple((page.extract_text() or "").strip() for page in pdf.pages)
    except Exception as exc:  # pragma: no cover — defensive; pdfplumber surface
        raise error_class(f"pdfplumber could not open {pdf_path}: {exc}") from exc

    if not any(pages):
        raise error_class(f"no text extracted from {pdf_path}; {pdf_label} may be scan-only or XFA")
    return pages


def extract_pages_text_from_bytes(
    pdf_bytes: bytes,
    *,
    error_class: type[Exception],
    pdf_label: str,
    source_label: str = "in-memory PDF",
) -> tuple[str, ...]:
    """Extract text from PDF bytes without materialising a plaintext file."""

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages = tuple((page.extract_text() or "").strip() for page in pdf.pages)
    except Exception as exc:  # pragma: no cover — defensive; pdfplumber surface
        raise error_class(f"pdfplumber could not open {source_label}: {exc}") from exc

    if not any(pages):
        raise error_class(f"no text extracted from {source_label}; {pdf_label} may be scan-only or XFA")
    return pages


__all__ = [
    "extract_pages_text_from_bytes",
    "extract_pages_text_from_path",
]
