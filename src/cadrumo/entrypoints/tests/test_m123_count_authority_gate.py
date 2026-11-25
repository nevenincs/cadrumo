"""Captured capital withholding leaves the Modelo 123 period stored but uncalculable, unverifiable and unfilable."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import (
    CAPITAL_YEAR,
    capital_payment,
    capital_request,
    withholding_producer,
)
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import build_ledger_payment_withholding_capture
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    quarterly_filer_cadence,
    quarterly_filer_cadence_for,
)
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.m123_count_authority_gate import Modelo123CountAuthorityUnresolvedError
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.core.operator_action_enums import NoRecoveryOutcome
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from cadrumo.domain.modelos.verification_report import VerificationReport
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition_work_ports import build_filing_action_ports
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from .modelo_gate_bucket_support import (
    calculate_without_inputs,
    ready_workflow_profile,
    seed_ready_capital_payer_profile,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000123"
_T0 = datetime(CAPITAL_YEAR + 1, 2, 1, 9, 0, tzinfo=UTC)
_ACCRUAL_Q2 = Period.from_year_and_code(CAPITAL_YEAR, "2T")


@dataclass(frozen=True, slots=True)
class _Bucket:
    objects: SecureObjectRepository
    work_unit: WorkUnit


@contextmanager
def _m123_bucket(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> Generator[_Bucket]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M123 count authority") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_ready_capital_payer_profile(bucket_id=_BUCKET_ID, at=_T0)
        snapshot = published_authority_operation().snapshot("123", filing_year=CAPITAL_YEAR, period="2T")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="123",
            filing_year=CAPITAL_YEAR,
            period=_ACCRUAL_Q2,
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            clock=_T0,
            operation=operation,
        )
        yield _Bucket(objects=objects, work_unit=work_unit)


def _calculate(bucket: _Bucket) -> CalculationRevisionId:
    return calculate_without_inputs(
        bucket_id=_BUCKET_ID, objects=bucket.objects, work_unit_id=bucket.work_unit.work_unit_id
    )


def _verify(revision_id: CalculationRevisionId, *, operation: PinnedAuthorityOperation) -> VerificationReport:
    return verify_modelo_revision_with_preconditions(
        revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        operator_scope_ports=build_operator_scope_ports(),
        actor="test",
        workflow_profile=ready_workflow_profile(),
        verification_repositories=build_test_verification_repository_bundle(),
        operation=operation,
    ).report


def _stored_revision(bucket: _Bucket, revision_id: CalculationRevisionId) -> CalculationRevision:
    revision = (
        CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load().get(revision_id)
    )
    assert revision is not None
    return revision


def _stored_reports(bucket: _Bucket) -> dict[str, VerificationReport]:
    return dict(VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load().reports)


def _capture_capital_coupon(objects: SecureObjectRepository) -> None:
    transaction = capital_payment()
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="d" * 64,
        request=capital_request(transaction),
        applicable_year=CAPITAL_YEAR,
        cadence=quarterly_filer_cadence(CAPITAL_YEAR),
    )
    assert capture.scope.modelo == "123"
    assert capture.scope.period == _ACCRUAL_Q2
    assert (
        withholding_producer(objects).capture(capture.command, cadence=quarterly_filer_cadence_for(capture.command))
        is not None
    )


def test_captured_capital_evidence_refuses_the_123_calculation_and_persists_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The count-authority refusal is typed, has no command action, and leaves no revision behind."""
    with _m123_bucket(tmp_path, operation=operation) as bucket:
        _capture_capital_coupon(bucket.objects)

        with pytest.raises(Modelo123CountAuthorityUnresolvedError) as exc_info:
            _calculate(bucket)

        revisions = CalculationRevisionCatalogueRepository(objects=bucket.objects).load().revisions
        reports = VerificationReportCatalogueRepository(objects=bucket.objects).load().reports
        work_unit = WorkUnitCatalogueRepository(objects=bucket.objects).load().get(bucket.work_unit.work_unit_id)
        evidence = RetencionObservationRepositoryAdapter(objects=bucket.objects).load_observations("123", _ACCRUAL_Q2)

    error = exc_info.value
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "modelo.work.calculate.m123_count_authority.resolved"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert error.precondition_failure is not None
    assert error.precondition_failure.scenario_id == "modelo.work.calculate.m123_count_authority.unresolved"
    (condition_evidence,) = verdict.evidence
    assert condition_evidence.values["captured_retencion_observations"] == 1
    assert condition_evidence.values["count_authority_resolved"] is False
    assert condition_evidence.values["period"] == "2T"
    assert get_registered_error_code(error).code == "REFUSED_MODELO_123_COUNT_AUTHORITY_UNRESOLVED"
    assert revisions == {}
    assert reports == {}
    assert work_unit is not None
    assert work_unit.current_calculation_revision_id is None
    assert len(evidence) == 1


def test_a_123_period_without_captured_evidence_still_calculates(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The same bucket without captured evidence reaches persistence, so the refusal is the evidence's."""
    with _m123_bucket(tmp_path, operation=operation) as bucket:
        _calculate(bucket)

        revisions = CalculationRevisionCatalogueRepository(objects=bucket.objects).load().revisions
        work_unit = WorkUnitCatalogueRepository(objects=bucket.objects).load().get(bucket.work_unit.work_unit_id)

    assert len(revisions) == 1
    assert work_unit is not None
    assert work_unit.current_calculation_revision_id in revisions


def _assert_unresolved_count_refusal(error: Modelo123CountAuthorityUnresolvedError, *, leaf: str) -> None:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == f"{leaf}.m123_count_authority.resolved"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert error.precondition_failure is not None
    assert error.precondition_failure.subject_leaf_key == leaf
    assert error.precondition_failure.scenario_id == f"{leaf}.m123_count_authority.unresolved"
    (condition_evidence,) = verdict.evidence
    assert condition_evidence.values["captured_retencion_observations"] == 1
    assert condition_evidence.values["count_authority_resolved"] is False
    assert get_registered_error_code(error).code == "REFUSED_MODELO_123_COUNT_AUTHORITY_UNRESOLVED"


def test_evidence_captured_after_calculation_refuses_verification_and_persists_no_report(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A draft calculated before capture cannot be verified once the window holds evidence."""
    with _m123_bucket(tmp_path, operation=operation) as bucket:
        revision_id = _calculate(bucket)
        _capture_capital_coupon(bucket.objects)

        with pytest.raises(Modelo123CountAuthorityUnresolvedError) as exc_info:
            _verify(revision_id, operation=operation)

        revision = _stored_revision(bucket, revision_id)
        reports = _stored_reports(bucket)

    _assert_unresolved_count_refusal(exc_info.value, leaf="modelo.work.verify")
    assert revision.state is CalculationRevisionState.BORRADOR
    assert revision.verified_at is None
    assert reports == {}


def test_evidence_captured_after_verification_refuses_filing_and_export(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A revision verified before capture is neither filed nor written out as a fichero."""
    export_path = tmp_path / f"modelo-123-{CAPITAL_YEAR}-2T.txt"
    with _m123_bucket(tmp_path, operation=operation) as bucket:
        revision_id = _calculate(bucket)
        granted = _verify(revision_id, operation=operation)
        assert granted.granted_verificado_completo is True
        _capture_capital_coupon(bucket.objects)

        with pytest.raises(Modelo123CountAuthorityUnresolvedError) as file_info:
            file_modelo_revision(
                revision_id,
                approved_verification_report_id=granted.verification_report_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                operator_scope_ports=build_operator_scope_ports(),
                ports=build_filing_action_ports(bucket_id=_BUCKET_ID, operation=operation),
                actor="test",
                workflow_profile=ready_workflow_profile(),
                operation=operation,
            )
        with pytest.raises(Modelo123CountAuthorityUnresolvedError) as export_info:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=revision_id,
                    output_path=export_path,
                    actor="test",
                ),
                workflow_profile=ready_workflow_profile(),
                export_ports=modelo_export_ports_for_test(bucket_id=_BUCKET_ID, secure_objects=bucket.objects),
                operation=operation,
            )

        revision = _stored_revision(bucket, revision_id)
        records = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load().records
        work_unit = WorkUnitCatalogueRepository(objects=bucket.objects).load().get(bucket.work_unit.work_unit_id)

    _assert_unresolved_count_refusal(file_info.value, leaf="modelo.work.file")
    _assert_unresolved_count_refusal(export_info.value, leaf="modelo.export")
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert records == {}
    assert work_unit is not None
    assert work_unit.current_filing_record_id is None
    assert work_unit.filed_calculation_revision_id is None
    assert not export_path.exists()


def test_a_123_revision_without_captured_evidence_still_reaches_verification(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The same draft without evidence gets a persisted report, so the verify refusal is the evidence's."""
    with _m123_bucket(tmp_path, operation=operation) as bucket:
        revision_id = _calculate(bucket)

        report = _verify(revision_id, operation=operation)

        revision = _stored_revision(bucket, revision_id)
        reports = _stored_reports(bucket)

    assert report.calculation_revision_id == revision_id
    assert report.granted_verificado_completo is True
    assert set(reports) == {report.verification_report_id}
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
