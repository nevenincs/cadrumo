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

from collections.abc import Collection
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from ....application.modelo.work_lifecycle import create_work_unit
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.bindings import CasillaObservationValueKind, RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition_work_ports import build_calculation_action_ports, build_work_lifecycle_ports
from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .observation_seeding_support import save_stamped_observation

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
#: The prior return's remainders that open this year's older Anexo C rows (1380, 1382, 1385).
_PRIOR_ANEXO_C_REMAINDERS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="_PRIOR_ANEXO_C_REMAINDERS") for box in ("1384", "1387", "1390")
)
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
        "retencion_soportada",
        *BUCKET_AGGREGATION_LOCK_SOURCES,
    },
)
__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _seed_profile(*identity: UserProfileFact, without: Collection[str] = ()) -> None:
    """Seed a single natural-person taxpayer whose facts cover Modelo 100's calculation bindings.

    ``without`` names the persona facts, such as its name, this taxpayer never stated.
    """
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                *identity,
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
            ),
            without=without,
        ),
        created_at=_T0,
        updated_at=_T0,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _seed_filed(
    secure_objects: SecureObjectRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_ids: tuple[CasillaId, ...],
) -> None:
    """Persist one filing's zero-valued source casillas through the production observation store."""
    observation = RegistryModeloObservation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=registry_grounded_observations(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=dict.fromkeys(casilla_ids, Decimal("0")),
        ),
    )
    repository = CalculationObservationRepository(objects=secure_objects)
    save_stamped_observation(repository, observation, source_kind=APP_FILING_SOURCE_KIND, captured_at=_T0)


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
        casilla_ids=(_BASE_LIQUIDABLE_NEGATIVA_GENERAL, *_PRIOR_ANEXO_C_REMAINDERS),
    )
    for source, casilla_id in _PAGOS_OUTPUT_BY_SOURCE.items():
        for quarter in ("1T", "2T", "3T", "4T"):
            _seed_filed(
                secure_objects, modelo=source, filing_year=_M100_YEAR, period=quarter, casilla_ids=(casilla_id,)
            )
    snapshot = published_authority_operation().snapshot("100", filing_year=_M100_YEAR, period=_ANNUAL)
    zero_bindings = {
        binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.source not in _SOURCED_ELSEWHERE
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
    _seed_profile(
        UserProfileFact(path="identity.tax_id", value="12345678Z"), without=("identity.name", "identity.surnames")
    )

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
