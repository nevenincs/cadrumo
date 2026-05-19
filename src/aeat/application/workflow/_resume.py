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
from ._persistence import load_run


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


__all__ = [
    "WorkflowResumeContext",
    "WorkflowResumeRefusedError",
    "resume_modelo_workflow",
]
