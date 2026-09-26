"""Behaviour tests for shared pdfplumber exception hygiene."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from .....domain.justificante.errors import PdfModeloImportError
from ..page_text_extraction import (
    extract_pages_text_concatenated,
    extract_pages_text_from_bytes,
    extract_pages_text_from_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_SENSITIVE_BASENAME = "12345678Z-renta-borrador.pdf"
_CORPUS = Path(__file__).parents[4] / "application" / "ledger" / "tests" / "_evidence_corpus"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _read_corpus(name: str) -> bytes:
    return (_CORPUS / name).read_bytes()


def _error_message(exc_info: pytest.ExceptionInfo[PdfModeloImportError]) -> str:
    return str(exc_info.value)


def _assert_sensitive_path_not_exposed(message: str, path: Path) -> None:
    assert _SENSITIVE_BASENAME not in message
    assert str(path) not in message
    assert "<input-pdf>" in message


def test_real_text_layer_invoice_extracts_content() -> None:
    """The real EN16931 reference invoice yields its text layer for the classifier."""
    pages = extract_pages_text_from_bytes(
        _read_corpus("zugferd_en16931_invoice.pdf"),
        error_class=ValueError,
        pdf_label="the invoice",
    )
    joined = "\n".join(pages)
    assert joined.strip()
    assert any(token in joined for token in ("Rechnung", "Invoice", "RECHNUNG", "EUR"))


def test_real_scanned_pdf_has_no_text_layer_then_rasterises() -> None:
    """A real image-only invoice PDF has no text layer, so it falls back to rasterisation."""
    from ....outbound.llm.providers.local import rasterise_pdf_pages_to_base64_png

    data = _read_corpus("scanned_invoice_from_commons_1.pdf")
    with pytest.raises(ValueError):  # no usable text layer -> caller routes to the vision reader
        extract_pages_text_from_bytes(data, error_class=ValueError, pdf_label="the invoice")
    pages = rasterise_pdf_pages_to_base64_png(data)
    assert pages
    assert base64.b64decode(pages[0])[:8] == _PNG_MAGIC


def test_foreign_language_invoice_still_extracts_text() -> None:
    """A non-Spanish (Hungarian) invoice still yields a usable text layer."""
    pages = extract_pages_text_from_bytes(
        _read_corpus("adversarial_foreign_language_invoice.pdf"),
        error_class=ValueError,
        pdf_label="the invoice",
    )
    assert any("SZAMLA" in p or "AFA" in p or "EUR" in p for p in pages)


def test_prompt_injection_invoice_extracts_text_without_executing_it() -> None:
    """Prompt-injection text in the invoice is extracted as inert text, not obeyed.

    Extraction returns the hostile text verbatim; the safety boundary is the
    downstream allow-list parser, not the extractor, which must simply not crash
    on adversarial content.
    """
    pages = extract_pages_text_from_bytes(
        _read_corpus("adversarial_prompt_injection_invoice.pdf"),
        error_class=ValueError,
        pdf_label="the invoice",
    )
    joined = "\n".join(pages)
    assert "SYSTEM OVERRIDE" in joined  # extracted verbatim as text, carries no authority


def test_malformed_pdf_raises_not_crashes() -> None:
    """A PDF header followed by garbage fails loudly on both parsers, never silently."""
    from ....outbound.llm.errors import LLMPdfRasterisationError
    from ....outbound.llm.providers.local import rasterise_pdf_pages_to_base64_png

    data = _read_corpus("adversarial_malformed.pdf")
    with pytest.raises(ValueError, match="pdfplumber could not open"):
        extract_pages_text_from_bytes(data, error_class=ValueError, pdf_label="the invoice")
    with pytest.raises(LLMPdfRasterisationError) as rasterisation:
        rasterise_pdf_pages_to_base64_png(data)
    assert rasterisation.value.context is not None
    assert rasterisation.value.context["rasterisation_stage"] == "document_open"
    assert rasterisation.value.context["rasterisation_error_type"]


def test_empty_pdf_raises_not_crashes() -> None:
    """A zero-byte .pdf fails loudly rather than producing a bogus result."""
    from ....outbound.llm.errors import LLMPdfRasterisationError
    from ....outbound.llm.providers.local import rasterise_pdf_pages_to_base64_png

    data = _read_corpus("adversarial_empty.pdf")
    assert data == b""
    with pytest.raises(LLMPdfRasterisationError) as rasterisation:
        rasterise_pdf_pages_to_base64_png(data)
    assert rasterisation.value.context is not None
    assert rasterisation.value.context["rasterisation_stage"] == "document_open"
    assert rasterisation.value.context["rasterisation_error_type"]


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
