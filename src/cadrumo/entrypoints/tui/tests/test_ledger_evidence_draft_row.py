"""The TUI draft row carries a degraded label reading from the draft the reader returned.

The evidence door turns the application's draft into the display row the
evidence screen renders. The draft records a label reading that stood without
its model fill as a reading-path fact rather than a field, so the row has to
lift it explicitly or the screen shows the empty fields as if the page lacked
them.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....application.ledger.invoice_draft_records import (
    InvoiceDraft,
    LabelReadingFallback,
    LabelReadingFallbackCause,
)
from ....core.config import override_settings
from ..ledger.evidence import draft_lines
from ..ledger_doors import _draft_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUSY = LabelReadingFallback(
    cause=LabelReadingFallbackCause.INFERENCE_SLOT_BUSY,
    unread_fields=("supplier_name",),
    reader_error_type="LLMBusyError",
    failed_condition_id="llm.local_inference.slot_available",
)


def _draft() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_tax_id="B92000082",
        invoice_number="T-0042-2026",
        invoice_date="2026-02-14",
        taxable_base=Decimal("60.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("12.60"),
        grand_total=Decimal("72.60"),
        currency="EUR",
    )


def test_the_draft_row_carries_the_degraded_reading_to_the_screen() -> None:
    row = _draft_row("8747cbf318cf0adb", _draft().with_label_reading_fallback(_BUSY))

    assert row.label_reading_fallback == _BUSY
    with override_settings(cadrumo_output_language="en"):
        assert "supplier_name" in draft_lines(row)[-1]


def test_a_draft_read_in_full_gives_a_row_with_no_degraded_reading() -> None:
    row = _draft_row("8747cbf318cf0adb", _draft())

    assert row.label_reading_fallback is None
