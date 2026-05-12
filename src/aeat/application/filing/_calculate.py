"""Typed summary surface for ``aeat app declaration calculate``.

The CLI contract requires bare ``aeat app declaration calculate`` to
print a compact summary table, blocker counts, warnings, and the next
action — and shows repair hints instead of succeeding silently when the
inputs are unresolved. The CLI cannot compute that summary by inspecting
:class:`aeat.domain.filing.FilingDraft` ad-hoc: the next-action heuristic
is shared logic the application layer owns, and the typed record gives
the renderers and tests a stable schema to target.

The :func:`summarise_calculation` helper turns a draft into the typed
summary consumed by renderers::

    draft = build_draft(...)
    summary = summarise_calculation(draft)
    render(summary)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...domain.filing import (
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
)
from .errors import FilingCalculateError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
"""Shared :class:`pydantic.ConfigDict` enforcing strict, frozen, no-extras."""


class DeclarationCalculateNextAction(StrEnum):
    """Closed catalogue of next operator actions surfaced after calculate.

    The CLI uses this to render the "next action" line of the bare
    ``aeat app declaration calculate`` summary.

    Attributes:
        RESOLVE_BLOCKERS: One or more validation findings at
            :attr:`FilingFindingSeverity.ERROR` block forward motion.
            The operator must edit inputs or fix the upstream catalogue
            before any review/approve/export step.
        REVIEW: The draft validated cleanly (or only carries
            informational findings) and is ready for human review via
            ``aeat app declaration review``.
        APPROVE: The draft has been reviewed and is awaiting human
            approval via ``aeat app declaration approve``.
        EXPORT: The draft is approved and may be exported via
            ``aeat app declaration export``.
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


class DeclarationCalculateSummary(BaseModel):
    """Typed summary of a single ``aeat app declaration calculate`` run.

    Attributes:
        draft_id: The :class:`aeat.domain.filing.FilingDraft` identity
            the summary was produced from.
        modelo: AEAT modelo identifier.
        period: Canonical period identifier (e.g. ``"2026Q1"``).
        status: The draft's :class:`FilingDraftStatus` after validation.
        blocker_count: Number of findings at
            :attr:`FilingFindingSeverity.ERROR`. Always ``>= 0``.
        warning_count: Number of findings at
            :attr:`FilingFindingSeverity.WARNING`. Always ``>= 0``.
        info_count: Number of findings at
            :attr:`FilingFindingSeverity.INFO`. Always ``>= 0``.
        next_action: Closed :class:`DeclarationCalculateNextAction`.
            Derived deterministically from ``status`` and the finding
            mix.
        repair_hints: Translation keys surfaced when ``next_action``
            is :attr:`DeclarationCalculateNextAction.RESOLVE_BLOCKERS`;
            empty otherwise. The CLI renders them under the summary
            line so the operator never sees a silent ERROR.
        narrative: Translation key for summary line.
        calculated_at: UTC timestamp of when the summary was produced.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    status: FilingDraftStatus
    blocker_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    info_count: int = Field(ge=0)
    next_action: DeclarationCalculateNextAction
    repair_hints: tuple[str, ...] = ()
    narrative: str
    calculated_at: datetime

    @model_validator(mode="after")
    def _enforce_repair_hint_invariant(self) -> DeclarationCalculateSummary:
        """Repair hints accompany the RESOLVE_BLOCKERS verdict only.

        The CLI renders ``repair_hints`` as a remediation block. Surfacing
        them on a non-blocker verdict would mislead the operator — and
        omitting them on a blocker verdict would yield a silent success.
        """
        if self.next_action is DeclarationCalculateNextAction.RESOLVE_BLOCKERS:
            if not self.repair_hints:
                raise FilingCalculateError("repair_hints must be non-empty when next_action is RESOLVE_BLOCKERS")
        else:
            if self.repair_hints:
                raise FilingCalculateError("repair_hints must be empty unless next_action is RESOLVE_BLOCKERS")
        return self


_DOWNSTREAM_STATUSES: frozenset[FilingDraftStatus] = frozenset(
    {
        FilingDraftStatus.SUBMITTED,
        FilingDraftStatus.ACKNOWLEDGED,
        FilingDraftStatus.REJECTED,
        FilingDraftStatus.AMENDED,
        FilingDraftStatus.CANCELLED,
    }
)
"""Statuses where the draft has left the calculate/approve/export flow."""


def _next_action_for(
    status: FilingDraftStatus,
    *,
    blocker_count: int,
) -> DeclarationCalculateNextAction:
    """Map ``(status, blocker_count)`` to the deterministic next action."""
    if blocker_count > 0:
        return DeclarationCalculateNextAction.RESOLVE_BLOCKERS
    if status in _DOWNSTREAM_STATUSES:
        return DeclarationCalculateNextAction.AMEND
    if status is FilingDraftStatus.APPROVAL_STALE:
        return DeclarationCalculateNextAction.REFRESH_APPROVAL
    if status is FilingDraftStatus.APPROVED:
        return DeclarationCalculateNextAction.EXPORT
    if status is FilingDraftStatus.READY_TO_SUBMIT:
        return DeclarationCalculateNextAction.APPROVE
    return DeclarationCalculateNextAction.REVIEW


def summarise_calculation(
    draft: FilingDraft,
    *,
    repair_hints: tuple[str, ...] = (),
    narrative: str | None = None,
    calculated_at: datetime | None = None,
) -> DeclarationCalculateSummary:
    """Build a :class:`DeclarationCalculateSummary` from a validated draft.

    Args:
        draft: The freshly built draft returned by
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
        A frozen :class:`DeclarationCalculateSummary`.

    Raises:
        FilingCalculateError: When ``repair_hints`` violates the
            ``RESOLVE_BLOCKERS`` invariant.
    """
    counts: dict[FilingFindingSeverity, int] = {
        FilingFindingSeverity.INFO: 0,
        FilingFindingSeverity.WARNING: 0,
        FilingFindingSeverity.ERROR: 0,
    }
    for finding in draft.findings:
        counts[finding.severity] += 1

    next_action = _next_action_for(draft.status, blocker_count=counts[FilingFindingSeverity.ERROR])
    resolved_narrative = narrative if narrative is not None else "filing.calculate.default_narrative"
    resolved_at = calculated_at if calculated_at is not None else draft.updated_at

    return DeclarationCalculateSummary(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        status=draft.status,
        blocker_count=counts[FilingFindingSeverity.ERROR],
        warning_count=counts[FilingFindingSeverity.WARNING],
        info_count=counts[FilingFindingSeverity.INFO],
        next_action=next_action,
        repair_hints=repair_hints,
        narrative=resolved_narrative,
        calculated_at=resolved_at,
    )


__all__ = [
    "DeclarationCalculateNextAction",
    "DeclarationCalculateSummary",
    "summarise_calculation",
]
