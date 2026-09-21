"""Typed, authority-selected recognition evidence for withholding observations.

This is an application boundary: it derives a filing recognition coordinate
from the underlying legal event evidence.  It deliberately has no writable
storage and accepts no caller-authored ``recognized_on`` value.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG


class WithholdingRecognitionRule(StrEnum):
    """The recognition rules whose 2025 applicability is explicitly grounded."""

    PAID_OR_SATISFIED = "paid_or_satisfied"
    EXIGIBILITY_OR_EARLIER_PAYMENT = "exigibility_or_earlier_payment"
    FORMALIZATION = "formalization"


class WithholdingRecipientTaxStatus(StrEnum):
    """The recipient residence status relevant to the first supported slice."""

    RESIDENT = "resident"
    NONRESIDENT = "nonresident"
    UNKNOWN = "unknown"


class WithholdingRecipientTaxRegime(StrEnum):
    """The recipient tax regime relevant to withholding recognition."""

    IRPF = "irpf"
    IS = "is"
    IRNR = "irnr"
    UNKNOWN = "unknown"


class WithholdingIncomeKind(StrEnum):
    """Income kinds with a distinct 2025 recognition treatment."""

    WORK = "work"
    PROFESSIONAL = "professional"
    URBAN_RENT = "urban_rent"
    ORDINARY_MOVABLE_CAPITAL = "ordinary_movable_capital"
    INVESTMENT_FUND = "investment_fund"


class WithholdingOperationKind(StrEnum):
    """Narrow operation distinction required by the supported rules."""

    ORDINARY = "ordinary"
    FORMALIZATION = "formalization"


class WithholdingRecognitionError(ValueError):
    """A stable, payload-free refusal at the recognition boundary."""

    def __init__(self, code: str) -> None:
        """Build a refusal that never echoes financial source evidence."""
        self.code = code
        super().__init__(f"withholding recognition refused: {code}")


class WithholdingDatedEvent(BaseModel):
    """One immutable underlying event used to derive recognition or settlement."""

    model_config = STRICT_FROZEN_CONFIG

    event_id: str = Field(min_length=1, max_length=128)
    occurred_on: date


class WithholdingRecognitionEvidence(BaseModel):
    """Facts from which the application derives, rather than accepts, recognition."""

    model_config = STRICT_FROZEN_CONFIG

    applicable_year: int = Field(ge=2000, le=9999)
    recipient_tax_status: WithholdingRecipientTaxStatus
    recipient_tax_regime: WithholdingRecipientTaxRegime
    income_kind: WithholdingIncomeKind
    operation_kind: WithholdingOperationKind
    payment_or_satisfaction: WithholdingDatedEvent | None = None
    exigibility: WithholdingDatedEvent | None = None
    formalization: WithholdingDatedEvent | None = None


class WithholdingRecognition(BaseModel):
    """The derived recognition coordinate and independent later settlement link."""

    model_config = STRICT_FROZEN_CONFIG

    rule: WithholdingRecognitionRule
    recognized_on: date
    recognition_event_id: str = Field(min_length=1, max_length=128)
    settlement_event_id: str | None = Field(default=None, min_length=1, max_length=128)


def derive_withholding_recognition(
    evidence: WithholdingRecognitionEvidence,
    *,
    modelo: str | None = None,
) -> WithholdingRecognition:
    """Derive recognition from grounded 2025 evidence or refuse before mutation.

    ``modelo`` is intentionally optional while rule derivation is shared.  The
    formalization representation is retained as evidence, but filing into 123
    or 193 refuses until the selected modelo mapping is grounded.
    """
    _validate_recipient(evidence)
    if evidence.applicable_year != 2025:
        raise WithholdingRecognitionError("unsupported_applicable_year")

    if evidence.income_kind in {
        WithholdingIncomeKind.WORK,
        WithholdingIncomeKind.PROFESSIONAL,
        WithholdingIncomeKind.URBAN_RENT,
    }:
        _require_ordinary_operation(evidence)
        _reject_event(evidence.exigibility, "conflicting_exigibility_evidence")
        _reject_event(evidence.formalization, "conflicting_formalization_evidence")
        event = _require_event(evidence.payment_or_satisfaction, "missing_payment_or_satisfaction_evidence")
        return WithholdingRecognition(
            rule=WithholdingRecognitionRule.PAID_OR_SATISFIED,
            recognized_on=event.occurred_on,
            recognition_event_id=event.event_id,
            settlement_event_id=event.event_id,
        )

    if evidence.income_kind is WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL:
        _require_ordinary_operation(evidence)
        _reject_event(evidence.formalization, "conflicting_formalization_evidence")
        exigibility = _require_event(evidence.exigibility, "missing_exigibility_evidence")
        payment = evidence.payment_or_satisfaction
        if payment is not None and payment.occurred_on < exigibility.occurred_on:
            return WithholdingRecognition(
                rule=WithholdingRecognitionRule.EXIGIBILITY_OR_EARLIER_PAYMENT,
                recognized_on=payment.occurred_on,
                recognition_event_id=payment.event_id,
                settlement_event_id=payment.event_id,
            )
        return WithholdingRecognition(
            rule=WithholdingRecognitionRule.EXIGIBILITY_OR_EARLIER_PAYMENT,
            recognized_on=exigibility.occurred_on,
            recognition_event_id=exigibility.event_id,
            settlement_event_id=payment.event_id if payment is not None else None,
        )

    if evidence.income_kind is WithholdingIncomeKind.INVESTMENT_FUND:
        if evidence.operation_kind is not WithholdingOperationKind.FORMALIZATION:
            raise WithholdingRecognitionError("unsupported_operation_kind")
        event = _require_event(evidence.formalization, "missing_formalization_evidence")
        _reject_event(evidence.exigibility, "conflicting_exigibility_evidence")
        if modelo in {"123", "193"}:
            raise WithholdingRecognitionError("unsupported_formalization_projection")
        return WithholdingRecognition(
            rule=WithholdingRecognitionRule.FORMALIZATION,
            recognized_on=event.occurred_on,
            recognition_event_id=event.event_id,
        )

    raise WithholdingRecognitionError("unsupported_income_kind")


def _validate_recipient(evidence: WithholdingRecognitionEvidence) -> None:
    if evidence.recipient_tax_status is WithholdingRecipientTaxStatus.UNKNOWN:
        raise WithholdingRecognitionError("unknown_recipient_tax_status")
    if evidence.recipient_tax_status is WithholdingRecipientTaxStatus.NONRESIDENT:
        raise WithholdingRecognitionError("irnr_unsupported")
    if evidence.recipient_tax_regime is WithholdingRecipientTaxRegime.UNKNOWN:
        raise WithholdingRecognitionError("unknown_recipient_tax_regime")
    if evidence.recipient_tax_regime is WithholdingRecipientTaxRegime.IRNR:
        raise WithholdingRecognitionError("irnr_unsupported")
    if evidence.recipient_tax_regime is WithholdingRecipientTaxRegime.IS:
        raise WithholdingRecognitionError("corporate_income_tax_unsupported")
    if evidence.recipient_tax_regime is not WithholdingRecipientTaxRegime.IRPF:
        raise WithholdingRecognitionError("recipient_status_regime_conflict")


def _require_ordinary_operation(evidence: WithholdingRecognitionEvidence) -> None:
    if evidence.operation_kind is not WithholdingOperationKind.ORDINARY:
        raise WithholdingRecognitionError("unsupported_operation_kind")


def _require_event(
    event: WithholdingDatedEvent | None,
    refusal_code: str,
) -> WithholdingDatedEvent:
    if event is None:
        raise WithholdingRecognitionError(refusal_code)
    return event


def _reject_event(event: WithholdingDatedEvent | None, refusal_code: str) -> None:
    if event is not None:
        raise WithholdingRecognitionError(refusal_code)


__all__ = [
    "WithholdingDatedEvent",
    "WithholdingIncomeKind",
    "WithholdingOperationKind",
    "WithholdingRecipientTaxRegime",
    "WithholdingRecipientTaxStatus",
    "WithholdingRecognition",
    "WithholdingRecognitionError",
    "WithholdingRecognitionEvidence",
    "WithholdingRecognitionRule",
    "derive_withholding_recognition",
]
