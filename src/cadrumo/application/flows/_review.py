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

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.flows import PageStatus
from ._definition import FlowDefinition
from ._engine import FlowState, page_status, visible_sequence
from ._errors import FlowSubmitError
from ._validators import ValidationVerdict, resolve_cross_field_validator

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
    answered_count: int = Field(ge=0)
    required_remaining: int = Field(ge=0)


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
