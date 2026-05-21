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

from pydantic import BaseModel, ConfigDict, Field

from ...domain.deadlines import ModeloDeadline
from ._errors import WorkflowError
from ._models import WorkflowAbortReason, WorkflowResult, WorkflowStage
from ._persistence import list_runs, load_run


class WorkflowResumeRefusedError(WorkflowError):
    """Raised when a prior :class:`WorkflowResult` cannot be resumed."""


_NON_RESUMABLE_REASONS: frozenset[WorkflowAbortReason] = frozenset(
    {
        WorkflowAbortReason.NO_PENDING_OBLIGATION,
        WorkflowAbortReason.ALREADY_FILED,
        WorkflowAbortReason.USER_CANCELLED,
    },
)


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

    Raises:
        WorkflowError: When the prior run cannot be loaded.
        WorkflowResumeRefusedError: When the prior run is not in
            ``ABORTED`` state, was aborted for a non-resumable reason,
            or lacks an ``obligation``.
    """
    prior: WorkflowResult = load_run(run_id)

    if prior.final_stage is not WorkflowStage.ABORTED:
        raise WorkflowResumeRefusedError(
            f"workflow run {run_id!r} is in final_stage={prior.final_stage.value!r}; only ABORTED runs may be resumed",
        )
    if prior.aborted_reason is None:  # defensive: validator enforces this
        raise WorkflowResumeRefusedError(
            f"workflow run {run_id!r} is ABORTED without aborted_reason; refusing to resume an inconsistent record",
        )
    if prior.aborted_reason in _NON_RESUMABLE_REASONS:
        raise WorkflowResumeRefusedError(
            f"workflow run {run_id!r} aborted for "
            f"{prior.aborted_reason.value}; this reason is terminal by "
            f"design and may not be resumed",
        )
    if prior.obligation is None:
        raise WorkflowResumeRefusedError(
            f"workflow run {run_id!r} carries no obligation; cannot determine (modelo, period) for a retry",
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
    matches = [
        run
        for run in list_runs()
        if run.obligation is not None
        and run.obligation.modelo == modelo
        and run.obligation.period == period
    ]
    if not matches:
        raise WorkflowError(
            f"no persisted workflow run for modelo={modelo} period={period}; "
            "drive the workflow at least once before resuming",
        )
    # list_runs() already sorts newest-first; be explicit so the
    # contract does not depend on that ordering.
    matches.sort(key=lambda run: run.started_at, reverse=True)
    return matches[0]


__all__ = [
    "WorkflowResumeContext",
    "WorkflowResumeRefusedError",
    "find_latest_run_for_period",
    "resume_modelo_workflow",
]
