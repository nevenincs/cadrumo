"""Workflow-gate support for modelo calculation revisions.

This module owns the adapter objects that let immutable calculation revisions
participate in the filing workflow engine. The public application facade
continues to export the operator-facing services from `aeat.application.modelo`.

Use of :class:`CalculationRevision`, :class:`TaxpayerProfile`, :class:`TransactionCatalogue` for compliance.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from ...application.auth import AuthProviderKind, select_provider
from ...core import Period
from ...core.config import Settings, load_settings
from ...domain.calculations.registry import RegistrySnapshotError
from ...domain.deadlines import DeadlineEngine, TaxpayerProfile
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._work_unit import WorkUnit
from ...domain.submission import ModeloDraftStatus, SubmissionEngine
from ...domain.transactions import TransactionCatalogue
from ..filing import (
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    filing_profile_from_taxpayer,
)
from ..workflow import (
    DeadlineEngineAdapter,
    ModeloInputs,
    RegistryModeloDraftProtocol,
    WorkflowEngine,
    WorkflowInputMismatchError,
    WorkflowPurpose,
    WorkflowResult,
    WorkflowRunRepository,
    WorkflowStage,
)
from ._action_errors import ModeloWorkflowGateError


@lru_cache(maxsize=512)
def _deadline_window_period_for_registry_period(
    *,
    modelo: str,
    filing_year: int,
    registry_period: str,
) -> Period | None:
    """Return the typed :class:`~aeat.core.Period` declared by the registry deadline window.

    Uses :class:`~aeat.domain.calculations.registry.RegistrySnapshotError` for
    snapshot lookup; :class:`~aeat.core.Period` for the returned value.
    """
    from ...core.resources import resources

    try:
        snapshot = resources().modelos.authority.snapshot(
            modelo,
            filing_year=filing_year,
            period=registry_period,
        )
    except RegistrySnapshotError:
        return None

    target = Period.from_year_and_code(filing_year, registry_period)
    for window in snapshot.revision.deadline_windows:
        if window.period == target:
            return window.period
    return None


def workflow_period_for_work_unit(work_unit: WorkUnit) -> Period:
    """Return the canonical :class:`~aeat.core.Period` consumed by the workflow engine."""
    registry_period = work_unit.period.registry_token
    if registry_period.endswith("T") and len(registry_period) == 2:
        declared = _deadline_window_period_for_registry_period(
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            registry_period=registry_period,
        )
        if declared is not None:
            return declared
        return work_unit.period
    return work_unit.period


class _RevisionInputsProvider:
    """Loads immutable calculation-revision inputs for the workflow gate."""

    def __init__(self, *, revision: CalculationRevision, work_unit: WorkUnit) -> None:
        self._revision = revision
        self._modelo = work_unit.modelo
        self._period = workflow_period_for_work_unit(work_unit)

    def load_inputs(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
    ) -> ModeloInputs:
        """Return the revision inputs when the workflow request matches it.

        Use of :class:`TaxpayerProfile` for compliance.
        """
        del profile
        if modelo != self._modelo or period != self._period:
            raise WorkflowInputMismatchError(
                "workflow input request does not match calculation revision",
                translated_message="application.modelo.errors.workflow_input_mismatch",
                context={
                    "expected_modelo": self._modelo,
                    "expected_period": str(self._period),
                    "requested_modelo": modelo,
                    "requested_period": str(period),
                },
            )
        return {
            **dict(self._revision.input_values_by_casilla_id),
            **dict(self._revision.binding_overrides),
            **dict(self._revision.relation_overrides),
        }


class _RevisionDraftBuilder:
    """Builds and locally approves the draft backed by the target revision."""

    def __init__(self, *, work_unit: WorkUnit, actor: str, clock: datetime) -> None:
        self._work_unit = work_unit
        self._actor = actor
        self._clock = clock
        self._schema_provider = build_runtime_schema_provider(
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            modelos=(work_unit.modelo,),
        )

    def build(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
        inputs: ModeloInputs,
        fail_on_warning: bool = False,
    ) -> RegistryModeloDraftProtocol:
        """Build a :class:`RegistryModeloDraftProtocol` and approve it when it is filing-ready.

        Uses :class:`TaxpayerProfile` for deadline and filing-period scoping.
        """
        draft = build_draft(
            modelo=modelo,
            period=period,
            profile=filing_profile_from_taxpayer(profile),
            inputs=inputs,
            schema_provider=self._schema_provider,
            fail_on_warning=fail_on_warning,
        )
        if draft.status is not ModeloDraftStatus.LISTO_PARA_PRESENTAR:
            return draft
        return approve_draft(
            draft,
            bucket_id=self._work_unit.bucket_id,
            approved_by=self._actor,
            schema_provider=self._schema_provider,
            transaction_catalogue=TransactionCatalogue(),
            approved_at=self._clock,
        )


class _RevisionDeadlineWindowChecker:
    """Checks the same deadline schedule the workflow gate already computed."""

    def __init__(self, *, profile: TaxpayerProfile, engine: DeadlineEngine) -> None:
        self._profile = profile
        self._engine = engine

    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        """Return whether the taxpayer has an open filing window."""
        schedule = self._engine.compute(self._profile, period.year, today=today)
        return any(
            obligation.modelo == modelo
            and obligation.period == period
            and obligation.opens_on <= today <= obligation.closes_on
            for obligation in schedule.obligations
        )


def build_revision_workflow_engine(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    profile: TaxpayerProfile,
    actor: str,
    clock: datetime,
    settings: Settings | None,
) -> WorkflowEngine:
    """Build and return a :class:`WorkflowEngine` configured for one calculation revision.

    Uses :class:`CalculationRevision` for revision inputs and :class:`TaxpayerProfile` for deadline scoping.
    """
    cfg = settings or load_settings()
    deadline_engine = DeadlineEngine()
    provider_kind = (
        AuthProviderKind(cfg.aeat_auth_provider.value)
        if cfg.aeat_auth_provider is not None
        else AuthProviderKind.CERTIFICATE
    )
    submission_engine = SubmissionEngine(
        auth_provider=select_provider(provider_kind, settings=cfg),
        deadline_checker=_RevisionDeadlineWindowChecker(profile=profile, engine=deadline_engine),
        settings=cfg,
    )
    return WorkflowEngine(
        deadline_engine=DeadlineEngineAdapter(deadline_engine),
        filing_draft_builder=_RevisionDraftBuilder(work_unit=work_unit, actor=actor, clock=clock),
        submission_engine=submission_engine,
        session=None,
        certificate_bundle=None,
        inputs_provider=_RevisionInputsProvider(
            revision=revision,
            work_unit=work_unit,
        ),
        settings=cfg,
    )


def run_revision_workflow_gate(
    *,
    engine: WorkflowEngine,
    profile: TaxpayerProfile,
    work_unit: WorkUnit,
    today: date,
    runs_dir: Path | None,
    run_repository: WorkflowRunRepository,
    resumed_from: str | None = None,
    purpose: WorkflowPurpose = WorkflowPurpose.FILE,
) -> WorkflowResult:
    """Run and persist the workflow gate for one modelo work unit and return a :class:`WorkflowResult`.

    Uses :class:`TaxpayerProfile` for deadline and filing-period scoping.
    """
    result = asyncio.run(
        engine.run_for_period(
            profile,
            work_unit.modelo,
            workflow_period_for_work_unit(work_unit),
            today=today,
            resumed_from=resumed_from,
            purpose=purpose,
        ),
    )
    run_repository.save(result, runs_dir=runs_dir)
    if result.final_stage is WorkflowStage.ABORTED:
        raise ModeloWorkflowGateError(result)
    return result


__all__ = [
    "_RevisionInputsProvider",
    "build_revision_workflow_engine",
    "run_revision_workflow_gate",
    "workflow_period_for_work_unit",
]
