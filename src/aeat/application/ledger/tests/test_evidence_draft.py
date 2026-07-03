"""Real-behaviour tests for on-host invoice-PDF field extraction into a draft.

Builds real text-bearing PDFs in memory (reportlab), wraps them as
``EvidenceInput``, and asserts :func:`extract_invoice_fields` recovers the
grounded fields with no file written and no field fabricated. No mocks.
"""

from __future__ import annotations

import hashlib
from io import BytesIO

import pytest

from .._evidence import MediaKind, PurchaseInvoiceEvidenceInputError
from .._evidence_draft import extract_invoice_fields
from .._evidence_input import EvidenceInput

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# A real Spanish CIF (Agencia Tributaria checksum-valid: leading letter B,
# 7 digits, digit control character computed by the AEAT algorithm).
_SUPPLIER_CIF = "B12345674"

_FULL_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0142",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

_PARTIAL_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    "Base imponible: 250,00",
    "Total factura: 250,00",
)


def _text_pdf_bytes(lines: tuple[str, ...]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    y = 760
    for line in lines:
        page.drawString(72, y, line)
        y -= 20
    page.save()
    return buf.getvalue()


def _evidence_input(data: bytes, media_kind: MediaKind, mime_type: str) -> EvidenceInput:
    return EvidenceInput(
        media_kind=media_kind,
        mime_type=mime_type,
        data=data,
        content_sha256=hashlib.sha256(data).hexdigest(),
        attachment_id="a" * 64,
    )


def test_extracts_every_field_from_a_full_invoice_layout_on_host() -> None:
    pdf = _text_pdf_bytes(_FULL_INVOICE_LINES)
    ev = _evidence_input(pdf, MediaKind.PDF, "application/pdf")

    draft = extract_invoice_fields(ev)

    assert draft.supplier_tax_id == _SUPPLIER_CIF
    assert draft.invoice_number == "2026-0142"
    assert draft.invoice_date == "2026-03-10"
    assert draft.taxable_base == 100
    assert draft.iva_rate == 21
    assert draft.iva_amount == 21
    assert draft.grand_total == 121
    assert draft.raw_text_length > 0


def test_missing_fields_are_none_not_fabricated() -> None:
    """A PDF missing several fields leaves them ``None``, never a guessed value."""
    pdf = _text_pdf_bytes(_PARTIAL_INVOICE_LINES)
    ev = _evidence_input(pdf, MediaKind.PDF, "application/pdf")

    draft = extract_invoice_fields(ev)

    assert draft.supplier_tax_id is None
    assert draft.invoice_number is None
    assert draft.invoice_date is None
    assert draft.iva_rate is None
    assert draft.iva_amount is None
    # The fields that ARE present in the source text are still recovered.
    assert draft.taxable_base == 250
    assert draft.grand_total == 250


def test_invalid_tax_id_lookalike_is_skipped_not_returned() -> None:
    """A digit run that merely looks like a tax id but fails the checksum is skipped."""
    # "A0000000A" has the coarse shape of a CIF but fails the AEAT check letter.
    lines = ("Factura", "Ref: A0000000A", "Total factura: 50,00")
    pdf = _text_pdf_bytes(lines)
    ev = _evidence_input(pdf, MediaKind.PDF, "application/pdf")

    draft = extract_invoice_fields(ev)

    assert draft.supplier_tax_id is None
    assert draft.grand_total == 50


def test_image_evidence_has_no_text_layer_and_refuses() -> None:
    ev = _evidence_input(b"\x89PNG\r\n\x1a\nfake-png-bytes", MediaKind.IMAGE, "image/png")

    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        extract_invoice_fields(ev)


def test_extraction_never_writes_a_file(tmp_path_factory: pytest.TempPathFactory) -> None:
    """The evidence bytes and extracted text stay in memory; nothing lands on disk."""
    empty_dir = tmp_path_factory.mktemp("no-write-expected")
    pdf = _text_pdf_bytes(_FULL_INVOICE_LINES)
    ev = _evidence_input(pdf, MediaKind.PDF, "application/pdf")

    extract_invoice_fields(ev)

    assert list(empty_dir.iterdir()) == []
