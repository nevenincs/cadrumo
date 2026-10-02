"""Builders for Modelo filing-record snapshot tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from cadrumo.core.period import Period
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    IvaCreditSnapshot,
    IvaSettlementPaymentEvidence,
    IvaSettlementRefundState,
    IvaSettlementSnapshot,
    ModeloRecord,
    derive_filing_record_id,
)

_BUCKET_ID = "30330300-0000-4000-8000-000000000901"
_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "b" * 64
FILING_RECORD_TEST_AT: Final[datetime] = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)


def build_iva_settlement_snapshot_for_test(**updates: object) -> IvaSettlementSnapshot:
    """Build the canonical settled-liability fixture used by filing snapshot tests."""
    payload: dict[str, object] = {
        "calculation_revision_id": _REVISION_ID,
        "declared_liability": Decimal("100.00"),
        "payment_evidence": (
            IvaSettlementPaymentEvidence(
                reference=FilingEvidenceReference(reference="secure-payment-evidence-1"),
                amount=Decimal("100.00"),
                effective_at=FILING_RECORD_TEST_AT,
            ),
        ),
        "refund_state": IvaSettlementRefundState.NOT_REQUESTED,
        "refund_requested_amount": Decimal("0"),
        "refund_approved_amount": Decimal("0"),
        "refund_paid_amount": Decimal("0"),
        "credit_snapshot": IvaCreditSnapshot(
            opening_amount=Decimal("30.00"),
            generated_amount=Decimal("20.00"),
            applied_amount=Decimal("10.00"),
            remaining_amount=Decimal("40.00"),
        ),
    }
    payload.update(updates)
    return IvaSettlementSnapshot.model_validate(payload)


def build_modelo_filing_record_for_test(
    *, modelo: str = "303", settlement: IvaSettlementSnapshot | None = None
) -> ModeloRecord:
    """Build a valid locally filed Modelo record with an optional settlement."""
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_REVISION_ID,
            filed_by="operator-A",
        ),
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_REVISION_ID,
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=FILING_RECORD_TEST_AT,
        filed_by="operator-A",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        settlement=settlement,
    )


__all__ = [
    "FILING_RECORD_TEST_AT",
    "build_iva_settlement_snapshot_for_test",
    "build_modelo_filing_record_for_test",
]
