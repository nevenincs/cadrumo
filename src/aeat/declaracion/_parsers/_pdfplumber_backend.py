"""Pdfplumber-backed page text extraction for declaración PDFs."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from .._errors import DeclaracionParseError


def extract_pages_text(pdf_path: Path) -> tuple[str, ...]:
    """Extract the text of each page in order.

    Raises:
        DeclaracionParseError: When pdfplumber cannot open the file
            or every page is empty (suggesting a scan-only PDF).
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
