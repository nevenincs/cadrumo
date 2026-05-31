"""Pdfplumber-backed page text extraction for Modelo 100 PDFs.

Implements the single :func:`extract_pages_text` primitive that the
borrador extractors consume. The function isolates the pdfplumber
dependency so other backends (e.g. pdfminer, OCR) can be swapped in
without touching extractor code.
"""

from __future__ import annotations

from pathlib import Path

from ...pdf._pdfplumber import extract_pages_text_from_path
from .._errors import BorradorParseError


def extract_pages_text(pdf_path: Path) -> tuple[str, ...]:
    """Extract the text of each page in order.

    Args:
        pdf_path: Path to the PDF whose pages will be read.

    Returns:
        A tuple of stripped per-page text strings, in page order.
    """
    return extract_pages_text_from_path(
        pdf_path,
        error_class=BorradorParseError,
        not_found_label="Modelo 100 PDF not found",
        pdf_label="PDF",
    )
