"""Workflow-resumption preconditions and context assembly.

Captures a prior :class:`application.workflow.run_models.WorkflowResult` through
explicit profile-bound ports and decides whether the operator may start a fresh attempt against the same
``(modelo, period)`` axis. Returns a
:class:`application.workflow.resume.WorkflowResumeContext` the caller hands to
:meth:`application.workflow.engine.WorkflowEngine.run_for_period` to drive the new
attempt.

The action is pure-local: no AEAT contact, no live read or write, no
mutation of the prior run record. Resuming a workflow is the operator
asking the local orchestrator to retry; whether that retry then
contacts AEAT depends on the engine, not on this action.

This module uses :class:`application.workflow.run_models.WorkflowResult`,
:class:`application.workflow.engine.WorkflowEngine`, and
:class:`domain.deadlines.models.ModeloDeadline` for workflow resumption logic.

See Also:
    :class:`application.workflow.run_models.WorkflowResult`
        Persisted terminal run record inspected before any resume context is
        returned.
    :class:`application.workflow.persistence.WorkflowRunRepository`
        Secure run-history repository behind
        :func:`application.workflow.persistence.load_run` and
        :func:`application.workflow.persistence.list_runs`.
    :class:`application.workflow.engine.WorkflowEngine`
        Fresh attempt executor that consumes
        :class:`application.workflow.resume.WorkflowResumeContext` through
        ``run_for_period(resumed_from=...)``.
    :mod:`application.modelo`
        Owns visible modelo work addressing, revision selection, and conversion
        from registry filing periods to workflow periods.
    :mod:`entrypoints.cli._modelo_work_runs_cli`
        CLI surface that resolves operator resume selectors and emits
        :class:`application.workflow.resume.WorkflowResumeTargetResolution`
        metadata.

Resumability rules:

  * the prior result MUST carry ``final_stage = ABORTED`` — DONE
    results are already filed and cannot be retried; in-progress
    results are not surfaced through
    :func:`application.workflow.persistence.load_run` and so cannot reach this path.
  * the prior result's ``aborted_reason`` MUST NOT be terminal-by-
    design (``NO_PENDING_OBLIGATION``, ``ALREADY_FILED``,
    ``USER_CANCELLED``). Those abort reasons describe states where
    retrying would not produce a different outcome.
  * the prior result MUST carry an ``obligation`` — without it we
    cannot enumerate the ``(modelo, period)`` to retry against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.hex import HEX_PATTERN_16, HEX_PATTERN_64
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..modelo.calculation_action_ports import CalculationActionPorts
from .abort import WorkflowAbortReason
from .errors import WorkflowError
from .run_models import WorkflowObligationFacts, WorkflowResult, WorkflowStage
from .run_read_ports import WorkflowRunReader

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
    from ...domain.calculations.registry.ids import RevisionId
    from ...domain.modelos.work_unit import WorkUnit
    from ..modelo.work_addressing import ModeloResolvedRevisionProjection, ModeloWorkTarget


class WorkflowResumeRefusalReason(StrEnum):
    """Closed reasons for refusing a captured run's resume context."""

    NOT_ABORTED = "not_aborted"
    NO_ABORTED_REASON = "no_aborted_reason"
    TERMINAL_REASON = "terminal_reason"
    NO_OBLIGATION = "no_obligation"


class WorkflowResumeRefusedError(WorkflowError):
    """Raised when a prior :class:`application.workflow.run_models.WorkflowResult` cannot be resumed."""

    def __init__(self, *, reason: WorkflowResumeRefusalReason, prior: WorkflowResult) -> None:
        """Retain a typed reason while preserving canonical localized guidance."""
        self.reason = reason
        super().__init__(
            f"workflow run {prior.run_id} cannot be resumed: {reason.value}",
            translated_message=f"application.workflow.errors.resume_refused_{reason.value}",
            context={
                "run_id": prior.run_id,
                "final_stage": prior.final_stage.value,
                "reason": prior.aborted_reason.value if prior.aborted_reason is not None else "",
            },
        )


class WorkflowResumeRunAmbiguousError(WorkflowError):
    """Raised when natural-key resume matches more than one workflow run."""

    def __init__(
        self,
        *,
        modelo: str,
        period: Period,
        candidates: tuple[WorkflowResumeRunCandidate, ...],
    ) -> None:
        """Capture the ambiguous modelo, period, and matching run candidates."""
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


def _captured_work_catalogue(ports: CalculationActionPorts, bucket_id: str | None) -> tuple[WorkUnitCatalogue, str]:
    """Capture only the catalogue supplied by the profile-bound composition."""
    repository = ports.work_lifecycle_ports.work_unit_repository
    resolved_bucket = repository.bucket_id
    if resolved_bucket is None:
        raise WorkflowError("workflow resume requires its bound profile catalogue")
    if bucket_id is not None and bucket_id != resolved_bucket:
        raise WorkflowError("workflow resume requires its bound profile catalogue")
    catalogue = repository.load()
    if any(unit.bucket_id != resolved_bucket for unit in catalogue):
        raise WorkflowError("workflow resume catalogue contains a foreign profile")
    return catalogue, resolved_bucket


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
    :class:`application.modelo.work_addressing.ModeloVisibleFilingTarget` and
    :class:`application.modelo.work_addressing.ModeloExactWorkUnitTarget` before workflow
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

    Produced from a resumable :class:`application.workflow.run_models.WorkflowResult`
    and passed to
    :meth:`application.workflow.engine.WorkflowEngine.run_for_period` by callers
    that launch the retry.
    """

    model_config = STRICT_FROZEN_CONFIG

    resumed_from_run_id: str = Field(min_length=16, max_length=16)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    obligation: WorkflowObligationFacts
    aborted_reason: WorkflowAbortReason


@dataclass(frozen=True, slots=True)
class WorkflowResumeSelection:
    """A selected address and the same immutable record used to resolve it."""

    resolution: WorkflowResumeTargetResolution
    prior: WorkflowResult

    def __post_init__(self) -> None:
        """Keep the selector metadata bound to the exact captured prior run."""
        if self.resolution.run_id != self.prior.run_id:
            raise ValueError("workflow resume selection names another run")
        obligation = self.prior.obligation
        if self.resolution.period is not None and (
            obligation is None
            or obligation.period != self.resolution.period
            or obligation.modelo != self.resolution.modelo
        ):
            raise ValueError("workflow resume selection differs from its captured obligation")


@dataclass(frozen=True)
class _ResumeTargetInputs:
    """Normalised operator selectors used by the unified resume resolver."""

    target: str | None
    workflow_run_id: str | None
    work_unit_id: str | None
    calculation_revision_id: CalculationRevisionId | None
    modelo: str | None
    year: int | None
    period: Period | None
    registry_revision_id: RevisionId | None
    bucket_id: str | None
    selector: object | None
    visible_supplied: bool


def resume_modelo_workflow(prior: WorkflowResult) -> WorkflowResumeContext:
    """Validate a captured run and return its fresh-attempt context.

    The caller is expected to drive
    :meth:`application.workflow.engine.WorkflowEngine.run_for_period` with
    ``modelo=context.modelo`` and ``period=context.period`` to produce
    a fresh :class:`application.workflow.run_models.WorkflowResult`.

    Args:
        prior: The exact immutable record captured by target resolution.

    Returns:
        A :class:`application.workflow.resume.WorkflowResumeContext` carrying the
        modelo, period, obligation, and aborted reason for the prior run.

    Raises:
        WorkflowResumeRefusedError: When the prior run is not in
            ``ABORTED`` state, was aborted for a non-resumable reason,
            or lacks an ``obligation``.
    """
    reason = workflow_resume_refusal_reason(
        final_stage=prior.final_stage,
        aborted_reason=prior.aborted_reason,
        has_obligation=prior.obligation is not None,
    )
    if reason is not None:
        raise WorkflowResumeRefusedError(reason=reason, prior=prior)
    if prior.obligation is None or prior.aborted_reason is None:
        raise WorkflowError("resumability policy returned incomplete context")

    return WorkflowResumeContext(
        resumed_from_run_id=prior.run_id,
        modelo=prior.obligation.modelo,
        period=prior.obligation.period,
        obligation=prior.obligation,
        aborted_reason=prior.aborted_reason,
    )


def workflow_resume_refusal_reason(
    *, final_stage: WorkflowStage, aborted_reason: WorkflowAbortReason | None, has_obligation: bool
) -> WorkflowResumeRefusalReason | None:
    """Classify captured terminal facts through the shared resumability policy."""
    if final_stage is not WorkflowStage.ABORTED:
        return WorkflowResumeRefusalReason.NOT_ABORTED
    if aborted_reason is None:
        return WorkflowResumeRefusalReason.NO_ABORTED_REASON
    if aborted_reason in _NON_RESUMABLE_REASONS:
        return WorkflowResumeRefusalReason.TERMINAL_REASON
    if not has_obligation:
        return WorkflowResumeRefusalReason.NO_OBLIGATION
    return None


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
    ports: CalculationActionPorts,
    runs: WorkflowRunReader,
) -> WorkflowResumeSelection:
    """Resolve an address and retain the exact record used by that lookup.

    Exact run ids remain the direct path. Work-unit ids, calculation-revision
    ids, and visible modelo/year/period selectors resolve through the public
    modelo addressing facade before workflow run lookup, so this service does
    not duplicate modelo selector policy.

    Returns:
        A selection containing the resolved address and its captured record.
    """
    inputs = _resume_target_inputs(
        target=target,
        workflow_run_id=workflow_run_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
        selector=selector,
    )
    _reject_resume_target_contradiction(inputs)
    inputs = _classify_resume_target(inputs)

    if inputs.workflow_run_id is not None:
        resolution = _workflow_run_id_resolution(inputs.workflow_run_id, source="workflow_run_id")
        return WorkflowResumeSelection(resolution, runs.load(resolution.run_id))
    if inputs.calculation_revision_id is not None:
        return _resolve_resume_from_calculation_revision(inputs.calculation_revision_id, ports=ports, runs=runs)
    if inputs.work_unit_id is not None:
        return _resolve_resume_from_work_unit_id(inputs.work_unit_id, selector=inputs.selector, ports=ports, runs=runs)
    if inputs.visible_supplied:
        return _resolve_resume_from_visible_inputs(inputs, ports=ports, runs=runs)
    raise WorkflowError(translated_message="application.workflow.errors.resume_target_required")


def _resume_target_inputs(
    *,
    target: str | None,
    workflow_run_id: str | None,
    work_unit_id: str | None,
    calculation_revision_id: CalculationRevisionId | None,
    modelo: str | None,
    year: int | None,
    period: Period | None,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None,
    selector: object | None,
) -> _ResumeTargetInputs:
    """Normalise optional exact ids while retaining visible-selector presence."""
    clean_target = _clean_resume_id(target)
    clean_run_id = _clean_resume_id(workflow_run_id)
    clean_work_id = _clean_resume_id(work_unit_id)
    clean_revision_id = _clean_resume_id(calculation_revision_id)
    return _ResumeTargetInputs(
        target=clean_target,
        workflow_run_id=clean_run_id,
        work_unit_id=clean_work_id,
        calculation_revision_id=clean_revision_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
        selector=selector,
        visible_supplied=any(value is not None for value in (modelo, year, period, registry_revision_id, bucket_id)),
    )


def _clean_resume_id(value: str | None) -> str | None:
    """Return a stripped id, treating whitespace-only input as absent."""
    if value is None:
        return None
    return value.strip() or None


def _reject_resume_target_contradiction(inputs: _ResumeTargetInputs) -> None:
    """Refuse multiple exact addresses or an exact plus visible address."""
    exact_count = sum(
        value is not None
        for value in (inputs.target, inputs.workflow_run_id, inputs.work_unit_id, inputs.calculation_revision_id)
    )
    if exact_count > 1 or (inputs.target is not None and inputs.visible_supplied):
        raise WorkflowError(translated_message="application.workflow.errors.resume_target_contradiction")


def _classify_resume_target(inputs: _ResumeTargetInputs) -> _ResumeTargetInputs:
    """Map the generic target token onto its canonical exact-id field."""
    if inputs.target is None:
        return inputs
    target = validate_workflow_resume_target_token(inputs.target)
    if _WORKFLOW_RUN_ID_RE.fullmatch(target):
        return replace(inputs, workflow_run_id=target)
    return replace(inputs, work_unit_id=target)


def validate_workflow_resume_target_token(value: str) -> str:
    """Validate an exact CLI address without loading private workflow history."""
    target = value.strip()
    if _WORKFLOW_RUN_ID_RE.fullmatch(target) or _WORK_UNIT_ID_RE.fullmatch(target):
        return target
    raise WorkflowError(
        translated_message="application.workflow.errors.resume_target_invalid",
        context={"target": value},
    )


def _resolve_resume_from_visible_inputs(
    inputs: _ResumeTargetInputs,
    *,
    ports: CalculationActionPorts,
    runs: WorkflowRunReader,
) -> WorkflowResumeSelection:
    """Validate and resolve a visible modelo filing selector."""
    if inputs.modelo is None or inputs.year is None or inputs.period is None:
        raise WorkflowError(
            translated_message="application.workflow.errors.resume_visible_target_incomplete",
            context={
                "modelo": inputs.modelo or "",
                "year": "" if inputs.year is None else str(inputs.year),
                "period": "" if inputs.period is None else str(inputs.period),
            },
        )
    return _resolve_resume_from_visible_target(
        modelo=inputs.modelo,
        year=inputs.year,
        period=inputs.period,
        registry_revision_id=inputs.registry_revision_id,
        bucket_id=inputs.bucket_id,
        selector=inputs.selector,
        ports=ports,
        runs=runs,
    )


def _workflow_run_id_resolution(run_id: str, *, source: str) -> WorkflowResumeTargetResolution:
    if not _WORKFLOW_RUN_ID_RE.fullmatch(run_id):
        raise WorkflowError(
            translated_message="application.workflow.errors.resume_run_id_invalid",
            context={"run_id": run_id},
        )
    return WorkflowResumeTargetResolution(run_id=run_id, source=source)


def _resolve_resume_from_calculation_revision(
    calculation_revision_id: CalculationRevisionId,
    *,
    ports: CalculationActionPorts,
    runs: WorkflowRunReader,
) -> WorkflowResumeSelection:
    from ..modelo.calculation_actions import get_recorded_calculation_revision
    from ..modelo.work_lifecycle import get_work_unit

    revision = get_recorded_calculation_revision(calculation_revision_id, ports=ports)
    work_unit = get_work_unit(revision.work_unit_id, ports=ports.work_lifecycle_ports)
    return _resolve_resume_from_work_unit(
        work_unit,
        source="calculation_revision_id",
        calculation_revision_id=revision.calculation_revision_id,
        runs=runs,
    )


def _resolve_resume_from_work_unit_id(
    work_unit_id: str,
    *,
    selector: object | None,
    ports: CalculationActionPorts,
    runs: WorkflowRunReader,
) -> WorkflowResumeSelection:
    from ..modelo.work_addressing import ModeloExactWorkUnitTarget, resolve_modelo_work_address_unit

    target = ModeloExactWorkUnitTarget(work_unit_id=work_unit_id)
    catalogue, bucket_id = _captured_work_catalogue(ports, None)
    if selector is not None:
        _resolve_revision_for_resume_target(
            target=target,
            selector=selector,
            catalogue=catalogue,
            bucket_id=bucket_id,
            ports=ports,
        )
    return _resolve_resume_from_work_unit(
        resolve_modelo_work_address_unit(target.to_work_address(), catalogue=catalogue, bucket_id=bucket_id),
        source="work_unit_id",
        latest=True,
        runs=runs,
    )


def _resolve_resume_from_visible_target(
    *,
    modelo: str,
    year: int,
    period: Period,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None,
    selector: object | None,
    ports: CalculationActionPorts,
    runs: WorkflowRunReader,
) -> WorkflowResumeSelection:
    from ..modelo.work_addressing import (
        ModeloExactWorkUnitTarget,
        ModeloVisibleFilingTarget,
        resolve_modelo_work_address_unit,
    )

    filing_period = _resolve_visible_period(modelo=modelo, year=year, period=period)
    target = ModeloVisibleFilingTarget(
        modelo=modelo,
        filing_year=year,
        period=filing_period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
    )
    catalogue, resolved_bucket_id = _captured_work_catalogue(ports, bucket_id)
    if selector is not None:
        revision = _resolve_revision_for_resume_target(
            target=target,
            selector=selector,
            catalogue=catalogue,
            bucket_id=resolved_bucket_id,
            ports=ports,
        )
        exact_target = ModeloExactWorkUnitTarget(work_unit_id=revision.work_unit_id)
        selection = _resolve_resume_from_work_unit(
            resolve_modelo_work_address_unit(
                exact_target.to_work_address(),
                catalogue=catalogue,
                bucket_id=resolved_bucket_id,
            ),
            source="visible_target_revision_selector",
            runs=runs,
        )
        return WorkflowResumeSelection(
            selection.resolution.model_copy(
                update={
                    "source": "visible_target_revision_selector",
                    "calculation_revision_id": revision.calculation_revision_id,
                    "short_calculation_revision_id": revision.short_calculation_revision_id,
                },
            ),
            selection.prior,
        )
    return resolve_modelo_workflow_run_for_resume(
        target,
        source="visible_target",
        catalogue=catalogue,
        bucket_id=resolved_bucket_id,
        runs=runs,
    )


def _resolve_revision_for_resume_target(
    *,
    target: ModeloWorkTarget,
    selector: object,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
    ports: CalculationActionPorts,
) -> ModeloResolvedRevisionProjection:
    from ..modelo.selectors import ModeloCalculationRevisionSelector
    from ..modelo.work_addressing import ModeloRevisionPick, resolve_modelo_revision_pick

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
    return resolve_modelo_revision_pick(
        target=target,
        pick=ModeloRevisionPick(selector=revision_selector),
        catalogue=catalogue,
        resolved_bucket_id=bucket_id,
        calculation_repository=ports.calculation_repository,
        operation=ports.operation,
    )


def _resolve_visible_period(*, modelo: str, year: int, period: Period) -> Period:
    if period.filing_year != year:
        raise WorkflowError(
            translated_message="application.workflow.errors.resume_visible_target_incomplete",
            context={"modelo": modelo, "year": str(year), "period": str(period)},
        )
    return period


def find_latest_run_for_period(*, modelo: str, period: Period, runs: WorkflowRunReader) -> WorkflowResult:
    """Return the most recent persisted workflow run for ``(modelo, period)``.

    A workflow run id is a 16-character hash an operator cannot derive
    by hand, so a caller that only knows the ``(modelo, period)`` of a
    work unit needs a way to resolve the run id. This helper scans the
    persisted run history and returns the newest run whose resolved
    obligation matches the supplied ``(modelo, period)``.

    The returned run is *not* gated for resumability — pass the captured record
    to :func:`application.workflow.resume.resume_modelo_workflow`, which
    applies the resumability rules and produces a precise refusal if the latest
    run cannot be retried.

    Args:
        modelo: Target modelo identifier.
        period: Target typed workflow period.
        runs: Explicit profile-bound reader used to capture candidate records.

    Returns:
        The newest matching :class:`application.workflow.run_models.WorkflowResult`.

    Raises:
        WorkflowError: When no persisted run targets ``(modelo, period)``.
    """
    matches = _runs_for_period(modelo=modelo, period=period, runs=runs)
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
    runs: WorkflowRunReader,
) -> WorkflowResult:
    """Return a workflow run for ``(modelo, period)`` or refuse ambiguity.

    Natural-key resume is an operator-facing lookup. If more than one
    persisted run exists for the same workflow period, the caller must
    choose an exact run id instead of guessing which attempt to resume.

    Returns:
        The unique matching :class:`application.workflow.run_models.WorkflowResult`.
    """
    matches = _runs_for_period(modelo=modelo, period=period, runs=runs)
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
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
    runs: WorkflowRunReader,
) -> WorkflowResumeSelection:
    """Resolve a modelo work target to a resume target resolution.

    The modelo application facade remains the owner of visible filing
    target lookup and registry-period to workflow-period conversion.
    Natural-key targets require exactly one persisted workflow run for
    that period; exact work-unit targets select the newest run for the
    resolved workflow period.

    Returns:
        A selection whose captured prior can be passed to
        :func:`application.workflow.resume.resume_modelo_workflow`.
    """
    from ..modelo.work_addressing import ModeloExactWorkUnitTarget, ModeloWorkAddress, resolve_modelo_work_target

    resolution = resolve_modelo_work_target(target, catalogue=catalogue, bucket_id=bucket_id)
    if resolution.work_unit is None:
        raise WorkflowError("a resolved modelo work target must carry the work unit the resume reads")
    exact_target = isinstance(target, ModeloExactWorkUnitTarget) or (
        isinstance(target, ModeloWorkAddress) and target.work_unit_id is not None
    )
    return _resolve_resume_from_work_unit(
        resolution.work_unit,
        source=source,
        latest=exact_target,
        runs=runs,
    )


def _resolve_resume_from_work_unit(
    work_unit: WorkUnit,
    *,
    source: str,
    latest: bool = False,
    calculation_revision_id: CalculationRevisionId | None = None,
    runs: WorkflowRunReader,
) -> WorkflowResumeSelection:
    from ..modelo.work_addressing import project_modelo_work_unit
    from ..modelo.workflow_gate import workflow_period_for_work_unit

    projection = project_modelo_work_unit(work_unit)
    workflow_period = workflow_period_for_work_unit(work_unit)
    if latest:
        run = find_latest_run_for_period(modelo=projection.modelo, period=workflow_period, runs=runs)
    else:
        run = find_unique_run_for_period(
            modelo=projection.modelo,
            period=workflow_period,
            work_unit_id=projection.work_unit_id,
            short_work_unit_id=projection.short_work_unit_id,
            runs=runs,
        )
    resolution = WorkflowResumeTargetResolution(
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
    return WorkflowResumeSelection(resolution, run)


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


def _runs_for_period(*, modelo: str, period: Period, runs: WorkflowRunReader) -> list[WorkflowResult]:
    matches = [
        run
        for run in runs.list()
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
    if run.obligation is None:
        raise WorkflowError("a resumable workflow run must carry the obligation it filed against")
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
    "WorkflowResumeRefusalReason",
    "WorkflowResumeRefusedError",
    "WorkflowResumeRunAmbiguousError",
    "WorkflowResumeRunCandidate",
    "WorkflowResumeSelection",
    "WorkflowResumeTargetResolution",
    "find_latest_run_for_period",
    "find_unique_run_for_period",
    "resolve_modelo_workflow_resume_target",
    "resolve_modelo_workflow_run_for_resume",
    "resume_modelo_workflow",
    "validate_workflow_resume_target_token",
    "workflow_resume_candidate_lines",
    "workflow_resume_refusal_reason",
]
