"""Cross-period clean-state external evidence provenance coverage."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    BUCKET_ID as _BUCKET_ID,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    CLOCK as _CLOCK,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    GROUP_MEMBER_A as _GROUP_MEMBER_A,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    GROUP_MEMBER_B as _GROUP_MEMBER_B,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    M353_PERIOD as _M353_PERIOD,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    M353_YEAR as _M353_YEAR,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    M390_PERIOD as _M390_PERIOD,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    M390_REVISION as _M390_REVISION,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    M390_YEAR as _M390_YEAR,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    m390_first_quarter_evidence as _m390_first_quarter_evidence,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    member_fan_in_requirement as _member_fan_in_requirement,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    persist_justificante_metadata as _persist_justificante_metadata,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    seed_member_322_filing as _seed_member_322_filing,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    seed_official_303_source_filings as _seed_official_303_source_filings,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    snapshot_353 as _snapshot_353,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    snapshot_390 as _snapshot_390,
)
from cadrumo.adapters.persistence.profile.tests._cross_period_clean_state_support import (
    store_ready_profile as _store_ready_profile,
)
from cadrumo.adapters.persistence.profile.tests._file_flow_support import calculation_ports_for_test
from cadrumo.adapters.persistence.profile.tests.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.cross_period_clean_state import evaluate_cross_period_clean_state
from cadrumo.application.calculations.cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodExpectedMemberSet,
)
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.verification_actions import verify_modelo_revision
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
)
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority as _indexed_authority_for_test,
)
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind
from cadrumo.domain.modelos.verification_report import ModeloVerificationFindingKind, VerificationCompletenessStatus

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_cross_period_clean_state_blocks_missing_aeat_register_observation_provenance(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                source_metadata_by_period={"1T": None},
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                taxpayer_tax_id="X1234567L",
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.clean is False
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_live_capture_observation_without_register_provenance(
    tmp_path: Path,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                evidence_kind_by_period={"1T": ExternalEvidenceKind.AEAT_LIVE_CAPTURE},
                source_kind_by_period={"1T": "aeat_sede_live_capture"},
                source_metadata_by_period={"1T": {}},
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                taxpayer_tax_id="X1234567L",
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.clean is False
        assert first_quarter.observation_source_kind == "aeat_sede_live_capture"
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_non_alta_aeat_register_observation_provenance(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                source_metadata_by_period={
                    "1T": {
                        "aeat_register_status": "BAJA",
                        "aeat_expediente_id": "EXP-303-REFERENCE-ONE",
                        "authenticated_identity": "X1234567L",
                    },
                },
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                taxpayer_tax_id="X1234567L",
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.clean is False
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_missing_aeat_register_reference(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                source_metadata_by_period={
                    "1T": {
                        "aeat_register_status": "ALTA",
                        "authenticated_identity": "X1234567L",
                        "aeat_justificante_csv": "JUST00001T",
                    },
                },
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                taxpayer_tax_id="X1234567L",
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.clean is False
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_wrong_authenticated_identity_observation_provenance(
    tmp_path: Path,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                source_metadata_by_period={
                    "1T": {
                        "aeat_register_status": "ALTA",
                        "aeat_expediente_id": "EXP-303-REFERENCE-ONE",
                        "authenticated_identity": "B12345678",
                    },
                },
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                taxpayer_tax_id="X1234567L",
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.clean is False
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_member_observation_authenticated_identity_mismatch(
    tmp_path: Path,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            requirement = _member_fan_in_requirement()
            _seed_member_322_filing(
                observation_repository,
                member_nif=_GROUP_MEMBER_A,
                source_casilla_ids=requirement.source_casilla_ids,
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "EXP-322-2026-12-A",
                    "authenticated_identity": _GROUP_MEMBER_B,
                },
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_353(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                expected_member_sets=(
                    CrossPeriodExpectedMemberSet(
                        source_modelo="322",
                        filing_year=_M353_YEAR,
                        period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                        member_nifs=(_GROUP_MEMBER_A,),
                    ),
                ),
                operation=_authority_operation_for_test,
            )

        member_evidence = next(
            evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in
        )
        assert verdict.clean is False
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in member_evidence.blockers


def test_cross_period_clean_state_blocks_dangling_justificante_evidence_reference(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                omit_justificante_metadata_periods={"1T"},
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                taxpayer_tax_id="X1234567L",
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.requires_clean_state is True
        assert verdict.clean is False
        assert first_quarter.external_evidence_kind == "aeat_justificante_pdf"
        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_csv_register_without_justificante_verification(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                evidence_kind_by_period={"1T": ExternalEvidenceKind.AEAT_CSV_REGISTER},
                omit_justificante_metadata_periods={"1T"},
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                taxpayer_tax_id="X1234567L",
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.requires_clean_state is True
        assert verdict.clean is False
        assert first_quarter.external_evidence_kind == "aeat_csv_register"
        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_accepts_csv_register_with_matching_justificante_metadata(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                evidence_kind_by_period={"1T": ExternalEvidenceKind.AEAT_CSV_REGISTER},
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                taxpayer_tax_id="X1234567L",
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert first_quarter.external_evidence_kind == "aeat_csv_register"
        assert first_quarter.blockers == ()


def test_cross_period_clean_state_accepts_live_capture_with_matching_justificante_metadata(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                evidence_kind_by_period={"1T": ExternalEvidenceKind.AEAT_LIVE_CAPTURE},
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                taxpayer_tax_id="X1234567L",
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert first_quarter.external_evidence_kind == "aeat_live_capture"
        assert first_quarter.blockers == ()
        assert verdict.clean is True


def test_cross_period_clean_state_blocks_live_capture_without_justificante_verification(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                evidence_kind_by_period={"1T": ExternalEvidenceKind.AEAT_LIVE_CAPTURE},
                omit_justificante_metadata_periods={"1T"},
            )

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.requires_clean_state is True
        assert verdict.clean is False
        assert first_quarter.external_evidence_kind == "aeat_live_capture"
        # AEAT_LIVE_CAPTURE is now a justificante-verified evidence kind (the captured
        # receipt is official filing evidence), so a live capture lacking the persisted
        # justificante record is blocked on the missing record rather than on the kind.
        # The safety intent — a live capture without justificante backing cannot clear a
        # dependent period — is preserved; only the blocker classification changed.
        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_mismatched_justificante_metadata(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            observation_repository = CalculationObservationRepository()
            _seed_official_303_source_filings(
                observation_repository=observation_repository,
                omit_justificante_metadata_periods={"1T"},
            )
            _persist_justificante_metadata("JUST00001T", modelo="303", period="2T", filing_year=_M390_YEAR)

            verdict = evaluate_cross_period_clean_state(
                _snapshot_390(),
                bucket_id=_BUCKET_ID,
                observation_repository=observation_repository,
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                justificante_repository=JustificanteRepository(),
                operation=_authority_operation_for_test,
            )

        first_quarter = _m390_first_quarter_evidence(verdict)
        assert verdict.clean is False
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_verify_modelo_revision_refuses_m390_when_prior_filings_are_not_clean(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            _store_ready_profile()
            work_unit_repository = WorkUnitCatalogueRepository()
            calculation_repository = CalculationRevisionCatalogueRepository()
            bucket_event_repository = BucketEventHistoryRepository()
            work_unit = create_work_unit(
                bucket_id=_BUCKET_ID,
                modelo="390",
                filing_year=_M390_YEAR,
                period=Period.from_year_and_code(_M390_YEAR, _M390_PERIOD),
                revision_id=_M390_REVISION,
                ports=WorkLifecyclePorts(
                    work_unit_repository=work_unit_repository,
                    bucket_event_repository=bucket_event_repository,
                ),
                clock=_CLOCK,
                operation=operation,
            )
            snapshot = _snapshot_390()
            binding_values = {binding.id: Decimal("0") for binding in snapshot.revision.bindings}
            with calculation_ports_for_test(
                bucket_id=_BUCKET_ID,
                work_unit_repository=work_unit_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=bucket_event_repository,
            ) as _calculation_ports_489:
                revision = calculate_modelo_revision(
                    work_unit.work_unit_id,
                    casilla_inputs={},
                    binding_values=binding_values,
                    ports=_calculation_ports_489,
                    clock=_CLOCK,
                )

            report = verify_modelo_revision(
                revision.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=build_test_verification_repository_bundle(),
                actor="operator-test",
                workflow_profile=TaxpayerProfile(
                    tax_id="X1234567L",
                    iva_regime=IVARegime("general"),
                    has_employees=False,
                    pays_rent_with_retencion=False,
                    does_intracomunitario=False,
                    bienes_extranjero_above_threshold=False,
                ),
                clock=_CLOCK,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=_authority_operation_for_test,
            )
            reloaded = calculation_repository.load().get(revision.calculation_revision_id)

        assert report.granted_verificado_completo is False
        assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
        assert reloaded is not None
        assert reloaded.state is CalculationRevisionState.BORRADOR
        assert any(
            finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN for finding in report.findings
        )
