"""Modelo 202 missing required bindings cannot produce filing-grade artifacts.

These tests exercise the real work-unit, calculation, verification, prior-filing
observation, and profile paths. An S.L. without the prior-12-month INCN or
relation-backed M202 facts must be refused before an all-zero draft, verified
revision, local filing, or export can be produced.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ...tests import register_wizard_catalogue

__all__ = ["register_wizard_catalogue"]

from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period
from ....domain.deadlines import (
    EntityType,
    IVARegime,
    LegalEntityForm,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ExternalEvidenceKind,
    WorkUnit,
    derive_calculation_revision_id,
    upsert_calculation_revision,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.env_scope import ready_clave_settings
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from .._action_errors import (
    CalculationRevisionStateError,
    ModeloRequiredBindingsMissingError,
)
from .._calculation_actions import calculate_modelo_revision
from .._export import (
    ModeloExportCommand,
    ModeloExportUnsupportedError,
    export_modelo_revision,
)
from .._filing_actions import file_modelo_revision
from .._verification_actions import verify_modelo_revision
from .._work_lifecycle import create_work_unit
from ..external_import_actions import import_external_filing_evidence
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_CLOCK = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
_BUCKET_ID = "69ba4fa8-427a-4853-8758-9ead443fb20c"
_TAX_ID = "B12345674"
_M202_RELATION_BINDING = "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
_M202_PRIOR_PAYMENTS_BINDING = "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores"
_M202_INCN_BINDING = "modelo-202-2025-y-siguientes-incn-prior-12-months"
_M200_CUOTA_LIQUIDA = "DP200014B:00592"
_ZERO_M202_CASILLA_VALUES = {
    "01": Decimal("0"),
    "03": Decimal("0"),
    "30": Decimal("0"),
    "34": Decimal("0"),
}


def _workflow_profile(incn: Decimal | None) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        activity_start_date=date(2020, 1, 1),
        incn_prior_12_months=incn,
        new_entity_first_two_profit_periods=False,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
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
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=tuple(facts),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def _seed_prior_m200_evidence(*, bucket_id: str) -> None:
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    snapshot = bundled_authority().snapshot("200", filing_year=2024, period="0A")
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="200",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_CLOCK,
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
    snapshot = bundled_authority().snapshot("202", filing_year=2026, period="1P")
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="202",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1P"),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_CLOCK,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-test",
        casilla_inputs={},
        binding_values={
            _M202_RELATION_BINDING: Decimal("0"),
            _M202_PRIOR_PAYMENTS_BINDING: Decimal("0"),
        },
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
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


def test_m202_missing_required_bindings_refuses_before_persisting_zero_draft(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=None)
        work_repo = WorkUnitCatalogueRepository()
        calc_repo = CalculationRevisionCatalogueRepository()
        snapshot = bundled_authority().snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )

        with pytest.raises(ModeloRequiredBindingsMissingError) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator-test",
                casilla_inputs={},
                binding_values={},
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
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


def test_m202_legacy_zero_revision_cannot_verify_file_or_export(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=Decimal("500000"))
        work_repo = WorkUnitCatalogueRepository()
        calc_repo = CalculationRevisionCatalogueRepository()
        filing_repo = ModeloRecordCatalogueRepository()
        verification_repo = VerificationReportCatalogueRepository()
        snapshot = bundled_authority().snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )
        draft = _seed_legacy_zero_m202_revision(
            work_unit=work_unit,
            calculation_repository=calc_repo,
            state=CalculationRevisionState.BORRADOR,
        )
        workflow_profile = _workflow_profile(Decimal("500000"))

        with pytest.raises(ModeloRequiredBindingsMissingError) as verify_error:
            verify_modelo_revision(
                draft.calculation_revision_id,
                actor="operator-test",
                workflow_profile=workflow_profile,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
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
        with pytest.raises(ModeloRequiredBindingsMissingError) as file_error:
            file_modelo_revision(
                verified.calculation_revision_id,
                actor="operator-test",
                workflow_profile=workflow_profile,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
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
        with pytest.raises(ModeloExportUnsupportedError) as export_error:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=export_path,
                    actor="operator-test",
                ),
                workflow_profile=workflow_profile,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
            )
        export_context = export_error.value.context
        assert export_context is not None
        export_modelo = export_context["modelo"]
        assert isinstance(export_modelo, str)
        assert export_modelo == "202"
        export_reason = export_context["reason"]
        assert isinstance(export_reason, str)
        assert "no complete export_layouts definition" in export_reason
        assert export_path.exists() is False


def test_m202_wrong_state_still_refuses_file_before_required_binding_gate(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=Decimal("500000"))
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID)
        _work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo = _calculate_m202(
            bucket_id=_BUCKET_ID,
        )

        with pytest.raises(
            CalculationRevisionStateError,
            match="error_modelo_calculation_revision_state",
        ) as state_error:
            file_modelo_revision(
                revision.calculation_revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(Decimal("500000")),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
            )
        state_context = state_error.value.context
        assert state_context is not None
        state = state_context["state"]
        assert isinstance(state, str)
        assert state == CalculationRevisionState.BORRADOR.value


def test_m202_missing_incn_with_explicit_relation_values_refuses_calculate(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=None)
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID)
        work_repo = WorkUnitCatalogueRepository()
        calc_repo = CalculationRevisionCatalogueRepository()
        snapshot = bundled_authority().snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )

        with pytest.raises(ModeloRequiredBindingsMissingError) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator-test",
                casilla_inputs={},
                binding_values={
                    _M202_RELATION_BINDING: Decimal("0"),
                    _M202_PRIOR_PAYMENTS_BINDING: Decimal("0"),
                },
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                clock=_CLOCK,
            )

        context2 = exc_info.value.context
        assert context2 is not None
        missing_bindings = context2["missing_bindings"]
        assert isinstance(missing_bindings, tuple)
        assert missing_bindings == (_M202_INCN_BINDING,)


@pytest.mark.parametrize("incn", (Decimal("500000"), Decimal("7000000")))
def test_m202_declared_incn_below_or_above_threshold_can_verify(tmp_path: Path, incn: Decimal) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=incn)
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID)
        _work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo = _calculate_m202(
            bucket_id=_BUCKET_ID,
        )

        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-test",
            workflow_profile=_workflow_profile(incn),
            settings=ready_clave_settings("12345678Z"),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            verification_repository=verification_repo,
            clock=_CLOCK,
        )

        assert report.granted_verificado_completo is True
        stored = calc_repo.load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored.state is CalculationRevisionState.VERIFICADO_COMPLETO
