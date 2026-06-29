"""Deadline resolution helpers for the workflow engine.

The deadline stage projects the active :class:`TaxpayerProfile` through the
domain deadline engine and selects one :class:`ModeloDeadline` from the computed
:class:`Schedule`. It keeps workflow verification and filing gates aligned with
the shared :func:`~aeat.domain.deadlines.compute_obligation_schedule` producer
used by state projections.

See Also:
    :class:`~aeat.application.workflow.WorkflowEngine`
        Composition root that calls these helpers from the
        ``COMPUTING_DEADLINES`` stage.
    :class:`~aeat.application.workflow.WorkflowPurpose`
        Purpose enum that decides whether a missing or late filing-window
        obligation aborts the run or remains informational context.
    :func:`~aeat.application.state_projection.build_pending_obligations`
        Projection-side consumer of the same deadline schedule producer.
    :mod:`aeat.domain.deadlines`
        Domain schedule authority that emits the :class:`Schedule` and
        :class:`ModeloDeadline` records selected here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import NoReturn

from ...core import Period
from ...core.time import now as _utcnow
from ...domain.deadlines import (
    ModeloDeadline,
    NoDeadlineWindowsError,
    Schedule,
    TaxpayerProfile,
    compute_obligation_schedule,
    next_deadline,
)
from ._engine_helpers import summary_text as _summary_text
from ._errors import WorkflowAbortSignalError
from ._models import WorkflowAbortReason, WorkflowPurpose, WorkflowStage, WorkflowStep
from ._protocols import DeadlineEngineProtocol

_MISSING_OBLIGATION_SUMMARY = (
    "No pending filing obligation for this modelo/period at the current date "
    "(the AEAT filing-obligation window is not open). Filing-to-fichero does "
    "not require this step: export the verified-complete revision with "
    "'aeat app modelo export' — that is the local finish line. 'work file' "
    "is the optional internal mark-as-filed step for when the obligation window is open."
)


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
    summary = _summary_text(_MISSING_OBLIGATION_SUMMARY)
    steps.append(
        WorkflowStep(
            stage=WorkflowStage.COMPUTING_DEADLINES,
            started_at=started,
            ended_at=_utcnow(),
            success=False,
            summary=summary,
        ),
    )
    raise WorkflowAbortSignalError(
        reason=WorkflowAbortReason.NO_PENDING_OBLIGATION,
        summary=summary,
    )


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
