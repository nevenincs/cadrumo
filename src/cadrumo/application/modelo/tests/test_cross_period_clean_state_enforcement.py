"""Filing-grade Modelo gates for cross-period clean-state proof."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ...tests.wizard_catalogue_fixtures import register_wizard_catalogue

__all__ = ["register_wizard_catalogue"]

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.deadlines.models import (
    CrossPeriodGroupMemberRoster,
    IrpfIncomeCategory,
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ....domain.contribuyente.entity_type import EntityType
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.filing_repository import upsert_filing_record
from ....domain.modelos.verification_report import ModeloVerificationFindingKind
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.env_scope import ready_clave_settings
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations.cross_period_clean_state import (
    CrossPeriodExpectedMemberSet,
    NoPriorObligationProvenanceKind,
    cross_period_dependency_requirements,
)
from ...calculations.observations_repository import (
    CalculationObservationRepository,
    ObservationSourceKind,
    is_official_aeat_observation_source,
)
from ..action_errors import ModeloCrossPeriodCleanStateError
from ..calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    mark_revision_verificado_completo,
)
from ..export import ModeloExportCommand, export_modelo_revision
from ..external_import_actions import import_external_filing_evidence
from ..filed_revision_observation import APP_FILING_SOURCE_KIND
from ..filing_actions import file_modelo_revision
from ..verification_actions import verify_modelo_revision
from ..work_lifecycle import create_work_unit
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository

_CLOCK = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
_M390_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio",
    surface="_M390_EJERCICIO_CASILLA",
)
_M390_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id(
    "decl.tipo-declaracion",
    surface="_M390_TIPO_DECLARACION_CASILLA",
)
_M202_2026_2P_REQUIRED_BINDING_OVERRIDES = {
    "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior": "0",
    "modelo-202-2025-y-siguientes-incn-prior-12-months": "7000000",
    "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores": "0",
}
_CROSS_PERIOD_EXPORT_PROFILE_ID = "39000000-0000-4000-8000-000000000001"
_CROSS_PERIOD_FILE_PROFILE_ID = "39000000-0000-4000-8000-000000000002"
_CROSS_PERIOD_MARK_PROFILE_ID = "39000000-0000-4000-8000-000000000003"
_CROSS_PERIOD_303_PROFILE_ID = "30300000-0000-4000-8000-000000000303"
_SALARIED_M100_PROFILE_ID = "10000000-0000-4000-8000-000000000100"
_SALARIED_M100_ZERO_BIN_PROFILE_ID = "10000000-0000-4000-8000-000000000101"
_CROSS_PERIOD_390_IMPORTED_PROFILE_ID = "39000000-0000-4000-8000-000000000390"
_CROSS_PERIOD_353_PROFILE_ID = "35300000-0000-4000-8000-000000000353"
_CROSS_PERIOD_353_ROSTER_PROFILE_ID = "35300000-0000-4000-8000-000000000354"
_DECLARED_CROSS_PERIOD_PROFILE_IDS = {
    ("390", "0A"): "39000000-0000-4000-8000-000000000004",
    ("180", "0A"): "18000000-0000-4000-8000-000000000180",
    ("190", "0A"): "19000000-0000-4000-8000-000000000190",
    ("193", "0A"): "19300000-0000-4000-8000-000000000193",
    ("100", "0A"): "10000000-0000-4000-8000-000000000102",
    ("202", "2P"): "20200000-0000-4000-8000-000000000202",
    ("200", "0A"): "20000000-0000-4000-8000-000000000200",
}


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
    )


def _seed_ready_profile(bucket_id: str, objects: SecureObjectRepository | None = None, *, modelo: str = "390") -> None:
    is_legal_entity = modelo in {"200", "202", "353"}
    facts = [
        UserProfileFact(path="identity.tax_id", value="B12345674" if is_legal_entity else "X1234567L"),
        UserProfileFact(path="identity.name", value="Test"),
        UserProfileFact(path="identity.surnames", value="Operator"),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="activities.description", value="economic activity"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.oss_enrolled", value=False),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(path="provenance.source", value="manual_cli"),
        UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
    ]
    if is_legal_entity:
        facts.extend(
            (
                UserProfileFact(path="identity.legal_name", value="Test Company SL"),
                UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
                UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
                UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="7000000"),
            ),
        )
    else:
        facts.extend(
            (
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            ),
        )
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=bucket_id,
        facts=tuple(facts),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    seed_test_profile_record(record)


def _seed_m100_profile_facts(bucket_id: str, objects: SecureObjectRepository | None) -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=bucket_id,
        facts=(
            UserProfileFact(path="identity.tax_id", value="X1234567L"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Salaried"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="activities.description", value="salaried income"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="provenance.source", value="manual_cli"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.sex", value="M"),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    seed_test_profile_record(record)


def _seed_verified_revision(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
) -> str:
    _seed_ready_profile(bucket_id, modelo=modelo)
    snapshot = bundled_authority().snapshot(modelo, filing_year=filing_year, period=period)
    binding_overrides = _verified_revision_binding_overrides(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )
    casilla_values = _verified_revision_casilla_values(
        modelo=modelo,
        filing_year=filing_year,
    )
    work_period = Period.from_year_and_code(filing_year, period)
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=work_period,
        revision_id=snapshot.revision.id,
        clock=_CLOCK,
    )
    filing_instance_evidence = (
        general_m303_filing_evidence(work_period, reference="test:cross-period-clean-state:m303")
        if modelo == "303"
        else None
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="operator-test",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(upsert_calculation_revision(repo.load(), revision))
    return revision_id


def _verified_revision_binding_overrides(
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> dict[str, str]:
    if modelo == "202" and filing_year == 2026 and period == "2P":
        return dict(_M202_2026_2P_REQUIRED_BINDING_OVERRIDES)
    return {}


def _verified_revision_casilla_values(*, modelo: str, filing_year: int) -> dict[CasillaId, Decimal]:
    if modelo == "390":
        return {
            _M390_EJERCICIO_CASILLA: Decimal(filing_year),
            _M390_TIPO_DECLARACION_CASILLA: Decimal("0"),
        }
    return {}


def _seed_draft_revision(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    binding_overrides: dict[str, str] | None = None,
    relation_overrides: dict[str, str] | None = None,
    casilla_values: dict[CasillaId, Decimal] | None = None,
) -> str:
    _seed_ready_profile(bucket_id, modelo=modelo)
    snapshot = bundled_authority().snapshot(modelo, filing_year=filing_year, period=period)
    work_period = Period.from_year_and_code(filing_year, period)
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=work_period,
        revision_id=snapshot.revision.id,
        clock=_CLOCK,
    )
    filing_instance_evidence = (
        general_m303_filing_evidence(work_period, reference="test:cross-period-clean-state:m303")
        if modelo == "303"
        else None
    )
    resolved_binding_overrides = binding_overrides or {}
    resolved_relation_overrides = relation_overrides or {}
    resolved_casilla_values = casilla_values or {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides=resolved_binding_overrides,
        relation_overrides=resolved_relation_overrides,
        casilla_values=resolved_casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        binding_overrides=resolved_binding_overrides,
        relation_overrides=resolved_relation_overrides,
        casilla_values=resolved_casilla_values,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(upsert_calculation_revision(repo.load(), revision))
    return revision_id


def test_export_refuses_verified_cross_period_revision_without_clean_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CROSS_PERIOD_EXPORT_PROFILE_ID) as profile:
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="180",
            filing_year=2026,
            period="0A",
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=revision_id,
                    output_path=tmp_path / "modelo-180.txt",
                    actor="operator-test",
                ),
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"


def test_file_refuses_verified_cross_period_revision_without_clean_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CROSS_PERIOD_FILE_PROFILE_ID) as profile:
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="390",
            filing_year=2025,
            period="0A",
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"


def test_direct_mark_verified_refuses_cross_period_revision_without_clean_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CROSS_PERIOD_MARK_PROFILE_ID) as profile:
        revision_id = _seed_draft_revision(
            bucket_id=profile.bucket_id,
            modelo="390",
            filing_year=2025,
            period="0A",
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            mark_revision_verificado_completo(
                revision_id,
                actor="operator-test",
                clock=_CLOCK,
            )

        stored = CalculationRevisionCatalogueRepository().load().revisions[revision_id]

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"
    assert stored.state is CalculationRevisionState.BORRADOR
    assert stored.verified_at is None
    assert stored.verified_by is None


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period"),
    (
        ("390", 2025, "0A"),
        ("180", 2026, "0A"),
        ("190", 2026, "0A"),
        ("193", 2026, "0A"),
        ("100", 2025, "0A"),
        ("202", 2026, "2P"),
        ("200", 2026, "0A"),
    ),
)
def test_file_refuses_declared_cross_period_modelos_without_clean_sources(
    tmp_path: Path,
    modelo: str,
    filing_year: int,
    period: str,
) -> None:
    bucket_id = _DECLARED_CROSS_PERIOD_PROFILE_IDS[(modelo, period)]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"


def test_verify_modelo_303_reports_clean_state_blocker_for_carry_forward_dependency(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CROSS_PERIOD_303_PROFILE_ID) as profile:
        revision_id = _seed_draft_revision(
            bucket_id=profile.bucket_id,
            modelo="303",
            filing_year=2026,
            period="2T",
        )

        report = verify_modelo_revision(
            revision_id,
            actor="operator-test",
            workflow_profile=_workflow_profile(),
            settings=ready_clave_settings("X1234567L"),
            clock=_CLOCK,
        )

    assert any(
        finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        and finding.message_facts.get("source_modelo") == "303"
        for finding in report.findings
    )


def test_verify_salaried_taxpayer_m100_has_no_cross_period_withholding_block(tmp_path: Path) -> None:
    """C3 end-to-end: a declared employee's Modelo 100 verify reports NO cross-period dependency block.

    The empty-profile [100, 2025, 0A] file case above raises ModeloCrossPeriodCleanStateError
    (130/131 fail-closed enforced). A profile declaring TRABAJO income (no actividad económica)
    scopes every withholding/pagos dependency (111/115/123/130/131/180/184/190/193) out as
    not-applicable, so the salaried filer's M100 carries no CROSS_PERIOD_DEPENDENCY_UNCLEAN finding.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SALARIED_M100_PROFILE_ID) as profile:
        revision_id = _seed_draft_revision(
            bucket_id=profile.bucket_id,
            modelo="100",
            filing_year=2025,
            period="0A",
        )
        salaried = _workflow_profile().model_copy(
            update={
                "entity_type": EntityType.NATURAL_PERSON,
                "irpf_income_categories": frozenset({IrpfIncomeCategory.TRABAJO}),
            },
        )
        report = verify_modelo_revision(
            revision_id,
            actor="operator-test",
            workflow_profile=salaried,
            settings=ready_clave_settings("X1234567L"),
            clock=_CLOCK,
        )

    withholding_pagos = {"111", "115", "123", "130", "131", "180", "184", "190", "193"}
    blocked = {
        modelo
        for finding in report.findings
        if finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        for modelo in withholding_pagos
        if finding.message_facts.get("source_modelo") == modelo
    }
    # The M100->M100 prior-year self-carry is a separate first-filer concern, not a withholding dep.
    assert not blocked, f"salaried M100 must not be cross-period-blocked on withholding/pagos deps, got {blocked}"


def test_verify_salaried_taxpayer_m100_with_zero_prior_bin_is_complete(tmp_path: Path) -> None:
    """A salaried M100 with explicit zero prior BIN is filable without prior M100 evidence."""
    zero_binding = "renta-2025-base-liquidable-negativa-general-anterior"
    retenciones_trabajo_binding = "renta-2025-modelo-111-retenciones-periodicas"
    retenciones_trabajo_casilla = "0596"
    retenciones_trabajo_amount = Decimal("4200.00")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SALARIED_M100_ZERO_BIN_PROFILE_ID) as profile:
        _seed_m100_profile_facts(profile.bucket_id, profile.repository)
        snapshot = bundled_authority().snapshot("100", filing_year=2025, period="0A")
        work_unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision_id=snapshot.revision.id,
            clock=_CLOCK,
        )
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator-test",
            casilla_inputs={
                "0003": Decimal("32000.00"),
                "0013": Decimal("2100.00"),
                "0014": Decimal("0"),
                "0015": Decimal("0"),
                "0016": Decimal("0"),
            },
            binding_values={
                "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0"),
                retenciones_trabajo_binding: retenciones_trabajo_amount,
                "renta-2025-modelo-123-retenciones-periodicas": Decimal("0"),
                zero_binding: Decimal("0"),
            },
            clock=_CLOCK,
        ).revision
        assert Decimal(revision.casilla_values[retenciones_trabajo_casilla]) == retenciones_trabajo_amount
        assert Decimal(revision.binding_overrides[retenciones_trabajo_binding]) == retenciones_trabajo_amount
        revision_id = revision.calculation_revision_id
        salaried = _workflow_profile().model_copy(
            update={
                "entity_type": EntityType.NATURAL_PERSON,
                "irpf_income_categories": frozenset({IrpfIncomeCategory.TRABAJO}),
            },
        )
        report = verify_modelo_revision(
            revision_id,
            actor="operator-test",
            workflow_profile=salaried,
            settings=ready_clave_settings("X1234567L"),
            clock=_CLOCK,
        )

    assert report.granted_verificado_completo is True
    assert not any(
        finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN for finding in report.findings
    )
    # The not-applicable advisory directs the operator to enter suffered
    # retenciones via the --binding source rather than --casilla. Its prose is
    # localised (the runtime resolves the Spanish catalogue string, e.g. "no
    # aplicables" / "--binding CLAVE=VALOR"), so assert on the locale-stable CLI
    # flag tokens the guidance names in every locale, not the English wording.
    assert any(
        finding.kind is ModeloVerificationFindingKind.ADVISORY
        and finding.message_locale_key == "application.modelo.findings.cross_period_modelo_not_applicable.message"
        for finding in report.findings
    )
    assert any(
        finding.kind is ModeloVerificationFindingKind.ADVISORY
        and finding.message_locale_key == "application.modelo.findings.cross_period_zero_value_previous_filing"
        for finding in report.findings
    )


def test_file_modelo_390_passes_clean_state_with_imported_bound_justificantes(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CROSS_PERIOD_390_IMPORTED_PROFILE_ID) as profile:
        _seed_ready_profile(profile.bucket_id, profile.repository, modelo="390")
        target_snapshot = bundled_authority().snapshot("390", filing_year=2025, period="0A")
        observations = CalculationObservationRepository()
        requirements_by_source: dict[tuple[str, int, str], set[CasillaId]] = {}
        for requirement in cross_period_dependency_requirements(target_snapshot):
            requirements_by_source.setdefault(
                (requirement.source_modelo, requirement.filing_year, requirement.period.registry_token),
                set(),
            ).update(requirement.source_casilla_ids)

        for (source_modelo, filing_year, period), source_casilla_ids in sorted(requirements_by_source.items()):
            source_snapshot = bundled_authority().snapshot(
                source_modelo,
                filing_year=filing_year,
                period=period,
            )
            source_work_unit = create_work_unit(
                bucket_id=profile.bucket_id,
                modelo=source_modelo,
                filing_year=filing_year,
                period=Period.from_year_and_code(filing_year, period),
                revision_id=source_snapshot.revision.id,
                clock=_CLOCK,
            )
            casilla_values = {
                casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(sorted(source_casilla_ids))
            }
            registry_observations = registry_grounded_observations(
                modelo=source_modelo,
                filing_year=filing_year,
                period=period,
                casilla_values=casilla_values,
            )
            evidence_reference_id = f"JUST{source_modelo}{filing_year}{period}"
            persist_justificante_metadata(
                evidence_reference_id,
                modelo=source_modelo,
                filing_year=filing_year,
                period=period,
                captured_at=_CLOCK,
            )
            if source_modelo == "303":
                filing_instance_evidence = general_m303_filing_evidence(
                    Period.from_year_and_code(filing_year, period),
                    reference="test:cross-period-clean-state:imported-m303",
                )
                calculation_revision_id = derive_calculation_revision_id(
                    work_unit_id=source_work_unit.work_unit_id,
                    input_values_by_casilla_id={},
                    binding_overrides={},
                    relation_overrides={},
                    casilla_values=casilla_values,
                    filing_instance_evidence=filing_instance_evidence,
                    source_provenance=(),
                )
                calculation_repository = CalculationRevisionCatalogueRepository()
                calculation_repository.save(
                    upsert_calculation_revision(
                        calculation_repository.load(),
                        CalculationRevision(
                            calculation_revision_id=calculation_revision_id,
                            work_unit_id=source_work_unit.work_unit_id,
                            state=CalculationRevisionState.PRESENTADO,
                            casilla_values=casilla_values,
                            observations=registry_observations,
                            created_at=_CLOCK,
                            updated_at=_CLOCK,
                            verified_at=_CLOCK,
                            verified_by="aeat-import-test",
                            filed_at=_CLOCK,
                            filed_by="aeat-import-test",
                            filing_instance_evidence=filing_instance_evidence,
                            source_provenance=(),
                        ),
                    )
                )
                filing_record_id = derive_filing_record_id(
                    work_unit_id=source_work_unit.work_unit_id,
                    calculation_revision_id=calculation_revision_id,
                    filed_by="aeat-import-test",
                )
                filing_repository = ModeloRecordCatalogueRepository()
                filing_repository.save(
                    upsert_filing_record(
                        filing_repository.load(),
                        ModeloRecord(
                            filing_record_id=filing_record_id,
                            work_unit_id=source_work_unit.work_unit_id,
                            calculation_revision_id=calculation_revision_id,
                            bucket_id=profile.bucket_id,
                            modelo=source_modelo,
                            filing_year=filing_year,
                            period=Period.from_year_and_code(filing_year, period),
                            filed_at=_CLOCK,
                            filed_by="aeat-import-test",
                            aeat_accepted=True,
                            external_evidence=ExternalEvidence(
                                kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                                reference_id=evidence_reference_id,
                                imported_at=_CLOCK,
                            ),
                        ),
                    )
                )
            else:
                import_external_filing_evidence(
                    work_unit_id=source_work_unit.work_unit_id,
                    casilla_values=casilla_values,
                    evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    evidence_reference_id=evidence_reference_id,
                    actor="aeat-import-test",
                    expected_tax_id="X1234567L",
                    clock=_CLOCK,
                )
            observations.save(
                observations.prepare_observation_envelope(
                    RegistryModeloObservation(
                        modelo=source_modelo,
                        filing_year=filing_year,
                        period=period,
                        observations=registry_observations,
                    ),
                    source_kind="aeat_sede_justificante",
                    captured_at=_CLOCK,
                    stamped_revision_id=source_snapshot.revision.id,
                    source_metadata={
                        "aeat_register_status": "ALTA",
                        "aeat_expediente_id": f"EXP-{source_modelo}-{filing_year}-{period}",
                        "aeat_justificante_csv": evidence_reference_id,
                        "authenticated_identity": "X1234567L",
                    },
                )
            )

        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="390",
            filing_year=2025,
            period="0A",
        )

        filing = file_modelo_revision(
            revision_id,
            actor="operator-test",
            workflow_profile=_workflow_profile(),
            clock=_CLOCK,
        )

    assert filing.modelo == "390"
    assert filing.filing_year == 2025
    assert filing.period == Period.from_year_and_code(2025, "0A")
    assert filing.status is ModeloRecordStatus.VIGENTE


def test_file_refuses_modelo_353_when_expected_member_roster_is_incomplete(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CROSS_PERIOD_353_PROFILE_ID) as profile:
        snapshot = bundled_authority().snapshot("353", filing_year=2026, period="12")
        requirement = next(
            item for item in cross_period_dependency_requirements(snapshot) if item.requires_member_fan_in
        )
        CalculationObservationRepository().save(
            CalculationObservationRepository().prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="322",
                    filing_year=2026,
                    period="12",
                    observations=registry_grounded_observations(
                        modelo="322",
                        filing_year=2026,
                        period="12",
                        casilla_values={
                            casilla_id: Decimal(index + 1)
                            for index, casilla_id in enumerate(requirement.source_casilla_ids)
                        },
                    ),
                ),
                source_kind="aeat_sede_justificante",
                captured_at=_CLOCK,
                member_nif="A00000000",
            )
        )
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="353",
            filing_year=2026,
            period="12",
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(),
                cross_period_expected_member_sets=(
                    CrossPeriodExpectedMemberSet(
                        source_modelo="322",
                        filing_year=2026,
                        period=Period.from_year_and_code(2026, "12"),
                        member_nifs=("A00000000", "B00000001"),
                    ),
                ),
                clock=_CLOCK,
            )

    failure = exc_info.value.precondition_failure
    assert failure is not None
    blocker_codes = str(failure.verdict.evidence[0].values["blocker_codes"]).split("|")
    assert "incomplete_group_member_coverage" in blocker_codes
    assert "missing_expected_group_member_roster" not in blocker_codes


def test_file_uses_profile_group_roster_for_modelo_353_member_fan_in(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CROSS_PERIOD_353_ROSTER_PROFILE_ID) as profile:
        snapshot = bundled_authority().snapshot("353", filing_year=2026, period="12")
        requirement = next(
            item for item in cross_period_dependency_requirements(snapshot) if item.requires_member_fan_in
        )
        CalculationObservationRepository().save(
            CalculationObservationRepository().prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="322",
                    filing_year=2026,
                    period="12",
                    observations=registry_grounded_observations(
                        modelo="322",
                        filing_year=2026,
                        period="12",
                        casilla_values={
                            casilla_id: Decimal(index + 1)
                            for index, casilla_id in enumerate(requirement.source_casilla_ids)
                        },
                    ),
                ),
                source_kind="aeat_sede_justificante",
                captured_at=_CLOCK,
                member_nif="A00000000",
            )
        )
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="353",
            filing_year=2026,
            period="12",
        )
        workflow_profile = _workflow_profile().model_copy(
            update={
                "cross_period_group_member_rosters": (
                    CrossPeriodGroupMemberRoster(
                        source_modelo="322",
                        filing_year=2026,
                        period=Period.from_year_and_code(2026, "12"),
                        member_nifs=("A00000000", "B00000000"),
                    ),
                ),
            },
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=workflow_profile,
                clock=_CLOCK,
            )

    failure = exc_info.value.precondition_failure
    assert failure is not None
    blocker_codes = str(failure.verdict.evidence[0].values["blocker_codes"]).split("|")
    assert "incomplete_group_member_coverage" in blocker_codes
    assert "missing_expected_group_member_roster" not in blocker_codes


def test_no_prior_obligation_provenance_never_has_official_source_capability() -> None:
    """Honesty: pre-activity suppression provenance is never official.

    The no-prior-obligation facet records a SUPPRESSION (no obligation existed),
    not a filing's AEAT evidence. None of its enum values - the facet
    discriminator, the operator-declared provenance, or the censo-corroborated
    provenance - may ever gain official-AEAT source capability. Were any
    admitted, an unevidenced pre-activity scoping could masquerade as official
    AEAT evidence and launder a dependent filing past the evidence gate.
    """
    for kind in NoPriorObligationProvenanceKind:
        assert not is_official_aeat_observation_source(kind.value)
    assert {kind for kind in ObservationSourceKind if kind.is_official_aeat} == {
        ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE,
        ObservationSourceKind.AEAT_CSV_REGISTER,
    }
    assert not is_official_aeat_observation_source("mixed")
    assert not is_official_aeat_observation_source("unknown_source")


def test_first_local_filing_still_persists_under_non_official_app_filing() -> None:
    """Honesty: the first local filing stays non-official ``app_filing``.

    The first-filer fix scopes a pre-activity DEMAND for evidence out of the graph;
    it never mints evidence. The local ``file`` flow still stamps its persisted
    observation as the non-official ``app_filing`` source kind, so a later dependent
    period still demands real AEAT evidence of that filing - the
    ``no-silent-under-declaration`` invariant is unchanged.
    """
    assert APP_FILING_SOURCE_KIND == "app_filing"
    assert not APP_FILING_SOURCE_KIND.is_official_aeat
