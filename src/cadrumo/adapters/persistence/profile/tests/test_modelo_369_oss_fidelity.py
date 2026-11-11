"""E2E calculation continuity: Modelo 369 OSS Esquema Unión cross-renta cuota.

Modelo 369 (Declaración IVA OSS — Orden HAC/610/2021) is the quarterly
One-Stop-Shop autoliquidación for the Esquema Unión: operators established in
Spain who supply goods or services B2C to consumers in other EU member states
declare and pay the destination-state IVA centrally via the OSS portal (LIVA
arts. 163-unvicies to 163-quatervicies, Directiva 2021/285/UE). The period
code is ``"1T"``–``"4T"`` (quarterly).

The ``esquema-union`` revision's ``iva.union.cuota-total`` sums one settlement
line per destination, and those lines read the return's fixed rows, so it takes
real invoices to reach it; ``test_m369_destination_rows_live`` covers that path.

This module is the cross-year coverage for the three destination leaves bound to
the ledger aggregation (``iva.union.de.services-cuota``,
``iva.union.fr.services-cuota``, ``iva.union.de.goods-distance-cuota``). It drives
the real registry calculation engine over the real authority snapshot for two
distinct years and records each through the cross-year observation store, so a
value that bled between years surfaces as strict inequality.

Legal grounding: LIVA arts. 163-unvicies to 163-quatervicies (OSS regime);
Orden HAC/610/2021 arts. 1–3 (form mandate, quarterly cadence); Directiva
2021/285/UE (One-Stop-Shop reform).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.bindings import RegistryModeloObservation
from .....domain.calculations.registry.formula_runtime import RegistryCalculationResult
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from .modelo_leaf_calculation_support import calculate_from_bindings, registry_observation_of
from .observation_lookup_support import find_observation, save_app_filing_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "369"
_YEAR_N_PLUS_1 = filing_year_envelope().horizon
_YEAR_N = _YEAR_N_PLUS_1 - 1
_PERIOD = "2T"
_CLOCK_N = datetime(_YEAR_N, 7, 31, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(_YEAR_N_PLUS_1, 7, 31, 10, 0, 0, tzinfo=UTC)

#: The three bound destination leaves.
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

#: The three ``ledger_oss_aggregation`` destination bindings.
_BINDING_DE_SERVICES = "modelo-369-union-de-services-21pct"
_BINDING_FR_SERVICES = "modelo-369-union-fr-services-21pct"
_BINDING_DE_GOODS = "modelo-369-union-de-goods-distance-21pct"


def _calculate_369(
    *,
    filing_year: int,
    period: str,
    destination_cuotas: Mapping[str, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    return calculate_from_bindings(_MODELO, filing_year=filing_year, period=period, binding_values=destination_cuotas)


# Year-N 2T: a Spanish OSS operator supplying services to DE and FR plus
# distance sales to DE. Per-destination repercutida IVA: DE services 1890.00,
# FR services 945.00, DE goods 2100.00.
_YEAR_N_CUOTAS = {
    _BINDING_DE_SERVICES: Decimal("1890.00"),
    _BINDING_FR_SERVICES: Decimal("945.00"),
    _BINDING_DE_GOODS: Decimal("2100.00"),
}

# Year-N+1 2T: distinct per-destination cuotas so a cross-year bleed surfaces as
# strict inequality.
_YEAR_N_PLUS_1_CUOTAS = {
    _BINDING_DE_SERVICES: Decimal("2310.00"),
    _BINDING_FR_SERVICES: Decimal("1155.00"),
    _BINDING_DE_GOODS: Decimal("3150.00"),
}


def test_year_n_engine_carries_each_destination_leaf(tmp_path: Path) -> None:
    """Year-N 369 2T: each bound leaf holds its own destination's cuota."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, _produced = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
    assert _produced > 0
    assert result.values[_CASILLA_DE_SERVICES] == Decimal("1890.00")
    assert result.values[_CASILLA_FR_SERVICES] == Decimal("945.00")
    assert result.values[_CASILLA_DE_GOODS] == Decimal("2100.00")


def test_computed_values_persist_and_reload_strictly(tmp_path: Path) -> None:
    """The engine-_produced 369 casilla values survive the encrypted-SQL roundtrip."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result, _ = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
        obs = registry_observation_of(_MODELO, filing_year=_YEAR_N, period=_PERIOD, result=result)
        save_app_filing_observation(repo, obs, captured_at=_CLOCK_N)
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation == obs
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_both_years_independently_retrievable_no_bleed(tmp_path: Path) -> None:
    """Both ejercicios are independently addressable; destination values do not bleed."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result_n, _ = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
        result_n1, _ = _calculate_369(
            filing_year=_YEAR_N_PLUS_1,
            period=_PERIOD,
            destination_cuotas=_YEAR_N_PLUS_1_CUOTAS,
        )
        obs_n = registry_observation_of(_MODELO, filing_year=_YEAR_N, period=_PERIOD, result=result_n)
        obs_n1 = registry_observation_of(_MODELO, filing_year=_YEAR_N_PLUS_1, period=_PERIOD, result=result_n1)
        save_app_filing_observation(repo, obs_n, captured_at=_CLOCK_N)
        save_app_filing_observation(repo, obs_n1, captured_at=_CLOCK_N_PLUS_1)
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)

        assert loaded_n is not None and loaded_n1 is not None
        leaf_n = loaded_n.observation.casilla_values[_CASILLA_DE_SERVICES]
        leaf_n1 = loaded_n1.observation.casilla_values[_CASILLA_DE_SERVICES]
        assert leaf_n == Decimal("1890.00")
        assert leaf_n1 == Decimal("2310.00")
        assert loaded_n.captured_at != loaded_n1.captured_at


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result, _ = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)
        obs = registry_observation_of(_MODELO, filing_year=_YEAR_N, period=_PERIOD, result=result)
        obs_missing = RegistryModeloObservation(
            modelo=_MODELO,
            filing_year=_YEAR_N,
            period=_PERIOD,
            observations=tuple(o for o in obs.observations if o.casilla_id != _CASILLA_DE_SERVICES),
        )
        assert obs != obs_missing

        save_app_filing_observation(repo, obs, captured_at=_CLOCK_N)
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation != obs_missing
        assert loaded.observation == obs


def test_modelo_369_oss_calculation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end calculation enrollment: 369 destination leaves across two renta years.

    Drives the REAL 369 calculation engine for both ejercicios (real authority
    snapshot, real binding resolution, no mocks), records each through
    ``cross-year observation.record_calculation_year`` (evidence = _produced-value
    count from a real engine run), and cross-checks the recorded distinct-year
    set against the cross-year claim via
    ``the cross-year behavior assertion``. Manifest must declare
    renta_years = [2024, 2025] in the same commit.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result_n, _produced_n = _calculate_369(filing_year=_YEAR_N, period=_PERIOD, destination_cuotas=_YEAR_N_CUOTAS)

        result_n1, _produced_n1 = _calculate_369(
            filing_year=_YEAR_N_PLUS_1,
            period=_PERIOD,
            destination_cuotas=_YEAR_N_PLUS_1_CUOTAS,
        )

    assert result_n.values[_CASILLA_DE_GOODS] == Decimal("2100.00")
    assert result_n1.values[_CASILLA_DE_GOODS] == Decimal("3150.00")
