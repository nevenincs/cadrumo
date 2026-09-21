"""Focused evidence derivation tests for the first withholding recognition slice."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingDatedEvent,
    WithholdingIncomeKind,
    WithholdingOperationKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
    WithholdingRecognitionError,
    WithholdingRecognitionEvidence,
    WithholdingRecognitionRule,
    derive_withholding_recognition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _evidence(**overrides: object) -> WithholdingRecognitionEvidence:
    values: dict[str, object] = {
        "applicable_year": 2025,
        "recipient_tax_status": WithholdingRecipientTaxStatus.RESIDENT,
        "recipient_tax_regime": WithholdingRecipientTaxRegime.IRPF,
        "income_kind": WithholdingIncomeKind.PROFESSIONAL,
        "operation_kind": WithholdingOperationKind.ORDINARY,
        "payment_or_satisfaction": WithholdingDatedEvent(event_id="payment-1", occurred_on=date(2025, 4, 2)),
    }
    values.update(overrides)
    return WithholdingRecognitionEvidence(**values)


@pytest.mark.parametrize(
    "income_kind",
    (
        WithholdingIncomeKind.WORK,
        WithholdingIncomeKind.PROFESSIONAL,
        WithholdingIncomeKind.URBAN_RENT,
    ),
)
def test_2025_resident_irpf_paid_or_satisfied_branches_derive_from_payment(
    income_kind: WithholdingIncomeKind,
) -> None:
    """The grounded work, professional, and urban-rent branches use payment evidence."""
    derived = derive_withholding_recognition(_evidence(income_kind=income_kind))

    assert derived.rule is WithholdingRecognitionRule.PAID_OR_SATISFIED
    assert derived.recognized_on == date(2025, 4, 2)
    assert derived.recognition_event_id == "payment-1"
    assert derived.settlement_event_id == "payment-1"


def test_ordinary_capital_uses_earlier_payment_or_exigibility() -> None:
    """Ordinary capital never assumes a universal payment-date rule."""
    base = _evidence(
        income_kind=WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
        exigibility=WithholdingDatedEvent(event_id="due-1", occurred_on=date(2025, 7, 1)),
        payment_or_satisfaction=WithholdingDatedEvent(event_id="paid-1", occurred_on=date(2025, 6, 30)),
    )
    earlier_payment = derive_withholding_recognition(base)
    later_payment = derive_withholding_recognition(
        base.model_copy(
            update={
                "payment_or_satisfaction": WithholdingDatedEvent(
                    event_id="settlement-1",
                    occurred_on=date(2026, 1, 15),
                )
            }
        )
    )

    assert earlier_payment.recognized_on == date(2025, 6, 30)
    assert earlier_payment.recognition_event_id == "paid-1"
    assert later_payment.recognized_on == date(2025, 7, 1)
    assert later_payment.recognition_event_id == "due-1"
    assert later_payment.settlement_event_id == "settlement-1"


@pytest.mark.parametrize(
    ("evidence", "code"),
    (
        (_evidence(payment_or_satisfaction=None), "missing_payment_or_satisfaction_evidence"),
        (_evidence(applicable_year=2024), "unsupported_applicable_year"),
        (_evidence(recipient_tax_status=WithholdingRecipientTaxStatus.UNKNOWN), "unknown_recipient_tax_status"),
        (_evidence(recipient_tax_status=WithholdingRecipientTaxStatus.NONRESIDENT), "irnr_unsupported"),
        (_evidence(recipient_tax_regime=WithholdingRecipientTaxRegime.IS), "corporate_income_tax_unsupported"),
        (
            _evidence(
                income_kind=WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
                exigibility=None,
            ),
            "missing_exigibility_evidence",
        ),
        (
            _evidence(exigibility=WithholdingDatedEvent(event_id="due-conflict", occurred_on=date(2025, 4, 1))),
            "conflicting_exigibility_evidence",
        ),
        (
            _evidence(
                income_kind=WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
                exigibility=WithholdingDatedEvent(event_id="due-1", occurred_on=date(2025, 7, 1)),
                formalization=WithholdingDatedEvent(event_id="formalization-conflict", occurred_on=date(2025, 7, 1)),
            ),
            "conflicting_formalization_evidence",
        ),
    ),
)
def test_unsupported_or_incomplete_evidence_refuses_before_a_command_is_built(
    evidence: WithholdingRecognitionEvidence,
    code: str,
) -> None:
    """All unsupported and incomplete branches fail closed at derivation."""
    with pytest.raises(WithholdingRecognitionError, match=code):
        derive_withholding_recognition(evidence)


def test_formalization_is_represented_but_123_and_193_refuse_without_mapping() -> None:
    """A modeled event is not silently promoted to an ungrounded projection."""
    evidence = _evidence(
        income_kind=WithholdingIncomeKind.INVESTMENT_FUND,
        operation_kind=WithholdingOperationKind.FORMALIZATION,
        payment_or_satisfaction=None,
        formalization=WithholdingDatedEvent(event_id="formalization-1", occurred_on=date(2025, 8, 1)),
    )

    assert derive_withholding_recognition(evidence).rule is WithholdingRecognitionRule.FORMALIZATION
    with pytest.raises(WithholdingRecognitionError, match="unsupported_formalization_projection"):
        derive_withholding_recognition(evidence, modelo="123")


def test_recognition_date_cannot_be_supplied_by_callers() -> None:
    """The evidence boundary forbids an authored recognition coordinate."""
    with pytest.raises(ValidationError, match="recognized_on"):
        _evidence(recognized_on=date(2025, 1, 1))
