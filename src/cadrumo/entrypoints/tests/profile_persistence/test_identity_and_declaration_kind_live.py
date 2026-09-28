"""Identity and declaration-kind casillas on the live calculate path.

A required text casilla the calculation supplies used to arrive empty unless a
placeholder zero stood in for it. On the live operator path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`),
over a real encrypted bucket and a synthetic profile:

* the Modelo 100 declarant NIF and name casillas take the profile's identity
  through their registry profile bindings, and are persisted as text inputs so
  a replay reads the same value back;
* a profile that declares no name leaves that casilla empty and the calculation
  returns an advisory naming the profile fields to declare;
* the Modelo 347 declaration-kind casilla takes the kind of declaration the
  work unit prepares -- an original one -- from the filing context.

Real registry authority, real engine, real source mesh; nothing is mocked.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from ....application.modelo.calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.bindings import CasillaObservationValueKind, RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ...adapter_composition import build_calculation_action_ports, build_work_lifecycle_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "5a1c7e20-0000-4000-8000-00000000d1d0"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_DECLARANTE_NIF: CasillaId = validated_casilla_id("DPNIF_D", surface="_DECLARANTE_NIF")
_DECLARANTE_NAME: CasillaId = validated_casilla_id("DP_APENOM_D", surface="_DECLARANTE_NAME")
_M347_DECLARATION_KIND: CasillaId = validated_casilla_id("decl.tipo-declaracion", surface="_M347_DECLARATION_KIND")
_M100_YEAR = 2024
_ANNUAL = "0A"
_BASE_LIQUIDABLE_NEGATIVA_GENERAL: CasillaId = validated_casilla_id("1391", surface="_BASE_LIQUIDABLE_NEGATIVA")
_PAGOS_OUTPUT_BY_SOURCE: dict[str, CasillaId] = {
    "130": validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT"),
    "131": validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT"),
}
_SOURCED_ELSEWHERE = frozenset(
    {
        "profile",
        "relation_prefill",
        "ledger_renta_income_aggregation",
        "ledger_renta_gastos_estimacion_directa_aggregation",
        "ledger_iva_aggregation",
        "ledger_oss_aggregation",
        "collectible_invoice",
        "payable_invoice",
    },
)
_OPTIONAL_PAYEE_RETENCIONES_BINDINGS: frozenset[BindingId] = frozenset({"renta-certificado-trabajo-retenciones"})

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _seed_profile(*identity: UserProfileFact) -> None:
    """Seed a single natural-person taxpayer whose facts cover Modelo 100's calculation bindings."""
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            *identity,
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
            UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
        ),
        created_at=_T0,
        updated_at=_T0,
        context=_profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _seed_filed(
    secure_objects: SecureObjectRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_id: CasillaId,
) -> None:
    """Persist one filed zero-valued source casilla through the production observation store."""
    observation = RegistryModeloObservation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=registry_grounded_observations(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values={casilla_id: Decimal("0")},
        ),
    )
    repository = CalculationObservationRepository(objects=secure_objects)
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
            stamped_revision_id=revision_id_for_observation(observation),
        ),
    )


def _calculate(
    secure_objects: SecureObjectRepository,
    *,
    modelo: str,
    filing_year: int,
    binding_values: dict[BindingId, Decimal] | None = None,
) -> BucketAggregationCalculationResult:
    snapshot = published_authority_operation().snapshot(modelo, filing_year=filing_year, period=_ANNUAL)
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, _ANNUAL),
            revision_id=snapshot.revision.id,
            ports=build_work_lifecycle_ports(bucket_id=_BUCKET_ID),
            operation=operation,
            clock=_T0,
        )
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
            binding_values=binding_values,
            clock=_T1,
        )


def _calculate_m100(secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    """Run the live Modelo 100 2024 calculation with every non-profile, non-relation binding at zero.

    The annual formulas read the prior-year negative base carry and the M130
    and M131 instalment relations directly, so those legs are seeded as filed
    zeros; they are not what this module asserts.
    """
    _seed_filed(
        secure_objects,
        modelo="100",
        filing_year=_M100_YEAR - 1,
        period=_ANNUAL,
        casilla_id=_BASE_LIQUIDABLE_NEGATIVA_GENERAL,
    )
    for source, casilla_id in _PAGOS_OUTPUT_BY_SOURCE.items():
        for quarter in ("1T", "2T", "3T", "4T"):
            _seed_filed(secure_objects, modelo=source, filing_year=_M100_YEAR, period=quarter, casilla_id=casilla_id)
    snapshot = published_authority_operation().snapshot("100", filing_year=_M100_YEAR, period=_ANNUAL)
    zero_bindings = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id not in _OPTIONAL_PAYEE_RETENCIONES_BINDINGS and binding.source not in _SOURCED_ELSEWHERE
    }
    return _calculate(secure_objects, modelo="100", filing_year=_M100_YEAR, binding_values=zero_bindings)


def _text_observation(result: BucketAggregationCalculationResult, casilla_id: CasillaId) -> str | None:
    for observation in result.revision.observations:
        if observation.casilla_id == casilla_id:
            assert observation.value_kind == CasillaObservationValueKind.TEXT
            return str(observation.value)
    return None


def test_the_declarant_identity_reaches_modelo_100_from_the_profile(secure_objects: SecureObjectRepository) -> None:
    _seed_profile(
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="identity.name", value="Maria"),
        UserProfileFact(path="identity.surnames", value="Garcia Lopez"),
    )

    result = _calculate_m100(secure_objects)

    assert _text_observation(result, _DECLARANTE_NIF) == "12345678Z"
    assert _text_observation(result, _DECLARANTE_NAME) == "Garcia Lopez Maria"
    # Persisted as text inputs, the spelling a replay of the revision reads back.
    assert result.revision.input_values_by_casilla_id[_DECLARANTE_NIF] == "12345678Z"
    assert result.revision.input_values_by_casilla_id[_DECLARANTE_NAME] == "Garcia Lopez Maria"
    assert not {_DECLARANTE_NIF, _DECLARANTE_NAME} & {
        diagnostic.casilla_id for diagnostic in result.source_diagnostics if diagnostic.reason == "unresolved_binding"
    }


def test_a_profile_without_a_name_leaves_it_empty_and_says_which_fields_to_declare(
    secure_objects: SecureObjectRepository,
) -> None:
    _seed_profile(UserProfileFact(path="identity.tax_id", value="12345678Z"))

    result = _calculate_m100(secure_objects)

    assert _text_observation(result, _DECLARANTE_NAME) is None
    assert _DECLARANTE_NAME not in result.revision.input_values_by_casilla_id
    (advisory,) = (
        diagnostic
        for diagnostic in result.source_diagnostics
        if diagnostic.reason == "unresolved_binding" and diagnostic.casilla_id == _DECLARANTE_NAME
    )
    assert advisory.source_kind == "profile"
    assert advisory.remedy is not None
    assert "identity.surnames" in advisory.remedy
    assert "identity.name" in advisory.remedy


def test_the_declaration_kind_reaches_modelo_347_from_the_filing_context(
    secure_objects: SecureObjectRepository,
) -> None:
    _seed_profile(
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="identity.name", value="Maria"),
        UserProfileFact(path="identity.surnames", value="Garcia Lopez"),
    )

    result = _calculate(secure_objects, modelo="347", filing_year=2025)

    assert _text_observation(result, _M347_DECLARATION_KIND) == "original"
    assert result.revision.input_values_by_casilla_id[_M347_DECLARATION_KIND] == "original"
