"""Behaviour tests for shared pdfplumber exception hygiene."""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import PdfModeloImportError
from ..page_text_extraction import extract_pages_text_concatenated, extract_pages_text_from_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_SENSITIVE_BASENAME = "12345678Z-renta-borrador.pdf"


def _error_message(exc_info: pytest.ExceptionInfo[PdfModeloImportError]) -> str:
    return str(exc_info.value)


def _assert_sensitive_path_not_exposed(message: str, path: Path) -> None:
    assert _SENSITIVE_BASENAME not in message
    assert str(path) not in message
    assert "<input-pdf>" in message


class TestPdfplumberPathErrorHygiene:
    """Path-based pdfplumber errors do not expose operator filenames."""

    def test_missing_pdf_uses_placeholder_source_label(self, tmp_path: Path) -> None:
        missing_pdf = tmp_path / _SENSITIVE_BASENAME

        with pytest.raises(PdfModeloImportError) as exc_info:
            extract_pages_text_from_path(
                missing_pdf,
                error_class=PdfModeloImportError,
                not_found_label="Modelo 100 PDF not found",
                pdf_label="PDF",
            )

        message = _error_message(exc_info)
        _assert_sensitive_path_not_exposed(message, missing_pdf)
        assert message == "Modelo 100 PDF not found: <input-pdf>"

    def test_invalid_pdf_uses_placeholder_source_label(self, tmp_path: Path) -> None:
        invalid_pdf = tmp_path / _SENSITIVE_BASENAME
        invalid_pdf.write_text("not a PDF", encoding="utf-8")

        with pytest.raises(PdfModeloImportError) as exc_info:
            extract_pages_text_from_path(
                invalid_pdf,
                error_class=PdfModeloImportError,
                not_found_label="Modelo 100 PDF not found",
                pdf_label="PDF",
            )

        message = _error_message(exc_info)
        _assert_sensitive_path_not_exposed(message, invalid_pdf)
        assert message.startswith("pdfplumber could not open <input-pdf>: ")

    def test_blank_pdf_uses_placeholder_source_label(self, tmp_path: Path) -> None:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        blank_pdf = tmp_path / _SENSITIVE_BASENAME
        page = canvas.Canvas(str(blank_pdf), pagesize=A4)
        page.showPage()
        page.save()

        with pytest.raises(PdfModeloImportError) as exc_info:
            extract_pages_text_from_path(
                blank_pdf,
                error_class=PdfModeloImportError,
                not_found_label="Modelo 100 PDF not found",
                pdf_label="PDF",
            )

        message = _error_message(exc_info)
        _assert_sensitive_path_not_exposed(message, blank_pdf)
        assert message == "no text extracted from <input-pdf>; PDF may be scan-only or XFA"

    def test_concatenated_invalid_pdf_uses_placeholder_source_label(self, tmp_path: Path) -> None:
        invalid_pdf = tmp_path / _SENSITIVE_BASENAME
        invalid_pdf.write_text("not a PDF", encoding="utf-8")

        with pytest.raises(PdfModeloImportError) as exc_info:
            extract_pages_text_concatenated(invalid_pdf, error_class=PdfModeloImportError)

        message = _error_message(exc_info)
        _assert_sensitive_path_not_exposed(message, invalid_pdf)
        assert message.startswith("pdfplumber failed to open <input-pdf>: ")
