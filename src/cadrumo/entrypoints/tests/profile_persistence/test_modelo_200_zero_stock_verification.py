"""Exercise M200's zero-loss-stock cap with published authority and real storage."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.cross_period_clean_state import cross_period_dependency_requirements
from cadrumo.application.calculations.observations_repository import ObservationSourceKind
from cadrumo.application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.external_import_actions import import_external_filing_evidence
from cadrumo.application.modelo.operation_definitions import resolve_active_workflow_profile
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.tests.env_scope import ready_clave_settings

if TYPE_CHECKING:
    from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
    from cadrumo.application.modelo.calculation_action_ports import CalculationActionPorts
    from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLOCK = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
_TAX_ID = "B12345674"
_SOURCE_PERIOD = "0A"
_SOURCE_YEAR = 2024
_TARGET_PERIOD = "0A"
_TARGET_YEAR = 2025
_SOURCE_BIN_CASILLA = validated_casilla_id("00671", surface="M200 prior loss stock")
_TARGET_BASE_INPUT_CASILLA = validated_casilla_id("DP200012:00501", surface="M200 positive base input")
_TARGET_APPLIED_BIN_CASILLA = validated_casilla_id("DP200014:00547", surface="M200 applied loss amount")
_TARGET_BASE_CASILLA = validated_casilla_id("DP200014:00550", surface="M200 computed base")
_TARGET_BIN_CEILING_CASILLA = validated_casilla_id("00670", surface="M200 computed loss ceiling")
_CAP_PREDICATE_ID = "modelo-200-compensacion-bin-no-excede-stock-disponible"
_PROFILE_BUCKET_ID = "20000000-0000-4000-8000-000000000299"


def _seed_legal_entity_profile(bucket_id: str, operation: PinnedAuthorityOperation) -> None:
    """Seed the existing synthetic corporate-profile shape under this operation's schema pin."""
    facts = (
        UserProfileFact(path="identity.tax_id", value=_TAX_ID),
        UserProfileFact(path="identity.name", value="Test"),
        UserProfileFact(path="identity.surnames", value="Operator"),
        UserProfileFact(path="identity.legal_name", value="Test Company SL"),
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
        UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
        UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
        UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
        UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="7000000"),
        UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
    )
    seed_test_profile_record(
        create_user_profile_record(
            context=operation.profile_create_context(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=facts,
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def _source_casillas_by_cohort(
    target_snapshot: RegistrySnapshot,
) -> dict[tuple[str, int, str], set[CasillaId]]:
    """Return the source casillas derived from every published target requirement."""
    source_casillas: dict[tuple[str, int, str], set[CasillaId]] = {}
    for requirement in cross_period_dependency_requirements(target_snapshot):
        cohort = (requirement.source_modelo, requirement.filing_year, requirement.period.registry_token)
        source_casillas.setdefault(cohort, set()).update(requirement.source_casilla_ids)
    expected_cohorts = {
        ("200", _SOURCE_YEAR, _SOURCE_PERIOD),
        ("202", _TARGET_YEAR, "1P"),
        ("202", _TARGET_YEAR, "2P"),
        ("202", _TARGET_YEAR, "3P"),
    }
    assert expected_cohorts <= source_casillas.keys(), (
        "the pinned target's cross-period graph no longer includes the expected M200/M202 filing cohorts"
    )
    assert _SOURCE_BIN_CASILLA in source_casillas[("200", _SOURCE_YEAR, _SOURCE_PERIOD)], (
        "the published target no longer declares prior M200 00671"
    )
    return source_casillas


def _import_clean_source_cohort(
    *,
    bucket_id: str,
    profile_repository: SecureObjectRepository,
    ports: CalculationActionPorts,
    observation_repository: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
    cohort: tuple[str, int, str],
    source_casilla_ids: set[CasillaId],
) -> None:
    """Create one synthetic filed source and its separately typed AEAT receipt observation."""
    source_modelo, filing_year, period = cohort
    source_snapshot = operation.snapshot(
        source_modelo,
        filing_year=filing_year,
        period=period,
        on=date(filing_year, 12, 31),
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    source_definitions = {casilla.id: casilla for casilla in source_snapshot.revision.casillas}
    assert source_casilla_ids <= source_definitions.keys(), (
        f"a {source_modelo}/{filing_year}/{period} dependency casilla is absent from the pinned source revision"
    )
    source_values = {casilla_id: Decimal("0") for casilla_id in source_casilla_ids}
    source_observations = tuple(
        CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            legal_refs=source_definitions[casilla_id].legal_refs,
            source_refs=source_definitions[casilla_id].source_refs,
        )
        for casilla_id, value in sorted(source_values.items())
    )
    registry_observation = RegistryModeloObservation(
        modelo=source_modelo,
        filing_year=filing_year,
        period=period,
        observations=source_observations,
    )

    source_period = Period.from_year_and_code(filing_year, period)
    source_work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=source_modelo,
        filing_year=filing_year,
        period=source_period,
        revision_id=source_snapshot.revision.id,
        actor=f"synthetic-m{source_modelo}-source",
        ports=ports.work_lifecycle_ports,
        clock=_CLOCK,
        operation=operation,
    )
    source_reference = f"JUST{source_modelo}{filing_year}{period}"
    persist_justificante_metadata(
        source_reference,
        modelo=source_modelo,
        filing_year=filing_year,
        period=period,
        captured_at=_CLOCK,
        tax_id=_TAX_ID,
    )
    source_import = import_external_filing_evidence(
        work_unit_id=source_work_unit.work_unit_id,
        casilla_values=source_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=source_reference,
        actor=f"synthetic-m{source_modelo}-source-import",
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
        filing_repository=ports.filing_repository,
        bucket_event_repository=ports.bucket_event_repository,
        justificante_repository=JustificanteRepository(objects=profile_repository),
        observation_repository=observation_repository,
        expected_tax_id=_TAX_ID,
        clock=_CLOCK,
        operation=operation,
    )
    imported_source_revision = ports.calculation_repository.load().get(
        source_import.filing_record.calculation_revision_id,
    )
    assert imported_source_revision is not None
    assert imported_source_revision.state is CalculationRevisionState.PRESENTADO
    assert all(imported_source_revision.casilla_values[casilla_id] == Decimal("0") for casilla_id in source_casilla_ids)
    assert source_import.filing_record.modelo == source_modelo
    assert source_import.filing_record.filing_year == filing_year
    assert source_import.filing_record.period == source_period
    assert source_import.filing_record.external_evidence is not None
    assert source_import.filing_record.external_evidence.reference_id == source_reference

    # PDF import creates the filed chain, while this separate typed envelope supplies
    # the registry-stamped source values required by clean-state verification.
    source_envelope = observation_repository.prepare_observation_envelope(
        registry_observation,
        source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        captured_at=_CLOCK,
        stamped_revision_id=source_snapshot.revision.id,
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": f"EXP-{source_modelo}-{filing_year}-{period}",
            "aeat_justificante_csv": source_reference,
            "authenticated_identity": _TAX_ID,
        },
    )
    assert source_envelope.stamped_revision_id == source_snapshot.revision.id
    assert source_envelope.observation.modelo == source_modelo
    assert source_envelope.observation.filing_year == filing_year
    assert source_envelope.observation.period == period
    assert source_envelope.source_metadata["authenticated_identity"] == _TAX_ID
    assert source_envelope.source_metadata["aeat_justificante_csv"] == source_reference
    observation_repository.save(source_envelope)


@pytest.mark.parametrize(
    ("applied_bin", "expects_cap_finding"),
    (
        pytest.param(Decimal("0.00"), False, id="zero-applied-control"),
        pytest.param(Decimal("100.00"), True, id="positive-applied-amount"),
    ),
)
def test_m200_zero_prior_stock_still_checks_positive_applied_amount(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    authority_operation: PinnedAuthorityOperation,
    applied_bin: Decimal,
    expects_cap_finding: bool,
) -> None:
    """A clean prior filing with zero stock must not disable the target cap check."""
    request.node.user_properties.extend(
        (
            ("authority_root", str(Path(os.environ["CADRUMO_AUTHORITY_ROOT"]).resolve())),
            ("authority_generation", authority_operation.generation.logical_generation),
        ),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_BUCKET_ID) as profile:
        _seed_legal_entity_profile(profile.bucket_id, authority_operation)
        ports = build_calculation_action_ports(
            bucket_id=profile.bucket_id,
            operation=authority_operation,
            objects=profile.repository,
        )

        target_snapshot = authority_operation.snapshot(
            "200",
            filing_year=_TARGET_YEAR,
            period=_TARGET_PERIOD,
            on=date(_TARGET_YEAR, 12, 31),
            grade=RegistryAuthorityGrade.FILING,
        )
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        source_casillas_by_cohort = _source_casillas_by_cohort(target_snapshot)
        clean_source_cohorts = set(source_casillas_by_cohort)
        for cohort, source_casilla_ids in sorted(source_casillas_by_cohort.items()):
            _import_clean_source_cohort(
                bucket_id=profile.bucket_id,
                profile_repository=profile.repository,
                ports=ports,
                observation_repository=observation_repository,
                operation=authority_operation,
                cohort=cohort,
                source_casilla_ids=source_casilla_ids,
            )

        target_period = Period.from_year_and_code(_TARGET_YEAR, _TARGET_PERIOD)
        target_work_unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo="200",
            filing_year=_TARGET_YEAR,
            period=target_period,
            revision_id=target_snapshot.revision.id,
            actor="synthetic-m200-target",
            ports=ports.work_lifecycle_ports,
            clock=_CLOCK,
            operation=authority_operation,
        )
        target_declared_ids = {casilla.id for casilla in target_snapshot.revision.casillas}
        assert {
            _TARGET_BASE_INPUT_CASILLA,
            _TARGET_APPLIED_BIN_CASILLA,
            _TARGET_BASE_CASILLA,
            _TARGET_BIN_CEILING_CASILLA,
        } <= target_declared_ids
        assert any(
            predicate.predicate_id == _CAP_PREDICATE_ID
            for predicate in target_snapshot.revision.verification_predicates
        ), "the pinned target revision does not carry the expected M200 cap predicate"

        correction_casilla_ids = (
            validated_casilla_id("DP200013:00417", surface="M200 ordinary correction input"),
            validated_casilla_id("DP200013:00418", surface="M200 ordinary correction input"),
        )
        assert set(correction_casilla_ids) <= target_declared_ids, (
            "the pinned target revision does not carry the expected M200 ordinary correction inputs"
        )
        correction_casillas = {casilla_id: Decimal("0") for casilla_id in correction_casilla_ids}
        calculated = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            target_work_unit.work_unit_id,
            ports=ports,
            actor="synthetic-m200-calculation",
            casilla_inputs={
                _TARGET_BASE_INPUT_CASILLA: Decimal("1000.00"),
                _TARGET_APPLIED_BIN_CASILLA: applied_bin,
                **correction_casillas,
            },
            clock=_CLOCK,
        )
        target_revision = calculated.revision
        assert _TARGET_APPLIED_BIN_CASILLA in target_revision.casilla_values
        assert target_revision.casilla_values[_TARGET_APPLIED_BIN_CASILLA] == applied_bin
        assert _TARGET_BASE_CASILLA in target_revision.casilla_values
        assert target_revision.casilla_values[_TARGET_BASE_CASILLA] > Decimal("0")
        assert _TARGET_BIN_CEILING_CASILLA in target_revision.casilla_values
        assert target_revision.casilla_values[_TARGET_BIN_CEILING_CASILLA] == Decimal("0")

        result = verify_modelo_revision_with_preconditions(
            str(target_revision.calculation_revision_id),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            operator_scope_ports=build_operator_scope_ports(),
            actor="synthetic-m200-verification",
            workflow_profile=resolve_active_workflow_profile(authority_operation),
            verification_repositories=build_test_verification_repository_bundle(),
            settings=ready_clave_settings(_TAX_ID),
            clock=_CLOCK,
            operation=authority_operation,
        )
        report = result.report
        unclean_source_cohorts = {
            (
                str(finding.message_facts.get("source_modelo")),
                int(finding.message_facts["year"]),
                str(finding.message_facts.get("period")),
            )
            for finding in report.findings
            if finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
            and "year" in finding.message_facts
        }
        assert clean_source_cohorts.isdisjoint(unclean_source_cohorts), (
            "a synthetic zero-value M200/M202 filed source was not classified clean"
        )
        cap_finding = any(
            finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
            and finding.severity is ModeloVerificationFindingSeverity.BLOCKING
            and finding.message_facts.get("predicate_id") == _CAP_PREDICATE_ID
            for finding in report.findings
        )
        assert cap_finding is expects_cap_finding
