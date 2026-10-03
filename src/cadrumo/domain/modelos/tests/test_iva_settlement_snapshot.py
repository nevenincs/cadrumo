"""Invariant coverage for immutable Modelo 303 settlement snapshots."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.modelos.filing_record import (
    IvaSettlementPaymentEvidence,
    IvaSettlementPaymentState,
    IvaSettlementRefundState,
)

from .filing_record_test_support import (
    FILING_RECORD_TEST_AT,
    build_iva_settlement_snapshot_for_test,
    build_modelo_filing_record_for_test,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_default_settlement_keeps_existing_and_non_iva_filing_records_valid() -> None:
    assert build_modelo_filing_record_for_test(modelo="130").settlement is None
    assert build_modelo_filing_record_for_test().settlement is None


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
                        effective_at=FILING_RECORD_TEST_AT,
                    ),
                    IvaSettlementPaymentEvidence(
                        reference=FilingEvidenceReference(reference="secure-payment-evidence-1"),
                        amount=Decimal("40.00"),
                        effective_at=FILING_RECORD_TEST_AT,
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
                "refund_approval_effective_at": FILING_RECORD_TEST_AT,
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
                "refund_approval_effective_at": FILING_RECORD_TEST_AT,
            },
            "refund amounts",
        ),
    ),
)
def test_settlement_snapshot_refuses_invalid_evidence_and_credit_matrix(
    updates: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        build_iva_settlement_snapshot_for_test(**updates)


def test_settlement_snapshot_separates_declared_liability_from_evidenced_payment() -> None:
    snapshot = build_iva_settlement_snapshot_for_test(
        payment_evidence=(
            IvaSettlementPaymentEvidence(
                reference=FilingEvidenceReference(reference="secure-payment-evidence-2"),
                amount=Decimal("25.00"),
                effective_at=FILING_RECORD_TEST_AT,
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
        effective_at=FILING_RECORD_TEST_AT,
    )

    snapshot = build_iva_settlement_snapshot_for_test(payment_evidence=(evidence, evidence))

    assert snapshot.payment_evidence == (evidence,)


def test_settlement_snapshot_refuses_negative_declared_liability() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        build_iva_settlement_snapshot_for_test(declared_liability=Decimal("-0.01"))


def test_iva_settlement_cannot_be_attached_to_a_non_iva_record() -> None:
    with pytest.raises(ValidationError, match="Modelo 303"):
        build_modelo_filing_record_for_test(modelo="130", settlement=build_iva_settlement_snapshot_for_test())


def test_settlement_snapshot_must_name_its_filing_record_calculation_revision() -> None:
    with pytest.raises(ValidationError, match="calculation revision must match"):
        build_modelo_filing_record_for_test(
            settlement=build_iva_settlement_snapshot_for_test(calculation_revision_id="c" * 64)
        )


def test_pending_filing_cannot_assert_an_official_refund_lifecycle() -> None:
    with pytest.raises(ValidationError, match="pending filing records"):
        build_modelo_filing_record_for_test(
            settlement=build_iva_settlement_snapshot_for_test(
                refund_state=IvaSettlementRefundState.REQUESTED,
                refund_requested_amount=Decimal("50.00"),
            )
        )
