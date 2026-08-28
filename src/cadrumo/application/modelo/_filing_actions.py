"""Filing-record actions for modelo calculation revisions.

:func:`~cadrumo.application.modelo.file_modelo_revision` promotes a verified
:class:`CalculationRevision` into a current
:class:`ModeloRecord` after the
:class:`WorkflowEngine` preflight gate passes. Filing
transitions and audit entries are persisted through the
:class:`BucketEventHistoryRepository` path shared by the
modelo revision services.

The action records the operator's local/internal filing state only. It never
submits to AEAT, never marks AEAT acceptance, and never fabricates official
external evidence. A successful transition sets the target revision to
``PRESENTADO``, creates a ``VIGENTE``
:class:`ModeloRecord` with ``aeat_accepted=False``, and
delegates cross-period carry projection to
:func:`~cadrumo.application.modelo._revision_persistence.persist_filed_revision`,
which stamps locally-filed observations as non-official ``app_filing`` evidence.

See Also:
    :func:`~cadrumo.application.modelo.import_external_filing_evidence`:
        Separate AEAT-attested import path that creates
        :class:`ExternalEvidence` baselines; this local
        filing action deliberately does not.
    :func:`~cadrumo.application.modelo._revision_persistence.persist_filed_revision`:
        Persists the filing catalogue, revision state, work-unit pointers,
        bucket events, participation index rows, and optional carry observation.
    :func:`~cadrumo.application.modelo._filed_revision_observation.persist_filed_revision_observation`:
        Projects filed casillas into non-official cross-period observations.
    :func:`~cadrumo.application.modelo._result_disposition_resolution.resolve_modelo_result_disposition`:
        Resolves the shared Modelo 303 refund/carry disposition before the file
        transition persists.
    :func:`~cadrumo.application.modelo._verification_actions._require_cross_period_clean_state`:
        Rechecks cross-period dependencies before local filing state is written.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import (
    PaymentElection,
    PriorDomiciliationElection,
    RefundElection,
    ResultDisposition,
)
from ...core.config import Settings
from ...core.identity import CalculationRevisionId
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloCode,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloRecordStatus,
    VerificationReport,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnit,
)
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations import (
    CalculationObservationRepository,
    CrossPeriodExpectedMemberSet,
    validate_m303_regimen_simplificado_annual_summary_target_revision,
)
from ..workflow.engine import WorkflowEngine
from ..workflow.persistence import WorkflowRunRepository
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloPreconditionErrorMixin,
    ModeloRecordNotFoundError,
    VerificationReportNotFoundError,
    WorkUnitNotFoundError,
)
from ._iva_wallet_gate import (
    require_persisted_iva_compensation_decision_matches_revision as _require_iva_compensation_revision_match,
)
from ._ledger_evidence_gate import raise_if_deductible_iva_evidence_missing
from ._m303_regimen_simplificado_scope import m303_regimen_simplificado_annual_summary_applies
from ._preconditions import build_modelo_work_file_unverified_revision_failure
from ._prior_domiciliation import resolve_prior_domiciliation_election
from ._required_binding_gate import (
    require_persisted_revision_required_bindings_resolved as _require_persisted_required_bindings_resolved,
)
from ._result_disposition_resolution import resolve_modelo_result_disposition
from ._revision_persistence import persist_filed_revision, require_filing_instance_evidence_for_work_unit
from ._verification_actions import (
    cross_period_expected_member_sets_from_profile,
    require_cross_period_clean_state,
)
from ._work_lifecycle import RevisionParentOperation, require_revision_parent_active
from ._workflow_gate import build_revision_workflow_engine as _build_revision_workflow_engine
from ._workflow_gate import run_revision_workflow_gate as _run_revision_workflow_gate

if TYPE_CHECKING:
    from ..calculations import IvaWalletDecisionRepository


class ModeloFilingEvidenceMissingError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when internal filing would seal deductible IVA without evidence."""


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


class _FilingRepositories(NamedTuple):
    """The catalogue repositories one filing run reads and writes."""

    work_units: WorkUnitCatalogueRepositoryProtocol
    calculations: CalculationRevisionCatalogueRepositoryProtocol
    filings: ModeloRecordCatalogueRepositoryProtocol
    verifications: VerificationReportCatalogueRepositoryProtocol
    observations: CalculationObservationRepository
    bucket_events: BucketEventHistoryRepositoryProtocol


def _resolve_filing_repositories(
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None,
    calculation_observation_repository: CalculationObservationRepository | None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
) -> _FilingRepositories:
    """Bind each repository to its caller-supplied override or the default profile-scoped one."""
    return _FilingRepositories(
        work_units=work_unit_repository or WorkUnitCatalogueRepository(),
        calculations=calculation_repository or CalculationRevisionCatalogueRepository(),
        filings=filing_repository or ModeloRecordCatalogueRepository(),
        verifications=verification_repository or VerificationReportCatalogueRepository(),
        observations=calculation_observation_repository or CalculationObservationRepository(),
        bucket_events=bucket_event_repository or BucketEventHistoryRepository(),
    )


def file_modelo_revision(
    calculation_revision_id: CalculationRevisionId,
    *,
    actor: str,
    workflow_profile: TaxpayerProfile,
    notes: str | None = None,
    refund_election: RefundElection = RefundElection.COMPENSAR,
    payment_election: PaymentElection = PaymentElection.INGRESO,
    prior_domiciliation_election: object = PriorDomiciliationElection.KEEP,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    calculation_observation_repository: CalculationObservationRepository | None = None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Mark a verified-complete revision as the current internal filed answer.

    This is the application service behind ``aeat app modelo work file``. It is
    a local state transition, not an AEAT presentation: the resulting
    :class:`ModeloRecord` has ``aeat_accepted=False`` and no
    external evidence.

    Preconditions and state changes:

    1. Verify the revision is in ``VERIFICADO_COMPLETO`` state.
    2. Recheck profile readiness, persisted Modelo 303 IVA-wallet decision
       compatibility, and cross-period clean state.
    3. Run the :class:`WorkflowEngine` gate for the
       revision's modelo and period.
    4. Resolve the Modelo 303 result disposition from
       :class:`RefundElection`, :class:`PaymentElection`, and
       :class:`TaxpayerProfile`.
    5. If a prior current filing exists, mark its
       :class:`ModeloRecord` as ``SUPERSEDIDO`` and its
       prior :class:`CalculationRevision` as
       ``PRESENTADO_SUPERSEDIDO``.
    6. Create the new filing record with status ``VIGENTE`` and transition the
       target calculation revision from ``VERIFICADO_COMPLETO`` to
       ``PRESENTADO``.
    7. Advance the work unit's ``filed_calculation_revision_id`` and
       ``current_filing_record_id`` pointers, emit ``MODELO_FILED``/
       ``MODELO_FILED_SUPERSEDED`` bucket events, and persist any local
       ``app_filing`` carry observation.

    Args:
        calculation_revision_id: The id of the verified-complete revision
            to file.
        actor: Operator identifier recorded in the filing record and audit
            trail.
        workflow_profile: The :class:`TaxpayerProfile`
            used to evaluate :class:`WorkflowEngine`
            gate conditions and cross-period clean-state applicability.
        notes: Optional operator-supplied filing notes.
        refund_election: The operator's per-filing Modelo 303 negative-result
            disposition election. Defaults to ``COMPENSAR`` (carry the credit
            forward). ``DEVOLVER`` requests the credit back as a refund and is
            honoured only when the period is a lawful refund period (the year's
            last filing period for a non-REDEME taxpayer; every period for REDEME).
            An out-of-window ``DEVOLVER`` is refused.
        payment_election: The operator's positive-result settlement election.
            ``INGRESO`` is the default, ``DOMICILIACION`` is available only for
            Modelo 303, and ``CUENTA_CORRIENTE`` remains explicitly refused
            until its AEAT capability is grounded.
        prior_domiciliation_election: Whether to preserve the prior direct debit
            or request its cancellation/modification. The latter is accepted
            only for an M303 rectificativa with the official baseline-U proof.
        work_unit_repository: Optional work-unit catalogue repository override.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        filing_repository: Optional filing-record catalogue repository
            override.
        verification_repository: Optional verification-report catalogue
            repository override used by the cross-period clean-state proof.
        bucket_event_repository: Optional bucket-event history repository
            override.
        iva_compensation_decision_repository: Optional IVA wallet decision
            repository override used to require that a persisted decision still
            matches the target revision.
        calculation_observation_repository: Optional calculation-observation
            repository override used by the cross-period clean-state proof and
            the non-official local carry projection.
        cross_period_expected_member_sets: Optional expected grupo member
            rosters used by the cross-period clean-state proof.
        workflow_engine: Optional workflow engine override for the preflight
            gate.
        workflow_runs_dir: Optional workflow runs directory override.
        settings: Optional settings override.
        clock: Optional UTC timestamp override.

    Returns:
        The newly created local :class:`ModeloRecord` in
        ``VIGENTE`` status.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not in
            ``VERIFICADO_COMPLETO`` state.
        WorkUnitNotFoundError: When the revision's parent work
            unit cannot be loaded.

    See Also:
        :func:`~cadrumo.application.modelo._revision_persistence.persist_filed_revision`:
            Performs the repository writes once all gates pass.
        :func:`~cadrumo.application.modelo.import_external_filing_evidence`:
            Creates official-evidence baselines for imported filings; use that
            path when a :class:`ExternalEvidence` reference
            must be carried.
        :func:`~cadrumo.application.modelo._filed_revision_observation.persist_filed_revision_observation`:
            Saves the non-official ``app_filing`` observation used by later
            ``previous_filing`` calculations.
        :func:`~cadrumo.application.modelo.export_modelo_revision`:
            Sibling local finish line that writes the fichero-BOE artefact
            without requiring this internal file marker.
    """
    wu_repo, cr_repo, fr_repo, vr_repo, obs_repo, bv_repo = _resolve_filing_repositories(
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        verification_repository=verification_repository,
        calculation_observation_repository=calculation_observation_repository,
        bucket_event_repository=bucket_event_repository,
    )
    if not isinstance(prior_domiciliation_election, PriorDomiciliationElection):
        from ._action_errors import ModeloPriorDomiciliationElectionRefusedError

        raise ModeloPriorDomiciliationElectionRefusedError(
            translated_message="errors.refused.refused_modelo_prior_domiciliation_election",
            context={"received_type": type(prior_domiciliation_election).__name__},
        )
    _concrete_bv = bv_repo if isinstance(bv_repo, BucketEventHistoryRepository) else BucketEventHistoryRepository()
    run_repo = WorkflowRunRepository(objects=_concrete_bv.secure_object_repository)

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
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
    require_filing_instance_evidence_for_work_unit(work_unit=work_unit, revision=target)
    require_revision_parent_active(
        work_unit=work_unit,
        calculation_revision_id=calculation_revision_id,
        operation=RevisionParentOperation.FILE,
    )
    validate_m303_regimen_simplificado_annual_summary_target_revision(
        target_work_unit=work_unit,
        target_revision=target,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        regimen_simplificado_applies=m303_regimen_simplificado_annual_summary_applies(work_unit),
    )
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
        existing = _existing_vigente_filing_record(fr_repo.load(), calculation_revision_id)
        if existing is not None:
            # An idempotent retry remains subject to the same fail-closed typed
            # election boundary: an unproven ``X`` request cannot hide behind
            # a prior local filing no-op.
            resolve_prior_domiciliation_election(
                election=prior_domiciliation_election,
                work_unit=work_unit,
                revision=target,
                filing_repository=fr_repo,
                observation_repository=obs_repo,
            )
            return existing
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

    _require_filing_preconditions(
        work_unit=work_unit,
        target=target,
        workflow_profile=workflow_profile,
        observation_repository=obs_repo,
        filing_repository=fr_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
    )

    now = clock or _utc_now()
    gate_engine = workflow_engine or _build_revision_workflow_engine(
        revision=target,
        work_unit=work_unit,
        profile=workflow_profile,
        actor=actor.strip(),
        clock=now,
        settings=settings,
    )
    _run_revision_workflow_gate(
        engine=gate_engine,
        profile=workflow_profile,
        work_unit=work_unit,
        today=now.date(),
        runs_dir=workflow_runs_dir,
        run_repository=run_repo,
    )

    result_disposition = _filed_revision_result_disposition(
        work_unit=work_unit,
        target=target,
        workflow_profile=workflow_profile,
        refund_election=refund_election,
        payment_election=payment_election,
    )
    prior_domiciliation_provenance = resolve_prior_domiciliation_election(
        election=prior_domiciliation_election,
        work_unit=work_unit,
        revision=target,
        filing_repository=fr_repo,
        observation_repository=obs_repo,
    )

    return persist_filed_revision(
        target=target,
        work_unit=work_unit,
        work_units=work_units,
        notes=notes,
        actor=actor,
        now=now,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        work_unit_repository=wu_repo,
        bucket_event_repository=bv_repo,
        calculation_observation_repository=obs_repo,
        result_disposition=result_disposition,
        prior_domiciliation_election=prior_domiciliation_provenance,
        taxpayer_nif=workflow_profile.tax_id,
    )


def _filed_revision_result_disposition(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    refund_election: RefundElection,
    payment_election: PaymentElection,
) -> ResultDisposition:
    """Resolve once at the filing boundary for both export and carry evidence."""
    return resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=target,
        workflow_profile=workflow_profile,
        period=work_unit.period,
        refund_election=refund_election,
        payment_election=payment_election,
    )


def _require_filing_preconditions(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> None:
    from ._profile_readiness_gate import require_profile_ready_for_work_unit

    raise_if_deductible_iva_evidence_missing(
        target,
        error_type=ModeloFilingEvidenceMissingError,
    )
    require_profile_ready_for_work_unit(work_unit)
    _require_persisted_required_bindings_resolved(
        work_unit=work_unit,
        revision=target,
        action="file",
    )
    iva_compensation_decision = _require_iva_compensation_revision_match(
        work_unit,
        target,
        repository=iva_compensation_decision_repository,
        subject_leaf_key="modelo.work.file",
    )
    require_cross_period_clean_state(
        work_unit,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        iva_compensation_decision=iva_compensation_decision,
        expected_member_sets=cross_period_expected_member_sets_from_profile(
            workflow_profile,
            cross_period_expected_member_sets,
        ),
        taxpayer_tax_id=workflow_profile.tax_id,
        activity_start_date=workflow_profile.activity_start_date,
        modelo_202_modality=derive_modelo_202_modality(workflow_profile).modality,
        taxpayer_files_economic_activity=derive_taxpayer_files_economic_activity(workflow_profile),
        workflow_profile=workflow_profile,
        target_revision=target,
        subject_leaf_key="modelo.work.file",
    )


def list_filing_records(
    *,
    bucket_id: str | None = None,
    modelo: str | ModeloCode | None = None,
    include_superseded: bool = False,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
) -> tuple[ModeloRecord, ...]:
    """List :class:`ModeloRecord` rows, optionally filtered to a bucket and modelo.

    Superseded records are excluded unless ``include_superseded``
    is true. Results are sorted by ``(bucket_id, filing_year,
    modelo, period, filed_at)``.
    """
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    catalogue = fr_repo.load()
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


def get_filing_record(
    filing_record_id: str,
    *,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
) -> ModeloRecord:
    """Return the :class:`ModeloRecord` for the given id, or raise."""
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    catalogue = fr_repo.load()
    record = catalogue.get(filing_record_id)
    if record is None:
        raise ModeloRecordNotFoundError(
            translated_message="application.modelo.errors.filing_record_not_found",
            context={"filing_record_id": filing_record_id},
        )
    return record


def list_verification_reports(
    *,
    calculation_revision_id: CalculationRevisionId | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
) -> tuple[VerificationReport, ...]:
    """List :class:`VerificationReport` records.

    Optionally filtered to one
    :class:`CalculationRevision`. The
    :class:`VerificationReportCatalogueRepositoryProtocol`
    supplies the persisted report catalogue. Results are sorted by
    ``(calculation_revision_id, run_at)``.
    """
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    catalogue = vr_repo.load()
    reports = tuple(
        r
        for r in catalogue.reports.values()
        if calculation_revision_id is None or r.calculation_revision_id == calculation_revision_id
    )
    return tuple(sorted(reports, key=lambda r: (r.calculation_revision_id, r.run_at)))


def get_verification_report(
    verification_report_id: str,
    *,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
) -> VerificationReport:
    """Return one :class:`VerificationReport` by id, or raise.

    The optional
    :class:`VerificationReportCatalogueRepositoryProtocol`
    supplies the persisted report catalogue for tests or alternate storage
    boundaries.
    """
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    catalogue = vr_repo.load()
    report = catalogue.get(verification_report_id)
    if report is None:
        raise VerificationReportNotFoundError(
            translated_message="application.modelo.errors.verification_report_not_found",
            context={"verification_report_id": verification_report_id},
        )
    return report
