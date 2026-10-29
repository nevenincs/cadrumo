"""Filing-record actions for modelo calculation revisions.

:func:`~cadrumo.application.modelo.filing_actions.file_modelo_revision` promotes a verified
:class:`CalculationRevision` into a current
:class:`ModeloRecord` after the
:class:`WorkflowEngine` preflight gate passes. Filing
transitions and audit entries are persisted through the application-owned
bucket-event capability shared by the modelo revision services.

The action records the operator's local/internal filing state only. It never
submits to AEAT, never marks AEAT acceptance, and never fabricates official
external evidence. A successful transition sets the target revision to
``PRESENTADO``, creates a ``VIGENTE``
:class:`ModeloRecord` with ``aeat_accepted=False``, and
delegates cross-period carry projection to
:func:`~cadrumo.application.modelo.filing_revision_persistence.persist_filed_revision`,
which stamps locally-filed observations as non-official ``app_filing`` evidence.

See Also:
    :func:`~cadrumo.application.modelo.external_import_actions.import_external_filing_evidence`:
        Separate AEAT-attested import path that creates
        :class:`ExternalEvidence` baselines; this local
        filing action deliberately does not.
    :func:`~cadrumo.application.modelo.filing_revision_persistence.persist_filed_revision`:
        Persists the filing catalogue, revision state, work-unit pointers,
        bucket events, participation index rows, and optional carry observation.
    :func:`~cadrumo.application.modelo.filed_revision_observation.prepare_filed_revision_observation`:
        Projects filed casillas into non-official cross-period observations.
    :func:`~cadrumo.application.modelo.result_disposition_resolution.resolve_modelo_result_disposition`:
        Resolves the shared Modelo 303 refund/carry disposition before the file
        transition persists.
    ``cadrumo.application.modelo.verification_actions._require_cross_period_clean_state``:
        Rechecks cross-period dependencies before local filing state is written.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import Settings
from ...core.diagnostic_log import diagnostic_timing_event
from ...core.identity.hex_ids import CalculationRevisionId, VerificationReportId
from ...core.logging import get_logger
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition
from ...core.time.clock import now as _utc_now
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue, ModeloRecordStatus
from ...domain.modelos.verification_report import VerificationReportCatalogue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ..calculations.cross_period_models import CrossPeriodExpectedMemberSet
from ..calculations.m303_regimen_simplificado_annual_summary import (
    validate_m303_regimen_simplificado_annual_summary_target_revision,
)
from ..workflow.engine import WorkflowEngine
from ._ledger_evidence_gate import raise_if_deductible_iva_evidence_missing
from ._required_binding_gate import (
    require_persisted_revision_required_bindings_resolved as _require_persisted_required_bindings_resolved,
)
from .action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloPreconditionErrorMixin,
    WorkUnitNotFoundError,
)
from .calculation_note_gate import require_work_unit_calculation_unblocked
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .filing_action_ports import FilingActionPorts
from .filing_revision_persistence import (
    persist_filed_revision,
    require_approved_verification_report,
    require_filing_instance_evidence_for_work_unit,
)
from .iva_wallet_gate import (
    require_persisted_iva_compensation_decision_matches_revision as _require_iva_compensation_revision_match,
)
from .lifecycle_clock_gate import (
    ModeloLifecycleClockOperation,
    filing_ordering_instants,
    require_lifecycle_clock_not_before,
)
from .m123_count_authority_gate import Modelo123CountAuthorityStage, require_modelo_123_count_authority
from .m193_settled_row_gate import Modelo193SettledRowStage, require_modelo_193_settled_row_amount_authority
from .m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_annual_summary_applies_to_profile,
    taxpayer_profile_for_work,
)
from .preconditions import build_modelo_work_file_unverified_revision_failure
from .prior_domiciliation import resolveprior_domiciliation_election
from .result_disposition_resolution import resolve_modelo_result_disposition
from .verification_cross_period import cross_period_expected_member_sets_from_profile, require_cross_period_clean_state
from .work_lifecycle import RevisionParentOperation, require_revision_parent_active
from .workflow_gate import build_revision_workflow_engine as _build_revision_workflow_engine
from .workflow_gate import run_revision_workflow_gate as _run_revision_workflow_gate

if TYPE_CHECKING:
    from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
    from ..auth.operator_scope_ports import OperatorScopePorts
    from .work_profile import ModeloWorkProfile

_LOGGER = get_logger(__name__)


def _filing_phase(stage: str) -> None:
    """Record bounded stage labels without filing identities or payloads."""
    diagnostic_timing_event(_LOGGER, "modelo_filing_phase", fields={"stage": stage})


class ModeloFilingEvidenceMissingError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when internal filing would seal deductible IVA without evidence."""


@dataclass(frozen=True, slots=True)
class ModeloFilingResult:
    """The filed record and whether this call published a new transition."""

    record: ModeloRecord
    published: bool


def _existing_vigente_filing_record(
    catalogue: ModeloRecordCatalogue,
    calculation_revision_id: CalculationRevisionId,
) -> ModeloRecord | None:
    """Return the current (VIGENTE) filing record for a filed revision, if any.

    Used by the idempotent re-file no-op: a revision already in ``PRESENTADO``
    state is the current filed answer, so its VIGENTE
    :class:`ModeloRecord` is returned unchanged. A
    ``PRESENTADO`` revision must have exactly one VIGENTE record; ``None``
    signals an inconsistent state the caller refuses rather than masking.
    """
    for record in catalogue.records.values():
        if record.calculation_revision_id == calculation_revision_id and record.status is ModeloRecordStatus.VIGENTE:
            return record
    return None


def _load_filing_context(
    calculation_revision_id: CalculationRevisionId,
    ports: FilingActionPorts,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None,
) -> tuple[
    CalculationRevisionCatalogue,
    CalculationRevision,
    WorkUnitCatalogue,
    WorkUnit,
    ModeloRecordCatalogue,
    str,
    ModeloWorkProfile | None,
]:
    wu_repo = ports.work_unit_repository
    cr_repo = ports.calculation_repository
    fr_repo = ports.filing_repository
    _filing_phase("load_begin")
    revisions = cr_repo.load(operation=operation)
    _filing_phase("load_end")
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    require_calculation_revision_coordinates_current(target, operation=operation)
    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={
                "calculation_revision_id": calculation_revision_id,
                "work_unit_id": target.work_unit_id,
            },
        )
    filing_baseline, filing_baseline_revision_id = fr_repo.load_revisioned()
    require_filing_instance_evidence_for_work_unit(work_unit=work_unit, revision=target)
    require_revision_parent_active(
        work_unit=work_unit,
        calculation_revision_id=calculation_revision_id,
        operation=RevisionParentOperation.FILE,
    )
    # Before the idempotent re-file no-op: a revision verified before evidence
    # was captured, or one carrying a Modelo 193 settled prior-accrual row,
    # must not be returned as the filed answer.
    require_modelo_123_count_authority(
        work_unit,
        retencion_ports=ports.retencion_observation_ports,
        stage=Modelo123CountAuthorityStage.FILE,
    )
    require_modelo_193_settled_row_amount_authority(work_unit, target, stage=Modelo193SettledRowStage.FILE)
    if profile is None:
        from .profile_readiness_gate import load_modelo_work_profile

        profile = load_modelo_work_profile(
            bucket_id=work_unit.bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        )
    validate_m303_regimen_simplificado_annual_summary_target_revision(
        target_work_unit=work_unit,
        target_revision=target,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        regimen_simplificado_applies=m303_regimen_simplificado_annual_summary_applies_to_profile(
            taxpayer_profile_for_work(profile),
        ),
        operation=operation,
    )
    return revisions, target, work_units, work_unit, filing_baseline, filing_baseline_revision_id, profile


def _require_filing_state(
    target: CalculationRevision,
    work_unit: WorkUnit,
    filing_baseline: ModeloRecordCatalogue,
    calculation_revision_id: CalculationRevisionId,
    approved_verification_report_id: VerificationReportId,
    prior_domiciliation_election: PriorDomiciliationElection,
    ports: FilingActionPorts,
    operation: PinnedAuthorityOperation,
) -> ModeloFilingResult | None:
    fr_repo = ports.filing_repository
    obs_repo = ports.observation_repository
    if target.state is CalculationRevisionState.PRESENTADO:
        # Idempotent re-file: this revision is already the current filed answer.
        # A retry of a completed single-subject file returns the existing VIGENTE
        # filing record as a clean no-op - no new filing record, no duplicate
        # MODELO_FILED lifecycle event, and (filing is a local transition, never
        # an AEAT submission per sensitive-financial-data-secure-storage-only) no write/submit path is
        # touched. Mirrors the verify-report content-pinned idempotency. The CLI
        # surfaces the no-op as an info Notice. A PRESENTADO revision with no
        # VIGENTE record is an inconsistent state, so it falls through to the
        # hard refusal below rather than fabricating a record.
        existing = _existing_vigente_filing_record(filing_baseline, calculation_revision_id)
        if existing is not None:
            require_approved_verification_report(
                target=target,
                approved_verification_report_id=approved_verification_report_id,
                catalogue=ports.verification_repository.load(operation=operation),
                operation=operation,
            )
            # An idempotent retry remains subject to the same fail-closed typed
            # election boundary: an unproven ``X`` request cannot hide behind
            # a prior local filing no-op.
            resolveprior_domiciliation_election(
                election=prior_domiciliation_election,
                work_unit=work_unit,
                revision=target,
                filing_repository=fr_repo,
                observation_repository=obs_repo,
                operation=operation,
            )
            return ModeloFilingResult(record=existing, published=False)
    if target.state is not CalculationRevisionState.VERIFICADO_COMPLETO:
        raise CalculationRevisionStateError(
            translated_message="errors.error.error_modelo_calculation_revision_state",
            context={"calculation_revision_id": calculation_revision_id, "state": target.state.value},
            precondition_failure=build_modelo_work_file_unverified_revision_failure(
                calculation_revision_id=calculation_revision_id,
                state=target.state.value,
                work_unit=work_unit,
            ),
        )

    return None


def _run_filing_workflow(
    workflow_engine: WorkflowEngine | None,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_scope_ports: OperatorScopePorts,
    target: CalculationRevision,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    actor: str,
    now: datetime,
    settings: Settings | None,
    ports: FilingActionPorts,
    operation: PinnedAuthorityOperation,
    workflow_runs_dir: Path | None,
) -> None:
    _filing_phase("workflow_begin")
    gate_engine = workflow_engine or _build_revision_workflow_engine(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=operator_scope_ports,
        revision=target,
        work_unit=work_unit,
        profile=workflow_profile,
        actor=actor.strip(),
        clock=now,
        settings=settings,
        draft_review_ports=ports.draft_review_ports,
        workflow_gate_ports=ports.workflow_gate_ports,
        operation=operation,
    )
    _run_revision_workflow_gate(
        engine=gate_engine,
        profile=workflow_profile,
        work_unit=work_unit,
        today=now.date(),
        runs_dir=workflow_runs_dir,
        run_repository=ports.workflow_run_repository,
    )

    _filing_phase("workflow_end")


def _check_filing_preconditions(
    ports: FilingActionPorts,
    operation: PinnedAuthorityOperation,
    target: CalculationRevision,
    work_unit: WorkUnit,
    approved_verification_report_id: VerificationReportId,
    clock: datetime | None,
    revisions: CalculationRevisionCatalogue,
    filing_baseline: ModeloRecordCatalogue,
    workflow_profile: TaxpayerProfile,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
    profile: ModeloWorkProfile | None,
) -> datetime:
    reports = ports.verification_repository.load(operation=operation)
    require_approved_verification_report(
        target=target,
        approved_verification_report_id=approved_verification_report_id,
        catalogue=reports,
        operation=operation,
    )

    now = clock or _utc_now()
    _require_filing_clock_ordered(
        now,
        target=target,
        work_unit=work_unit,
        revisions=revisions,
        filing_catalogue=filing_baseline,
    )
    _filing_phase("preconditions_begin")
    _require_filing_preconditions(
        evaluated_at=now,
        work_unit=work_unit,
        target=target,
        calculation_catalogue=revisions,
        filing_catalogue=filing_baseline,
        verification_catalogue=reports,
        workflow_profile=workflow_profile,
        ports=ports,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
        operation=operation,
        profile=profile,
    )

    _filing_phase("preconditions_end")
    return now


def _require_prior_election(prior_domiciliation_election: object) -> PriorDomiciliationElection:
    if not isinstance(prior_domiciliation_election, PriorDomiciliationElection):
        from .action_errors import ModeloPriorDomiciliationElectionRefusedError

        raise ModeloPriorDomiciliationElectionRefusedError(
            translated_message="errors.refused.refused_modeloprior_domiciliation_election",
            context={"received_type": type(prior_domiciliation_election).__name__},
        )

    return prior_domiciliation_election


def file_modelo_revision(
    calculation_revision_id: CalculationRevisionId,
    *,
    approved_verification_report_id: VerificationReportId,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_scope_ports: OperatorScopePorts,
    ports: FilingActionPorts,
    actor: str,
    workflow_profile: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
    notes: str | None = None,
    refund_election: RefundElection = RefundElection.COMPENSAR,
    payment_election: PaymentElection = PaymentElection.INGRESO,
    prior_domiciliation_election: object = PriorDomiciliationElection.KEEP,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
    profile: ModeloWorkProfile | None = None,
) -> ModeloFilingResult:
    """File a verified revision as the current local answer, without submitting to AEAT.

    Recheck the approved report, profile and cross-period evidence, then run the
    pinned workflow before deriving the filing disposition and atomically
    persisting the revision, record, observations and lifecycle event. A retry
    of an already-filed revision returns its existing record only after the same
    report and prior-domiciliation checks. A clock preceding retained evidence is
    refused before a write. The returned witness says whether this call published.

    Takes ``workflow_profile`` as a :class:`TaxpayerProfile`.
    """
    prior_domiciliation_election = _require_prior_election(prior_domiciliation_election)
    revisions, target, work_units, work_unit, filing_baseline, filing_baseline_revision_id, profile = (
        _load_filing_context(calculation_revision_id, ports, operation, profile)
    )
    existing = _require_filing_state(
        target,
        work_unit,
        filing_baseline,
        calculation_revision_id,
        approved_verification_report_id,
        prior_domiciliation_election,
        ports,
        operation,
    )
    if existing is not None:
        return existing

    now = _check_filing_preconditions(
        ports,
        operation,
        target,
        work_unit,
        approved_verification_report_id,
        clock,
        revisions,
        filing_baseline,
        workflow_profile,
        cross_period_expected_member_sets,
        profile,
    )
    _run_filing_workflow(
        workflow_engine,
        certificate_secret_backend_factory,
        operator_scope_ports,
        target,
        work_unit,
        workflow_profile,
        actor,
        now,
        settings,
        ports,
        operation,
        workflow_runs_dir,
    )
    return _persist_filing_result(
        work_unit=work_unit,
        target=target,
        workflow_profile=workflow_profile,
        refund_election=refund_election,
        payment_election=payment_election,
        prior_domiciliation_election=prior_domiciliation_election,
        ports=ports,
        operation=operation,
        approved_verification_report_id=approved_verification_report_id,
        filing_baseline_revision_id=filing_baseline_revision_id,
        work_units=work_units,
        notes=notes,
        actor=actor,
        now=now,
    )


def _persist_filing_result(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    refund_election: RefundElection,
    payment_election: PaymentElection,
    prior_domiciliation_election: PriorDomiciliationElection,
    ports: FilingActionPorts,
    operation: PinnedAuthorityOperation,
    approved_verification_report_id: VerificationReportId,
    filing_baseline_revision_id: str,
    work_units: WorkUnitCatalogue,
    notes: str | None,
    actor: str,
    now: datetime,
) -> ModeloFilingResult:
    result_disposition = _filed_revision_result_disposition(
        work_unit=work_unit,
        target=target,
        workflow_profile=workflow_profile,
        refund_election=refund_election,
        payment_election=payment_election,
    )
    prior_domiciliation_provenance = resolveprior_domiciliation_election(
        election=prior_domiciliation_election,
        work_unit=work_unit,
        revision=target,
        filing_repository=ports.filing_repository,
        observation_repository=ports.observation_repository,
        operation=operation,
    )

    _filing_phase("persistence_begin")
    record = persist_filed_revision(
        target=target,
        approved_verification_report_id=approved_verification_report_id,
        filing_baseline_revision_id=filing_baseline_revision_id,
        work_unit=work_unit,
        work_units=work_units,
        notes=notes,
        actor=actor,
        now=now,
        calculation_repository=ports.calculation_repository,
        filing_repository=ports.filing_repository,
        verification_repository=ports.verification_repository,
        work_unit_repository=ports.work_unit_repository,
        bucket_event_repository=ports.bucket_event_repository,
        calculation_observation_repository=ports.observation_repository,
        participation_index_repository=ports.participation_index_repository,
        prorrata_register_repository=ports.prorrata_register_repository,
        operation=operation,
        iva_compensation_history_repository=ports.iva_compensation_history_repository,
        result_disposition=result_disposition,
        prior_domiciliation_election=prior_domiciliation_provenance,
        taxpayer_nif=workflow_profile.tax_id,
        justificante_repository=ports.justificante_repository,
    )
    _filing_phase("persistence_end")
    return ModeloFilingResult(record=record, published=True)


def _filed_revision_result_disposition(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    refund_election: RefundElection,
    payment_election: PaymentElection,
) -> ResultDisposition | None:
    """Resolve once at the filing boundary for both export and carry evidence."""
    return resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=target,
        workflow_profile=workflow_profile,
        period=work_unit.period,
        refund_election=refund_election,
        payment_election=payment_election,
    )


def _require_filing_clock_ordered(
    now: datetime,
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    revisions: CalculationRevisionCatalogue,
    filing_catalogue: ModeloRecordCatalogue,
) -> None:
    """Refuse a filing clock earlier than any instant the filing's writes are ordered after.

    Runs before the workflow gate and the co-committed filing writes, so a
    refused clock leaves no workflow run, filing record or advanced pointer.
    """
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    require_lifecycle_clock_not_before(
        now,
        operation=ModeloLifecycleClockOperation.FILE,
        instants=filing_ordering_instants(
            revision=target,
            work_unit=work_unit,
            prior_current=prior_current,
            prior_revision=None if prior_current is None else revisions.get(prior_current.calculation_revision_id),
        ),
    )


def _require_filing_preconditions(
    *,
    evaluated_at: datetime,
    work_unit: WorkUnit,
    target: CalculationRevision,
    calculation_catalogue: CalculationRevisionCatalogue,
    filing_catalogue: ModeloRecordCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    workflow_profile: TaxpayerProfile,
    ports: FilingActionPorts,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None,
) -> None:
    from .profile_readiness_gate import require_profile_ready_for_work_unit

    raise_if_deductible_iva_evidence_missing(
        target,
        error_type=ModeloFilingEvidenceMissingError,
        operation=operation,
    )
    require_profile_ready_for_work_unit(
        work_unit,
        profile_decode_context=operation.profile_decode_context(),
        operation=operation,
        profile=profile,
    )
    _require_persisted_required_bindings_resolved(
        work_unit=work_unit, revision=target, action="file", operation=operation
    )
    require_work_unit_calculation_unblocked(work_unit=work_unit, revision=target, action="file", operation=operation)
    iva_compensation_decision = _require_iva_compensation_revision_match(
        work_unit,
        target,
        repository=ports.iva_compensation_decision_repository,
        observation_repository=ports.observation_repository,
        history_repository=ports.iva_compensation_history_repository,
        operation=operation,
        subject_leaf_key="modelo.work.file",
        evaluated_at=evaluated_at,
    )
    require_cross_period_clean_state(
        work_unit,
        observation_repository=ports.observation_repository,
        filing_repository=ports.filing_repository,
        calculation_repository=ports.calculation_repository,
        calculation_catalogue=calculation_catalogue,
        filing_catalogue=filing_catalogue,
        verification_catalogue=verification_catalogue,
        verification_repository=ports.verification_repository,
        justificante_repository=ports.justificante_repository,
        iva_compensation_decision=iva_compensation_decision,
        expected_member_sets=cross_period_expected_member_sets_from_profile(
            workflow_profile,
            cross_period_expected_member_sets,
        ),
        taxpayer_tax_id=workflow_profile.tax_id,
        activity_start_date=workflow_profile.activity_start_date,
        modelo_202_modality=derive_modelo_202_modality(
            workflow_profile,
            effective_date=date(work_unit.filing_year, 12, 31),
        ).modality,
        taxpayer_files_economic_activity=derive_taxpayer_files_economic_activity(workflow_profile),
        workflow_profile=workflow_profile,
        target_revision=target,
        subject_leaf_key="modelo.work.file",
        operation=operation,
    )


def list_filing_records(
    *,
    ports: FilingActionPorts,
    bucket_id: str | None = None,
    modelo: str | ModeloCode | None = None,
    include_superseded: bool = False,
) -> tuple[ModeloRecord, ...]:
    """List :class:`ModeloRecord` rows, optionally filtered to a bucket and modelo.

    Superseded records are excluded unless ``include_superseded``
    is true. Results are sorted by ``(bucket_id, filing_year,
    modelo, period, filed_at)``.
    """
    catalogue = ports.filing_repository.load()
    modelo_code = ModeloCode(str(modelo)) if modelo is not None else None
    records = tuple(
        record
        for record in catalogue.records.values()
        if (bucket_id is None or record.bucket_id == bucket_id)
        and (modelo_code is None or record.modelo == modelo_code)
        and (include_superseded or record.status is ModeloRecordStatus.VIGENTE)
    )
    return tuple(
        sorted(
            records,
            key=lambda r: (r.bucket_id, r.filing_year, str(r.modelo), r.period.registry_token, r.filed_at),
        ),
    )
