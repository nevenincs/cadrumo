"""The evidence draft shows why fields are unread when the model fill did not run.

A draft whose label reading stood without its model fill has empty fields that
the page may well print. Without its own line the TUI draft reads exactly like a
document that prints fewer fields, so each cause gets a line naming what stopped
the fill, the fields it left unread and the remedy that cause asks for.
"""

from __future__ import annotations

import pytest

from .....application.ledger.invoice_draft_records import LabelReadingFallback, LabelReadingFallbackCause
from .....core.config import override_settings
from .....domain.iva.classification import InvoiceKind
from ..evidence import draft_lines
from ..models import LedgerEvidenceDraftV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _draft(fallback: LabelReadingFallback | None) -> LedgerEvidenceDraftV1:
    return LedgerEvidenceDraftV1(
        evidence_id="8747cbf318cf0adb",
        supplier_name=None,
        supplier_tax_id="B92000082",
        invoice_number="T-0042-2026",
        invoice_date="2026-02-14",
        taxable_base="60.00",
        iva_rate="21",
        iva_amount="12.60",
        grand_total="72.60",
        currency=None,
        suggested_kind=InvoiceKind.RECEIVED,
        discrepancies=0,
        label_reading_fallback=fallback,
    )


def _fallback(cause: LabelReadingFallbackCause) -> LabelReadingFallback:
    return LabelReadingFallback(
        cause=cause,
        unread_fields=("currency", "supplier_name"),
        reader_error_type="ReaderFailureForTest",
    )


def test_a_draft_read_in_full_shows_no_label_reading_line() -> None:
    """The positive control: the extra line belongs to the degraded draft alone."""
    with override_settings(cadrumo_output_language="en"):
        lines = draft_lines(_draft(None))

    assert len(lines) == 4
    assert not any("currency, supplier_name" in line for line in lines)


@pytest.mark.parametrize(
    ("cause", "remedy"),
    [
        (LabelReadingFallbackCause.READER_UNAVAILABLE, "Check the reader"),
        (LabelReadingFallbackCause.LOAD_HEADROOM_REFUSED, "Free memory"),
        (LabelReadingFallbackCause.INFERENCE_SLOT_BUSY, "once it finishes"),
    ],
)
def test_a_degraded_draft_names_the_unread_fields_and_the_remedy_for_its_cause(
    cause: LabelReadingFallbackCause,
    remedy: str,
) -> None:
    with override_settings(cadrumo_output_language="en"):
        lines = draft_lines(_draft(_fallback(cause)))

    assert len(lines) == 5
    last = lines[-1]
    assert "currency, supplier_name" in last
    assert "2 field(s)" in last
    assert remedy in last


def test_every_cause_has_its_own_line() -> None:
    """Two causes sharing a line would send an operator to free memory while another read holds the slot."""
    with override_settings(cadrumo_output_language="en"):
        rendered = {cause: draft_lines(_draft(_fallback(cause)))[-1] for cause in LabelReadingFallbackCause}

    assert len(set(rendered.values())) == len(LabelReadingFallbackCause)
