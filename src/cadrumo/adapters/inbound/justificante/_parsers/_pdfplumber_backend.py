"""pdfplumber-backed text extraction for justificante PDFs.

Implements the ``PDFPLUMBER`` branch of
:class:`~domain.justificante.JustificanteParserBackend` for the
:mod:`adapters.inbound.justificante._parsers` dispatch layer.
Concatenates the ``page.extract_text()`` output of every non-empty page;
layout-sensitive parsing is left to the regex extractor downstream.

Both path and bytes helpers translate extraction failures into
:class:`~domain.justificante.JustificanteParseError`. The bytes helper
uses the shared inbound PDF bytes primitive so secure-storage captures can be
parsed without plaintext temporary files.
"""

from __future__ import annotations

from pathlib import Path

from .....domain.justificante import JustificanteParseError
from ...pdf.page_text_extraction import (
    extract_pages_text_concatenated,
    extract_pages_text_from_bytes,
)


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Return the concatenated text of ``pdf_path`` using pdfplumber.

    Args:
        pdf_path: Path to the PDF to open.

    Returns:
        A single string with every page's ``extract_text`` result joined by
        newlines. Empty pages are skipped.

    Raises:
        JustificanteParseError: If pdfplumber cannot read any text.
    """
    return extract_pages_text_concatenated(pdf_path, error_class=JustificanteParseError)


def extract_text_pdfplumber_bytes(pdf_bytes: bytes) -> str:
    """Return concatenated text from in-memory PDF bytes using pdfplumber.

    Raises:
        JustificanteParseError: If pdfplumber cannot read any text.
    """
    return "\n".join(
        extract_pages_text_from_bytes(
            pdf_bytes,
            error_class=JustificanteParseError,
            pdf_label="PDF",
            source_label="in-memory justificante PDF",
        )
    )
