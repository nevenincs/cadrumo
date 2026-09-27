"""Focused evidence derivation tests for withholding recognition across the support envelope."""

from __future__ import annotations

from datetime import date
from functools import cache

import pytest
from pydantic import ValidationError

from cadrumo.application.aggregation.withholding_recognition import (
    RECOGNITION_RULE_PROVISIONS,
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
from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_legal_reference,
    published_supported_filing_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return support.years


_YEAR = _supported_years()[0]


def _evidence(year: int = _YEAR, **overrides: object) -> WithholdingRecognitionEvidence:
    values: dict[str, object] = {
        "applicable_year": year,
        "recipient_tax_status": WithholdingRecipientTaxStatus.RESIDENT,
        "recipient_tax_regime": WithholdingRecipientTaxRegime.IRPF,
        "income_kind": WithholdingIncomeKind.PROFESSIONAL,
        "operation_kind": WithholdingOperationKind.ORDINARY,
        "payment_or_satisfaction": WithholdingDatedEvent(event_id="payment-1", occurred_on=date(year, 4, 2)),
    }
    values.update(overrides)
    return WithholdingRecognitionEvidence(**values)


@pytest.mark.parametrize("year", _supported_years())
def test_every_rule_provision_is_in_force_throughout_every_supported_year(year: int) -> None:
    """A rule applies to a year only while the RIRPF provisions it rests on are in force for all of it."""
    for rule, provisions in RECOGNITION_RULE_PROVISIONS.items():
        for provision in provisions:
            reference = published_legal_reference(provision)
            assert reference.effective_from <= date(year, 1, 1), (rule, provision, year)
            assert reference.effective_to is None or reference.effective_to >= date(year, 12, 31), (
                rule,
                provision,
                year,
            )


def test_every_rule_names_its_governing_provisions() -> None:
    assert set(RECOGNITION_RULE_PROVISIONS) == set(WithholdingRecognitionRule)
    assert all(RECOGNITION_RULE_PROVISIONS.values())


@pytest.mark.parametrize("year", _supported_years())
@pytest.mark.parametrize(
    "income_kind",
    (
        WithholdingIncomeKind.WORK,
        WithholdingIncomeKind.PROFESSIONAL,
        WithholdingIncomeKind.URBAN_RENT,
    ),
)
def test_resident_irpf_paid_or_satisfied_branches_derive_from_payment(
    income_kind: WithholdingIncomeKind,
    year: int,
) -> None:
    """The grounded work, professional, and urban-rent branches use payment evidence."""
    derived = derive_withholding_recognition(_evidence(year, income_kind=income_kind))

    assert derived.rule is WithholdingRecognitionRule.PAID_OR_SATISFIED
    assert derived.recognized_on == date(year, 4, 2)
    assert derived.recognition_event_id == "payment-1"
    assert derived.settlement_event_id == "payment-1"


@pytest.mark.parametrize("year", _supported_years())
def test_ordinary_capital_uses_earlier_payment_or_exigibility(year: int) -> None:
    """Ordinary capital never assumes a universal payment-date rule."""
    base = _evidence(
        year,
        income_kind=WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
        exigibility=WithholdingDatedEvent(event_id="due-1", occurred_on=date(year, 7, 1)),
        payment_or_satisfaction=WithholdingDatedEvent(event_id="paid-1", occurred_on=date(year, 6, 30)),
    )
    earlier_payment = derive_withholding_recognition(base)
    later_payment = derive_withholding_recognition(
        base.model_copy(
            update={
                "payment_or_satisfaction": WithholdingDatedEvent(
                    event_id="settlement-1",
                    occurred_on=date(year + 1, 1, 15),
                )
            }
        )
    )

    assert earlier_payment.recognized_on == date(year, 6, 30)
    assert earlier_payment.recognition_event_id == "paid-1"
    assert later_payment.recognized_on == date(year, 7, 1)
    assert later_payment.recognition_event_id == "due-1"
    assert later_payment.settlement_event_id == "settlement-1"


@pytest.mark.parametrize(
    ("evidence", "code"),
    (
        (_evidence(payment_or_satisfaction=None), "missing_payment_or_satisfaction_evidence"),
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
            _evidence(exigibility=WithholdingDatedEvent(event_id="due-conflict", occurred_on=date(_YEAR, 4, 1))),
            "conflicting_exigibility_evidence",
        ),
        (
            _evidence(
                income_kind=WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
                exigibility=WithholdingDatedEvent(event_id="due-1", occurred_on=date(_YEAR, 7, 1)),
                formalization=WithholdingDatedEvent(event_id="formalization-conflict", occurred_on=date(_YEAR, 7, 1)),
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
        formalization=WithholdingDatedEvent(event_id="formalization-1", occurred_on=date(_YEAR, 8, 1)),
    )

    assert derive_withholding_recognition(evidence).rule is WithholdingRecognitionRule.FORMALIZATION
    with pytest.raises(WithholdingRecognitionError, match="unsupported_formalization_projection"):
        derive_withholding_recognition(evidence, modelo="123")


def test_recognition_date_cannot_be_supplied_by_callers() -> None:
    """The evidence boundary forbids an authored recognition coordinate."""
    with pytest.raises(ValidationError, match="recognized_on"):
        _evidence(recognized_on=date(_YEAR, 1, 1))
