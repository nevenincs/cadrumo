"""Modelo file-flow application tests split by workflow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import NamedTuple, cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.calculation_catalogue_tamper_support import (
    plant_calculation_revision_unchecked,
)
from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.modelo.action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    VerificationOutcomeIncompleteError,
)
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.calculation_revision_queries import get_calculation_revision
from cadrumo.application.modelo.revision_selection_operation import (
    MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionExecutor,
    ModeloWorkRevisionProjection,
    ModeloWorkRevisionRequest,
)
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.verification_repository_ports import VerificationRepositoryBundle
from cadrumo.application.modelo.work_lifecycle import get_work_unit
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.workflow.run_models import WorkflowDeadlineContextDetails, WorkflowPurpose, WorkflowStage
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.domain.modelos.calculation_repository import (
    CalculationRevisionPersistenceError,
    upsert_calculation_revision,
)
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
)
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_filing_action_ports,
    build_work_lifecycle_ports,
)
from cadrumo.entrypoints.tests.filing_record_read_support import (
    persisted_verification_report,
    persisted_verification_reports,
)
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    FILE_FLOW_PROFILE_ID,
    M130_CARRY_FORWARD_CASILLA,
    M130_HOME_DEDUCTION_CASILLA,
    T1,
    T2,
    T3,
    VERIFY_MODELO,
    VERIFY_PERIOD,
    VERIFY_REVISION,
    Repos,
    calculate_baseline_130_revision,
    canonical_work_unit_period,
    registry_required_manual_casillas,
    seed_modelo_193_work_unit,
    seed_work_unit,
    verify_revision,
    workflow_gate,
    workflow_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def _verification_repositories_for_test(repos: Repos):
    """Compose verification capabilities while retaining fixture repositories."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    return replace(
        build_test_verification_repository_bundle(),
        work_unit=wu_repo,
        calculation=cr_repo,
        filing=fr_repo,
        verification=vr_repo,
        bucket_event=bv_repo,
    )


def test_verify_refuses_persisted_registry_revision_divergence(repos: Repos) -> None:
    """Verification cannot interpret a stored calculation under a different schema."""
    wu_repo, cr_repo, _, _vr_repo, _bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_baseline_130_revision(work_unit)
    stale = revision.model_copy(
        update={
            "registry_snapshot_ref": revision.registry_snapshot_ref.model_copy(
                update={"revision_id": "persisted-stale-revision"}
            )
        }
    )
    # The planted coordinate also contradicts its saved rendering snapshot.
    # Pin that concrete integrity failure before asserting the sanitized read
    # refusal, so an unrelated persistence failure cannot satisfy this test.
    with pytest.raises(ValidationError, match="saved rendering snapshot belongs to another calculation coordinate"):
        type(stale).model_validate(stale.model_dump(mode="python", context={"secure_calculation_revision": True}))
    plant_calculation_revision_unchecked(cr_repo.load(), stale)

    # The repository read refuses the planted row before the action reaches its
    # own divergence check.
    with (
        pytest.raises(CalculationRevisionPersistenceError) as refusal,
        bundled_indexed_authority().operation() as operation,
    ):
        verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            actor="operator-A",
            workflow_profile=workflow_profile(),
            clock=T1,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert refusal.value.context == {"reason": "invalid_payload"}


def test_verify_grants_for_a_closed_past_period_real_registry(repos: Repos, monkeypatch: pytest.MonkeyPatch) -> None:
    """``work verify`` is independent of the AEAT filing calendar.

    A modelo 130 calculation for 2024 Q1 — whose filing window closed
    in April 2024 — is verified at a 2026 clock. ``compute_obligation``
    derives the schedule from ``today.year`` (2026), so no obligation
    exists for the 2024 period at all. The pre-deadline-independence
    behaviour aborted here with ``NO_PENDING_OBLIGATION``; verify must
    now still grant ``VERIFICADO_COMPLETO`` because the calculation is
    sound and verification does not depend on the filing window.
    """

    wu_repo, cr_repo, _, _vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)

    revision = calculate_baseline_130_revision(work_unit)

    reads: list[str] = []
    load = cr_repo.load
    load_revisioned = cr_repo.load_revisioned

    def counted_load(*, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue:
        reads.append("load")
        return load(operation=operation)

    def counted_load_revisioned(
        *, operation: PinnedAuthorityOperation | None = None
    ) -> tuple[CalculationRevisionCatalogue, str]:
        reads.append("load_revisioned")
        return load_revisioned(operation=operation)

    with bundled_indexed_authority().operation() as operation:
        seed_clean_cross_period_sources(
            work_unit,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=repos[2],
            bucket_event_repository=bv_repo,
            operation=operation,
        )
        gate = workflow_gate(revision=revision, work_unit=work_unit, clock=T2, operation=operation)
        with monkeypatch.context() as scoped:
            scoped.setattr(cr_repo, "load", counted_load)
            scoped.setattr(cr_repo, "load_revisioned", counted_load_revisioned)
            report = verify_modelo_revision_with_preconditions(
                revision.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=_verification_repositories_for_test(repos),
                actor="operator-A",
                workflow_profile=gate.profile,
                workflow_engine=gate.engine,
                clock=T2,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            ).report

    assert reads == ["load_revisioned"], reads

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE

    with bundled_indexed_authority().operation() as operation:
        refreshed = get_calculation_revision(
            revision.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
        )
    assert refreshed.state is CalculationRevisionState.VERIFICADO_COMPLETO


def test_verify_repairs_missing_current_revision_pointer(repos: Repos) -> None:
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    baseline_inputs = dict(DEFAULT_130_BASELINE_INPUTS)
    baseline_inputs.pop(M130_CARRY_FORWARD_CASILLA, None)
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=baseline_inputs,
            binding_values=DEFAULT_130_BINDING_VALUES,
            clock=T1,
        ).revision
    calculated_work_unit = get_work_unit(
        work_unit.work_unit_id, ports=build_work_lifecycle_ports(bucket_id=FILE_FLOW_PROFILE_ID)
    )
    assert calculated_work_unit.current_calculation_revision_id == revision.calculation_revision_id
    wu_repo.save(
        upsert_work_unit(
            wu_repo.load(),
            calculated_work_unit.model_copy(update={"current_calculation_revision_id": None}),
        ),
    )

    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert report.granted_verificado_completo is True
    repaired = get_work_unit(work_unit.work_unit_id, ports=build_work_lifecycle_ports(bucket_id=FILE_FLOW_PROFILE_ID))
    assert repaired.current_calculation_revision_id == revision.calculation_revision_id


def test_verify_does_not_overwrite_different_current_revision(repos: Repos) -> None:
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    baseline_inputs = dict(DEFAULT_130_BASELINE_INPUTS)
    baseline_inputs.pop(M130_CARRY_FORWARD_CASILLA, None)
    with bundled_indexed_authority().operation() as operation:
        first = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=baseline_inputs,
            binding_values=DEFAULT_130_BINDING_VALUES,
            clock=T1,
        ).revision
    second_inputs = dict(baseline_inputs)
    second_inputs[M130_HOME_DEDUCTION_CASILLA] = second_inputs[M130_HOME_DEDUCTION_CASILLA] + Decimal("1")
    with bundled_indexed_authority().operation() as operation:
        second = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=second_inputs,
            binding_values=DEFAULT_130_BINDING_VALUES,
            clock=T2,
        ).revision
    assert first.calculation_revision_id != second.calculation_revision_id
    current_work_unit = get_work_unit(
        work_unit.work_unit_id, ports=build_work_lifecycle_ports(bucket_id=FILE_FLOW_PROFILE_ID)
    )
    assert current_work_unit.current_calculation_revision_id == second.calculation_revision_id

    report = verify_revision(
        first.calculation_revision_id,
        revision=first,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    assert report.granted_verificado_completo is True
    preserved = get_work_unit(work_unit.work_unit_id, ports=build_work_lifecycle_ports(bucket_id=FILE_FLOW_PROFILE_ID))
    assert preserved.current_calculation_revision_id == second.calculation_revision_id


def test_verify_records_deadline_state_as_informational_not_abort(repos: Repos) -> None:
    """The verify run's ``COMPUTING_DEADLINES`` step never aborts.

    For a closed past period it records the filing-window state as an
    informational success step, so ``readiness`` and ``verify`` agree:
    a readiness-ready modelo stays reachable by verify.
    """

    wu_repo, _cr_repo, _, _, _bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values=DEFAULT_130_BINDING_VALUES,
            clock=T1,
        ).revision
        gate = workflow_gate(revision=revision, work_unit=work_unit, clock=T2, operation=operation)
        result = asyncio.run(
            gate.engine.run_for_period(
                gate.profile,
                work_unit.modelo,
                canonical_work_unit_period(work_unit),
                today=T2.date(),
                purpose=WorkflowPurpose.VERIFY,
            ),
        )

    assert result.final_stage is WorkflowStage.DONE
    assert result.aborted_reason is None
    deadline_steps = [s for s in result.steps if s.stage is WorkflowStage.COMPUTING_DEADLINES]
    assert len(deadline_steps) == 1
    deadline_step = deadline_steps[0]
    assert deadline_step.success is True
    assert isinstance(deadline_step.details, WorkflowDeadlineContextDetails)
    assert deadline_step.details.deadline_role is not None
    assert deadline_step.details.deadline_role.value == "informational"


def test_get_calculation_revision_raises_on_missing_id(repos: Repos) -> None:
    _, _cr_repo, _, _, _ = repos
    with pytest.raises(CalculationRevisionNotFoundError), bundled_indexed_authority().operation() as operation:
        get_calculation_revision(
            "0" * 64,
            ports=build_calculation_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
        )


def test_verify_grants_when_all_required_casillas_present_real_registry(
    repos: Repos,
) -> None:
    """Real e2e: registry resolves modelo 180 (2024, 0A); every required
    manual casilla is supplied; the verifier persists a granted report
    in encrypted storage; the calculation revision transitions
    DRAFT → VERIFICADO_COMPLETO. No mocks, no in-memory fakes — the
    SQL repository encrypts on save and decrypts on load."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    required = registry_required_manual_casillas(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )

    revision = calculate_baseline_130_revision(work_unit)

    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    # The report carries no BLOCKING finding. Other non-blocking advisory findings
    # may be present, but source-revision re-confirmation failures are blockers.
    assert not any(f.severity is ModeloVerificationFindingSeverity.BLOCKING for f in report.findings)
    assert all(f.kind is ModeloVerificationFindingKind.ADVISORY for f in report.findings)
    assert set(report.resolved_casilla_ids) == set(required)
    assert report.missing_required_casilla_ids == ()

    with bundled_indexed_authority().operation() as operation:
        refreshed = get_calculation_revision(
            revision.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
        )
    assert refreshed.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert refreshed.verified_at == T2
    assert refreshed.verified_by == "operator-A"

    # Round-trip through encrypted storage.
    with bundled_indexed_authority().operation() as operation:
        persisted = persisted_verification_report(
            report.verification_report_id,
            ports=build_filing_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
            operation=operation,
        )
    assert persisted.granted_verificado_completo is True
    assert persisted.completeness_status is VerificationCompletenessStatus.COMPLETE


def test_verify_refuses_when_required_casilla_missing_real_registry(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Real e2e: omit one required casilla; the verifier emits a
    BLOCKING ``MISSING_REQUIRED_CASILLA`` finding for it; the
    revision stays DRAFT; the refused report is still persisted so
    the audit trail records the refusal."""

    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    work_unit = seed_modelo_193_work_unit(wu_repo)
    required = registry_required_manual_casillas(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    assert required

    omitted = required[0]
    supplied = {cid: Decimal("1") for cid in required[1:]}

    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=supplied,
            clock=T1,
        ).revision
    seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        operation=operation,
    )

    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            actor="operator-A",
            workflow_profile=workflow_profile(),
            clock=T2,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report

    assert report.granted_verificado_completo is False
    # No per-perceptor withholding record exists, and the bucket calculation notes that absence
    # as blocking, so the report is blocked beside the missing casilla rather than only incomplete.
    assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
    assert any(
        f.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
        and f.severity is ModeloVerificationFindingSeverity.BLOCKING
        and f.casilla_id == omitted
        for f in report.findings
    )
    assert omitted in report.missing_required_casilla_ids

    with bundled_indexed_authority().operation() as operation:
        refreshed = get_calculation_revision(
            revision.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
        )
    assert refreshed.state is CalculationRevisionState.BORRADOR

    with bundled_indexed_authority().operation() as operation:
        persisted = persisted_verification_report(
            report.verification_report_id,
            ports=build_filing_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
            operation=operation,
        )
    assert persisted.granted_verificado_completo is False


def test_work_unit_creation_refuses_unresolvable_registry_snapshot_before_verify(repos: Repos) -> None:
    """An unsupported coordinate cannot create state for a later verify path."""

    from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError

    wu_repo, _, _, _, _ = repos
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        seed_work_unit(
            wu_repo,
            modelo=VERIFY_MODELO,
            filing_year=2010,
            period=VERIFY_PERIOD,
            revision_id=VERIFY_REVISION,
        )


def test_verify_reverify_collapses_to_existing_report_real_registry(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Real e2e: re-verifying an already-verified revision is a guarded no-op.

    Per aeat-cli-contract, verify is a creating
    mutation keyed on the clock-free derived report id
    (``derive_verification_report_id`` folds the outcome, not ``run_at``). A retry
    against a locked ``VERIFICADO_COMPLETO`` revision — whose content, and thus
    verification outcome, cannot change — collapses to the EXISTING granting
    report: same report id, ``run_at`` unchanged (NOT re-stamped to the retry
    clock), no second verification lifecycle event, revision still verified. It
    must never refuse. Mirrors the re-file no-op.
    """

    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_baseline_130_revision(work_unit)
    seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        first = verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            actor="operator-A",
            workflow_profile=workflow_profile(),
            clock=T2,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report
    assert first.granted_verificado_completo is True
    with bundled_indexed_authority().operation() as operation:
        refreshed_state = get_calculation_revision(
            revision.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
        ).state
    assert refreshed_state is CalculationRevisionState.VERIFICADO_COMPLETO

    def _verification_event_ids() -> tuple[str, ...]:
        events = bv_repo.load().for_bucket(
            work_unit.bucket_id,
            event_types=(
                BucketEventType.MODELO_VERIFICATION_PASSED,
                BucketEventType.MODELO_VERIFICATION_REFUSED,
            ),
        )
        return tuple(event.event_id for event in events)

    event_ids_after_first = _verification_event_ids()
    with bundled_indexed_authority().operation() as operation:
        reports_after_first = tuple(
            r.verification_report_id
            for r in persisted_verification_reports(
                calculation_revision_id=revision.calculation_revision_id,
                ports=build_filing_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
                operation=operation,
            )
        )

    # Re-verify at a LATER clock (T3): must collapse, not refuse.
    with bundled_indexed_authority().operation() as operation:
        second = verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            actor="operator-A",
            workflow_profile=workflow_profile(),
            clock=T3,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report

    # Same content-addressed report; anti-tautology — run_at stays T2, NOT re-stamped to T3.
    assert second.verification_report_id == first.verification_report_id
    assert second.run_at == first.run_at == T2
    assert second.granted_verificado_completo is True
    # No second lifecycle event, and the report catalogue is unchanged.
    assert _verification_event_ids() == event_ids_after_first
    with bundled_indexed_authority().operation() as operation:
        reports_after_second = tuple(
            r.verification_report_id
            for r in persisted_verification_reports(
                calculation_revision_id=revision.calculation_revision_id,
                ports=build_filing_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
                operation=operation,
            )
        )
    assert reports_after_second == reports_after_first
    with bundled_indexed_authority().operation() as operation:
        refreshed_state = get_calculation_revision(
            revision.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
        ).state
    assert refreshed_state is CalculationRevisionState.VERIFICADO_COMPLETO


def test_verify_refuses_non_draft_revision_with_no_granting_report(repos: Repos) -> None:
    """The idempotent collapse stays guarded: a non-draft revision with NO granting
    report is an inconsistent state that still refuses.

    This is the anti-tautology proof for the collapse — the fix does not blanket-
    accept every non-draft revision; it collapses ONLY when a granting report
    actually exists, and otherwise keeps the hard state refusal.
    """

    wu_repo, cr_repo, _, _vr_repo, _bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values=DEFAULT_130_BINDING_VALUES,
            clock=T1,
        ).revision
    # Construct the inconsistent persisted state directly: this test owns the
    # verifier's refusal of a sealed revision that has no granting report.
    verified = revision.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": T2,
            "verified_by": "operator-A",
            "updated_at": T2,
        }
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), verified))
    assert verified.state is CalculationRevisionState.VERIFICADO_COMPLETO

    with (
        pytest.raises(CalculationRevisionStateError, match=r"state|DRAFT|draft"),
        bundled_indexed_authority().operation() as operation,
    ):
        verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            actor="operator-A",
            workflow_profile=workflow_profile(),
            clock=T3,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )


def test_list_and_get_verification_reports_real_registry(repos: Repos) -> None:
    """Real e2e: reports persist through the encrypted catalogue and
    are indexable by id and by calculation_revision_id."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_baseline_130_revision(work_unit)
    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    with bundled_indexed_authority().operation() as operation:
        listed = persisted_verification_reports(
            calculation_revision_id=revision.calculation_revision_id,
            ports=build_filing_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
            operation=operation,
        )
        assert tuple(r.verification_report_id for r in listed) == (report.verification_report_id,)

        fetched = persisted_verification_report(
            report.verification_report_id,
            ports=build_filing_action_ports(bucket_id=FILE_FLOW_PROFILE_ID, operation=operation),
            operation=operation,
        )
        assert fetched.verification_report_id == report.verification_report_id


def _received_invoice(bucket_id: str, *, number: str, issued_at: date) -> Invoice:
    base_total, iva_total = Decimal("2479.34"), Decimal("520.66")
    grand_total = base_total + iva_total
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=InvoiceKind.RECEIVED,
            invoice_number=number,
            issued_at=issued_at,
            counterparty_tax_id="B00015016",
            currency="EUR",
            grand_total=grand_total,
        ),
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_name="PROVEEDOR EJEMPLO SL",
        counterparty_tax_id="B00015016",
        counterparty_country="ES",
        base_total=base_total,
        iva_total=iva_total,
        grand_total=grand_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Operacion interior",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva_total,
            ),
        ),
        payment_status=PaymentStatus.PAID,
    )


def test_verify_takes_modelo_347_counterparty_fields_from_their_rows_real_registry(repos: Repos) -> None:
    """Modelo 347's counterparty NIF and operation key are answered by the detail rows.

    Both are required manual casillas, and both are fields the counterparty
    record fills once per row, so calculate refuses them as scalar inputs.
    Verify has to read them the same way, or a return whose every counterparty
    row carries them would be refused for want of scalars it cannot accept.
    """
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, modelo="347", filing_year=2024, period="0A", revision_id="2011-2024")
    # Four received invoices of 3.000,00 from one supplier, one per quarter: a declarable
    # 12.000,00 counterparty (clave A) that the invoice resolver puts on the row channel.
    invoices = tuple(
        _received_invoice(work_unit.bucket_id, number=f"P-{quarter}", issued_at=date(2024, 3 * quarter - 1, 10))
        for quarter in (1, 2, 3, 4)
    )
    InvoiceCatalogueRepository(bucket_id=work_unit.bucket_id).save(build_invoice_catalogue(invoices))

    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            clock=T1,
        ).revision
    assert revision.row_binding_values["modelo-347-contraparte-row-nif"] == {"1": "B00015016"}
    assert Decimal(revision.row_binding_values["modelo-347-contraparte-row-importe"]["1"]) == Decimal("12000.00")
    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    row_fields = {"contraparte.nif", "contraparte.clave-operacion"}
    assert not row_fields & {str(casilla_id) for casilla_id in report.missing_required_casilla_ids}, report.findings


def _select_revision_to_file(
    bundle: VerificationRepositoryBundle, calculation_revision_id: str, operation: PinnedAuthorityOperation
) -> ModeloWorkRevisionProjection:
    """Select one revision for filing through the registered selection executor over real repositories."""
    subject_ref = profile_operation_subject(FILE_FLOW_PROFILE_ID)
    request = OperationRequest[ModeloWorkRevisionRequest](
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=ModeloWorkRevisionRequest(
            profile_id=UUID(FILE_FLOW_PROFILE_ID),
            calculation_revision_id=calculation_revision_id,
            default_for="file",
        ),
    )
    captured: list[BaseModel] = []

    class Events:
        async def phase(self, phase_code: object) -> None:
            del phase_code

        async def effect(self, effect: OperationEffect) -> None:
            assert effect is OperationEffect.NONE

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            del written_at
            captured.append(operand)
            return "selection"

    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                authority_operation=operation,
                identity=SimpleNamespace(subject_ref=subject_ref),
                events=Events(),
                operands=Operands(),
            ),
        ),
    )
    asyncio.run(
        ModeloWorkRevisionExecutor(lambda _profile_id, *, operation, mutation_writer=None: bundle).execute(
            request, context
        )
    )
    (projection,) = captured
    assert isinstance(projection, ModeloWorkRevisionProjection)
    return projection


class _GrantWithoutLock(NamedTuple):
    """A Modelo 130 revision whose verification granted but whose lock never landed."""

    work_unit_bucket_id: str
    revision_id: str
    first: VerificationReport
    verify: Callable[[datetime, str], VerificationReport]


def _grant_without_lock(repos: Repos) -> _GrantWithoutLock:
    """Grant a revision, then put back its unlocked record, as a lost lock write leaves it."""
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    baseline_inputs = dict(DEFAULT_130_BASELINE_INPUTS)
    baseline_inputs.pop(M130_CARRY_FORWARD_CASILLA, None)
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=baseline_inputs,
            binding_values=DEFAULT_130_BINDING_VALUES,
            clock=T1,
        ).revision
    assert revision.state is CalculationRevisionState.BORRADOR

    def verify(clock: datetime, actor: str) -> VerificationReport:
        report = verify_revision(
            revision.calculation_revision_id,
            revision=revision,
            work_unit=work_unit,
            actor=actor,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=clock,
        )
        assert isinstance(report, VerificationReport)
        return report

    first = verify(T2, "operator-A")
    assert first.granted_verificado_completo is True
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    assert cr_repo.load().revisions[revision.calculation_revision_id].state is CalculationRevisionState.BORRADOR
    return _GrantWithoutLock(work_unit.bucket_id, revision.calculation_revision_id, first, verify)


def _stored_grant_ids(bucket_id: str, calculation_revision_id: str) -> list[str]:
    with bundled_indexed_authority().operation() as operation:
        stored = persisted_verification_reports(
            calculation_revision_id=calculation_revision_id,
            ports=build_filing_action_ports(bucket_id=bucket_id, operation=operation),
            operation=operation,
        )
    return [report.verification_report_id for report in stored if report.granted_verificado_completo]


def _select_to_file(calculation_revision_id: str) -> ModeloWorkRevisionProjection:
    with bundled_indexed_authority().operation() as operation:
        return _select_revision_to_file(build_test_verification_repository_bundle(), calculation_revision_id, operation)


def test_a_grant_saved_before_its_revision_was_locked_is_settled_by_verifying_again(repos: Repos) -> None:
    """Verification saves its report, then locks the revision in a separate write.

    When the second write never lands, the profile holds a granted report beside
    a revision still in BORRADOR. Filing refuses that pair as an incomplete
    verification rather than trusting the report, and verifying again settles
    it: the identical outcome collapses onto the one saved report and the
    revision is locked.
    """
    lost = _grant_without_lock(repos)
    with pytest.raises(VerificationOutcomeIncompleteError):
        _select_to_file(lost.revision_id)

    second = lost.verify(T3, "operator-A")

    assert second.granted_verificado_completo is True
    assert second.verification_report_id == lost.first.verification_report_id
    assert _stored_grant_ids(lost.work_unit_bucket_id, lost.revision_id) == [lost.first.verification_report_id]
    selected = _select_to_file(lost.revision_id)
    assert selected.calculation_state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert selected.granted_verificado_completo is True
    assert selected.verification_report_id == lost.first.verification_report_id


def test_verifying_again_from_another_surface_after_a_lost_lock_keeps_one_grant(repos: Repos) -> None:
    """The window verified, its lock was lost, and the command line verified again under its own actor.

    The second actor's outcome is a distinct report, and it supersedes the
    first actor's grant rather than standing beside it, so the revision is
    locked with exactly the one grant that its lock names and can be filed.
    """
    lost = _grant_without_lock(repos)

    second = lost.verify(T3, "operator-B")

    assert second.granted_verificado_completo is True
    assert second.verification_report_id != lost.first.verification_report_id
    assert _stored_grant_ids(lost.work_unit_bucket_id, lost.revision_id) == [second.verification_report_id]
    selected = _select_to_file(lost.revision_id)
    assert selected.calculation_state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert selected.granted_verificado_completo is True
    assert selected.verification_report_id == second.verification_report_id


def test_a_revision_already_locked_beside_a_stray_grant_can_be_filed_on_its_own_grant(repos: Repos) -> None:
    """A profile whose earlier verifications left two grants on a locked revision is not stuck.

    The stray grant comes from the attempt whose lock never landed; it does not
    match the revision's lock, so selection for filing takes the grant the lock
    names instead of refusing the revision forever.
    """
    _wu_repo, _cr_repo, _, vr_repo, _bv_repo = repos
    lost = _grant_without_lock(repos)
    second = lost.verify(T3, "operator-B")
    # The catalogue as an earlier verification left it, with the first actor's grant beside the lock's.
    vr_repo.save(
        VerificationReportCatalogue(reports={**vr_repo.load().reports, lost.first.verification_report_id: lost.first})
    )
    assert sorted(_stored_grant_ids(lost.work_unit_bucket_id, lost.revision_id)) == sorted(
        [lost.first.verification_report_id, second.verification_report_id]
    )

    selected = _select_to_file(lost.revision_id)

    assert selected.calculation_state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert selected.granted_verificado_completo is True
    assert selected.verification_report_id == second.verification_report_id
