"""Deadline decisions and context for the filing workflow."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

from ...core.modelo import Modelo
from ...core.operator_action_enums import (
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ...core.period import Period
from ...core.time.clock import now as _utcnow
from ...domain.deadlines.models import ModeloDeadline, ObligationStatus
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict
from ._deadline_stage import abort_missing_deadline_obligation
from .abort import WorkflowAbortReason
from .engine_helpers import (
    DeadlineRole,
    FilingWindowState,
)
from .errors import WorkflowAbortSignalError, WorkflowError
from .run_models import (
    WorkflowDeadlineContextDetails,
    WorkflowObligationFacts,
    WorkflowPurpose,
    WorkflowStage,
    WorkflowStep,
)

type WorkflowDeadlineTarget = ModeloDeadline | WorkflowObligationFacts


def no_recovery_verdict(
    *,
    condition_id: str,
    evidence_id: str,
    provenance: ActionEvidenceProvenance,
    values: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome,
) -> PreconditionVerdict:
    """Build one closed non-actionable workflow precondition outcome."""
    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id=evidence_id,
        facts=values,
        provenance=provenance,
        outcome=outcome,
    )


def decide_filing_deadline(
    *,
    obligation: ModeloDeadline | None,
    target_modelo: str | None,
    target_period: Period | None,
    today: date,
    started: datetime,
    steps: list[WorkflowStep],
    purpose: WorkflowPurpose,
) -> WorkflowDeadlineTarget:
    """Record the selected deadline and enforce the workflow purpose."""
    if purpose is WorkflowPurpose.VERIFY:
        return _record_verify_deadline_context(
            obligation=obligation,
            target_modelo=target_modelo,
            target_period=target_period,
            today=today,
            started=started,
            steps=steps,
        )

    if obligation is None:
        abort_missing_deadline_obligation(started=started, steps=steps)

    if obligation.opens_on > today:
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=_utcnow(),
                success=False,
                summary_locale_key="application.workflow.steps.deadline_future",
                details=WorkflowDeadlineContextDetails(
                    kind="deadline_context",
                    modelo=obligation.modelo,
                    period=obligation.period,
                    opens_on=obligation.opens_on,
                    closes_on=obligation.closes_on,
                    filing_window=FilingWindowState.FUTURE,
                    deadline_role=DeadlineRole.BINDING,
                ),
                precondition_verdict=no_recovery_verdict(
                    condition_id="workflow.deadline.filing_window_open",
                    evidence_id="workflow.deadline.window",
                    provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                    values={
                        "filing_window": FilingWindowState.FUTURE.value,
                        "modelo": obligation.modelo.value,
                        "filing_year": obligation.period.filing_year,
                        "period_code": obligation.period.registry_token,
                    },
                    outcome=NoRecoveryOutcome.TERMINAL,
                ),
            ),
        )
        raise WorkflowAbortSignalError(reason=WorkflowAbortReason.NO_PENDING_OBLIGATION)

    if obligation.closes_on < today:
        if target_modelo is not None and target_period is not None:
            # A targeted but closed-window obligation that genuinely
            # existed is filed locally and late (extemporánea, con recargo)
            # rather than refused; `work file` contacts AEAT zero times.
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=True,
                    summary_locale_key="application.workflow.steps.deadline_overdue",
                    details=WorkflowDeadlineContextDetails(
                        kind="deadline_context",
                        modelo=obligation.modelo,
                        period=obligation.period,
                        closes_on=obligation.closes_on,
                        overdue=True,
                        extemporanea=True,
                    ),
                ),
            )
            return obligation
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=_utcnow(),
                success=False,
                summary_locale_key="application.workflow.steps.deadline_closed",
                details=WorkflowDeadlineContextDetails(
                    kind="deadline_context",
                    modelo=obligation.modelo,
                    period=obligation.period,
                    closes_on=obligation.closes_on,
                ),
                precondition_verdict=no_recovery_verdict(
                    condition_id="workflow.deadline.filing_window_open",
                    evidence_id="workflow.deadline.window",
                    provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                    values={
                        "filing_window": FilingWindowState.CLOSED.value,
                        "modelo": obligation.modelo.value,
                        "filing_year": obligation.period.filing_year,
                        "period_code": obligation.period.registry_token,
                    },
                    outcome=NoRecoveryOutcome.TERMINAL,
                ),
            ),
        )
        raise WorkflowAbortSignalError(reason=WorkflowAbortReason.DEADLINE_PASSED)

    steps.append(
        WorkflowStep(
            stage=WorkflowStage.COMPUTING_DEADLINES,
            started_at=started,
            ended_at=_utcnow(),
            success=True,
            summary_locale_key="application.workflow.steps.deadline_open",
            details=WorkflowDeadlineContextDetails(
                kind="deadline_context",
                modelo=obligation.modelo,
                period=obligation.period,
                opens_on=obligation.opens_on,
                closes_on=obligation.closes_on,
            ),
        ),
    )
    return obligation


def _record_verify_deadline_context(
    *,
    obligation: ModeloDeadline | None,
    target_modelo: str | None,
    target_period: Period | None,
    today: date,
    started: datetime,
    steps: list[WorkflowStep],
) -> WorkflowDeadlineTarget:
    """Record the filing-window state for a verify run without aborting.

    Verification of a calculation is independent of the AEAT filing
    calendar. This
    helper turns the ``COMPUTING_DEADLINES`` stage into a purely
    informational step for :attr:`WorkflowPurpose.VERIFY`: it never
    raises ``NO_PENDING_OBLIGATION`` or ``DEADLINE_PASSED``.

    When a scheduled obligation matches the verify target, its real
    filing window is surfaced as informational ``details``. When
    none matches, a context-only :class:`ModeloDeadline` is
    synthesised so the downstream draft/validation stages still
    have a ``(modelo, period)`` carrier; the synthetic record is
    explicitly marked ``NOT_APPLICABLE`` and never reaches a
    filing path.
    """
    if obligation is not None:
        if obligation.opens_on > today:
            window_state = FilingWindowState.FUTURE
        elif obligation.closes_on >= today:
            window_state = FilingWindowState.OPEN
        else:
            window_state = FilingWindowState.CLOSED
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary_locale_key="application.workflow.steps.deadline_informational",
                details=WorkflowDeadlineContextDetails(
                    kind="deadline_context",
                    modelo=obligation.modelo,
                    period=obligation.period,
                    opens_on=obligation.opens_on,
                    closes_on=obligation.closes_on,
                    filing_window=window_state,
                    deadline_role=DeadlineRole.INFORMATIONAL,
                ),
            ),
        )
        return obligation

    if target_modelo is None or target_period is None:
        raise WorkflowError(
            translated_message="errors.error.error_workflow",
            context={"workflow": "verify", "explicit_target_supplied": False},
        )
    synthetic = WorkflowObligationFacts(
        modelo=Modelo(target_modelo),
        period=target_period,
        opens_on=today,
        closes_on=today,
        status=ObligationStatus.NOT_APPLICABLE,
    )
    steps.append(
        WorkflowStep(
            stage=WorkflowStage.COMPUTING_DEADLINES,
            started_at=started,
            ended_at=_utcnow(),
            success=True,
            summary_locale_key="application.workflow.steps.deadline_absent",
            details=WorkflowDeadlineContextDetails(
                kind="deadline_context",
                modelo=Modelo(target_modelo),
                period=target_period,
                filing_window=FilingWindowState.ABSENT,
                deadline_role=DeadlineRole.INFORMATIONAL,
            ),
        ),
    )
    return synthetic


def persisted_obligation(obligation: WorkflowDeadlineTarget | None) -> WorkflowObligationFacts | None:
    """Return the locale-neutral durable projection for an in-flight deadline."""
    if obligation is None or isinstance(obligation, WorkflowObligationFacts):
        return obligation
    return WorkflowObligationFacts.from_deadline(obligation)
