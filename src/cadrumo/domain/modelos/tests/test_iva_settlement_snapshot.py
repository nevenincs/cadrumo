"""Invariant coverage for immutable Modelo 303 settlement snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.core.period import Period
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    IvaCreditSnapshot,
    IvaSettlementPaymentEvidence,
    IvaSettlementPaymentState,
    IvaSettlementRefundState,
    IvaSettlementSnapshot,
    ModeloRecord,
    derive_filing_record_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "30330300-0000-4000-8000-000000000901"
_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "b" * 64
_AT = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)


def _settlement(**updates: object) -> IvaSettlementSnapshot:
    payload: dict[str, object] = {
        "calculation_revision_id": _REVISION_ID,
        "declared_liability": Decimal("100.00"),
        "payment_evidence": (
            IvaSettlementPaymentEvidence(
                reference=FilingEvidenceReference(reference="secure-payment-evidence-1"),
                amount=Decimal("100.00"),
                effective_at=_AT,
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


def _record(*, modelo: str = "303", settlement: IvaSettlementSnapshot | None = None) -> ModeloRecord:
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
        filed_at=_AT,
        filed_by="operator-A",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        settlement=settlement,
    )


def test_default_settlement_keeps_existing_and_non_iva_filing_records_valid() -> None:
    assert _record(modelo="130").settlement is None
    assert _record().settlement is None


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        (
            {
                "credit_snapshot": {
                    "opening_amount": Decimal("30.00"),
                    "generated_amount": Decimal("20.00"),
                    "applied_amount": Decimal("10.00"),
                    "remaining_amount": Decimal("39.00"),
                }
            },
            "remaining_amount",
        ),
        (
            {
                "payment_evidence": (
                    IvaSettlementPaymentEvidence(
                        reference=FilingEvidenceReference(reference="secure-payment-evidence-1"),
                        amount=Decimal("60.00"),
                        effective_at=_AT,
                    ),
                    IvaSettlementPaymentEvidence(
                        reference=FilingEvidenceReference(reference="secure-payment-evidence-1"),
                        amount=Decimal("40.00"),
                        effective_at=_AT,
                    ),
                ),
            },
            "conflicting facts",
        ),
        (
            {
                "refund_state": IvaSettlementRefundState.PAID,
                "refund_requested_amount": Decimal("50.00"),
                "refund_approved_amount": Decimal("40.00"),
                "refund_paid_amount": Decimal("20.00"),
                "refund_approval_evidence_reference": FilingEvidenceReference(
                    reference="secure-refund-approval-evidence-1"
                ),
                "refund_approval_effective_at": _AT,
            },
            "paid refund",
        ),
        (
            {
                "refund_state": IvaSettlementRefundState.APPROVED,
                "refund_requested_amount": Decimal("50.00"),
                "refund_approved_amount": Decimal("51.00"),
                "refund_approval_evidence_reference": FilingEvidenceReference(
                    reference="secure-refund-approval-evidence-1"
                ),
                "refund_approval_effective_at": _AT,
            },
            "refund amounts",
        ),
    ),
)
def test_settlement_snapshot_refuses_invalid_evidence_and_credit_matrix(
    updates: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _settlement(**updates)


def test_settlement_snapshot_separates_declared_liability_from_evidenced_payment() -> None:
    snapshot = _settlement(
        payment_evidence=(
            IvaSettlementPaymentEvidence(
                reference=FilingEvidenceReference(reference="secure-payment-evidence-2"),
                amount=Decimal("25.00"),
                effective_at=_AT,
            ),
        ),
    )

    assert snapshot.declared_liability == Decimal("100.00")
    assert snapshot.evidenced_payment_amount == Decimal("25.00")
    assert snapshot.payment_state is IvaSettlementPaymentState.PARTIALLY_EVIDENCED


def test_identical_payment_evidence_collapses_without_erasing_its_artifact() -> None:
    evidence = IvaSettlementPaymentEvidence(
        reference=FilingEvidenceReference(reference="secure-payment-evidence-2"),
        amount=Decimal("25.00"),
        effective_at=_AT,
    )

    snapshot = _settlement(payment_evidence=(evidence, evidence))

    assert snapshot.payment_evidence == (evidence,)


def test_settlement_snapshot_refuses_negative_declared_liability() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        _settlement(declared_liability=Decimal("-0.01"))


def test_iva_settlement_cannot_be_attached_to_a_non_iva_record() -> None:
    with pytest.raises(ValidationError, match="Modelo 303"):
        _record(modelo="130", settlement=_settlement())


def test_settlement_snapshot_must_name_its_filing_record_calculation_revision() -> None:
    with pytest.raises(ValidationError, match="calculation revision must match"):
        _record(settlement=_settlement(calculation_revision_id="c" * 64))


def test_pending_filing_cannot_assert_an_official_refund_lifecycle() -> None:
    with pytest.raises(ValidationError, match="pending filing records"):
        _record(
            settlement=_settlement(
                refund_state=IvaSettlementRefundState.REQUESTED,
                refund_requested_amount=Decimal("50.00"),
            )
        )
