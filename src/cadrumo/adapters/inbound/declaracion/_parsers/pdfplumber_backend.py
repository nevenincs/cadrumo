"""Pdfplumber-backed page text extraction for declaración PDFs.

Wraps :mod:`pdfplumber` behind
``adapters.inbound.declaracion._parsers._pdfplumber_backend.extract_pages_text``
and
``adapters.inbound.declaracion._parsers._pdfplumber_backend.extract_pages_text_from_bytes``,
which return one stripped text string per page. Errors from the underlying
library and pathological inputs (missing file, scan-only PDF without an OCR
layer) are translated into
:class:`~adapters.inbound.declaracion.errors.DeclaracionParseError`.

Both routes delegate to the shared pdfplumber primitives in
:mod:`adapters.inbound.pdf.page_text_extraction`, so the declaración parser
reads page text exactly as the other inbound PDF adapters do. The bytes route
keeps decrypted content in memory and never writes it to disk.
"""

from __future__ import annotations

from pathlib import Path

from ...pdf.page_text_extraction import extract_pages_text_from_bytes as _extract_pages_text_from_bytes_impl
from ...pdf.page_text_extraction import extract_pages_text_from_path as _extract_pages_text_from_path_impl
from ..errors import DeclaracionParseError


def extract_pages_text(pdf_path: Path) -> tuple[str, ...]:
    """Extract the text of each page in order with the shared pdfplumber primitive.

    Args:
        pdf_path: Filesystem path of the PDF to read.

    Returns:
        Tuple with one stripped string per page in the source order.
        Empty pages preserve their slot as the empty string.

    Raises:
        DeclaracionParseError: When the PDF is missing or no extractable text
            can be read from any page.
    """
    return _extract_pages_text_from_path_impl(
        pdf_path,
        error_class=DeclaracionParseError,
        not_found_label="declaración PDF not found",
        pdf_label="the PDF",
    )


def extract_pages_text_from_bytes(pdf_bytes: bytes, *, source_label: str = "in-memory PDF") -> tuple[str, ...]:
    """Extract text from PDF bytes without materialising a plaintext file.

    Uses the shared pdfplumber bytes primitive, so the caller's decrypted bytes
    stay in memory.

    Raises:
        DeclaracionParseError: When no extractable text can be read from the
            supplied PDF bytes.
    """
    return _extract_pages_text_from_bytes_impl(
        pdf_bytes,
        error_class=DeclaracionParseError,
        pdf_label="the PDF",
        source_label=source_label,
    )
