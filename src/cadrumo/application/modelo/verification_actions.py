"""Verify modelo revisions and persist their reports, co-commits, and lifecycle events."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import Settings
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.secure_object_write import SecureObjectWrite
from ...core.time.clock import now as _utc_now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.calculation_repository import upsert_calculation_revision
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ...domain.modelos.participation_index import TransactionRevisionParticipation, upsert_transaction_participation
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    TransactionParticipationIndexRepositoryProtocol,
)
from ...domain.modelos.repository import upsert_work_unit
from ...domain.modelos.verification_report import (
    VerificationCompletenessStatus,
)
from ...domain.modelos.verification_repository import upsert_verification_report
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.ledger_filing_snapshot import (
    assert_evidence_covers_snapshot,
    compute_ledger_filing_snapshot,
)
from ..calculations.cross_period_models import CrossPeriodExpectedMemberSet
from ..calculations.m303_regimen_simplificado_annual_summary import (
    validate_m303_regimen_simplificado_annual_summary_target_revision,
)
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
from ..workflow.engine import WorkflowEngine
from ..workflow.run_models import WorkflowPurpose
from ._ledger_anchor_capture import capture_revision_ledger_evidence
from ._registry_helpers import assert_revision_content_integrity as _assert_revision_content_integrity
from ._required_binding_gate import (
    require_persisted_revision_required_bindings_resolved as _require_persisted_required_bindings_resolved,
)
from .action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    WorkUnitNotFoundError,
)
from .calculation_note_gate import require_work_unit_calculation_unblocked
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .lifecycle_clock_gate import (
    ModeloLifecycleClockOperation,
    require_lifecycle_clock_not_before,
    verification_ordering_instants,
)
from .m123_count_authority_gate import Modelo123CountAuthorityStage, require_modelo_123_count_authority
from .m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_annual_summary_applies_to_profile,
    taxpayer_profile_for_work,
)
from .revision_persistence import (
    emit_modelo_bucket_event as _emit_bucket_event,
)
from .revision_persistence import (
    require_filing_instance_evidence_for_work_unit,
)
from .stored_row_field_input_gate import refuse_stored_row_field_scalar_inputs as _refuse_stored_row_field_scalar_inputs
from .verification_gate_findings import collect_verification_gate_findings
from .verification_model_findings import append_readable_model_findings
from .verification_preconditions import (
    ModeloVerificationResult,
    project_verification_findings,
)
from .verification_report_facts import (
    build_verification_report,
    classify_verification_outcome,
    granting_verification_report,
)
from .verification_repository_ports import VerificationRepositoryBundle
from .work_lifecycle import RevisionParentOperation, require_revision_parent_active
from .workflow_gate import build_revision_workflow_engine as _build_revision_workflow_engine
from .workflow_gate import run_revision_workflow_gate as _run_revision_workflow_gate

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
    from ..auth.operator_scope_ports import OperatorScopePorts
    from .work_profile import ModeloWorkProfile


def verify_modelo_revision_with_preconditions(
    calculation_revision_id: CalculationRevisionId,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_scope_ports: OperatorScopePorts,
    actor: str,
    workflow_profile: TaxpayerProfile,
    verification_repositories: VerificationRepositoryBundle,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> ModeloVerificationResult:
    """Evaluate a draft revision against registry, clean-state, provenance, and workflow gates.

    The verifier loads the draft
    :class:`CalculationRevision`,
    resolves its work unit and :class:`RegistrySnapshot`, builds verify-time findings,
    classifies the outcome, persists a :class:`VerificationReport`, records
    bucket history, and updates the :class:`CalculationRevision` only when the
    verified-complete transition is granted.

    The supplied :class:`TaxpayerProfile` scopes
    deadline/applicability decisions. The transaction port in the required
    :class:`VerificationRepositoryBundle` supplies non-blocking
    transaction-evidence advisories for source rows attached to the revision.
    WARNING-severity advisories remain report content; only BLOCKING severity
    can refuse the transition.

    Args:
        calculation_revision_id: Stable id of the draft
            :class:`CalculationRevision` to verify.
        certificate_secret_backend_factory: Factory for the certificate-secret
            capability used by the workflow gate when verification grants.
        operator_scope_ports: Operator-scope capabilities used by the workflow
            gate when verification grants.
        actor: Operator label recorded on the verification report and bucket
            history event.
        workflow_profile: :class:`TaxpayerProfile`
            supplying profile facts for workflow, deadline, applicability, and
            registry predicate gates.
        verification_repositories: Required application-owned bundle containing
            every repository capability used by the verification gates and
            persistence path. The outer composition root binds all concrete
            implementations for one profile bucket.
        cross_period_expected_member_sets: Optional expected-member overrides
            for the cross-period clean-state gate.
        workflow_engine: Optional :class:`~cadrumo.application.workflow.engine.WorkflowEngine`
            override for tests and controlled workflow runs.
        workflow_runs_dir: Optional workflow-runs directory override.
        settings: Optional runtime settings for workflow-engine construction.
        clock: Optional timestamp override for deterministic verification.
        operation: Caller-owned generation-pinned authority operation. When
            supplied, every registry snapshot and point consumer in this path
            reads from that operation generation.
        profile: The work profile the calling command already loaded for the
            revision's bucket. When omitted, this entry loads it once; every
            profile read below uses the record the readiness gate checked.

    Returns:
        The application result containing the persisted
        :class:`VerificationReport` and its ordered typed preconditions.

    Raises:
        :class:`~cadrumo.application.modelo.action_errors.CalculationRevisionNotFoundError`: The
            requested calculation revision does not exist in the active
            catalogue.
        :class:`~cadrumo.application.modelo.action_errors.CalculationRevisionStateError`: The
            revision is not in ``BORRADOR`` state.
        :class:`~cadrumo.application.modelo.action_errors.WorkUnitNotFoundError`: The owning work
            unit is missing.
        :class:`~cadrumo.application.modelo.action_errors.ModeloCrossPeriodCleanStateError`: A
            required cross-period dependency has a blocking clean-state finding.
        :class:`~cadrumo.application.modelo.lifecycle_clock_gate.ModeloLifecycleClockPrecedesError`:
            ``clock`` precedes the revision's or work unit's ``created_at``;
            refused before anything is persisted.
    """
    repos = verification_repositories
    cr_repo = repos.calculation
    wu_repo = repos.work_unit
    vr_repo = repos.verification
    # Revisioned, and threaded to the persistence below: the catalogue is
    # composed into a co-commit there, so it cannot use a self-committing
    # mutation, and the revision belongs to whoever performed the read.
    revisions, revisions_revision_id = cr_repo.load_revisioned(operation=operation)
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
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}",
        )
    require_revision_parent_active(
        work_unit=work_unit,
        calculation_revision_id=calculation_revision_id,
        operation=RevisionParentOperation.VERIFY,
    )
    # Before the idempotent no-op below: a revision granted before evidence was
    # captured must not be reported as verified beside that evidence either.
    require_modelo_123_count_authority(
        work_unit,
        retencion_ports=repos.retencion_observation_ports,
        stage=Modelo123CountAuthorityStage.VERIFY,
    )
    if target.state is not CalculationRevisionState.BORRADOR:
        # Idempotent re-verify (aeat-cli-contract): a
        # revision that has already been verified-and-granted (VERIFICADO_COMPLETO,
        # or PRESENTADO after filing) is LOCKED — its content, and therefore its
        # verification outcome, cannot change — so a retry returns the existing
        # granting VerificationReport as a clean no-op: no re-run of the
        # verification gates, no duplicate report (the report id is clock-free —
        # derive_verification_report_id folds the outcome, not run_at), and no
        # second lifecycle event. The CLI surfaces the no-op as an info Notice.
        # A non-draft revision with no granting report is an inconsistent state,
        # so it falls through to the hard refusal below rather than fabricating
        # one. Mirrors the re-file no-op in file_modelo_revision.
        existing = granting_verification_report(
            require_verification_report_coordinates_current(vr_repo.load(operation=operation), operation=operation),
            calculation_revision_id,
        )
        if existing is not None:
            return ModeloVerificationResult(
                report=existing,
                published=False,
                finding_preconditions=project_verification_findings(
                    existing.findings,
                    failures_by_finding_id={},
                ),
            )
        raise CalculationRevisionStateError(
            translated_message="errors.error.error_modelo_calculation_revision_state",
            context={"calculation_revision_id": calculation_revision_id, "state": target.state.value},
        )

    _assert_revision_content_integrity(target)
    _refuse_stored_row_field_scalar_inputs(target, work_unit=work_unit, operation=operation)
    from .profile_readiness_gate import load_modelo_work_profile, require_profile_ready_for_work_unit

    if profile is None:
        profile = load_modelo_work_profile(
            bucket_id=work_unit.bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        )
    validate_m303_regimen_simplificado_annual_summary_target_revision(
        target_work_unit=work_unit,
        target_revision=target,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=repos.filing,
        regimen_simplificado_applies=m303_regimen_simplificado_annual_summary_applies_to_profile(
            taxpayer_profile_for_work(profile),
        ),
        operation=operation,
    )
    require_filing_instance_evidence_for_work_unit(work_unit=work_unit, revision=target)

    checked_profile = require_profile_ready_for_work_unit(
        work_unit,
        profile_decode_context=operation.profile_decode_context(),
        operation=operation,
        profile=profile,
    )
    _require_persisted_required_bindings_resolved(
        work_unit=work_unit, revision=target, action="verify", operation=operation
    )
    require_work_unit_calculation_unblocked(work_unit=work_unit, revision=target, action="verify", operation=operation)

    now = clock or _utc_now()
    # Finding collection can refresh persisted wallet authority.
    require_lifecycle_clock_not_before(
        now,
        operation=ModeloLifecycleClockOperation.VERIFY,
        instants=verification_ordering_instants(revision=target, work_unit=work_unit),
    )
    findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id = (
        collect_verification_gate_findings(
            work_unit=work_unit,
            target=target,
            workflow_profile=workflow_profile,
            observation_repository=repos.observation,
            filing_repository=repos.filing,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            justificante_repository=repos.justificante,
            transaction_repository=repos.transaction,
            invoice_repository=repos.draft_review_ports.invoice_repository,
            iva_compensation_decision_repository=repos.iva_compensation_decision,
            iva_compensation_history_repository=repos.iva_compensation_history,
            cross_period_expected_member_sets=cross_period_expected_member_sets,
            operation=operation,
            work_profile=checked_profile,
            ledger_membership_ports=repos.ledger_membership_ports,
            evaluated_at=now,
        )
    )
    # A registry-snapshot refusal already stands as a blocking finding, and
    # without a valid snapshot the model-specific checks have nothing to compare
    # against; running them would only re-request the refused snapshot.
    append_readable_model_findings(findings, failures_by_finding_id, work_unit, target, repos, operation)
    completeness, granted = classify_verification_outcome(
        findings=findings,
        missing_required=missing_required_casilla_ids,
    )

    report = build_verification_report(
        calculation_revision_id=calculation_revision_id,
        registry_snapshot_ref=target.registry_snapshot_ref,
        findings=findings,
        resolved_casilla_ids=resolved_casilla_ids,
        missing_required_casilla_ids=missing_required_casilla_ids,
        completeness=completeness,
        granted=granted,
        actor=actor,
        run_at=now,
    )

    if granted:
        gate_engine = workflow_engine or _build_revision_workflow_engine(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=operator_scope_ports,
            revision=target,
            work_unit=work_unit,
            profile=workflow_profile,
            actor=actor.strip(),
            clock=now,
            settings=settings,
            draft_review_ports=repos.draft_review_ports,
            workflow_gate_ports=repos.workflow_gate_ports,
            operation=operation,
        )
        _run_revision_workflow_gate(
            engine=gate_engine,
            profile=workflow_profile,
            work_unit=work_unit,
            today=now.date(),
            runs_dir=workflow_runs_dir,
            run_repository=repos.workflow_run,
            purpose=WorkflowPurpose.VERIFY,
        )

    # Persist the report regardless of outcome — failed attempts
    # are part of the audit trail.
    vr_repo.save(
        upsert_verification_report(
            require_verification_report_coordinates_current(vr_repo.load(operation=operation), operation=operation),
            report,
        ),
        operation=operation,
    )

    if granted:
        _persist_verified_revision_evidence(
            target=target,
            actor=actor,
            now=now,
            revisions=revisions,
            revisions_revision_id=revisions_revision_id,
            work_unit=work_unit,
            transaction_repository=repos.transaction,
            calculation_repository=cr_repo,
            participation_index_repository=repos.participation_index,
        )
        _repair_verified_revision_current_pointer(
            work_unit=work_unit,
            calculation_revision_id=calculation_revision_id,
            verified_at=now,
            work_unit_repository=wu_repo,
        )

    _emit_verification_bucket_event(
        repository=repos.bucket_event,
        work_unit=work_unit,
        target=target,
        report_id=report.verification_report_id,
        calculation_revision_id=calculation_revision_id,
        completeness=completeness,
        granted=granted,
        finding_count=len(findings),
        missing_required_count=len(missing_required_casilla_ids),
        actor=actor,
        occurred_at=now,
    )

    return ModeloVerificationResult(
        report=report,
        published=True,
        finding_preconditions=project_verification_findings(
            findings,
            failures_by_finding_id=failures_by_finding_id,
        ),
    )


def _repair_verified_revision_current_pointer(
    *,
    work_unit: WorkUnit,
    calculation_revision_id: CalculationRevisionId,
    verified_at: datetime,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
) -> None:
    work_units = work_unit_repository.load()
    latest = work_units.get(work_unit.work_unit_id)
    if latest is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit.work_unit_id, "phase": "verification"},
        )
    if latest.current_calculation_revision_id == calculation_revision_id:
        return
    if latest.current_calculation_revision_id is not None:
        return

    # Guarded: stamping this pointer rewrites the WHOLE singleton catalogue, so
    # a work unit another operator created or advanced in the interim would be
    # discarded by a repair that was only meant to fill in one pointer. The
    # already-set and absent checks above ran against the catalogue this call
    # read; re-running them inside the mutation is what makes the retry honest,
    # because a concurrent verification may have set the very pointer this
    # repair exists to fill.
    def _stamp(current: WorkUnitCatalogue) -> WorkUnitCatalogue:
        """Fill in the pointer, unless the catalogue being written already has one."""
        present = current.get(work_unit.work_unit_id)
        if present is None or present.current_calculation_revision_id is not None:
            return current
        return upsert_work_unit(
            current,
            present.model_copy(
                update={
                    "current_calculation_revision_id": calculation_revision_id,
                    "updated_at": verified_at,
                },
            ),
        )

    work_unit_repository.mutate(_stamp)


def _build_participation_writes(
    *,
    verified: CalculationRevision,
    work_unit: WorkUnit,
    participation_index_repository: TransactionParticipationIndexRepositoryProtocol,
) -> tuple[SecureObjectWrite, ...]:
    """Build the per-transaction participation-index co-emission writes.

    For each ``source_transaction_id`` of the verified revision, load that
    transaction's existing
    :class:`~TransactionRevisionParticipationIndex`, upsert
    the new ``VERIFICADO_COMPLETO`` participation (replacing any prior entry for
    the same revision), and return the resulting ``SecureObjectWrite`` so the
    caller co-emits them in the same atomic unit of work as the revision save. A
    revision with no contributing transactions yields no writes.
    """
    writes: list[SecureObjectWrite] = []
    for transaction_id in verified.source_transaction_ids:
        index = participation_index_repository.load(transaction_id)
        participation = TransactionRevisionParticipation(
            calculation_revision_id=verified.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_state=CalculationRevisionState.VERIFICADO_COMPLETO.value,
        )
        updated = upsert_transaction_participation(index, participation)
        writes.append(participation_index_repository.to_secure_object_write(updated))
    return tuple(writes)


def _persist_verified_revision_evidence(
    *,
    target: CalculationRevision,
    actor: str,
    now: datetime,
    revisions: CalculationRevisionCatalogue,
    revisions_revision_id: str,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    participation_index_repository: TransactionParticipationIndexRepositoryProtocol,
) -> None:
    catalogue = transaction_repository.load()
    filing_snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=target.source_transaction_ids,
        catalogue=catalogue,
        captured_at=now,
    )
    filing_evidence = capture_revision_ledger_evidence(
        revision=target,
        catalogue=catalogue,
        snapshot_fingerprint=filing_snapshot.snapshot_fingerprint,
        captured_at=now,
    )
    assert_evidence_covers_snapshot(filing_snapshot, filing_evidence)
    verified = target.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
            "ledger_filing_snapshot": filing_snapshot,
            "ledger_filing_evidence": filing_evidence,
        },
    )
    updated_catalogue = upsert_calculation_revision(revisions, verified)
    participation_writes = _build_participation_writes(
        verified=verified,
        work_unit=work_unit,
        participation_index_repository=participation_index_repository,
    )
    # Co-emit the participation index atomically with the revision save (per the
    # composition-service single-writer discipline): the index and the verified
    # revision land or fail together. A revision with no contributing
    # transactions produces no extra writes and degenerates to the plain save.
    calculation_repository.save_with_secure_object_writes(
        updated_catalogue,
        participation_writes,
        expected_revision_id=revisions_revision_id,
    )


def _emit_verification_bucket_event(
    *,
    repository: BucketEventHistoryRepositoryProtocol,
    work_unit: WorkUnit,
    target: CalculationRevision,
    report_id: str,
    calculation_revision_id: CalculationRevisionId,
    completeness: VerificationCompletenessStatus,
    granted: bool,
    finding_count: int,
    missing_required_count: int,
    actor: str,
    occurred_at: datetime,
) -> None:
    _emit_bucket_event(
        repository=repository,
        bucket_id=work_unit.bucket_id,
        event_type=(
            BucketEventType.MODELO_VERIFICATION_PASSED if granted else BucketEventType.MODELO_VERIFICATION_REFUSED
        ),
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.VERIFICATION_REPORT,
        object_id=report_id,
        payload={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": target.work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "completeness_status": completeness.value,
            "finding_count": str(finding_count),
            "missing_required_count": str(missing_required_count),
        },
    )
