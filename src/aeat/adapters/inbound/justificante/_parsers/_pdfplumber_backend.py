"""pdfplumber-backed text extraction for justificante PDFs.

Implements the :data:`aeat.domain.justificante._schema.JustificanteParserBackend.PDFPLUMBER`
branch of the parser dispatch in
:mod:`aeat.adapters.inbound.justificante._parsers`. Concatenates the
``page.extract_text()`` output of every non-empty page; layout-sensitive
parsing is left to the regex extractor downstream.
"""

from __future__ import annotations

from pathlib import Path

from .....domain.justificante._errors import JustificanteParseError
from ...pdf._pdfplumber import extract_pages_text_concatenated, extract_pages_text_from_bytes


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Return the concatenated text of ``pdf_path`` using pdfplumber.

    Args:
        pdf_path: Path to the PDF to open.

    Returns:
        A single string with every page's ``extract_text`` result joined by
        newlines. Empty pages are skipped.
    """
    return extract_pages_text_concatenated(pdf_path, error_class=JustificanteParseError)


def extract_text_pdfplumber_bytes(pdf_bytes: bytes) -> str:
    """Return concatenated text from in-memory PDF bytes using pdfplumber."""
    return "\n".join(
        extract_pages_text_from_bytes(
            pdf_bytes,
            error_class=JustificanteParseError,
            pdf_label="PDF",
            source_label="in-memory justificante PDF",
        )
    )
