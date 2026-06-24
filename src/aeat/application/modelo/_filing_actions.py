"""Filing-record actions for modelo calculation revisions.

Use of :class:`BucketEventHistoryRepository` for compliance.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ...core import RefundElection
from ...core.config import Settings
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepository
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry import derive_modelo_202_modality
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._calculation_revision import CalculationRevisionState
from ...domain.modelos._filing_record import ModeloRecord, ModeloRecordStatus
from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._verification_report import VerificationReport
from ...domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ..calculations import CalculationObservationRepository, CrossPeriodExpectedMemberSet
from ..workflow import WorkflowEngine, WorkflowRunRepository
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    VerificationReportNotFoundError,
    WorkUnitNotFoundError,
)
from ._iva_wallet_gate import (
    require_persisted_iva_compensation_decision_matches_revision as _require_iva_compensation_revision_match,
)
from ._result_disposition_resolution import revision_is_refund_disposition
from ._revision_persistence import persist_filed_revision
from ._verification_actions import (
    _cross_period_expected_member_sets_from_profile,
    _require_cross_period_clean_state,
    _taxpayer_files_economic_activity,
)
from ._workflow_gate import build_revision_workflow_engine as _build_revision_workflow_engine
from ._workflow_gate import run_revision_workflow_gate as _run_revision_workflow_gate

if TYPE_CHECKING:
    from ..calculations._observations_repository import IvaWalletDecisionRepository


def file_modelo_revision(
    calculation_revision_id: str,
    *,
    actor: str,
    workflow_profile: TaxpayerProfile,
    notes: str | None = None,
    refund_election: RefundElection = RefundElection.COMPENSAR,
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
    """File a verified-complete revision as the current filed answer.

    State transitions performed atomically (from the caller's
    perspective — each repository save is sequenced):

    1. Verify the revision is in ``VERIFICADO_COMPLETO`` state.
    2. Run the workflow gate for the revision's modelo and period.
    3. Look up any existing current filing record for the same
       (bucket, modelo, year, period) tuple.
    4. If a prior current filing exists:
        * mark the prior filing record ``SUPERSEDED`` with
          ``superseded_at`` and ``superseded_by_filing_record_id``;
        * transition the prior filed calculation revision from
          ``FILED`` to ``FILED_SUPERSEDED``.
    5. Create the new filing record with status ``CURRENT``.
    6. Transition the target calculation revision from
       ``VERIFICADO_COMPLETO`` to ``FILED``.
    7. Advance the work unit's ``filed_calculation_revision_id``
       and ``current_filing_record_id`` pointers.

    Args:
        calculation_revision_id: The id of the verified-complete revision
            to file.
        actor: Operator identifier recorded in the filing record and audit
            trail.
        workflow_profile: The :class:`TaxpayerProfile` used to evaluate workflow
            gate conditions.
        notes: Optional operator-supplied filing notes.
        refund_election: The operator's per-filing Modelo 303 negative-result
            disposition election. Defaults to ``COMPENSAR`` (carry the credit
            forward). ``DEVOLVER`` requests the credit back as a refund and is
            honoured only when the period is a lawful refund period (the year's
            last filing period for a non-REDEME taxpayer; every period for REDEME).
            An out-of-window ``DEVOLVER`` is refused.
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
            repository override.
        calculation_observation_repository: Optional calculation-observation
            repository override used by the cross-period clean-state proof.
        cross_period_expected_member_sets: Optional expected grupo member
            rosters used by the cross-period clean-state proof.
        workflow_engine: Optional workflow engine override for the preflight
            gate.
        workflow_runs_dir: Optional workflow runs directory override.
        settings: Optional settings override.
        clock: Optional UTC timestamp override.

    Returns:
        The newly created :class:`ModeloRecord` in ``CURRENT`` status.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not in
            ``VERIFICADO_COMPLETO`` state.
        WorkUnitNotFoundError: When the revision's parent work
            unit cannot be loaded.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    obs_repo = calculation_observation_repository or CalculationObservationRepository()
    bv_repo: BucketEventHistoryRepositoryProtocol = bucket_event_repository or BucketEventHistoryRepository()
    _concrete_bv = bv_repo if isinstance(bv_repo, BucketEventHistoryRepository) else BucketEventHistoryRepository()
    run_repo = WorkflowRunRepository(objects=_concrete_bv.secure_object_repository)

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    if target.state is not CalculationRevisionState.VERIFICADO_COMPLETO:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only VERIFICADO_COMPLETO revisions can be filed",
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}",
        )
    iva_compensation_decision = _require_iva_compensation_revision_match(
        work_unit,
        target,
        repository=iva_compensation_decision_repository,
    )
    _require_cross_period_clean_state(
        work_unit,
        observation_repository=obs_repo,
        filing_repository=fr_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        iva_compensation_decision=iva_compensation_decision,
        expected_member_sets=_cross_period_expected_member_sets_from_profile(
            workflow_profile,
            cross_period_expected_member_sets,
        ),
        taxpayer_tax_id=workflow_profile.tax_id,
        activity_start_date=workflow_profile.activity_start_date,
        modelo_202_modality=derive_modelo_202_modality(workflow_profile).modality,
        taxpayer_files_economic_activity=_taxpayer_files_economic_activity(workflow_profile),
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

    # Determine the filing disposition ONCE from the same shared resolver the
    # export reads (resolve_modelo_result_disposition): a Modelo 303 devolución
    # period (REDEME monthly-refund or non-REDEME last-period opt-in) returns the
    # credit, so the cross-period carry persisted below must generate zero
    # compensación rather than double-claim the refunded credit into the next
    # period's casilla 110. The export's fichero "D" and this carry now read one
    # determined fact from the same ``refund_election`` (RD 1624/1992 art. 30 /
    # Ley 37/1992 art. 116). An out-of-window ``DEVOLVER`` election is refused
    # here, before the filing transition persists.
    refunded = revision_is_refund_disposition(
        work_unit=work_unit,
        revision=target,
        workflow_profile=workflow_profile,
        period=work_unit.period,
        refund_election=refund_election,
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
        refunded=refunded,
    )


def list_filing_records(
    *,
    bucket_id: str | None = None,
    include_superseded: bool = False,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
) -> tuple[ModeloRecord, ...]:
    """List :class:`ModeloRecord` filing records, optionally filtered to a bucket.

    Superseded records are excluded unless ``include_superseded``
    is true. Results are sorted by ``(bucket_id, filing_year,
    modelo, period, filed_at)``.
    """
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    catalogue = fr_repo.load()
    records = tuple(
        record
        for record in catalogue.values()
        if (bucket_id is None or record.bucket_id == bucket_id)
        and (include_superseded or record.status is ModeloRecordStatus.VIGENTE)
    )
    return tuple(
        sorted(
            records,
            key=lambda r: (r.bucket_id, r.filing_year, str(r.modelo), r.period, r.filed_at),
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
    calculation_revision_id: str | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
) -> tuple[VerificationReport, ...]:
    """List :class:`VerificationReport` records, optionally filtered to one calculation revision.

    Results are sorted by ``(calculation_revision_id, run_at)``.
    """
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    catalogue = vr_repo.load()
    reports = tuple(
        r
        for r in catalogue.values()
        if calculation_revision_id is None or r.calculation_revision_id == calculation_revision_id
    )
    return tuple(sorted(reports, key=lambda r: (r.calculation_revision_id, r.run_at)))


def get_verification_report(
    verification_report_id: str,
    *,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
) -> VerificationReport:
    """Return one :class:`VerificationReport` by id, or raise."""
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    catalogue = vr_repo.load()
    report = catalogue.get(verification_report_id)
    if report is None:
        raise VerificationReportNotFoundError(
            translated_message="application.modelo.errors.verification_report_not_found",
            context={"verification_report_id": verification_report_id},
        )
    return report
