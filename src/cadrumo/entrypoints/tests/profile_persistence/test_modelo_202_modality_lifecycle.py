"""Modelo 202 missing required bindings cannot produce filing-grade artifacts.

These tests exercise the real work-unit, calculation, verification, prior-filing
observation, and profile paths. An S.L. without the prior-12-month INCN or
relation-backed M202 facts must be refused before an all-zero draft, verified
revision, local filing, or export can be produced.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from ....application.tests.wizard_catalogue_fixtures import register_wizard_catalogue
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ...adapter_composition import (
    build_calculation_action_ports,
    build_filing_action_ports,
    build_verification_repository_bundle,
)
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)

__all__ = ["register_wizard_catalogue"]

from ....application.modelo.action_errors import CalculationRevisionStateError, ModeloRequiredBindingsMissingError
from ....application.modelo.calculation_actions import calculate_modelo_revision
from ....application.modelo.export import ModeloExportCommand, export_modelo_revision
from ....application.modelo.external_import_actions import import_external_filing_evidence
from ....application.modelo.filing_action_ports import FilingActionPorts
from ....application.modelo.filing_actions import file_modelo_revision
from ....application.modelo.verification_actions import verify_modelo_revision
from ....application.modelo.verification_repository_ports import VerificationRepositoryBundle
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.contribuyente.entity_type import EntityType, LegalEntityForm
from ....domain.deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.env_scope import ready_clave_settings
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from ....adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_CLOCK = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
_BUCKET_ID = "69ba4fa8-427a-4853-8758-9ead443fb20c"
_TAX_ID = "B12345674"
_M202_RELATION_BINDING = "modelo-202-cuota-base-ejercicio-anterior"
_M202_PRIOR_PAYMENTS_BINDING = "modelo-202-pagos-fraccionados-anteriores"
_M202_INCN_BINDING = "modelo-202-incn-prior-12-months"
_M200_CUOTA_LIQUIDA = "DP200014B:00592"
_ZERO_M202_CASILLA_VALUES = {
    "01": Decimal("0"),
    "03": Decimal("0"),
    "30": Decimal("0"),
    "34": Decimal("0"),
}


def _work_ports(work_repo: WorkUnitCatalogueRepository) -> WorkLifecyclePorts:
    """Compose the lifecycle ports over the isolated work-unit repository."""
    return WorkLifecyclePorts(
        work_unit_repository=work_repo,
        bucket_event_repository=BucketEventHistoryRepository(),
    )


def _verification_ports(
    *,
    work_repo: WorkUnitCatalogueRepository,
    calc_repo: CalculationRevisionCatalogueRepository,
    filing_repo: ModeloRecordCatalogueRepository,
    verification_repo: VerificationReportCatalogueRepository,
) -> VerificationRepositoryBundle:
    """Compose the complete verification bundle over the isolated repositories."""
    return replace(
        build_verification_repository_bundle(_BUCKET_ID),
        work_unit=work_repo,
        calculation=calc_repo,
        filing=filing_repo,
        verification=verification_repo,
    )


def _filing_ports(
    *,
    work_repo: WorkUnitCatalogueRepository,
    calc_repo: CalculationRevisionCatalogueRepository,
    filing_repo: ModeloRecordCatalogueRepository,
    verification_repo: VerificationReportCatalogueRepository,
) -> FilingActionPorts:
    """Compose the complete filing bundle over the isolated repositories."""
    return replace(
        build_filing_action_ports(bucket_id=_BUCKET_ID),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        verification_repository=verification_repo,
    )


def workflow_profile(incn: Decimal | None) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        entity_type=EntityType.from_registry("legal_entity"),
        legal_entity_form=LegalEntityForm.from_registry("sl"),
        iva_regime=IVARegime("GENERAL"),
        activity_start_date=date(2020, 1, 1),
        incn_prior_12_months=incn,
        new_entity_first_two_profit_periods=False,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.from_registry("common_regime"),
            regime_composition=M303RegimeComposition.from_registry("general"),
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
    )


def _seed_profile(*, bucket_id: str, incn: Decimal | None) -> None:
    facts = [
        UserProfileFact(path="identity.tax_id", value=_TAX_ID),
        UserProfileFact(path="identity.name", value="Ana"),
        UserProfileFact(path="identity.surnames", value="Sociedad Limitada"),
        UserProfileFact(path="identity.legal_name", value="Taller Sol Sociedad Limitada"),
        UserProfileFact(path="activities.description", value="taller mecanico"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.oss_enrolled", value=False),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
        UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
        UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
        UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="renta_filing.declaration_type", value="1"),
    ]
    if incn is not None:
        facts.append(UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=incn))
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=tuple(facts),
            created_at=_CLOCK,
            updated_at=_CLOCK,
            context=_profile_creation_context_for_test(),
        ),
    )


def _seed_prior_m200_evidence(*, bucket_id: str, operation: PinnedAuthorityOperation) -> None:
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    snapshot = published_authority_operation().snapshot(
        "200", filing_year=2024, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="200",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        revision_id=snapshot.revision.id,
        ports=_work_ports(work_repo),
        clock=_CLOCK,
        operation=operation,
    )
    evidence_reference_id = "JUSTM20020240A"
    casilla_values = {_M200_CUOTA_LIQUIDA: Decimal("0")}
    persist_justificante_metadata(
        evidence_reference_id,
        modelo="200",
        filing_year=2024,
        period="0A",
        captured_at=_CLOCK,
        tax_id=_TAX_ID,
    )
    import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor="aeat-import-test",
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        observation_repository=CalculationObservationRepository(),
        expected_tax_id=_TAX_ID,
        clock=_CLOCK,
    )
    CalculationObservationRepository().save(
        CalculationObservationRepository().prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="200",
                filing_year=2024,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="200",
                    filing_year=2024,
                    period="0A",
                    casilla_values=casilla_values,
                    grade=RegistryAuthorityGrade.CALCULATION,
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_CLOCK,
            stamped_revision_id=snapshot.revision.id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": "EXP-M200-2024-0A",
                "aeat_justificante_csv": evidence_reference_id,
                "authenticated_identity": _TAX_ID,
            },
        )
    )


def _calculate_m202(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> tuple[
    WorkUnit,
    CalculationRevision,
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
]:
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    verification_repo = VerificationReportCatalogueRepository()
    snapshot = published_authority_operation().snapshot("202", filing_year=2026, period="1P")
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="202",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1P"),
        revision_id=snapshot.revision.id,
        ports=_work_ports(work_repo),
        clock=_CLOCK,
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            actor="operator-test",
            casilla_inputs={},
            binding_values={
                _M202_RELATION_BINDING: Decimal("0"),
                _M202_PRIOR_PAYMENTS_BINDING: Decimal("0"),
            },
            clock=_CLOCK,
        )
    refreshed_work_unit = work_repo.load().get(work_unit.work_unit_id)
    assert refreshed_work_unit is not None
    return refreshed_work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo


def _seed_legacy_zero_m202_revision(
    *,
    work_unit: WorkUnit,
    calculation_repository: CalculationRevisionCatalogueRepository,
    state: CalculationRevisionState,
) -> CalculationRevision:
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=_ZERO_M202_CASILLA_VALUES,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=state,
        casilla_values=_ZERO_M202_CASILLA_VALUES,
        observations=registry_grounded_observations(
            modelo="202",
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=_ZERO_M202_CASILLA_VALUES,
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator-test" if state is not CalculationRevisionState.BORRADOR else None,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), revision))
    return revision


def test_m202_missing_required_bindings_refuses_before_persisting_zero_draft(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=None)
        work_repo = WorkUnitCatalogueRepository()
        calc_repo = CalculationRevisionCatalogueRepository()
        snapshot = published_authority_operation().snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            ports=_work_ports(work_repo),
            clock=_CLOCK,
            operation=operation,
        )

        with (
            pytest.raises(ModeloRequiredBindingsMissingError) as exc_info,
            bundled_indexed_authority().operation() as operation,
        ):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
                actor="operator-test",
                casilla_inputs={},
                binding_values={},
                clock=_CLOCK,
            )

        context = exc_info.value.context
        assert context is not None
        missing_bindings = context["missing_bindings"]
        assert isinstance(missing_bindings, tuple)
        assert set(missing_bindings) == {
            _M202_INCN_BINDING,
            _M202_RELATION_BINDING,
            _M202_PRIOR_PAYMENTS_BINDING,
        }
        assert calc_repo.load().revisions == {}
        stored_work_unit = work_repo.load().get(work_unit.work_unit_id)
        assert stored_work_unit is not None
        assert stored_work_unit.current_calculation_revision_id is None


def test_m202_legacy_zero_revision_cannot_verify_file_or_export(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=Decimal("500000"))
        work_repo = WorkUnitCatalogueRepository()
        calc_repo = CalculationRevisionCatalogueRepository()
        filing_repo = ModeloRecordCatalogueRepository()
        verification_repo = VerificationReportCatalogueRepository()
        snapshot = published_authority_operation().snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            ports=_work_ports(work_repo),
            clock=_CLOCK,
            operation=operation,
        )
        draft = _seed_legacy_zero_m202_revision(
            work_unit=work_unit,
            calculation_repository=calc_repo,
            state=CalculationRevisionState.BORRADOR,
        )
        profile = workflow_profile(Decimal("500000"))

        with (
            pytest.raises(ModeloRequiredBindingsMissingError) as verify_error,
            bundled_indexed_authority().operation() as operation,
        ):
            verify_modelo_revision(
                draft.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=_verification_ports(
                    work_repo=work_repo,
                    calc_repo=calc_repo,
                    filing_repo=filing_repo,
                    verification_repo=verification_repo,
                ),
                actor="operator-test",
                workflow_profile=profile,
                clock=_CLOCK,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )
        verify_failure = verify_error.value.precondition_failure
        assert verify_failure is not None
        assert verify_failure.scenario_id == "modelo.work.verify.required_bindings_missing"
        verify_context = verify_error.value.context
        assert verify_context is not None
        verify_missing_bindings = verify_context["missing_bindings"]
        assert isinstance(verify_missing_bindings, tuple)
        assert _M202_INCN_BINDING in verify_missing_bindings
        stored = calc_repo.load().get(draft.calculation_revision_id)
        assert stored is not None
        assert stored.state is CalculationRevisionState.BORRADOR

        verified = _seed_legacy_zero_m202_revision(
            work_unit=work_unit,
            calculation_repository=calc_repo,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
        )
        with (
            pytest.raises(ModeloRequiredBindingsMissingError) as file_error,
            bundled_indexed_authority().operation() as operation,
        ):
            file_modelo_revision(
                verified.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                actor="operator-test",
                workflow_profile=profile,
                ports=_filing_ports(
                    work_repo=work_repo,
                    calc_repo=calc_repo,
                    filing_repo=filing_repo,
                    verification_repo=verification_repo,
                ),
                clock=_CLOCK,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )
        file_failure = file_error.value.precondition_failure
        assert file_failure is not None
        assert file_failure.scenario_id == "modelo.work.file.required_bindings_missing"
        file_context = file_error.value.context
        assert file_context is not None
        file_missing_bindings = file_context["missing_bindings"]
        assert isinstance(file_missing_bindings, tuple)
        assert _M202_PRIOR_PAYMENTS_BINDING in file_missing_bindings
        export_path = tmp_path / "modelo-202-2026-1P.txt"
        with (
            pytest.raises(ModeloRequiredBindingsMissingError) as export_error,
            bundled_indexed_authority().operation() as operation,
        ):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=export_path,
                    actor="operator-test",
                ),
                workflow_profile=profile,
                export_ports=modelo_export_ports_for_test(
                    bucket_id=_BUCKET_ID,
                    taxpayer_tax_id=profile.tax_id,
                    work_unit=work_repo,
                    calculation=calc_repo,
                    filing=filing_repo,
                    verification=verification_repo,
                ),
                operation=operation,
                clock=_CLOCK,
            )
        export_context = export_error.value.context
        assert export_context is not None
        export_missing_bindings = export_context["missing_bindings"]
        assert isinstance(export_missing_bindings, tuple)
        assert _M202_PRIOR_PAYMENTS_BINDING in export_missing_bindings
        assert export_path.exists() is False


def test_m202_wrong_state_still_refuses_file_before_required_binding_gate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=Decimal("500000"))
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID, operation=operation)
        _work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo = _calculate_m202(
            bucket_id=_BUCKET_ID,
            operation=operation,
        )

        with (
            pytest.raises(
                CalculationRevisionStateError,
                match="error_modelo_calculation_revision_state",
            ) as state_error,
            bundled_indexed_authority().operation() as operation,
        ):
            file_modelo_revision(
                revision.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                actor="operator-test",
                workflow_profile=workflow_profile(Decimal("500000")),
                ports=_filing_ports(
                    work_repo=work_repo,
                    calc_repo=calc_repo,
                    filing_repo=filing_repo,
                    verification_repo=verification_repo,
                ),
                clock=_CLOCK,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )
        state_context = state_error.value.context
        assert state_context is not None
        state = state_context["state"]
        assert isinstance(state, str)
        assert state == CalculationRevisionState.BORRADOR.value


def test_m202_missing_incn_with_explicit_relation_values_refuses_calculate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=None)
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID, operation=operation)
        work_repo = WorkUnitCatalogueRepository()
        CalculationRevisionCatalogueRepository()
        snapshot = published_authority_operation().snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            ports=_work_ports(work_repo),
            clock=_CLOCK,
            operation=operation,
        )

        with (
            pytest.raises(ModeloRequiredBindingsMissingError) as exc_info,
            bundled_indexed_authority().operation() as operation,
        ):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
                actor="operator-test",
                casilla_inputs={},
                binding_values={
                    _M202_RELATION_BINDING: Decimal("0"),
                    _M202_PRIOR_PAYMENTS_BINDING: Decimal("0"),
                },
                clock=_CLOCK,
            )

        context2 = exc_info.value.context
        assert context2 is not None
        missing_bindings = context2["missing_bindings"]
        assert isinstance(missing_bindings, tuple)
        assert missing_bindings == (_M202_INCN_BINDING,)


@pytest.mark.parametrize("incn", (Decimal("500000"), Decimal("7000000")))
def test_m202_declared_incn_below_or_above_threshold_can_verify(
    tmp_path: Path, incn: Decimal, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=incn)
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID, operation=operation)
        _work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo = _calculate_m202(
            bucket_id=_BUCKET_ID,
            operation=operation,
        )

        with bundled_indexed_authority().operation() as operation:
            report = verify_modelo_revision(
                revision.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=_verification_ports(
                    work_repo=work_repo,
                    calc_repo=calc_repo,
                    filing_repo=filing_repo,
                    verification_repo=verification_repo,
                ),
                actor="operator-test",
                workflow_profile=workflow_profile(incn),
                settings=ready_clave_settings("12345678Z"),
                clock=_CLOCK,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )

        assert report.granted_verificado_completo is True
        stored = calc_repo.load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored.state is CalculationRevisionState.VERIFICADO_COMPLETO
