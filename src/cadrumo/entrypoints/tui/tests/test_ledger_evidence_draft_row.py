"""The TUI draft row carries a degraded label reading from the extraction projection.

The evidence door turns the extract operation's projection into the display row
the evidence screen renders. The projection carries a label reading that stood
without its model fill beside the draft rather than as a field, so the row has
to lift it explicitly or the screen shows the empty fields as if the page lacked
them.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest

from ....application.ledger.invoice_draft_records import (
    InvoiceDraft,
    LabelReadingFallback,
    LabelReadingFallbackCause,
)
from ....application.ledger.invoice_evidence_extract_operation import LedgerEvidenceExtractProjection
from ....application.ledger.invoice_evidence_operation_dtos import (
    InvoiceDraftProjectionV1,
    LabelReadingFallbackProjectionV1,
)
from ....core.config import override_settings
from ....core.operations import OperationEffect
from ..ledger.evidence_draft import draft_lines
from ..ledger.runtime_evidence import RuntimeEvidenceTuiDoorV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EVIDENCE_ID = "8747cbf318cf0adb"

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


def _projection(fallback: LabelReadingFallback | None) -> LedgerEvidenceExtractProjection:
    return LedgerEvidenceExtractProjection(
        profile_id=UUID(int=1),
        evidence_id=_EVIDENCE_ID,
        source_sha256="a" * 64,
        draft_review_sha256="b" * 64,
        consent_audit_effect=OperationEffect.NONE,
        draft=InvoiceDraftProjectionV1.from_draft(_draft()),
        label_reading_fallback=None if fallback is None else LabelReadingFallbackProjectionV1.from_fallback(fallback),
    )


def test_the_draft_row_carries_the_degraded_reading_to_the_screen() -> None:
    row = RuntimeEvidenceTuiDoorV1._draft(_projection(_BUSY), evidence_id=_EVIDENCE_ID)

    assert row.label_reading_fallback == _BUSY
    with override_settings(cadrumo_output_language="en"):
        assert "supplier_name" in draft_lines(row)[-1]


def test_a_draft_read_in_full_gives_a_row_with_no_degraded_reading() -> None:
    row = RuntimeEvidenceTuiDoorV1._draft(_projection(None), evidence_id=_EVIDENCE_ID)

    assert row.label_reading_fallback is None
