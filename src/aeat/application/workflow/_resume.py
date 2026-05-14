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

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...domain.deadlines import FilingObligation
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
    obligation: FilingObligation
    aborted_reason: WorkflowAbortReason


class WorkflowResumeCommand(BaseModel):
    """Command contract for continuing an aborted workflow run."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    workflow_run_id: str = Field(min_length=16, max_length=16)


class WorkflowResumeLogFields(BaseModel):
    """Stable, non-secret log fields for workflow resume decisions."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    service_name: str = "workflow_resume"
    prior_workflow_run_id: str = Field(min_length=16, max_length=16)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    aborted_reason: WorkflowAbortReason

    def as_extra(self) -> dict[str, str]:
        return {
            "service_name": self.service_name,
            "prior_workflow_run_id": self.prior_workflow_run_id,
            "modelo": self.modelo,
            "period": self.period,
            "aborted_reason": self.aborted_reason.value,
        }


class WorkflowResumeResult(BaseModel):
    """Backend result contract for an accepted workflow resume request."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    prior_workflow_run_id: str = Field(min_length=16, max_length=16)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    obligation: FilingObligation
    aborted_reason: WorkflowAbortReason
    context: WorkflowResumeContext
    log_fields: WorkflowResumeLogFields


def resume_modelo_workflow(
    command: WorkflowResumeCommand,
    *,
    objects: SecureObjectRepository | None = None,
) -> WorkflowResumeResult:
    """Validate a workflow resume command and return a fresh-attempt contract.

    The caller is expected to drive
    :meth:`WorkflowEngine.run_for_period` with
    ``modelo=result.context.modelo``, ``period=result.context.period``, and
    ``resumed_from=result.context.resumed_from_run_id`` to produce a fresh
    :class:`WorkflowResult`.

    Raises:
        WorkflowError: When the prior run cannot be loaded.
        WorkflowResumeRefusedError: When the prior run is not in
            ``ABORTED`` state, was aborted for a non-resumable reason,
            or lacks an ``obligation``.
    """
    prior: WorkflowResult = load_run(command.workflow_run_id, objects=objects)

    if prior.final_stage is not WorkflowStage.ABORTED:
        raise WorkflowResumeRefusedError(
            f"workflow run {command.workflow_run_id!r} is in final_stage="
            f"{prior.final_stage.value!r}; only ABORTED runs may be resumed",
        )
    if prior.aborted_reason is None:  # defensive: validator enforces this
        raise WorkflowResumeRefusedError(
            f"workflow run {command.workflow_run_id!r} is ABORTED without aborted_reason; "
            f"refusing to resume an inconsistent record",
        )
    if prior.aborted_reason in _NON_RESUMABLE_REASONS:
        raise WorkflowResumeRefusedError(
            f"workflow run {command.workflow_run_id!r} aborted for "
            f"{prior.aborted_reason.value}; this reason is terminal by "
            f"design and may not be resumed",
        )
    if prior.obligation is None:
        raise WorkflowResumeRefusedError(
            f"workflow run {command.workflow_run_id!r} carries no obligation; cannot "
            f"determine (modelo, period) for a retry",
        )

    context = WorkflowResumeContext(
        resumed_from_run_id=prior.run_id,
        modelo=prior.obligation.modelo,
        period=prior.obligation.period,
        obligation=prior.obligation,
        aborted_reason=prior.aborted_reason,
    )
    log_fields = WorkflowResumeLogFields(
        prior_workflow_run_id=context.resumed_from_run_id,
        modelo=context.modelo,
        period=context.period,
        aborted_reason=context.aborted_reason,
    )
    return WorkflowResumeResult(
        prior_workflow_run_id=context.resumed_from_run_id,
        modelo=context.modelo,
        period=context.period,
        obligation=context.obligation,
        aborted_reason=context.aborted_reason,
        context=context,
        log_fields=log_fields,
    )


__all__ = [
    "WorkflowResumeCommand",
    "WorkflowResumeContext",
    "WorkflowResumeLogFields",
    "WorkflowResumeRefusedError",
    "WorkflowResumeResult",
    "resume_modelo_workflow",
]
