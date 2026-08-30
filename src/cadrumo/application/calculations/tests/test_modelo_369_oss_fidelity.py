"""E2E calculation continuity: Modelo 369 OSS Esquema Unión cross-renta cuota.

Modelo 369 (Declaración IVA OSS — Orden HAC/610/2021) is the quarterly
One-Stop-Shop autoliquidación for the Esquema Unión: operators established in
Spain who supply goods or services B2C to consumers in other EU member states
declare and pay the destination-state IVA centrally via the OSS portal (LIVA
arts. 163-unvicies to 163-quatervicies, Directiva 2021/285/UE). The period
code is ``"1T"``–``"4T"`` (quarterly).

The casilla schema (``esquema-union`` revision) includes three bound
destination cuota leaves and one computed total:
- ``decl.ejercicio`` — ejercicio (informational)
- ``decl.periodo`` — quarterly period code (informational)
- ``iva.union.de.services-cuota`` — IVA OSS Unión destination DE, servicios (bound)
- ``iva.union.fr.services-cuota`` — IVA OSS Unión destination FR, servicios (bound)
- ``iva.union.de.goods-distance-cuota`` — IVA OSS Unión destination DE, ventas a
  distancia + interfaces electrónicas (bound)
- ``iva.union.cuota-total`` — total, **computed** by the registry formula
  ``modelo-369-union-cuota-total`` = ``add`` of the three destination leaves.

This module is the multi-year-renta authorization enrollment for Modelo 369.
The 369 backend carries a real calculation engine (the ``add`` formula above
plus the three ``ledger_oss_aggregation`` destination bindings), so the
enrollment is **calculation-mode**: it drives the REAL registry calculation
engine (``calculate_registry_snapshot`` over the real authority snapshot, real
binding resolution — no mocks) for two distinct renta years, asserting the
engine computes ``iva.union.cuota-total`` as the cross-destination sum, and
records each year through :meth:`EnrollmentRecorder.record_calculation_year`
with the real produced-value count as un-fakeable evidence.

Grounding (non-tautological): the per-destination cuota leaves are supplied as
the ledger-aggregation binding facts (the OSS portal sums each destination
state's repercutida IVA); the load-bearing assertion is the *wiring* invariant
— the engine's ``iva.union.cuota-total`` equals the sum of the three supplied
destination leaves, which Orden HAC/610/2021 art. 1 / LIVA art. 163-unvicies
define as the total cuota repercutida del Esquema Unión. The total is produced
by the real engine from the destination inputs, never hand-computed against the
formula under test.

Legal grounding: LIVA arts. 163-unvicies to 163-quatervicies (OSS regime);
Orden HAC/610/2021 arts. 1–3 (form mandate, quarterly cadence); Directiva
2021/285/UE (One-Stop-Shop reform).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ..observations_repository import CalculationObservationRepository
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "369"
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025
_PERIOD = "2T"
_CLOCK_N = datetime(2024, 7, 31, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2025, 7, 31, 10, 0, 0, tzinfo=UTC)

#: The computed total casilla and its three bound destination leaves.
_CASILLA_TOTAL: CasillaId = validated_casilla_id(
    "iva.union.cuota-total",
    surface="test_modelo_369_oss_fidelity:_CASILLA_TOTAL",
)
_CASILLA_DE_SERVICES: CasillaId = validated_casilla_id(
    "iva.union.de.services-cuota",
    surface="test_modelo_369_oss_fidelity:_CASILLA_DE_SERVICES",
)
_CASILLA_FR_SERVICES: CasillaId = validated_casilla_id(
    "iva.union.fr.services-cuota",
    surface="test_modelo_369_oss_fidelity:_CASILLA_FR_SERVICES",
)
_CASILLA_DE_GOODS: CasillaId = validated_casilla_id(
    "iva.union.de.goods-distance-cuota",
    surface="test_modelo_369_oss_fidelity:_CASILLA_DE_GOODS",
)

#: The three ``ledger_oss_aggregation`` destination bindings whose facts the OSS
#: portal sums per destination state. Supplying them as the per-destination
#: repercutida IVA lets the engine compute the total via the real ``add``
#: formula ``modelo-369-union-cuota-total``.
_BINDING_DE_SERVICES = "modelo-369-union-de-services-21pct"
_BINDING_FR_SERVICES = "modelo-369-union-fr-services-21pct"
_BINDING_DE_GOODS = "modelo-369-union-de-goods-distance-21pct"


def _calculate_369(
    *,
    filing_year: int,
    period: str,
    destination_cuotas: Mapping[str, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL registry 369 calculation; return result + produced-value count.

    ``destination_cuotas`` is keyed by binding id (the per-destination
    ``ledger_oss_aggregation`` cuota). The bound destination leaves are resolved
    from those facts and the engine computes ``iva.union.cuota-total`` via the
    real ``add`` formula.
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=period)
    binding_values = dict(destination_cuotas)
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result, len(result.values)


def _registry_observation(
    *,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=filing_year,
        period=period,
        observations=result.observations,
    )


# Year-N 2T: a Spanish OSS operator supplying services to DE and FR plus
# distance sales to DE. Per-destination repercutida IVA: DE services 1890.00,
# FR services 945.00, DE goods 2100.00. The engine derives the total
# 1890 + 945 + 2100 = 4935.00 — produced by the real ``add`` formula, never
# hand-computed against it.
_YEAR_N_CUOTAS = {
    _BINDING_DE_SERVICES: Decimal("1890.00"),
    _BINDING_FR_SERVICES: Decimal("945.00"),
    _BINDING_DE_GOODS: Decimal("2100.00"),
}

# Year-N+1 2T: distinct per-destination cuotas so a cross-year bleed surfaces as
# strict inequality. 2310 + 1155 + 3150 = 6615.00.
_YEAR_N_PLUS_1_CUOTAS = {
    _BINDING_DE_SERVICES: Decimal("2310.00"),
    _BINDING_FR_SERVICES: Decimal("1155.00"),
    _BINDING_DE_GOODS: Decimal("3150.00"),
}


def test_year_n_engine_computes_cuota_total_as_cross_destination_sum(tmp_path: Path) -> None:
    """Year-N 369 2T: the engine computes the total as the sum of destination leaves.

    The total is produced by the real ``add`` formula from the three supplied
    destination cuotas, never hand-computed against the formula under test.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, produced = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
    assert produced > 0
    expected_sum = (
        _YEAR_N_CUOTAS[_BINDING_DE_SERVICES] + _YEAR_N_CUOTAS[_BINDING_FR_SERVICES] + _YEAR_N_CUOTAS[_BINDING_DE_GOODS]
    )
    assert result.values[_CASILLA_TOTAL] == expected_sum
    assert result.values[_CASILLA_DE_SERVICES] == _YEAR_N_CUOTAS[_BINDING_DE_SERVICES]


def test_computed_total_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """The engine-produced 369 casilla values survive the encrypted-SQL roundtrip."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result, _ = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
        obs = _registry_observation(filing_year=_YEAR_N, period=_PERIOD, result=result)
        repo.save(repo.prepare_observation_envelope(obs, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation == obs
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_both_years_independently_retrievable_no_bleed(tmp_path: Path) -> None:
    """Both ejercicios are independently addressable; cuota-total values do not bleed."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result_n, _ = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
        result_n1, _ = _calculate_369(
            filing_year=_YEAR_N_PLUS_1,
            period=_PERIOD,
            destination_cuotas=_YEAR_N_PLUS_1_CUOTAS,
        )
        obs_n = _registry_observation(filing_year=_YEAR_N, period=_PERIOD, result=result_n)
        obs_n1 = _registry_observation(filing_year=_YEAR_N_PLUS_1, period=_PERIOD, result=result_n1)
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)

        assert loaded_n is not None and loaded_n1 is not None
        total_n = loaded_n.observation.casilla_values[_CASILLA_TOTAL]
        total_n1 = loaded_n1.observation.casilla_values[_CASILLA_TOTAL]
        assert total_n == Decimal("4935.00")
        assert total_n1 == Decimal("6615.00")
        assert total_n != total_n1, "iva.union.cuota-total bled between year-N and year-N+1"
        assert loaded_n.captured_at != loaded_n1.captured_at


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result, _ = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
        obs = _registry_observation(filing_year=_YEAR_N, period=_PERIOD, result=result)
        obs_missing = RegistryModeloObservation(
            modelo=_MODELO,
            filing_year=_YEAR_N,
            period=_PERIOD,
            observations=tuple(o for o in obs.observations if o.casilla_id != _CASILLA_TOTAL),
        )
        assert obs != obs_missing

        repo.save(repo.prepare_observation_envelope(obs, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation != obs_missing
        assert loaded.observation == obs


def test_modelo_369_oss_calculation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end calculation enrollment: 369 cuota-total across two renta years.

    Drives the REAL 369 calculation engine for both ejercicios (real authority
    snapshot, real binding resolution, no mocks), records each through
    :meth:`EnrollmentRecorder.record_calculation_year` (evidence = produced-value
    count from a real engine run), and cross-checks the recorded distinct-year
    set against the authorization manifest via
    :func:`assert_enrollment_matches_manifest`. Manifest must declare
    renta_years = [2024, 2025] in the same commit.
    """
    recorder = EnrollmentRecorder(_MODELO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        result_n, produced_n = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        result_n1, produced_n1 = _calculate_369(
            filing_year=_YEAR_N_PLUS_1,
            period=_PERIOD,
            destination_cuotas=_YEAR_N_PLUS_1_CUOTAS,
        )
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Cross-renta wiring invariant: each year's engine total is the sum of that
    # year's destination leaves, and the two years are distinct.
    assert result_n.values[_CASILLA_TOTAL] == Decimal("4935.00")
    assert result_n1.values[_CASILLA_TOTAL] == Decimal("6615.00")
    assert result_n.values[_CASILLA_TOTAL] != result_n1.values[_CASILLA_TOTAL]

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
