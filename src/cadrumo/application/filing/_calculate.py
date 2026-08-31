"""Typed, non-directive summary surface for filing draft calculations.

This module does not run the registry formula graph. It summarises an
already-built :class:`domain.filing.ModeloDraft` into a frozen
:class:`DeclaracionCalculateSummary` with the draft status and finding counts.
When validation is blocked, it transports the failed condition as a shared
typed no-recovery verdict.  The draft has no work-unit address, so this layer
must not manufacture a review, approval, export, or repair command.

The :func:`summarise_calculation` helper turns a draft into the typed
summary consumed by renderers::

    draft = build_draft(...)
    summary = summarise_calculation(draft)
    render(summary)

See Also:
    :func:`application.filing.build_draft`
        Registry-backed draft construction that produces the
        :class:`domain.filing.ModeloDraft` summarised here.
    :class:`domain.submission.ModeloDraftStatus`
        Lifecycle states that drive the next-action mapping.
    :func:`application.modelo.calculation_result_summary`
        Separate persisted-revision summary for headline casillas chosen
        from registry verification expectations.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.errors.severity import BaseSeverity
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...core.time.utc import validate_utc_aware
from ...domain.filing.schema import ModeloDraft
from ...domain.submission._protocols import ModeloDraftStatus
from ..operator_actions._models import PreconditionVerdict
from .errors import FilingPreconditionCondition, filing_no_recovery_verdict


class DeclaracionCalculateSummary(BaseModel):
    """Typed summary of a single modelo calculation run.

    Attributes:
        draft_id: The :class:`domain.filing.ModeloDraft` identity
            the summary was produced from.
        modelo: AEAT modelo identifier.
        period: Typed filing period for the draft.
        status: The draft's :class:`ModeloDraftStatus` after validation.
        blocker_count: Number of findings at
            :attr:`BaseSeverity.ERROR`. Always ``>= 0``.
        warning_count: Number of findings at
            :attr:`BaseSeverity.WARNING`. Always ``>= 0``.
        info_count: Number of findings at
            :attr:`BaseSeverity.INFO`. Always ``>= 0``.
        precondition_verdict: The explicit, fact-only refusal when an
            ``ERROR`` finding blocks the draft. ``None`` when no condition
            failed. The summary never declares a command because a draft
            alone does not carry the canonical work-unit binding.
        narrative: Translation key for summary line.
        calculated_at: UTC timestamp of when the summary was produced.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    status: ModeloDraftStatus
    blocker_count: NonNegativeInt
    warning_count: NonNegativeInt
    info_count: NonNegativeInt
    precondition_verdict: PreconditionVerdict | None = None
    narrative: str
    calculated_at: datetime

    @field_validator("calculated_at")
    @classmethod
    def _calculated_at_is_utc(cls, value: datetime) -> datetime:
        """Reject naive and non-UTC summary timestamps at the application boundary."""
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _require_blocker_verdict(self) -> DeclaracionCalculateSummary:
        """Require a terminal condition exactly when validation is blocked."""
        has_blockers = self.blocker_count > 0
        if has_blockers != (self.precondition_verdict is not None):
            raise ValueError("calculation blocker state must exactly match its precondition verdict")
        return self


def summarise_calculation(
    draft: ModeloDraft,
    *,
    narrative: str | None = None,
    calculated_at: datetime | None = None,
) -> DeclaracionCalculateSummary:
    """Build a :class:`DeclaracionCalculateSummary` from a validated draft.

    Args:
        draft: The :class:`ModeloDraft` returned by
            :func:`application.filing.build_draft`.
        narrative: Optional override for the translation key summary
            line. When ``None``, a default narrative key
            is used.
        calculated_at: Optional UTC timestamp. Defaults to the draft's
            ``updated_at``.

    Returns:
        A frozen :class:`DeclaracionCalculateSummary`.
    """
    counts: dict[BaseSeverity, int] = {
        BaseSeverity.INFO: 0,
        BaseSeverity.WARNING: 0,
        BaseSeverity.ERROR: 0,
    }
    for finding in draft.findings:
        counts[finding.severity] += 1

    blocker_count = counts[BaseSeverity.ERROR]
    resolved_narrative = narrative if narrative is not None else "filing.calculate.default_narrative"
    resolved_at = calculated_at if calculated_at is not None else draft.updated_at

    return DeclaracionCalculateSummary(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        status=draft.status,
        blocker_count=blocker_count,
        warning_count=counts[BaseSeverity.WARNING],
        info_count=counts[BaseSeverity.INFO],
        precondition_verdict=(
            filing_no_recovery_verdict(
                FilingPreconditionCondition.CALCULATION_FINDINGS_CLEAR,
                facts={
                    "draft_id": draft.draft_id,
                    "modelo": draft.modelo,
                    "period": draft.period.registry_token,
                    "filing_year": draft.period.filing_year,
                    "blocker_count": blocker_count,
                },
            )
            if blocker_count > 0
            else None
        ),
        narrative=resolved_narrative,
        calculated_at=resolved_at,
    )


__all__ = [
    "DeclaracionCalculateSummary",
    "summarise_calculation",
]
