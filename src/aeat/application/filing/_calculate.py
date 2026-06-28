"""Typed summary surface for filing draft calculation results.

This module does not run the registry formula graph. It summarises an
already-built :class:`aeat.domain.filing.ModeloDraft` into a frozen
:class:`DeclaracionCalculateSummary` so CLI renderers can display the
draft status, finding counts, repair hints, and
:class:`DeclaracionCalculateNextAction` without re-implementing lifecycle
policy.

The CLI contract requires modelo calculation to print a compact summary
table, blocker counts, warnings, and the next action. When inputs are
unresolved, repair hints must be present instead of allowing a silent
success. The CLI cannot compute that summary by inspecting a draft
ad hoc: the next-action heuristic is shared logic the application layer
owns, and this typed record gives renderers and tests a stable schema.

The :func:`summarise_calculation` helper turns a draft into the typed
summary consumed by renderers::

    draft = build_draft(...)
    summary = summarise_calculation(draft)
    render(summary)

See Also:
    :func:`aeat.application.filing.build_draft`
        Registry-backed draft construction that produces the
        :class:`aeat.domain.filing.ModeloDraft` summarised here.
    :class:`aeat.domain.submission.ModeloDraftStatus`
        Lifecycle states that drive the next-action mapping.
    :func:`aeat.application.modelo.calculation_result_summary`
        Separate persisted-revision summary for headline casillas chosen
        from registry verification expectations.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.errors import BaseSeverity
from ...domain.filing import ModeloDraft
from ...domain.submission._protocols import ModeloDraftStatus
from .errors import ModeloCalculateError


class DeclaracionCalculateNextAction(StrEnum):
    """Closed catalogue of next operator actions surfaced after calculate.

    The CLI uses this to render the "next action" line of the bare
    modelo calculation summary.

    Attributes:
        RESOLVE_BLOCKERS: One or more validation findings at
            :attr:`BaseSeverity.ERROR` block forward motion.
            The operator must edit inputs or fix the upstream catalogue
            before any review/approve/export step.
        REVIEW: The draft validated cleanly (or only carries
            informational findings) and is ready for human review via
            modelo review.
        APPROVE: The draft has been reviewed and is awaiting human
            approval through the modelo workflow.
        EXPORT: The draft is approved and may be exported via
            modelo export.
        REFRESH_APPROVAL: The draft was previously approved but the
            approval is stale; the operator must re-approve.
        AMEND: The draft is in a downstream lifecycle state
            (submitted / acknowledged / rejected / amended / cancelled);
            corrective work runs through a fresh recalculation rather
            than the calculate flow.
    """

    RESOLVE_BLOCKERS = "resolve-blockers"
    REVIEW = "review"
    APPROVE = "approve"
    EXPORT = "export"
    REFRESH_APPROVAL = "refresh-approval"
    AMEND = "amend"


class DeclaracionCalculateSummary(BaseModel):
    """Typed summary of a single modelo calculation run.

    Attributes:
        draft_id: The :class:`aeat.domain.filing.ModeloDraft` identity
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
        next_action: Closed :class:`DeclaracionCalculateNextAction`.
            Derived deterministically from ``status`` and the finding
            mix.
        repair_hints: Translation keys surfaced when ``next_action``
            is :attr:`DeclaracionCalculateNextAction.RESOLVE_BLOCKERS`;
            empty otherwise. The CLI renders them under the summary
            line so the operator never sees a silent ERROR.
        narrative: Translation key for summary line.
        calculated_at: UTC timestamp of when the summary was produced.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    status: ModeloDraftStatus
    blocker_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    info_count: int = Field(ge=0)
    next_action: DeclaracionCalculateNextAction
    repair_hints: tuple[str, ...] = ()
    narrative: str
    calculated_at: datetime

    @model_validator(mode="after")
    def _enforce_repair_hint_invariant(self) -> DeclaracionCalculateSummary:
        """Repair hints accompany the RESOLVE_BLOCKERS verdict only.

        The CLI renders ``repair_hints`` as a remediation block. Surfacing
        them on a non-blocker verdict would mislead the operator — and
        omitting them on a blocker verdict would yield a silent success.
        """
        if self.next_action is DeclaracionCalculateNextAction.RESOLVE_BLOCKERS:
            if not self.repair_hints:
                raise ModeloCalculateError("repair_hints must be non-empty when next_action is RESOLVE_BLOCKERS")
        else:
            if self.repair_hints:
                raise ModeloCalculateError("repair_hints must be empty unless next_action is RESOLVE_BLOCKERS")
        return self


_DOWNSTREAM_STATUSES: frozenset[ModeloDraftStatus] = frozenset(
    {
        ModeloDraftStatus.PRESENTADA,
        ModeloDraftStatus.ACEPTADA,
        ModeloDraftStatus.RECHAZADA,
        ModeloDraftStatus.ENMENDADO,
        ModeloDraftStatus.ANULADO,
    },
)
"""Statuses where the draft has left the calculate/approve/export flow."""


def _next_action_for(
    status: ModeloDraftStatus,
    *,
    blocker_count: int,
) -> DeclaracionCalculateNextAction:
    """Map ``(status, blocker_count)`` to the deterministic next action."""
    if blocker_count > 0:
        return DeclaracionCalculateNextAction.RESOLVE_BLOCKERS
    if status in _DOWNSTREAM_STATUSES:
        return DeclaracionCalculateNextAction.AMEND
    if status is ModeloDraftStatus.APROBACION_CADUCADA:
        return DeclaracionCalculateNextAction.REFRESH_APPROVAL
    if status is ModeloDraftStatus.APROBADO:
        return DeclaracionCalculateNextAction.EXPORT
    if status is ModeloDraftStatus.LISTO_PARA_PRESENTAR:
        return DeclaracionCalculateNextAction.APPROVE
    return DeclaracionCalculateNextAction.REVIEW


def summarise_calculation(
    draft: ModeloDraft,
    *,
    repair_hints: tuple[str, ...] = (),
    narrative: str | None = None,
    calculated_at: datetime | None = None,
) -> DeclaracionCalculateSummary:
    """Build a :class:`DeclaracionCalculateSummary` from a validated draft.

    Args:
        draft: The :class:`ModeloDraft` returned by
            :func:`aeat.application.filing.build_draft`.
        repair_hints: Translation keys for remediation hints. Required when
            the draft carries any ``ERROR`` finding (the CLI must not
            surface a silent blocker); rejected
            otherwise. Passing the existing draft findings unchanged
            is acceptable; callers that derive richer hints from
            upstream catalogues can provide their own.
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

    next_action = _next_action_for(draft.status, blocker_count=counts[BaseSeverity.ERROR])
    resolved_narrative = narrative if narrative is not None else "filing.calculate.default_narrative"
    resolved_at = calculated_at if calculated_at is not None else draft.updated_at

    return DeclaracionCalculateSummary(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        status=draft.status,
        blocker_count=counts[BaseSeverity.ERROR],
        warning_count=counts[BaseSeverity.WARNING],
        info_count=counts[BaseSeverity.INFO],
        next_action=next_action,
        repair_hints=repair_hints,
        narrative=resolved_narrative,
        calculated_at=resolved_at,
    )


__all__ = [
    "DeclaracionCalculateNextAction",
    "DeclaracionCalculateSummary",
    "summarise_calculation",
]
