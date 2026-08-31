"""The review projection: the flow's summary surface and its submit gate.

The review surface is a substrate primitive every domain flow receives
for free: an enumeration of the visible pages (plus any stale orphans no
longer visible) with their :class:`PageStatus`, per-section grouping,
jump targets, and the single submit-eligibility verdict. Submission is
possible only from review and only when every required visible page is
validly answered, no staleness or deferral remains, and every
section-exit and flow-scope validator passes — the substrate's
completeness gate.
"""

from __future__ import annotations

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.flows import PageStatus
from ...core.models import STRICT_FROZEN_CONFIG
from .definition import FlowDefinition
from .engine import FlowState, page_status, visible_sequence
from .errors import FlowSubmitError
from .validators import ValidationVerdict, resolve_cross_field_validator

_PAGE_BADGE_LOCALE_KEYS: tuple[str, ...] = (
    "flows.progress.required",
    "flows.progress.optional",
)
"""Static declaration of the required/optional badge catalogue keys.

Frontends select between the pair at render time through a variable
``tr()`` call, which the locale usage scanner cannot see; declaring the
keys here keeps the authored catalogue leaves recognised as live."""


class ReviewRow(BaseModel):
    """One page's entry on the review surface."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    section_id: str
    status: PageStatus
    required: bool
    jumpable: bool
    verdicts: tuple[ValidationVerdict, ...] = ()


class ReviewProjection(BaseModel):
    """The full review surface: rows, blocking verdicts, submit eligibility.

    ``blocking`` aggregates every reason submission is refused, each a
    typed verdict the frontend renders verbatim — the projection never
    collapses refusals into a bare boolean.
    """

    model_config = STRICT_FROZEN_CONFIG

    flow_id: str
    rows: tuple[ReviewRow, ...]
    flow_verdicts: tuple[ValidationVerdict, ...] = ()
    submit_eligible: bool
    blocking: tuple[ValidationVerdict, ...] = ()
    answered_count: NonNegativeInt
    required_remaining: NonNegativeInt

    @model_validator(mode="after")
    def _derived_state_matches_rows(self) -> ReviewProjection:
        """Refuse projections whose reported review state contradicts their rows."""
        _validate_flow_verdicts(self.flow_verdicts)
        _validate_answered_count(self.rows, self.answered_count)
        _validate_required_remaining(self.rows, self.required_remaining)
        _validate_blocking_state(self)
        return self


def _validate_flow_verdicts(flow_verdicts: tuple[ValidationVerdict, ...]) -> None:
    """Review projections retain only failed flow-scope verdicts."""
    if any(verdict.ok for verdict in flow_verdicts):
        raise ValueError("review projection flow_verdicts must contain only failures")


def _validate_answered_count(rows: tuple[ReviewRow, ...], answered_count: int) -> None:
    """Confirm the serialized answered count matches its row state."""
    expected_answered_count = sum(1 for row in rows if row.status is PageStatus.ANSWERED)
    if answered_count != expected_answered_count:
        raise ValueError("review projection answered_count must match answered rows")


def _validate_required_remaining(rows: tuple[ReviewRow, ...], required_remaining: int) -> None:
    """Confirm the serialized required count excludes answered and stale rows."""
    expected_required_remaining = sum(
        1 for row in rows if row.required and row.status is not PageStatus.ANSWERED and row.jumpable
    )
    if required_remaining != expected_required_remaining:
        raise ValueError("review projection required_remaining must match outstanding required rows")


def _validate_blocking_state(projection: ReviewProjection) -> None:
    """Confirm the blocking verdict tuple and submit flag derive from the same rows."""
    expected_blocking = _blocking_verdicts(list(projection.rows), projection.flow_verdicts)
    if projection.blocking != expected_blocking:
        raise ValueError("review projection blocking verdicts must match rows and flow failures")
    if projection.submit_eligible != (not expected_blocking):
        raise ValueError("review projection submit_eligible must match blocking verdicts")


def review(definition: FlowDefinition, state: FlowState) -> ReviewProjection:
    """Project the current state onto the review surface.

    Visible pages appear in walk order; committed answers whose page is
    no longer visible (a gating change or a shrunk repeating group)
    appear after them as non-jumpable stale rows so nothing the operator
    entered ever silently disappears from the summary.
    """
    sequence = visible_sequence(definition, state)
    visible_keys = {entry.key for entry in sequence}

    rows: list[ReviewRow] = []
    for entry in sequence:
        rows.append(
            ReviewRow(
                key=entry.key,
                section_id=entry.section_id,
                status=page_status(state, entry.key),
                required=entry.page.required,
                jumpable=True,
                verdicts=state.verdicts.get(entry.key, ()),
            ),
        )
    for key in sorted(state.stale - visible_keys):
        rows.append(
            ReviewRow(
                key=key,
                section_id="",
                status=PageStatus.STALE,
                required=False,
                jumpable=False,
            ),
        )

    flow_verdicts = _run_flow_validators(definition, state)
    blocking = _blocking_verdicts(rows, flow_verdicts)
    answered = sum(1 for row in rows if row.status is PageStatus.ANSWERED)
    required_remaining = sum(
        1 for row in rows if row.required and row.status is not PageStatus.ANSWERED and row.jumpable
    )
    return ReviewProjection(
        flow_id=definition.id,
        rows=tuple(rows),
        flow_verdicts=flow_verdicts,
        submit_eligible=not blocking,
        blocking=blocking,
        answered_count=answered,
        required_remaining=required_remaining,
    )


def assert_submit_eligible(definition: FlowDefinition, state: FlowState) -> ReviewProjection:
    """Return the review projection, refusing loudly when submission is blocked.

    The domain flow calls this immediately before handing the typed
    answers to its persistence hook; the refusal enumerates every
    blocking verdict so the operator (or the driving agent) sees the
    complete remaining-work list, never a bare denial.
    """
    projection = review(definition, state)
    if not projection.submit_eligible:
        raise FlowSubmitError(
            translated_message="application.flows.errors.submit_blocked",
            context={
                "flow_id": definition.id,
                "blocking_count": len(projection.blocking),
                "required_remaining": projection.required_remaining,
            },
        )
    return projection


def _run_flow_validators(definition: FlowDefinition, state: FlowState) -> tuple[ValidationVerdict, ...]:
    failures: list[ValidationVerdict] = []
    for validator_id in definition.flow_validator_ids:
        for verdict in resolve_cross_field_validator(validator_id)(state.answers):
            if not verdict.ok:
                failures.append(verdict)
    return tuple(failures)


def _blocking_verdicts(
    rows: list[ReviewRow],
    flow_verdicts: tuple[ValidationVerdict, ...],
) -> tuple[ValidationVerdict, ...]:
    blocking: list[ValidationVerdict] = []
    for row in rows:
        if row.required and row.status is PageStatus.UNANSWERED and row.jumpable:
            blocking.append(
                ValidationVerdict.failed("flows.review.required_unanswered", page_key=row.key),
            )
        if row.status is PageStatus.INVALID:
            blocking.append(ValidationVerdict.failed("flows.review.page_invalid", page_key=row.key))
        if row.status is PageStatus.STALE:
            blocking.append(ValidationVerdict.failed("flows.review.page_stale", page_key=row.key))
        if row.status is PageStatus.DEFERRED:
            blocking.append(ValidationVerdict.failed("flows.review.page_deferred", page_key=row.key))
    blocking.extend(flow_verdicts)
    return tuple(blocking)


__all__ = [
    "ReviewProjection",
    "ReviewRow",
    "assert_submit_eligible",
    "review",
]
