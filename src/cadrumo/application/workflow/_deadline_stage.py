"""Deadline resolution helpers for the workflow engine.

The deadline stage projects the active :class:`TaxpayerProfile` through the
domain deadline engine and selects one :class:`ModeloDeadline` from the computed
:class:`Schedule`. It keeps workflow verification and filing gates aligned with
the shared :func:`~domain.deadlines.compute_obligation_schedule` producer
used by state projections.

See Also:
    :class:`~application.workflow.WorkflowEngine`
        Composition root that calls these helpers from the
        ``COMPUTING_DEADLINES`` stage.
    :class:`~application.workflow.WorkflowPurpose`
        Purpose enum that decides whether a missing or late filing-window
        obligation aborts the run or remains informational context.
    :func:`~application.state_projection.build_pending_obligations`
        Projection-side consumer of the same deadline schedule producer.
    :mod:`domain.deadlines`
        Domain schedule authority that emits the :class:`Schedule` and
        :class:`ModeloDeadline` records selected here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import NoReturn

from ...core import ActionEvidenceProvenance, NoRecoveryOutcome, Period
from ...core.time import now as _utcnow
from ...domain.deadlines import (
    ModeloDeadline,
    NoDeadlineWindowsError,
    Schedule,
    TaxpayerProfile,
    compute_obligation_schedule,
    next_deadline,
)
from ..operator_actions import no_action_precondition_verdict
from ._errors import WorkflowAbortSignalError
from ._protocols import DeadlineEngineProtocol
from ._run_models import WorkflowAbortReason, WorkflowPurpose, WorkflowStage, WorkflowStep


def resolve_deadline_stage_obligation(
    deadline_engine: DeadlineEngineProtocol,
    profile: TaxpayerProfile,
    *,
    target_modelo: str | None,
    target_period: Period | None,
    today: date,
    purpose: WorkflowPurpose,
) -> ModeloDeadline | None:
    """Return the obligation the workflow deadline stage should evaluate.

    Args:
        deadline_engine: Deadline engine implementation that produces a
            :class:`Schedule`.
        profile: The :class:`TaxpayerProfile` used to compute obligations.
        target_modelo: Optional exact modelo filter for a work-unit target.
        target_period: Optional exact :class:`Period` filter for a work-unit
            target.
        today: Reference date for deadline status classification.
        purpose: Workflow purpose controlling late-local-file fallback behavior.

    Returns:
        The selected :class:`ModeloDeadline`, or ``None`` when no matching
        obligation exists.
    """
    schedule = _deadline_stage_schedule(
        deadline_engine,
        profile,
        target_modelo=target_modelo,
        target_period=target_period,
        today=today,
        purpose=purpose,
    )
    if target_modelo is not None and target_period is not None:
        matches = [o for o in schedule.obligations if o.modelo == target_modelo and o.period == target_period]
        return matches[0] if matches else None
    return next_deadline(schedule, today=today)


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
            ended_at=_utcnow(),
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


def _deadline_stage_schedule(
    deadline_engine: DeadlineEngineProtocol,
    profile: TaxpayerProfile,
    *,
    target_modelo: str | None,
    target_period: Period | None,
    today: date,
    purpose: WorkflowPurpose,
) -> Schedule:
    if (
        purpose is WorkflowPurpose.FILE
        and target_modelo is not None
        and target_period is not None
        and target_period.filing_year != today.year
    ):
        try:
            return deadline_engine.compute(profile, target_period.filing_year, today=today)
        except NoDeadlineWindowsError:
            return compute_obligation_schedule(deadline_engine, profile, today=today)
    return compute_obligation_schedule(deadline_engine, profile, today=today)


__all__ = ["abort_missing_deadline_obligation", "resolve_deadline_stage_obligation"]
