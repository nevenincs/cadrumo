"""Deadline decisions and context for the filing workflow."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from datetime import date, datetime

from ...core.filing_timeliness import FilingTimeliness
from ...core.modelo import Modelo
from ...core.operator_action_enums import (
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.deadlines.effective_close import resolve_effective_filing_deadline, resolve_filing_timeliness
from ...domain.deadlines.models import ModeloDeadline, ObligationStatus
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict
from .abort import WorkflowAbortReason
from .deadline_stage import abort_missing_deadline_obligation
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


def _filing_window_closed_on(
    *,
    obligation: ModeloDeadline,
    today: date,
    authority_operation: PinnedAuthorityOperation | None,
) -> date | None:
    """Return the effective close date when the window has genuinely closed, else ``None``.

    The obligation carries the close date the registry declares. A declaration
    whose window ends on a non-business day runs to the next business day (Ley
    39/2015 art. 30.5 through Ley 58/2003 art. 7.2), so comparing the declared
    date against ``today`` refuses a filing on the shifted day that the
    calculate posture, the declaration editor, the filing calendar and the
    filing receipt all call in time. The decision therefore reads the one
    shared effective-deadline projection, and the receipt's kept posture and
    this gate cannot disagree.

    An effective close the projection cannot establish -- an unknown projected
    close, or a window it does not resolve -- is not proof that the window has
    closed, so it is reported as still open rather than as a late filing.
    """
    if authority_operation is not None:
        pin = nullcontext(authority_operation)
    else:
        pin = bundled_indexed_authority().operation()
    with pin as pinned:
        if (
            resolve_filing_timeliness(
                str(obligation.modelo),
                obligation.period.filing_year,
                obligation.period,
                presented_on=today,
                operation=pinned,
            )
            is not FilingTimeliness.EXTEMPORANEA
        ):
            return None
        deadline = resolve_effective_filing_deadline(
            str(obligation.modelo),
            obligation.period.filing_year,
            obligation.period,
            operation=pinned,
        )
    return deadline.closes_on if deadline is not None else obligation.closes_on


def decide_filing_deadline(
    *,
    obligation: ModeloDeadline | None,
    target_modelo: str | None,
    target_period: Period | None,
    today: date,
    started: datetime,
    steps: list[WorkflowStep],
    purpose: WorkflowPurpose,
    authority_operation: PinnedAuthorityOperation | None = None,
) -> WorkflowDeadlineTarget:
    """Record the selected deadline and enforce the workflow purpose.

    ``authority_operation`` keeps the lateness decision on the caller's pinned
    authority generation; without one a bundled indexed operation is opened for
    the decision alone.
    """
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
                ended_at=now(),
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

    closed_on = _filing_window_closed_on(
        obligation=obligation,
        today=today,
        authority_operation=authority_operation,
    )
    if closed_on is not None:
        if target_modelo is not None and target_period is not None:
            # A targeted but closed-window obligation that genuinely
            # existed is filed locally and late (extemporánea, con recargo)
            # rather than refused; `work file` contacts AEAT zero times.
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=now(),
                    success=True,
                    summary_locale_key="application.workflow.steps.deadline_overdue",
                    details=WorkflowDeadlineContextDetails(
                        kind="deadline_context",
                        modelo=obligation.modelo,
                        period=obligation.period,
                        closes_on=closed_on,
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
                ended_at=now(),
                success=False,
                summary_locale_key="application.workflow.steps.deadline_closed",
                details=WorkflowDeadlineContextDetails(
                    kind="deadline_context",
                    modelo=obligation.modelo,
                    period=obligation.period,
                    closes_on=closed_on,
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
            ended_at=now(),
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
        elif obligation.adjusted_closes_on >= today:
            # The effective close, so the window is not reported shut on a day
            # the filer may still file.
            window_state = FilingWindowState.OPEN
        else:
            window_state = FilingWindowState.CLOSED
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=now(),
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
            ended_at=now(),
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
