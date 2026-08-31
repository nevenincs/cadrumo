"""Workflow-gate support for modelo calculation revisions.

This module owns the adapter objects that let immutable calculation revisions
participate in the filing workflow engine. The public application facade
continues to export the operator-facing services from
:mod:`~cadrumo.application.modelo`.

The gate adapts one persisted
:class:`CalculationRevision` and its
:class:`WorkUnit` into
:class:`~cadrumo.application.workflow.WorkflowEngine` inputs. It scopes deadline
and filing-window checks with :class:`TaxpayerProfile`,
and locally approves filing drafts through the transient
:class:`TransactionCatalogue` used by the filing
surface.

The gate is a precondition runner, not the owner of verification reports or
filing records. :mod:`~cadrumo.application.modelo._verification_actions` invokes it
with :class:`~cadrumo.application.workflow.WorkflowPurpose.VERIFY` after local
verification findings have granted, while
:mod:`~cadrumo.application.modelo._filing_actions` invokes it with
:class:`~cadrumo.application.workflow.WorkflowPurpose.FILE` before local
mark-as-filed persistence. Aborted workflow runs are persisted for audit and then
surfaced as :class:`~cadrumo.application.modelo.ModeloWorkflowGateError`.

See Also:
    :mod:`~cadrumo.application.workflow.engine`:
        Owns deadline-independence for VERIFY and late-local FILE behavior.
    :mod:`~cadrumo.application.workflow._deadline_stage`:
        Selects the workflow obligation before submission preflight is reached.
    :class:`~cadrumo.domain.submission.SubmissionEngine`:
        Runs the read-only preflight gates using the deadline-window checker
        configured here.
    :class:`~cadrumo.domain.submission.DeadlineWindowChecker`:
        Protocol satisfied by the revision deadline-window adapter below.
    :mod:`~cadrumo.application.modelo._verification_actions`:
        Owns verification finding/report persistence around this gate.
    :mod:`~cadrumo.application.modelo._filing_actions`:
        Owns local filing-record persistence after this gate succeeds.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from ...adapters.persistence.profile.submission import SubmissionRepository
from ...application.auth.providers import select_provider
from ...core.auth_provider import AuthProviderKind
from ...core.config import Settings, load_settings
from ...core.period import Period
from ...domain.deadlines.engine import DeadlineEngine
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.deadlines.plazo import resolve_filing_window
from ...domain.filing.protocols import ModeloInputs
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from ...domain.submission.engine import SubmissionEngine
from ...domain.submission.models import ModeloDraftStatus
from ...domain.submission.protocols import DeadlineWindowChecker
from ...domain.transactions.models import TransactionCatalogue
from ..filing._draft_construction import build_draft
from ..filing.draft_review import approve_draft
from ..filing.runtime import build_runtime_schema_provider, filing_profile_from_taxpayer
from ..workflow.adapters import DeadlineEngineAdapter
from ..workflow.engine import WorkflowEngine
from ..workflow.errors import WorkflowInputMismatchError
from ..workflow.persistence import WorkflowRunRepository
from ..workflow.protocols import RegistryModeloDraftProtocol
from ..workflow.run_models import WorkflowPurpose, WorkflowResult, WorkflowStage
from ._action_errors import ModeloWorkflowGateError
from ._revision_replay_inputs import revision_filing_replay_inputs
from ._row_source_identity_replay import attach_revision_row_source_identities


@lru_cache(maxsize=512)
def _deadline_window_period_for_registry_period(
    *,
    modelo: str,
    filing_year: int,
    registry_period: str,
) -> Period | None:
    """Return the typed :class:`~cadrumo.core.Period` declared by the registry deadline window.

    Delegates entirely to :func:`~cadrumo.domain.deadlines.resolve_filing_window`,
    the single matching authority for "which registry deadline window covers this
    filing target" — this helper only projects the matched window's
    :class:`~cadrumo.core.Period` rather than its dates. Returns ``None`` when the
    registry declares no window for the combination.
    """
    target = Period.from_year_and_code(filing_year, registry_period)
    window = resolve_filing_window(modelo, filing_year, target)
    return None if window is None else window.period


def workflow_period_for_work_unit(work_unit: WorkUnit) -> Period:
    """Return the canonical :class:`~cadrumo.core.Period` consumed by the workflow engine.

    Quarterly work units use their registry token (for example ``"1T"``) but the
    deadline engine may declare a typed window period with a richer canonical
    shape. When the registry exposes such a deadline window, this helper returns
    that declared period so the workflow run addresses the same obligation the
    deadline engine will compute.
    """
    if not work_unit.period.is_quarterly:
        return work_unit.period

    declared = _deadline_window_period_for_registry_period(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        registry_period=work_unit.period.registry_token,
    )
    return declared or work_unit.period


class _RevisionInputsProvider:
    """Load immutable :class:`CalculationRevision` inputs for the workflow gate."""

    def __init__(self, *, revision: CalculationRevision, work_unit: WorkUnit) -> None:
        self._revision = revision
        self._work_unit = work_unit
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

        The :class:`TaxpayerProfile` parameter comes from the workflow Protocol and
        is passed to :func:`revision_filing_replay_inputs` so applicability-driven
        relation zeroes can be derived after ``modelo`` and
        :class:`~cadrumo.core.Period` have matched the stored revision.
        """
        if modelo != self._modelo or period != self._period:
            raise WorkflowInputMismatchError(
                translated_message="application.modelo.errors.workflow_input_mismatch",
                context={
                    "expected_modelo": self._modelo,
                    "expected_period": str(self._period),
                    "requested_modelo": modelo,
                    "requested_period": str(period),
                },
            )
        return revision_filing_replay_inputs(
            revision=self._revision,
            work_unit=self._work_unit,
            workflow_profile=profile,
        )


class _RevisionDraftBuilder:
    """Build and locally approve the draft backed by the target :class:`WorkUnit`."""

    def __init__(self, *, revision: CalculationRevision, work_unit: WorkUnit, actor: str, clock: datetime) -> None:
        self._revision = revision
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

        The :class:`TaxpayerProfile` is converted to the filing profile Protocol;
        approval uses a transient :class:`TransactionCatalogue` because persisted
        transaction evidence remains owned by the calculation revision.
        """
        draft = build_draft(
            modelo=modelo,
            period=period,
            profile=filing_profile_from_taxpayer(profile),
            inputs=inputs,
            schema_provider=self._schema_provider,
            fail_on_warning=fail_on_warning,
        )
        draft = attach_revision_row_source_identities(draft=draft, revision=self._revision)
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
    """Checks the same deadline schedule the workflow gate already computed.

    This adapter satisfies :class:`~cadrumo.domain.submission.DeadlineWindowChecker`
    and is passed to :class:`~cadrumo.domain.submission.SubmissionEngine` for
    submission-preflight window checks. The workflow engine decides by
    :class:`~cadrumo.application.workflow.WorkflowPurpose` whether that preflight
    window check is relevant; this adapter only answers the raw "is the window
    open today?" question.
    """

    def __init__(self, *, profile: TaxpayerProfile, engine: DeadlineEngine) -> None:
        self._profile = profile
        self._engine = engine

    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        """Return whether the taxpayer has an open filing window."""
        schedule = self._engine.compute(self._profile, period.filing_year, today=today)
        return any(
            obligation.modelo == modelo
            and obligation.period == period
            and obligation.opens_on <= today <= obligation.closes_on
            for obligation in schedule.obligations
        )


def build_revision_deadline_window_checker(
    *,
    profile: TaxpayerProfile,
    engine: DeadlineEngine,
) -> DeadlineWindowChecker:
    """Build the revision filing-window checker for one taxpayer.

    The returned :class:`DeadlineWindowChecker` binds the supplied
    :class:`TaxpayerProfile` and :class:`DeadlineEngine`. It answers raw,
    inclusive window membership for an exact modelo and period; workflow
    purpose and skip policy remain owned by the workflow engine.

    Args:
        profile: Taxpayer facts used to compute the obligation schedule.
        engine: Registry-backed deadline engine used for that schedule.

    Returns:
        The production deadline-window checker bound to ``profile``.
    """
    return _RevisionDeadlineWindowChecker(profile=profile, engine=engine)


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

    The engine is wired with:

    * a deadline adapter over :class:`~cadrumo.domain.deadlines.DeadlineEngine`;
    * a revision-backed inputs provider that replays persisted calculation values;
    * a draft builder that validates and locally approves a registry draft;
    * a submission engine using the configured auth provider.

    The returned engine does not persist verification reports or filing records;
    callers decide the :class:`WorkflowPurpose` and perform state mutation only
    after :func:`run_revision_workflow_gate` returns successfully.

    Args:
        revision: The immutable :class:`CalculationRevision` whose persisted
            values are replayed into the workflow draft.
        work_unit: The :class:`WorkUnit` that
            supplies modelo, filing year, period, and bucket identity.
        profile: The :class:`TaxpayerProfile` used for deadline and applicability
            scoping inside the workflow engine.
        actor: Operator label used when locally approving the transient draft.
        clock: Timestamp used for local draft approval metadata.
        settings: Optional runtime :class:`~cadrumo.core.config.Settings`; defaults
            to :func:`~cadrumo.core.config.load_settings`.
    """
    cfg = settings or load_settings()
    deadline_engine = DeadlineEngine()
    provider_kind = cfg.cadrumo_auth_provider if cfg.cadrumo_auth_provider is not None else AuthProviderKind.CERTIFICATE
    submission_engine = SubmissionEngine(
        auth_provider=select_provider(provider_kind, settings=cfg),
        deadline_checker=build_revision_deadline_window_checker(profile=profile, engine=deadline_engine),
        settings=cfg,
        repository=SubmissionRepository(),
    )
    return WorkflowEngine(
        deadline_engine=DeadlineEngineAdapter(deadline_engine),
        filing_draft_builder=_RevisionDraftBuilder(revision=revision, work_unit=work_unit, actor=actor, clock=clock),
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

    ``purpose`` selects the workflow policy: VERIFY validates the calculation
    independently of the filing-window calendar, while FILE retains the local
    filing obligation gate and late-filing handling. Every result is saved through
    ``run_repository`` before the caller sees it. If the workflow aborts, the
    persisted result is raised as :class:`ModeloWorkflowGateError`; no downstream
    verification or filing state should be written by the caller after that.

    Returns:
        The successful :class:`WorkflowResult`.

    Args:
        engine: The :class:`WorkflowEngine` configured for the target revision.
        profile: The :class:`TaxpayerProfile` used by the workflow run.
        work_unit: The :class:`WorkUnit` whose
            modelo and period select the workflow target.
        today: Reference date for deadline and preflight stages.
        runs_dir: Optional filesystem location for persisted workflow runs.
        run_repository: Repository that stores the resulting workflow run.
        resumed_from: Optional workflow run id when this execution resumes a
            prior run.
        purpose: Workflow policy to apply, usually VERIFY or FILE.
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
    "build_revision_deadline_window_checker",
    "build_revision_workflow_engine",
    "run_revision_workflow_gate",
    "workflow_period_for_work_unit",
]
