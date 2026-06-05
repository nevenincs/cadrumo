"""Workflow-resumption preconditions and context assembly.

Loads a prior :class:`WorkflowResult` by ``run_id`` and decides whether
the operator may start a fresh attempt against the same
``(modelo, period)`` axis. Returns a :class:`WorkflowResumeContext` the
caller hands to :meth:`WorkflowEngine.run_for_period` to drive the
new attempt.

The action is pure-local: no AEAT contact, no live read or write, no
mutation of the prior run record. Resuming a workflow is the operator
asking the local orchestrator to retry; whether that retry then
contacts AEAT depends on the engine, not on this action.

Resumability rules:

  * the prior result MUST carry ``final_stage = ABORTED`` — DONE
    results are already filed and cannot be retried; in-progress
    results are not surfaced through :func:`load_run` and so cannot
    reach this path.
  * the prior result's ``aborted_reason`` MUST NOT be terminal-by-
    design (``NO_PENDING_OBLIGATION``, ``ALREADY_FILED``,
    ``USER_CANCELLED``). Those abort reasons describe states where
    retrying would not produce a different outcome.
  * the prior result MUST carry an ``obligation`` — without it we
    cannot enumerate the ``(modelo, period)`` to retry against.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ...domain.deadlines import ModeloDeadline
from ._errors import WorkflowError
from ._models import WorkflowAbortReason, WorkflowResult, WorkflowStage
from ._persistence import list_runs, load_run


class WorkflowResumeRefusedError(WorkflowError):
    """Raised when a prior :class:`WorkflowResult` cannot be resumed."""


class WorkflowResumeRunAmbiguousError(WorkflowError):
    """Raised when natural-key resume matches more than one workflow run."""

    def __init__(
        self,
        *,
        modelo: str,
        period: str,
        candidates: tuple[WorkflowResumeRunCandidate, ...],
    ) -> None:
        self.modelo = modelo
        self.period = period
        self.candidates = candidates
        super().__init__(
            translated_message="application.workflow.errors.resume_run_ambiguous",
            context={
                "modelo": modelo,
                "period": period,
                "candidate_count": str(len(candidates)),
                "candidates": workflow_resume_candidate_lines(candidates),
            },
        )


_NON_RESUMABLE_REASONS: frozenset[WorkflowAbortReason] = frozenset(
    {
        WorkflowAbortReason.NO_PENDING_OBLIGATION,
        WorkflowAbortReason.ALREADY_FILED,
        WorkflowAbortReason.USER_CANCELLED,
    },
)


class WorkflowResumeRunCandidate(BaseModel):
    """Operator-facing workflow run candidate for natural-key resume guidance."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    run_id: str = Field(min_length=16, max_length=16)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    final_stage: str = Field(min_length=1, max_length=64)
    aborted_reason: str | None = None
    started_at: datetime


class WorkflowResumeContext(BaseModel):
    """Inputs the engine needs to start a fresh attempt over a prior run."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    resumed_from_run_id: str = Field(min_length=16, max_length=16)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    obligation: ModeloDeadline
    aborted_reason: WorkflowAbortReason


def resume_modelo_workflow(run_id: str) -> WorkflowResumeContext:
    """Validate that ``run_id`` may be resumed and return a fresh-attempt context.

    The caller is expected to drive
    :meth:`WorkflowEngine.run_for_period` with
    ``modelo=context.modelo`` and ``period=context.period`` to produce
    a fresh :class:`WorkflowResult`.

    Args:
        run_id: The 16-character hex run id of the prior aborted workflow
            run to resume.

    Returns:
        A :class:`WorkflowResumeContext` carrying the modelo, period,
        obligation, and aborted reason for the prior run.

    Raises:
        WorkflowResumeRefusedError: When the prior run is not in
            ``ABORTED`` state, was aborted for a non-resumable reason,
            or lacks an ``obligation``.
    """
    prior: WorkflowResult = load_run(run_id)

    if prior.final_stage is not WorkflowStage.ABORTED:
        raise WorkflowResumeRefusedError(
            translated_message="application.workflow.errors.resume_refused_not_aborted",
            context={"run_id": run_id, "final_stage": prior.final_stage.value},
        )
    if prior.aborted_reason is None:  # defensive: validator enforces this
        raise WorkflowResumeRefusedError(
            translated_message="application.workflow.errors.resume_refused_no_aborted_reason",
            context={"run_id": run_id},
        )
    if prior.aborted_reason in _NON_RESUMABLE_REASONS:
        raise WorkflowResumeRefusedError(
            translated_message="application.workflow.errors.resume_refused_terminal_reason",
            context={"run_id": run_id, "reason": prior.aborted_reason.value},
        )
    if prior.obligation is None:
        raise WorkflowResumeRefusedError(
            translated_message="application.workflow.errors.resume_refused_no_obligation",
            context={"run_id": run_id},
        )

    return WorkflowResumeContext(
        resumed_from_run_id=prior.run_id,
        modelo=prior.obligation.modelo,
        period=prior.obligation.period,
        obligation=prior.obligation,
        aborted_reason=prior.aborted_reason,
    )


def find_latest_run_for_period(*, modelo: str, period: str) -> WorkflowResult:
    """Return the most recent persisted workflow run for ``(modelo, period)``.

    A workflow run id is a 16-character hash an operator cannot derive
    by hand, so a caller that only knows the ``(modelo, period)`` of a
    work unit needs a way to resolve the run id. This helper scans the
    persisted run history and returns the newest run whose resolved
    obligation matches the supplied ``(modelo, period)``.

    The returned run is *not* gated for resumability — pass its
    ``run_id`` to :func:`resume_modelo_workflow`, which applies the
    resumability rules and produces a precise refusal if the latest
    run cannot be retried.

    Args:
        modelo: Target modelo identifier.
        period: Target workflow period token (e.g. ``"2026Q1"``).

    Returns:
        The newest matching :class:`WorkflowResult`.

    Raises:
        WorkflowError: When no persisted run targets ``(modelo, period)``.
    """
    matches = _runs_for_period(modelo=modelo, period=period)
    if not matches:
        raise WorkflowError(
            translated_message="application.workflow.errors.no_run_for_period",
            context={"modelo": modelo, "period": period},
        )
    return matches[0]


def find_unique_run_for_period(*, modelo: str, period: str) -> WorkflowResult:
    """Return one persisted run for ``(modelo, period)`` or refuse ambiguity.

    Natural-key resume is an operator-facing lookup. If more than one
    persisted run exists for the same workflow period, the caller must
    choose an exact run id instead of guessing which attempt to resume.
    """
    matches = _runs_for_period(modelo=modelo, period=period)
    if not matches:
        raise WorkflowError(
            translated_message="application.workflow.errors.no_run_for_period",
            context={"modelo": modelo, "period": period},
        )
    if len(matches) > 1:
        raise WorkflowResumeRunAmbiguousError(
            modelo=modelo,
            period=period,
            candidates=tuple(_workflow_resume_run_candidate(run) for run in matches),
        )
    return matches[0]


def workflow_resume_candidate_lines(candidates: tuple[WorkflowResumeRunCandidate, ...]) -> str:
    """Return tabular candidate guidance for ambiguous natural-key resume."""
    rows = [
        "candidates:",
        "run_id\tmodelo\tperiod\tfinal_stage\taborted_reason\tstarted_at",
    ]
    for candidate in candidates:
        rows.append(
            "\t".join(
                (
                    candidate.run_id,
                    candidate.modelo,
                    candidate.period,
                    candidate.final_stage,
                    candidate.aborted_reason or "",
                    candidate.started_at.isoformat(),
                )
            )
        )
    return "\n".join(rows)


def _runs_for_period(*, modelo: str, period: str) -> list[WorkflowResult]:
    matches = [
        run
        for run in list_runs()
        if run.obligation is not None and run.obligation.modelo == modelo and run.obligation.period == period
    ]
    matches.sort(key=lambda run: run.started_at, reverse=True)
    return matches


def _workflow_resume_run_candidate(run: WorkflowResult) -> WorkflowResumeRunCandidate:
    assert run.obligation is not None
    return WorkflowResumeRunCandidate(
        run_id=run.run_id,
        modelo=run.obligation.modelo,
        period=run.obligation.period,
        final_stage=run.final_stage.value,
        aborted_reason=run.aborted_reason.value if run.aborted_reason is not None else None,
        started_at=run.started_at,
    )


__all__ = [
    "WorkflowResumeContext",
    "WorkflowResumeRefusedError",
    "WorkflowResumeRunAmbiguousError",
    "WorkflowResumeRunCandidate",
    "find_latest_run_for_period",
    "find_unique_run_for_period",
    "resume_modelo_workflow",
    "workflow_resume_candidate_lines",
]
