"""Pdfplumber-backed page text extraction for Modelo 100 PDFs.

Implements the single :func:`extract_pages_text` primitive that the
borrador extractors consume. The function isolates the pdfplumber
dependency so other backends (e.g. pdfminer, OCR) can be swapped in
without touching extractor code.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from .._errors import BorradorParseError


def extract_pages_text(pdf_path: Path) -> tuple[str, ...]:
    """Extract the text of each page in order.

    Args:
        pdf_path: Path to the PDF whose pages will be read.

    Returns:
        A tuple of stripped per-page text strings, in page order.

    Raises:
        :exc:`aeat.adapters.inbound.borrador._errors.BorradorParseError`:
            When pdfplumber cannot open the file, or when every page is
            empty (suggesting a scan-only or XFA PDF).
    """
    if not pdf_path.is_file():
        raise BorradorParseError(f"Modelo 100 PDF not found: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = tuple((page.extract_text() or "").strip() for page in pdf.pages)
    except Exception as exc:  # pragma: no cover — defensive; pdfplumber surface
        raise BorradorParseError(f"pdfplumber could not open {pdf_path}: {exc}") from exc

    if not any(pages):
        raise BorradorParseError(f"no text extracted from {pdf_path}; PDF may be scan-only or XFA")
    return pages
