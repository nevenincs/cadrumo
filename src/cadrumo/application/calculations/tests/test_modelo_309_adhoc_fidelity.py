"""E2E calculation continuity: Modelo 309 IVA no periódico cross-renta cuota.

Modelo 309 (IVA no periódico — Orden HAC/3625/2003) is an ad-hoc IVA
declaration for operators who trigger an IVA obligation outside the standard
periodic schedule: acquisitions of new means of transport from the EU,
operators under the régimen especial de la agricultura, operators who become
taxable on a recargo-de-equivalencia discharge, or ejecución forzosa
proceedings. The period code is ``"AD-HOC"``.

The casilla schema has two bound leaves and one computed total:
- ``iva.autorepercutido.intracomunitaria`` — cuota IVA autorepercutida en
  adquisiciones intracomunitarias (nuevos medios de transporte, etc.) (bound)
- ``iva.soportado.recargo-equivalencia`` — cuota IVA soportado por minoristas
  en recargo de equivalencia (devolución a viajeros) (bound)
- ``iva.cuota-no-periodica-total`` — total, **computed** by the registry
  formula ``modelo-309-iva-cuota-no-periodica-total`` = ``add`` of the two
  leaves above.

This module is the multi-year-renta authorization enrollment for Modelo 309.
The 309 backend carries a real calculation engine (the ``add`` formula above
plus the two ``ledger_iva_aggregation`` bindings), so the enrollment is
**calculation-mode**: it drives the REAL registry calculation engine
(``calculate_registry_snapshot`` over the real authority snapshot, real binding
resolution — no mocks) for two distinct renta years, asserting the engine
computes ``iva.cuota-no-periodica-total`` as the two-leaf sum, and records each
year through :meth:`EnrollmentRecorder.record_calculation_year` with the real
produced-value count as un-fakeable evidence.

Grounding (non-tautological): the two cuota leaves are supplied as the
ledger-aggregation binding facts (the autorepercutido and recargo-equivalencia
cuotas); the load-bearing assertion is the *wiring* invariant — the engine's
``iva.cuota-no-periodica-total`` equals the sum of the two supplied leaves,
which Orden HAC/3625/2003 apartado 1 defines as the total cuota of the ad-hoc
declaration. The total is produced by the real engine from the leaf inputs,
never hand-computed against the formula under test.

Legal grounding: Orden HAC/3625/2003 apartados 1 y 3 (form mandate); LIVA
arts. 84, 92 (autorepercusión, recargo de equivalencia); RD 1624/1992 art. 71
(régimen especial).
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
from ..multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ..observations_repository import CalculationObservationRepository
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "309"
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025
_PERIOD = "AD-HOC"
_CLOCK_N = datetime(2024, 4, 10, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2025, 3, 5, 10, 0, 0, tzinfo=UTC)

#: The computed total casilla and its two bound leaves.
_CASILLA_TOTAL: CasillaId = validated_casilla_id(
    "iva.cuota-no-periodica-total",
    surface="test_modelo_309_adhoc_fidelity:_CASILLA_TOTAL",
)
_CASILLA_AUTOREPERCUTIDO: CasillaId = validated_casilla_id(
    "iva.autorepercutido.intracomunitaria",
    surface="test_modelo_309_adhoc_fidelity:_CASILLA_AUTOREPERCUTIDO",
)
_CASILLA_RECARGO: CasillaId = validated_casilla_id(
    "iva.soportado.recargo-equivalencia",
    surface="test_modelo_309_adhoc_fidelity:_CASILLA_RECARGO",
)

#: The two ``ledger_iva_aggregation`` bindings whose facts feed the leaves.
_BINDING_AUTOREPERCUTIDO = "modelo-309-iva-autorepercutido-intracomunitaria-cuota"
_BINDING_RECARGO = "modelo-309-iva-soportado-recargo-equivalencia-cuota"


def _calculate_309(
    *,
    filing_year: int,
    period: str,
    leaf_cuotas: Mapping[str, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL registry 309 calculation; return result + produced-value count.

    ``leaf_cuotas`` is keyed by binding id. The bound leaves are resolved from
    those facts and the engine computes ``iva.cuota-no-periodica-total`` via the
    real ``add`` formula.
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=period)
    binding_values = dict(leaf_cuotas)
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


# Year-N: acquisition of a new intracomunitario transport vehicle.
# autorepercutido = 4200.00 (21% on a €20,000 vehicle), recargo = 0. The engine
# derives the total 4200 + 0 = 4200.00 — produced by the real ``add`` formula,
# never hand-computed against it.
_YEAR_N_CUOTAS = {
    _BINDING_AUTOREPERCUTIDO: Decimal("4200.00"),
    _BINDING_RECARGO: Decimal("0"),
}

# Year-N+1: a recargo-de-equivalencia discharge event with distinct cuotas so a
# cross-year bleed surfaces as strict inequality. 0 + 315 = 315.00.
_YEAR_N_PLUS_1_CUOTAS = {
    _BINDING_AUTOREPERCUTIDO: Decimal("0"),
    _BINDING_RECARGO: Decimal("315.00"),
}


def test_year_n_engine_computes_total_as_two_leaf_sum(tmp_path: Path) -> None:
    """Year-N 309: the engine computes the total as the sum of the two leaves.

    The total is produced by the real ``add`` formula from the two supplied
    leaf cuotas, never hand-computed against the formula under test.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, produced = _calculate_309(filing_year=_YEAR_N, period=_PERIOD, leaf_cuotas=_YEAR_N_CUOTAS)
    assert produced > 0
    expected_sum = _YEAR_N_CUOTAS[_BINDING_AUTOREPERCUTIDO] + _YEAR_N_CUOTAS[_BINDING_RECARGO]
    assert result.values[_CASILLA_TOTAL] == expected_sum
    assert result.values[_CASILLA_AUTOREPERCUTIDO] == _YEAR_N_CUOTAS[_BINDING_AUTOREPERCUTIDO]


def test_computed_total_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """The engine-produced 309 casilla values survive the encrypted-SQL roundtrip."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result, _ = _calculate_309(filing_year=_YEAR_N, period=_PERIOD, leaf_cuotas=_YEAR_N_CUOTAS)
        obs = _registry_observation(filing_year=_YEAR_N, period=_PERIOD, result=result)
        repo.save(repo.prepare_observation_envelope(obs, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation == obs
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_both_years_independently_retrievable_no_bleed(tmp_path: Path) -> None:
    """Both ejercicios are independently addressable; cuota values do not bleed."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result_n, _ = _calculate_309(filing_year=_YEAR_N, period=_PERIOD, leaf_cuotas=_YEAR_N_CUOTAS)
        result_n1, _ = _calculate_309(filing_year=_YEAR_N_PLUS_1, period=_PERIOD, leaf_cuotas=_YEAR_N_PLUS_1_CUOTAS)
        obs_n = _registry_observation(filing_year=_YEAR_N, period=_PERIOD, result=result_n)
        obs_n1 = _registry_observation(filing_year=_YEAR_N_PLUS_1, period=_PERIOD, result=result_n1)
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)

        assert loaded_n is not None and loaded_n1 is not None
        cuota_n = loaded_n.observation.casilla_values[_CASILLA_TOTAL]
        cuota_n1 = loaded_n1.observation.casilla_values[_CASILLA_TOTAL]
        assert cuota_n == Decimal("4200.00")
        assert cuota_n1 == Decimal("315.00")
        assert cuota_n != cuota_n1, "iva.cuota-no-periodica-total bled between exercises"
        assert loaded_n.captured_at != loaded_n1.captured_at


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        result, _ = _calculate_309(filing_year=_YEAR_N, period=_PERIOD, leaf_cuotas=_YEAR_N_CUOTAS)
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


def test_modelo_309_adhoc_calculation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end calculation enrollment: 309 cuota total across two renta years.

    Drives the REAL 309 calculation engine for both ejercicios (real authority
    snapshot, real binding resolution, no mocks), records each through
    :meth:`EnrollmentRecorder.record_calculation_year` (evidence = produced-value
    count from a real engine run), and cross-checks the recorded distinct-year
    set against the authorization manifest via
    :func:`assert_enrollment_matches_manifest`. Manifest must declare
    renta_years = [2024, 2025] in the same commit.
    """
    recorder = EnrollmentRecorder(_MODELO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        result_n, produced_n = _calculate_309(filing_year=_YEAR_N, period=_PERIOD, leaf_cuotas=_YEAR_N_CUOTAS)
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        result_n1, produced_n1 = _calculate_309(
            filing_year=_YEAR_N_PLUS_1,
            period=_PERIOD,
            leaf_cuotas=_YEAR_N_PLUS_1_CUOTAS,
        )
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Cross-renta wiring invariant: each year's engine total is the sum of that
    # year's leaves, and the two years are distinct.
    assert result_n.values[_CASILLA_TOTAL] == Decimal("4200.00")
    assert result_n1.values[_CASILLA_TOTAL] == Decimal("315.00")
    assert result_n.values[_CASILLA_TOTAL] != result_n1.values[_CASILLA_TOTAL]

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
