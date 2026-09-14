"""Real-behaviour tests for on-host text-layer evidence extraction.

Builds a real text-bearing PDF in memory (reportlab), wraps it as an
EvidenceInput, and asserts the on-host extractor returns the embedded text with
no file written. No mocks.
"""

from __future__ import annotations

import hashlib

import pytest

from ....tests.pdf_fixtures import text_pdf_bytes
from ....core.document_shape import DocumentShape
from ..evidence_input import EvidenceInput
from ..evidence_textlayer import extract_evidence_text
from ._evidence_textlayer_test_support import text_layer_ports_for_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INVOICE_LINE = "Factura Acme SL base imponible 100,00 IVA 21,00 total 121,00"
_TEXT_LAYER_PORTS = text_layer_ports_for_pages((_INVOICE_LINE,))


def _evidence_input(data: bytes, mime_type: str, *, document_shape: DocumentShape) -> EvidenceInput:
    return EvidenceInput(
        mime_type=mime_type,
        document_shape=document_shape,
        data=data,
        content_sha256=hashlib.sha256(data).hexdigest(),
        attachment_id="a" * 64,
    )


def test_extracts_text_layer_from_pdf_bytes_on_host() -> None:
    pdf = text_pdf_bytes((_INVOICE_LINE,))
    ev = _evidence_input(pdf, "application/pdf", document_shape=DocumentShape.PDF_TEXT_LAYER)
    text = extract_evidence_text(ev, text_layer_ports=_TEXT_LAYER_PORTS)
    assert "Factura Acme SL" in text
    assert "121,00" in text


def test_image_evidence_has_no_text_layer() -> None:
    ev = _evidence_input(
        b"\x89PNG\r\n\x1a\nfake-png-bytes",
        "image/png",
        document_shape=DocumentShape.IMAGE,
    )
    from ..evidence_errors import PurchaseInvoiceEvidenceInputError

    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        extract_evidence_text(ev, text_layer_ports=_TEXT_LAYER_PORTS)
