"""Calculation enrollment: Modelo 714 art.31 joint limit from same-year M100.

This test drives the real registry calculation path for Modelo 714 across two
renta years. Each year saves real local Modelo 100 observations, resolves the
M714 same-year M100 relations through the local relation resolver, then runs
the M714 formula engine through casilla 40.

See Also:
    :func:`~application.calculations._relation_prefill.resolve_relations_from_local_store`
        Resolves the same-year Modelo 100 relation values this enrollment feeds
        into the Patrimonio art.31 formula chain.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Evaluates the registry snapshot after the relation values and manual
        Modelo 714 inputs are assembled.
    :class:`~application.calculations.EnrollmentRecorder`
        Captures the two distinct renta years asserted against the authorization
        manifest.
    :mod:`~domain.calculations.registry.tests.test_modelo_714_registry`
        Registry-level proof for the same art.31 relations and calculation
        chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ids import RelationId

from ....core import (
    CasillaId,
    validated_casilla_id,
)
from ....domain.calculations.registry.authority import bundled_authority
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "714"
_SOURCE_MODELO = "100"
_RENTA_YEARS = (2023, 2024)
_CAPTURED_AT = datetime(2025, 6, 20, 10, 0, 0, tzinfo=UTC)


_M100_BASE_IMPONIBLE_GENERAL: CasillaId = validated_casilla_id("0435", surface="M714 enrollment casilla id")
_M100_BASE_IMPONIBLE_AHORRO: CasillaId = validated_casilla_id("0460", surface="M714 enrollment casilla id")
_M100_CUOTA_INTEGRA_ESTATAL: CasillaId = validated_casilla_id("0545", surface="M714 enrollment casilla id")
_M100_CUOTA_INTEGRA_AUTONOMICA: CasillaId = validated_casilla_id("0546", surface="M714 enrollment casilla id")

_PATRIMONIO_BASE_LIQUIDABLE: CasillaId = validated_casilla_id(
    "patrimonio.base-liquidable", surface="M714 enrollment casilla id"
)
_PATRIMONIO_DIVIDENDOS_NO_IRPF: CasillaId = validated_casilla_id(
    "patrimonio.dividendos-no-irpf", surface="M714 enrollment casilla id"
)
_PATRIMONIO_BASE_AHORRO_EXCLUIDA: CasillaId = validated_casilla_id(
    "patrimonio.base-ahorro-excluida", surface="M714 enrollment casilla id"
)
_PATRIMONIO_IRPF_CUOTAS_EXCLUIDAS_BASE_AHORRO: CasillaId = validated_casilla_id(
    "patrimonio.irpf-cuotas-excluidas-base-ahorro", surface="M714 enrollment casilla id"
)
_PATRIMONIO_CUOTA_INTEGRA_SUSCEPTIBLE_LIMITACION: CasillaId = validated_casilla_id(
    "patrimonio.cuota-integra-susceptible-limitacion", surface="M714 enrollment casilla id"
)
_PATRIMONIO_CUOTA_INTEGRA: CasillaId = validated_casilla_id(
    "patrimonio.cuota-integra", surface="M714 enrollment casilla id"
)
_PATRIMONIO_IRPF_BASES_IMPONIBLES: CasillaId = validated_casilla_id(
    "patrimonio.irpf-bases-imponibles", surface="M714 enrollment casilla id"
)
_PATRIMONIO_LIMITE_CONJUNTO: CasillaId = validated_casilla_id(
    "patrimonio.limite-conjunto", surface="M714 enrollment casilla id"
)
_PATRIMONIO_IRPF_CUOTAS_INTEGRAS: CasillaId = validated_casilla_id(
    "patrimonio.irpf-cuotas-integras", surface="M714 enrollment casilla id"
)
_PATRIMONIO_SUMA_CUOTAS_LIMITE: CasillaId = validated_casilla_id(
    "patrimonio.suma-cuotas-limite", surface="M714 enrollment casilla id"
)
_PATRIMONIO_EXCESO_LIMITE_CONJUNTO: CasillaId = validated_casilla_id(
    "patrimonio.exceso-limite-conjunto", surface="M714 enrollment casilla id"
)
_PATRIMONIO_REDUCCION_LIMITE_80: CasillaId = validated_casilla_id(
    "patrimonio.reduccion-limite-80", surface="M714 enrollment casilla id"
)
_PATRIMONIO_TOTAL_CUOTA_INTEGRA: CasillaId = validated_casilla_id(
    "patrimonio.total-cuota-integra", surface="M714 enrollment casilla id"
)

_M714_REL_100_BASE_IMPONIBLE_GENERAL: RelationId = "m714-rel-100-base-imponible-general"
_M714_REL_100_BASE_IMPONIBLE_AHORRO: RelationId = "m714-rel-100-base-imponible-ahorro"
_M714_REL_100_CUOTA_INTEGRA_ESTATAL: RelationId = "m714-rel-100-cuota-integra-estatal"
_M714_REL_100_CUOTA_INTEGRA_AUTONOMICA: RelationId = "m714-rel-100-cuota-integra-autonomica"


@dataclass(frozen=True, slots=True)
class JointLimitScenario:
    filing_year: int
    base_liquidable: Decimal
    m100_base_general: Decimal
    m100_base_ahorro: Decimal
    m100_cuota_estatal: Decimal
    m100_cuota_autonomica: Decimal
    dividendos_no_irpf: Decimal
    base_ahorro_excluida: Decimal
    cuota_irpf_excluida: Decimal
    cuota_ip_susceptible: Decimal
    expected_cuota_integra: Decimal
    expected_irpf_bases: Decimal
    expected_limite_conjunto: Decimal
    expected_irpf_cuotas: Decimal
    expected_suma_cuotas: Decimal
    expected_exceso: Decimal
    expected_suelo_80: Decimal
    expected_total_cuota: Decimal


_SCENARIOS: dict[int, JointLimitScenario] = {
    2023: JointLimitScenario(
        filing_year=2023,
        base_liquidable=Decimal("1000000.00"),
        m100_base_general=Decimal("10000.00"),
        m100_base_ahorro=Decimal("20000.00"),
        m100_cuota_estatal=Decimal("3000.00"),
        m100_cuota_autonomica=Decimal("4000.00"),
        dividendos_no_irpf=Decimal("0.00"),
        base_ahorro_excluida=Decimal("15000.00"),
        cuota_irpf_excluida=Decimal("2000.00"),
        cuota_ip_susceptible=Decimal("5490.36"),
        expected_cuota_integra=Decimal("5490.36"),
        expected_irpf_bases=Decimal("30000.00"),
        expected_limite_conjunto=Decimal("9000.00"),
        expected_irpf_cuotas=Decimal("7000.00"),
        expected_suma_cuotas=Decimal("10490.36"),
        expected_exceso=Decimal("1490.36"),
        expected_suelo_80=Decimal("4392.29"),
        expected_total_cuota=Decimal("4000.00"),
    ),
    2024: JointLimitScenario(
        filing_year=2024,
        base_liquidable=Decimal("700000.00"),
        m100_base_general=Decimal("8000.00"),
        m100_base_ahorro=Decimal("7000.00"),
        m100_cuota_estatal=Decimal("1000.00"),
        m100_cuota_autonomica=Decimal("1200.00"),
        dividendos_no_irpf=Decimal("0.00"),
        base_ahorro_excluida=Decimal("5000.00"),
        cuota_irpf_excluida=Decimal("500.00"),
        cuota_ip_susceptible=Decimal("2790.36"),
        expected_cuota_integra=Decimal("2790.36"),
        expected_irpf_bases=Decimal("15000.00"),
        expected_limite_conjunto=Decimal("6000.00"),
        expected_irpf_cuotas=Decimal("2200.00"),
        expected_suma_cuotas=Decimal("4490.36"),
        expected_exceso=Decimal("0.00"),
        expected_suelo_80=Decimal("2232.29"),
        expected_total_cuota=Decimal("2790.36"),
    ),
}


def _m100_observation(scenario: JointLimitScenario):
    return registry_grounded_modelo_observation(
        modelo=_SOURCE_MODELO,
        filing_year=scenario.filing_year,
        period="0A",
        casilla_values={
            _M100_BASE_IMPONIBLE_GENERAL: scenario.m100_base_general,
            _M100_BASE_IMPONIBLE_AHORRO: scenario.m100_base_ahorro,
            _M100_CUOTA_INTEGRA_ESTATAL: scenario.m100_cuota_estatal,
            _M100_CUOTA_INTEGRA_AUTONOMICA: scenario.m100_cuota_autonomica,
        },
    )


def _manual_m714_inputs(scenario: JointLimitScenario) -> dict[CasillaId, Decimal]:
    return {
        _PATRIMONIO_BASE_LIQUIDABLE: scenario.base_liquidable,
        _PATRIMONIO_DIVIDENDOS_NO_IRPF: scenario.dividendos_no_irpf,
        _PATRIMONIO_BASE_AHORRO_EXCLUIDA: scenario.base_ahorro_excluida,
        _PATRIMONIO_IRPF_CUOTAS_EXCLUIDAS_BASE_AHORRO: scenario.cuota_irpf_excluida,
        _PATRIMONIO_CUOTA_INTEGRA_SUSCEPTIBLE_LIMITACION: scenario.cuota_ip_susceptible,
    }


def _calculate_714_from_local_m100(
    *,
    scenario: JointLimitScenario,
    repository: CalculationObservationRepository,
) -> RegistryCalculationResult:
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=scenario.filing_year, period="0A")
    prefill = resolve_relations_from_local_store(
        snapshot,
        repository=repository,
        captured_at=_CAPTURED_AT,
        m111_no_retenciones_periods=frozenset(),
        not_applicable_source_modelos=frozenset(),
    )
    relation_values = {item.relation: item.value for item in prefill.values if item.value is not None}
    assert relation_values == {
        _M714_REL_100_BASE_IMPONIBLE_GENERAL: scenario.m100_base_general,
        _M714_REL_100_BASE_IMPONIBLE_AHORRO: scenario.m100_base_ahorro,
        _M714_REL_100_CUOTA_INTEGRA_ESTATAL: scenario.m100_cuota_estatal,
        _M714_REL_100_CUOTA_INTEGRA_AUTONOMICA: scenario.m100_cuota_autonomica,
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs=_manual_m714_inputs(scenario),
        relation_values=relation_values,
        date_context={"filing_period": date(scenario.filing_year, 12, 31)},
    )


def _assert_joint_limit_outputs(result: RegistryCalculationResult, scenario: JointLimitScenario) -> None:
    assert result.values[_PATRIMONIO_CUOTA_INTEGRA] == scenario.expected_cuota_integra
    assert result.values[_PATRIMONIO_IRPF_BASES_IMPONIBLES] == scenario.expected_irpf_bases
    assert result.values[_PATRIMONIO_LIMITE_CONJUNTO] == scenario.expected_limite_conjunto
    assert result.values[_PATRIMONIO_IRPF_CUOTAS_INTEGRAS] == scenario.expected_irpf_cuotas
    assert result.values[_PATRIMONIO_SUMA_CUOTAS_LIMITE] == scenario.expected_suma_cuotas
    assert result.values[_PATRIMONIO_EXCESO_LIMITE_CONJUNTO] == scenario.expected_exceso
    assert result.values[_PATRIMONIO_REDUCCION_LIMITE_80] == scenario.expected_suelo_80
    assert result.values[_PATRIMONIO_TOTAL_CUOTA_INTEGRA] == scenario.expected_total_cuota


def test_modelo_714_joint_limit_calculates_from_local_m100_observation(tmp_path: Path) -> None:
    """M714 resolves same-year M100 outputs from the local store and calculates casilla 40."""
    scenario = _SCENARIOS[2023]
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                _m100_observation(scenario), source_kind="app_filing", captured_at=_CAPTURED_AT
            )
        )
        result = _calculate_714_from_local_m100(scenario=scenario, repository=repo)

    _assert_joint_limit_outputs(result, scenario)


def test_modelo_714_joint_limit_calculation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: M714 art.31 calculation across two renta years."""
    recorder = EnrollmentRecorder(_MODELO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        for filing_year in _RENTA_YEARS:
            scenario = _SCENARIOS[filing_year]
            repo.save(
                repo.prepare_observation_envelope(
                    _m100_observation(scenario), source_kind="app_filing", captured_at=_CAPTURED_AT
                )
            )
            result = _calculate_714_from_local_m100(scenario=scenario, repository=repo)
            _assert_joint_limit_outputs(result, scenario)
            recorder.record_calculation_year(filing_year=filing_year, produced_value_count=len(result.values))

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == _RENTA_YEARS
    assert_enrollment_matches_manifest(evidence)
