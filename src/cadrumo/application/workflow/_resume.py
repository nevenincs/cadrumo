"""Workflow-resumption preconditions and context assembly.

Loads a prior :class:`application.workflow.WorkflowResult` by ``run_id``
and decides whether the operator may start a fresh attempt against the same
``(modelo, period)`` axis. Returns a
:class:`application.workflow.WorkflowResumeContext` the caller hands to
:meth:`application.workflow.WorkflowEngine.run_for_period` to drive the new
attempt.

The action is pure-local: no AEAT contact, no live read or write, no
mutation of the prior run record. Resuming a workflow is the operator
asking the local orchestrator to retry; whether that retry then
contacts AEAT depends on the engine, not on this action.

This module uses :class:`application.workflow.WorkflowResult`,
:class:`application.workflow.WorkflowEngine`, and
:class:`domain.deadlines.ModeloDeadline` for workflow resumption logic.

See Also:
    :class:`application.workflow.WorkflowResult`
        Persisted terminal run record inspected before any resume context is
        returned.
    :class:`application.workflow.WorkflowRunRepository`
        Secure run-history repository behind
        :func:`application.workflow.load_run` and
        :func:`application.workflow.list_runs`.
    :class:`application.workflow.WorkflowEngine`
        Fresh attempt executor that consumes
        :class:`application.workflow.WorkflowResumeContext` through
        ``run_for_period(resumed_from=...)``.
    :mod:`application.modelo`
        Owns visible modelo work addressing, revision selection, and conversion
        from registry filing periods to workflow periods.
    :mod:`entrypoints.cli._modelo_work_runs_cli`
        CLI surface that resolves operator resume selectors and emits
        :class:`application.workflow.WorkflowResumeTargetResolution`
        metadata.

Resumability rules:

  * the prior result MUST carry ``final_stage = ABORTED`` — DONE
    results are already filed and cannot be retried; in-progress
    results are not surfaced through
    :func:`application.workflow.load_run` and so cannot reach this path.
  * the prior result's ``aborted_reason`` MUST NOT be terminal-by-
    design (``NO_PENDING_OBLIGATION``, ``ALREADY_FILED``,
    ``USER_CANCELLED``). Those abort reasons describe states where
    retrying would not produce a different outcome.
  * the prior result MUST carry an ``obligation`` — without it we
    cannot enumerate the ``(modelo, period)`` to retry against.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import HEX_PATTERN_16, HEX_PATTERN_64, STRICT_FROZEN_CONFIG, Period
from ...core.identity import CalculationRevisionId, WorkUnitId
from ._errors import WorkflowError
from ._persistence import list_runs, load_run
from ._run_models import WorkflowAbortReason, WorkflowObligationFacts, WorkflowResult, WorkflowStage

if TYPE_CHECKING:
    #: ``RevisionId`` is an ``Annotated[str, ...]`` alias, but importing it from
    #: the registry package executes that package, and the whole registry --
    #: 153 modules -- comes with it. This module is imported eagerly by the
    #: workflow package, so a bare ``cadrumo --help`` paid a full registry
    #: import for one type alias used only in annotations.
    #:
    #: Safe to defer here and checked rather than assumed: this module carries
    #: ``from __future__ import annotations`` so annotations are never
    #: evaluated at runtime, the three functions annotated with it are
    #: undecorated, and the pydantic models in this module use
    #: ``CalculationRevisionId`` instead -- a pydantic field WOULD need the
    #: symbol at model-build time and could not be deferred this way.
    from ...domain.calculations.registry import RevisionId
    from ...domain.modelos import WorkUnit
    from ..modelo import ModeloResolvedRevisionProjection, ModeloWorkTarget


class WorkflowResumeRefusedError(WorkflowError):
    """Raised when a prior :class:`application.workflow.WorkflowResult` cannot be resumed."""


class WorkflowResumeRunAmbiguousError(WorkflowError):
    """Raised when natural-key resume matches more than one workflow run."""

    def __init__(
        self,
        *,
        modelo: str,
        period: Period,
        candidates: tuple[WorkflowResumeRunCandidate, ...],
    ) -> None:
        self.modelo = modelo
        self.period = period
        self.candidates = candidates
        super().__init__(
            translated_message="application.workflow.errors.resume_run_ambiguous",
            context={
                "modelo": modelo,
                "period": str(period),
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
_WORKFLOW_RUN_ID_RE = re.compile(HEX_PATTERN_16)
_WORK_UNIT_ID_RE = re.compile(HEX_PATTERN_64)


class WorkflowResumeRunCandidate(BaseModel):
    """Operator-facing workflow run candidate for natural-key resume guidance."""

    model_config = STRICT_FROZEN_CONFIG

    run_id: str = Field(min_length=16, max_length=16)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    final_stage: str = Field(min_length=1, max_length=64)
    aborted_reason: str | None = None
    started_at: datetime
    short_work_unit_id: str | None = None
    work_unit_id: WorkUnitId | None = None


class WorkflowResumeTargetResolution(BaseModel):
    """Resolved workflow-run target plus visible modelo work metadata.

    Carries the ``WorkflowResult.run_id`` value selected by direct run id,
    work-unit id, calculation-revision id, or visible modelo filing selector.
    Visible and exact modelo targets are resolved through
    :class:`application.modelo.ModeloVisibleFilingTarget` and
    :class:`application.modelo.ModeloExactWorkUnitTarget` before workflow
    run lookup.
    """

    model_config = STRICT_FROZEN_CONFIG

    run_id: str = Field(min_length=16, max_length=16)
    source: str = Field(min_length=1, max_length=64)
    modelo: str | None = None
    period: Period | None = None
    filing_year: int | None = None
    work_unit_id: WorkUnitId | None = None
    short_work_unit_id: str | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    short_calculation_revision_id: str | None = None


class WorkflowResumeContext(BaseModel):
    """Inputs the engine needs to start a fresh attempt over a prior run.

    Produced from a resumable :class:`application.workflow.WorkflowResult`
    and passed to
    :meth:`application.workflow.WorkflowEngine.run_for_period` by callers
    that launch the retry.
    """

    model_config = STRICT_FROZEN_CONFIG

    resumed_from_run_id: str = Field(min_length=16, max_length=16)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    obligation: WorkflowObligationFacts
    aborted_reason: WorkflowAbortReason


def resume_modelo_workflow(run_id: str) -> WorkflowResumeContext:
    """Validate that ``run_id`` may be resumed and return a fresh-attempt context.

    The caller is expected to drive
    :meth:`application.workflow.WorkflowEngine.run_for_period` with
    ``modelo=context.modelo`` and ``period=context.period`` to produce
    a fresh :class:`application.workflow.WorkflowResult`.

    Args:
        run_id: The 16-character hex run id of the prior aborted workflow
            run to resume.

    Returns:
        A :class:`application.workflow.WorkflowResumeContext` carrying the
        modelo, period, obligation, and aborted reason for the prior run.

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
            # BOTH message and translated_message, deliberately. The
            # operator-facing envelope resolves ``translated_message`` first
            # (``core.errors._registry.resolve_error_message``), so this
            # ``message`` changes nothing an operator sees -- it changes only
            # ``str(exc)``, which is what a traceback and a failing test's own
            # summary line show.
            #
            # Without it the failure line is the bare key, identical for every
            # non-resumable reason, with the discriminating one reachable only
            # through ``context["reason"]``. That is how two unrelated defects
            # come to present byte-identically and get triaged as one.
            f"workflow run {run_id} cannot be resumed: aborted as {prior.aborted_reason.value}",
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


def resolve_modelo_workflow_resume_target(
    *,
    target: str | None = None,
    workflow_run_id: str | None = None,
    work_unit_id: str | None = None,
    calculation_revision_id: CalculationRevisionId | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: Period | None = None,
    registry_revision_id: RevisionId | None = None,
    bucket_id: str | None = None,
    selector: object | None = None,
) -> WorkflowResumeTargetResolution:
    """Resolve the operator's resume address and return a target resolution.

    Exact run ids remain the direct path. Work-unit ids, calculation-revision
    ids, and visible modelo/year/period selectors resolve through the public
    modelo addressing facade before workflow run lookup, so this service does
    not duplicate modelo selector policy.

    Returns:
        A :class:`application.workflow.WorkflowResumeTargetResolution`
        carrying the selected run id and any resolved modelo work metadata.
    """
    clean_target = target.strip() if target is not None and target.strip() else None
    clean_run_id = workflow_run_id.strip() if workflow_run_id is not None and workflow_run_id.strip() else None
    clean_work_id = work_unit_id.strip() if work_unit_id is not None and work_unit_id.strip() else None
    clean_revision_id = (
        calculation_revision_id.strip()
        if calculation_revision_id is not None and calculation_revision_id.strip()
        else None
    )
    visible_supplied = any(value is not None for value in (modelo, year, period, registry_revision_id, bucket_id))
    exact_count = sum(value is not None for value in (clean_target, clean_run_id, clean_work_id, clean_revision_id))
    if exact_count > 1 or (clean_target is not None and visible_supplied):
        raise WorkflowError(translated_message="application.workflow.errors.resume_target_contradiction")

    if clean_run_id is not None:
        return _workflow_run_id_resolution(clean_run_id, source="workflow_run_id")
    if clean_target is not None:
        if _WORKFLOW_RUN_ID_RE.fullmatch(clean_target):
            return WorkflowResumeTargetResolution(run_id=clean_target, source="workflow_run_id")
        if _WORK_UNIT_ID_RE.fullmatch(clean_target):
            clean_work_id = clean_target
        else:
            raise WorkflowError(
                translated_message="application.workflow.errors.resume_target_invalid",
                context={"target": clean_target},
            )

    if clean_revision_id is not None:
        return _resolve_resume_from_calculation_revision(clean_revision_id)
    if clean_work_id is not None:
        return _resolve_resume_from_work_unit_id(clean_work_id, selector=selector)

    if visible_supplied:
        if modelo is None or year is None or period is None:
            raise WorkflowError(
                translated_message="application.workflow.errors.resume_visible_target_incomplete",
                context={
                    "modelo": modelo or "",
                    "year": "" if year is None else str(year),
                    "period": "" if period is None else str(period),
                },
            )
        return _resolve_resume_from_visible_target(
            modelo=modelo,
            year=year,
            period=period,
            registry_revision_id=registry_revision_id,
            bucket_id=bucket_id,
            selector=selector,
        )

    raise WorkflowError(translated_message="application.workflow.errors.resume_target_required")


def _workflow_run_id_resolution(run_id: str, *, source: str) -> WorkflowResumeTargetResolution:
    if not _WORKFLOW_RUN_ID_RE.fullmatch(run_id):
        raise WorkflowError(
            translated_message="application.workflow.errors.resume_run_id_invalid",
            context={"run_id": run_id},
        )
    return WorkflowResumeTargetResolution(run_id=run_id, source=source)


def _resolve_resume_from_calculation_revision(
    calculation_revision_id: CalculationRevisionId,
) -> WorkflowResumeTargetResolution:
    from ..modelo import get_calculation_revision, get_work_unit

    revision = get_calculation_revision(calculation_revision_id)
    work_unit = get_work_unit(revision.work_unit_id)
    return _resolve_resume_from_work_unit(
        work_unit,
        source="calculation_revision_id",
        calculation_revision_id=revision.calculation_revision_id,
    )


def _resolve_resume_from_work_unit_id(work_unit_id: str, *, selector: object | None) -> WorkflowResumeTargetResolution:
    from ..modelo import ModeloExactWorkUnitTarget, resolve_modelo_work_address_unit

    target = ModeloExactWorkUnitTarget(work_unit_id=work_unit_id)
    if selector is not None:
        _resolve_revision_for_resume_target(target=target, selector=selector)
    return _resolve_resume_from_work_unit(
        resolve_modelo_work_address_unit(target.to_work_address()),
        source="work_unit_id",
        latest=True,
    )


def _resolve_resume_from_visible_target(
    *,
    modelo: str,
    year: int,
    period: Period,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None,
    selector: object | None,
) -> WorkflowResumeTargetResolution:
    from ..modelo import ModeloExactWorkUnitTarget, ModeloVisibleFilingTarget, resolve_modelo_work_address_unit

    filing_period = _resolve_visible_period(modelo=modelo, year=year, period=period)
    target = ModeloVisibleFilingTarget(
        modelo=modelo,
        filing_year=year,
        period=filing_period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
    )
    if selector is not None:
        revision = _resolve_revision_for_resume_target(target=target, selector=selector)
        exact_target = ModeloExactWorkUnitTarget(work_unit_id=revision.work_unit_id)
        resolution = _resolve_resume_from_work_unit(
            resolve_modelo_work_address_unit(exact_target.to_work_address()),
            source="visible_target_revision_selector",
        )
        return resolution.model_copy(
            update={
                "source": "visible_target_revision_selector",
                "calculation_revision_id": revision.calculation_revision_id,
                "short_calculation_revision_id": revision.short_calculation_revision_id,
            },
        )
    return resolve_modelo_workflow_run_for_resume(
        target,
        source="visible_target",
    )


def _resolve_revision_for_resume_target(
    *,
    target: ModeloWorkTarget,
    selector: object,
) -> ModeloResolvedRevisionProjection:
    from ..modelo import ModeloCalculationRevisionSelector, ModeloRevisionPick, resolve_modelo_revision_pick

    try:
        revision_selector = (
            selector
            if isinstance(selector, ModeloCalculationRevisionSelector)
            else ModeloCalculationRevisionSelector(str(selector).strip())
        )
    except ValueError as exc:
        raise WorkflowError(
            translated_message="application.workflow.errors.resume_revision_selector_invalid",
            context={"selector": str(selector)},
        ) from exc
    return resolve_modelo_revision_pick(target=target, pick=ModeloRevisionPick(selector=revision_selector))


def _resolve_visible_period(*, modelo: str, year: int, period: Period) -> Period:
    if period.filing_year != year:
        raise WorkflowError(
            translated_message="application.workflow.errors.resume_visible_target_incomplete",
            context={"modelo": modelo, "year": str(year), "period": str(period)},
        )
    return period


def find_latest_run_for_period(*, modelo: str, period: Period) -> WorkflowResult:
    """Return the most recent persisted workflow run for ``(modelo, period)``.

    A workflow run id is a 16-character hash an operator cannot derive
    by hand, so a caller that only knows the ``(modelo, period)`` of a
    work unit needs a way to resolve the run id. This helper scans the
    persisted run history and returns the newest run whose resolved
    obligation matches the supplied ``(modelo, period)``.

    The returned run is *not* gated for resumability — pass its
    ``run_id`` to :func:`application.workflow.resume_modelo_workflow`, which
    applies the resumability rules and produces a precise refusal if the latest
    run cannot be retried.

    Args:
        modelo: Target modelo identifier.
        period: Target typed workflow period.

    Returns:
        The newest matching :class:`application.workflow.WorkflowResult`.

    Raises:
        WorkflowError: When no persisted run targets ``(modelo, period)``.
    """
    matches = _runs_for_period(modelo=modelo, period=period)
    if not matches:
        raise WorkflowError(
            translated_message="application.workflow.errors.no_run_for_period",
            context={"modelo": modelo, "period": str(period)},
        )
    return matches[0]


def find_unique_run_for_period(
    *,
    modelo: str,
    period: Period,
    work_unit_id: str | None = None,
    short_work_unit_id: str | None = None,
) -> WorkflowResult:
    """Return a workflow run for ``(modelo, period)`` or refuse ambiguity.

    Natural-key resume is an operator-facing lookup. If more than one
    persisted run exists for the same workflow period, the caller must
    choose an exact run id instead of guessing which attempt to resume.

    Returns:
        The unique matching :class:`application.workflow.WorkflowResult`.
    """
    matches = _runs_for_period(modelo=modelo, period=period)
    if not matches:
        raise WorkflowError(
            translated_message="application.workflow.errors.no_run_for_period",
            context={"modelo": modelo, "period": str(period)},
        )
    if len(matches) > 1:
        raise WorkflowResumeRunAmbiguousError(
            modelo=modelo,
            period=period,
            candidates=tuple(
                _workflow_resume_run_candidate(
                    run,
                    work_unit_id=work_unit_id,
                    short_work_unit_id=short_work_unit_id,
                )
                for run in matches
            ),
        )
    return matches[0]


def resolve_modelo_workflow_run_for_resume(
    target: ModeloWorkTarget,
    *,
    source: str = "modelo_work_target",
) -> WorkflowResumeTargetResolution:
    """Resolve a modelo work target to a resume target resolution.

    The modelo application facade remains the owner of visible filing
    target lookup and registry-period to workflow-period conversion.
    Natural-key targets require exactly one persisted workflow run for
    that period; exact work-unit targets select the newest run for the
    resolved workflow period.

    Returns:
        A :class:`application.workflow.WorkflowResumeTargetResolution`
        suitable for passing to :func:`application.workflow.resume_modelo_workflow`.
    """
    from ..modelo import ModeloExactWorkUnitTarget, ModeloWorkAddress, resolve_modelo_work_target

    resolution = resolve_modelo_work_target(target)
    assert resolution.work_unit is not None
    exact_target = isinstance(target, ModeloExactWorkUnitTarget) or (
        isinstance(target, ModeloWorkAddress) and target.work_unit_id is not None
    )
    return _resolve_resume_from_work_unit(
        resolution.work_unit,
        source=source,
        latest=exact_target,
    )


def resolve_modelo_visible_workflow_run_for_resume(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_revision_id: RevisionId | None = None,
    bucket_id: str | None = None,
) -> WorkflowResumeTargetResolution:
    """Resolve natural modelo filing selectors to a resume target resolution.

    The selector is represented as a
    :class:`application.modelo.ModeloVisibleFilingTarget` before delegation
    to the shared modelo addressing facade.

    Returns:
        A :class:`WorkflowResumeTargetResolution` for the visible filing target.
    """
    from ..modelo import ModeloVisibleFilingTarget

    return resolve_modelo_workflow_run_for_resume(
        ModeloVisibleFilingTarget(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            registry_revision_id=registry_revision_id,
            bucket_id=bucket_id,
        ),
    )


def resolve_modelo_exact_workflow_run_for_resume(
    *,
    work_unit_id: str,
    bucket_id: str | None = None,
) -> WorkflowResumeTargetResolution:
    """Resolve an exact work-unit id to a resume target resolution.

    Exact work-unit ids are represented as
    :class:`application.modelo.ModeloExactWorkUnitTarget` values before
    workflow run lookup.

    Returns:
        A :class:`WorkflowResumeTargetResolution` for the exact work-unit id.
    """
    from ..modelo import ModeloExactWorkUnitTarget

    return resolve_modelo_workflow_run_for_resume(
        ModeloExactWorkUnitTarget(work_unit_id=work_unit_id, bucket_id=bucket_id),
    )


def _resolve_resume_from_work_unit(
    work_unit: WorkUnit,
    *,
    source: str,
    latest: bool = False,
    calculation_revision_id: CalculationRevisionId | None = None,
) -> WorkflowResumeTargetResolution:
    from ..modelo import project_modelo_work_unit, workflow_period_for_work_unit

    projection = project_modelo_work_unit(work_unit)
    workflow_period = workflow_period_for_work_unit(work_unit)
    if latest:
        run = find_latest_run_for_period(modelo=projection.modelo, period=workflow_period)
    else:
        run = find_unique_run_for_period(
            modelo=projection.modelo,
            period=workflow_period,
            work_unit_id=projection.work_unit_id,
            short_work_unit_id=projection.short_work_unit_id,
        )
    return WorkflowResumeTargetResolution(
        run_id=run.run_id,
        source=source,
        modelo=projection.modelo,
        period=workflow_period,
        filing_year=projection.filing_year,
        work_unit_id=projection.work_unit_id,
        short_work_unit_id=projection.short_work_unit_id,
        calculation_revision_id=calculation_revision_id,
        short_calculation_revision_id=calculation_revision_id[-12:] if calculation_revision_id is not None else None,
    )


def workflow_resume_candidate_lines(candidates: tuple[WorkflowResumeRunCandidate, ...]) -> str:
    """Return tabular candidate guidance for ambiguous natural-key resume.

    Args:
        candidates: :class:`WorkflowResumeRunCandidate` rows collected from the
            ambiguous workflow-period lookup.
    """
    rows = [
        "candidates:",
        "run_id\tmodelo\tperiod\tfinal_stage\taborted_reason\tstarted_at\tshort_work_unit_id\twork_unit_id",
    ]
    for candidate in candidates:
        rows.append(
            "\t".join(
                (
                    candidate.run_id,
                    candidate.modelo,
                    str(candidate.period),
                    candidate.final_stage,
                    candidate.aborted_reason or "",
                    candidate.started_at.isoformat(),
                    candidate.short_work_unit_id or "",
                    candidate.work_unit_id or "",
                ),
            ),
        )
    return "\n".join(rows)


def _runs_for_period(*, modelo: str, period: Period) -> list[WorkflowResult]:
    matches = [
        run
        for run in list_runs()
        if run.obligation is not None and run.obligation.modelo == modelo and run.obligation.period == period
    ]
    matches.sort(key=lambda run: run.started_at, reverse=True)
    return matches


def _workflow_resume_run_candidate(
    run: WorkflowResult,
    *,
    work_unit_id: str | None = None,
    short_work_unit_id: str | None = None,
) -> WorkflowResumeRunCandidate:
    assert run.obligation is not None
    return WorkflowResumeRunCandidate(
        run_id=run.run_id,
        modelo=run.obligation.modelo,
        period=run.obligation.period,
        final_stage=run.final_stage.value,
        aborted_reason=run.aborted_reason.value if run.aborted_reason is not None else None,
        started_at=run.started_at,
        work_unit_id=work_unit_id,
        short_work_unit_id=short_work_unit_id,
    )


__all__ = [
    "WorkflowResumeContext",
    "WorkflowResumeRefusedError",
    "WorkflowResumeRunAmbiguousError",
    "WorkflowResumeRunCandidate",
    "WorkflowResumeTargetResolution",
    "find_latest_run_for_period",
    "find_unique_run_for_period",
    "resolve_modelo_exact_workflow_run_for_resume",
    "resolve_modelo_visible_workflow_run_for_resume",
    "resolve_modelo_workflow_resume_target",
    "resolve_modelo_workflow_run_for_resume",
    "resume_modelo_workflow",
    "workflow_resume_candidate_lines",
]
