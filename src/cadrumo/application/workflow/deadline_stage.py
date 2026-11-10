"""Deadline resolution helpers for the workflow engine.

The deadline stage projects the active :class:`TaxpayerProfile` through the
domain deadline engine and selects one :class:`ModeloDeadline`: the exact
work-unit target's obligation, or the next one of the computed
:class:`Schedule`, the shared
:func:`~domain.deadlines.engine.compute_obligation_schedule` producer used by
state projections.

See Also:
    :class:`~application.workflow.engine.WorkflowEngine`
        Composition root that calls these helpers from the
        ``COMPUTING_DEADLINES`` stage.
    :class:`~application.workflow.run_models.WorkflowPurpose`
        Purpose enum that decides whether a missing filing-window obligation
        aborts the run or remains informational context.
    :func:`~application.state_projection.build_pending_obligations`
        Projection-side consumer of the same deadline schedule producer.
    :mod:`domain.deadlines`
        Domain schedule authority that emits the :class:`Schedule` and
        :class:`ModeloDeadline` records selected here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import NoReturn

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.period import Period
from ...core.time.clock import now
from ...domain.deadlines.engine import compute_obligation_schedule, next_deadline
from ...domain.deadlines.models import ModeloDeadline, TaxpayerProfile
from ..operator_actions.preconditions import no_action_precondition_verdict
from .abort import WorkflowAbortReason
from .errors import WorkflowAbortSignalError
from .protocols import DeadlineEngineProtocol
from .run_models import WorkflowStage, WorkflowStep


def resolve_deadline_stage_obligation(
    deadline_engine: DeadlineEngineProtocol,
    profile: TaxpayerProfile,
    *,
    target_modelo: str | None,
    target_period: Period | None,
    today: date,
) -> ModeloDeadline | None:
    """Return the obligation the workflow deadline stage should evaluate.

    An exact work-unit target is addressed through
    :meth:`~domain.deadlines.engine.DeadlineEngine.target_obligation`, which
    reads the windows of the target's own filing year: a past period keeps its
    obligation after its window closes, and a fact the taxpayer has not
    answered does not rule it out. Without a target the stage takes the next
    open obligation of the current schedule.

    Args:
        deadline_engine: Deadline engine implementation that produces a
            :class:`Schedule`.
        profile: The :class:`TaxpayerProfile` used to compute obligations.
        target_modelo: Optional exact modelo filter for a work-unit target.
        target_period: Optional exact :class:`Period` filter for a work-unit
            target.
        today: Reference date for deadline status classification.

    Returns:
        The selected :class:`ModeloDeadline`, or ``None`` when no matching
        obligation exists.
    """
    if target_modelo is not None and target_period is not None:
        return deadline_engine.target_obligation(profile, modelo=target_modelo, period=target_period, today=today)
    return next_deadline(compute_obligation_schedule(deadline_engine, profile, today=today), today=today)


def abort_missing_deadline_obligation(
    *,
    started: datetime,
    steps: list[WorkflowStep],
) -> NoReturn:
    """Record and raise the deadline-stage no-obligation abort."""
    steps.append(
        WorkflowStep(
            stage=WorkflowStage.COMPUTING_DEADLINES,
            started_at=started,
            ended_at=now(),
            success=False,
            summary_locale_key="application.workflow.steps.deadline_missing",
            precondition_verdict=no_action_precondition_verdict(
                condition_id="workflow.deadline.filing_window_open",
                evidence_id="workflow.deadline.window",
                facts={"filing_window_open": False},
                provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                outcome=NoRecoveryOutcome.TERMINAL,
            ),
        ),
    )
    raise WorkflowAbortSignalError(reason=WorkflowAbortReason.NO_PENDING_OBLIGATION)


__all__ = ["abort_missing_deadline_obligation", "resolve_deadline_stage_obligation"]
