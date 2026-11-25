"""A total printed only as the amount payable is the invoice's total.

Many invoices print their total once, as "Total a pagar". The label reader
reads that line as the amount payable, which is the total less any retención,
and used it only to check the retención against a separately printed total, so
an invoice with no other total line was left with its total unread. With no
total printed, the total is the amount payable plus the printed retención, kept
only when it closes against the base, the cuota, the recargo and the suplidos.

Each document here is a real synthetic PDF read through the production text
layer.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from ...application.ledger.document_transcription import DocumentTranscription
from ...application.ledger.evidence_textlayer import text_layer_transcriber_identity
from ...application.ledger.invoice_label_reader import LabelReading, read_invoice_fields_by_labels
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...tests.pdf_fixtures import text_pdf_bytes
from ..ledger_evidence_extraction_composition import evidence_text_layer_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_HEADER = (
    "FACTURA",
    "Proveedor: Cloud Ejemplo SL",
    "NIF: B00015016",
    "Numero de factura: CLO-2026-QA1",
    "Fecha de expedicion: 15/01/2026",
    "Base imponible: 100,00 EUR",
    "Tipo IVA: 21%",
    "Cuota IVA: 21,00 EUR",
)


def _read_pdf(lines: tuple[str, ...], operation: PinnedAuthorityOperation) -> LabelReading:
    pdf = text_pdf_bytes(lines)
    pages = evidence_text_layer_ports().extract_pages_text(pdf)
    transcription = DocumentTranscription(
        text="\n".join(pages),
        page_count=len(pages),
        source_content_sha256=hashlib.sha256(pdf).hexdigest(),
        transcriber=text_layer_transcriber_identity(),
    )
    return read_invoice_fields_by_labels(transcription, operation=operation)


def test_a_total_printed_only_as_the_amount_payable_is_read(operation: PinnedAuthorityOperation) -> None:
    reading = _read_pdf((*_HEADER, "Total a pagar: 121,00 EUR"), operation)

    assert reading.draft.grand_total == Decimal("121.00")
    assert reading.draft.taxable_base == Decimal("100.00")
    assert reading.draft.discrepancies == ()


def test_the_amount_payable_after_a_retencion_gives_the_total_before_it(operation: PinnedAuthorityOperation) -> None:
    reading = _read_pdf((*_HEADER, "Retencion IRPF (15%): -15,00 EUR", "Total a pagar: 106,00 EUR"), operation)

    assert reading.draft.grand_total == Decimal("121.00")
    assert reading.draft.retencion_amount == Decimal("15.00")


def test_an_amount_payable_that_does_not_close_is_not_taken_as_the_total(operation: PinnedAuthorityOperation) -> None:
    reading = _read_pdf((*_HEADER, "Total a pagar: 130,00 EUR"), operation)

    assert reading.draft.grand_total is None
    assert (DraftDiscrepancyKind.ARITHMETIC_CLOSURE, "grand_total") in {
        (finding.kind, finding.field) for finding in reading.draft.discrepancies
    }
