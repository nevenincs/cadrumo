"""Pdfplumber-backed page text extraction for Modelo 100 PDFs.

Implements the single
:func:`~adapters.inbound.borrador._parsers._pdfplumber_backend.extract_pages_text`
primitive that the borrador extractors consume. The function isolates the
pdfplumber dependency so other backends (e.g. pdfminer, OCR) can be swapped in
without touching extractor code.

The backend delegates to
:func:`~adapters.inbound.pdf.page_text_extraction.extract_pages_text_from_path` and
wraps failures in :class:`~adapters.inbound.borrador.BorradorParseError`
so callers stay inside the borrador parse-error family.
"""

from __future__ import annotations

from pathlib import Path

from ...pdf import extract_pages_text_from_path
from ..errors import BorradorParseError


def extract_pages_text(pdf_path: Path) -> tuple[str, ...]:
    """Extract stripped text from each Modelo 100 PDF page in order.

    Args:
        pdf_path: Path to the PDF whose pages will be read.

    Returns:
        A tuple of stripped per-page text strings, in page order.

    Raises:
        BorradorParseError: When the source path is missing or the PDF backend
            cannot extract page text.
    """
    return extract_pages_text_from_path(
        pdf_path,
        error_class=BorradorParseError,
        not_found_label="Modelo 100 PDF not found",
        pdf_label="PDF",
    )
