"""Evidence notice and confirmed reconciliation shared by the filed-capture projection fixtures."""

from __future__ import annotations

from ....application.live.filed_single_capture_operation import (
    FiledCaptureNoticeV1,
    FiledReconciliationNoticeV1,
    FiledReconciliationV1,
)
from ....application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from ....core.json_contract import NoticeSeverity


def incomplete_receipt_notice() -> FiledCaptureNoticeV1:
    """Return the evidence notice that reports receipt metadata the capture could not complete."""
    return FiledCaptureNoticeV1(
        severity=NoticeSeverity.WARNING,
        code="live.filed.capture_test",
        message="Receipt metadata was incomplete",
        context=(("reason", "unavailable"),),
    )


def confirmed_reconciliation(*, bucket_id: str, filing_year: int, period: str) -> FiledReconciliationV1:
    """Return a confirmed reconciliation of record-1 that affects two further records."""
    return FiledReconciliationV1(
        outcome=FilingReconciliationOutcome.CONFIRMED.value,
        bucket_id=bucket_id,
        modelo="303",
        filing_year=filing_year,
        period=period,
        member_nif="X1234567A",
        filing_record_id="record-1",
        affected_filing_record_ids=("record-2", "record-3"),
        differing_casilla_ids=("casilla.a", "casilla.b"),
        evidence_basis="casillas",
        notices=(FiledReconciliationNoticeV1(code="receipt_totals_only", context=(("reason", "receipt"),)),),
    )
