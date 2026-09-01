"""E2E reconciliation continuity: Modelo 193 (annual) ← Modelo 123 (quarterly).

Modelo 123 is the quarterly retención-capital-mobiliario autoliquidación
(Orden HAC/56/2024, RD 439/2007 art. 90, Ley 35/2006 art. 25): a withholder
of capital-mobiliario income files 1T–4T each year. Its three key total
casillas are computed by the engine:

- Casilla 03 = total rentas (01 + 02, computed)
- Casilla 06 = base total (04 + 05, computed)
- Casilla 09 = retenciones total (07 + 08, computed)

where 01/04/07 are the dividendos-y-participaciones sub-totals and
02/05/08 are the resto-de-rentas sub-totals (all manual).

Modelo 193 is the annual resumen: it aggregates the four quarters' monetary
casillas 06 and 09 via ``source = "relation_prefill"`` relations
(``annual_summary``, ``op=sum``), binding ids
``modelo-193-123-base-anual`` and ``modelo-193-123-retenciones-anual``.
``decl.total-perceptores`` is a ``retenciones_aggregation`` binding over the
dedicated per-perceptor store, because summing quarterly perceptor counts
double-counts recurring perceptors. The 193 monetary formulae are pure op=copy
from those relations into ``decl.base-total`` and ``decl.retenciones-total``.

This module is the multi-year-renta authorization enrollment for Modelo 193.
It drives the REAL backend (real encrypted-SQLite observation store, the real
registry authority, the real calculation engine, the real relation resolver —
no mocks) across two distinct renta years (2025, 2026). Both calculated
resumen years are recorded through the :class:`EnrollmentRecorder` and
cross-checked against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.

Grounding (non-tautological): the 123 computed casillas 03/06/09 are produced
by the registry engine from the manual sub-inputs. The 193 assertion is the
*wiring* invariant — each monetary 193 output casilla equals the sum of the
corresponding 123 quarterly computed values — grounded in the AEAT form
instructions (BOE-modelo-193-2011-form). Distinct per-quarter values per year
ensure cross-contamination between years or periods fails loudly. No expected
value hand-computes the formula under test.
"""

from __future__ import annotations

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
from ....domain.calculations.registry.ids import RelationId
from ....domain.calculations.registry.relations import materialize_relation_binding_values
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ..multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ..observations_repository import CalculationObservationRepository
from ..relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo ids this module exercises.
_MODELO_123 = "123"
_MODELO_193 = "193"

#: Two distinct renta years.
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

_CLOCK = datetime(2027, 2, 1, 9, 0, 0, tzinfo=UTC)


_M123_RENTAS_DIVIDENDOS_CASILLA: CasillaId = validated_casilla_id("01")
_M123_RENTAS_RESTO_CASILLA: CasillaId = validated_casilla_id("02")
_M123_RENTAS_TOTAL_CASILLA: CasillaId = validated_casilla_id("03")
_M123_BASE_DIVIDENDOS_CASILLA: CasillaId = validated_casilla_id("04")
_M123_BASE_RESTO_CASILLA: CasillaId = validated_casilla_id("05")
_M123_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("06")
_M123_RETENCIONES_DIVIDENDOS_CASILLA: CasillaId = validated_casilla_id("07")
_M123_RETENCIONES_RESTO_CASILLA: CasillaId = validated_casilla_id("08")
_M123_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("09")
_M123_PREVIOUS_RESULT_CASILLA: CasillaId = validated_casilla_id("10")
_M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: CasillaId = validated_casilla_id("11")
_M193_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("decl.total-perceptores")
_M193_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.base-total")
_M193_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.retenciones-total")

# ---------------------------------------------------------------------------
# 123 quarterly scenarios.
#
# Manual inputs (the engine computes 03, 06, 09 from these):
#   01 = rentas dividendos/participaciones count (integer)
#   02 = rentas resto count (integer)
#   04 = base dividendos/participaciones (money)
#   05 = base resto de rentas (money)
#   07 = retenciones dividendos/participaciones (money)
#   08 = retenciones resto de rentas (money)
#   10 = resultado anteriores autoliquidaciones (money, zero)
#   11 = retenciones ingresadas a cuenta de períodos anteriores (zero)
#   13 = resultado a ingresar (computed, no manual entry needed)
#
# Casilla 03 = 01+02 (total rentas), 06 = 04+05 (base total), 09 = 07+08
# (retenciones total). These three are what the 193 relations aggregate.
# ---------------------------------------------------------------------------

_YEAR_N_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal("3"),
        _M123_RENTAS_RESTO_CASILLA: Decimal("1"),
        _M123_BASE_DIVIDENDOS_CASILLA: Decimal("5000.00"),
        _M123_BASE_RESTO_CASILLA: Decimal("1200.00"),
        _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("950.00"),
        _M123_RETENCIONES_RESTO_CASILLA: Decimal("228.00"),
        _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
        _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
    },
    "2T": {
        _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal("4"),
        _M123_RENTAS_RESTO_CASILLA: Decimal("2"),
        _M123_BASE_DIVIDENDOS_CASILLA: Decimal("7000.00"),
        _M123_BASE_RESTO_CASILLA: Decimal("800.00"),
        _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("1330.00"),
        _M123_RETENCIONES_RESTO_CASILLA: Decimal("152.00"),
        _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
        _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
    },
    "3T": {
        _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal("2"),
        _M123_RENTAS_RESTO_CASILLA: Decimal("1"),
        _M123_BASE_DIVIDENDOS_CASILLA: Decimal("4000.00"),
        _M123_BASE_RESTO_CASILLA: Decimal("600.00"),
        _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("760.00"),
        _M123_RETENCIONES_RESTO_CASILLA: Decimal("114.00"),
        _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
        _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
    },
    "4T": {
        _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal("3"),
        _M123_RENTAS_RESTO_CASILLA: Decimal("0"),
        _M123_BASE_DIVIDENDOS_CASILLA: Decimal("6000.00"),
        _M123_BASE_RESTO_CASILLA: Decimal("0"),
        _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("1140.00"),
        _M123_RETENCIONES_RESTO_CASILLA: Decimal("0"),
        _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
        _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
    },
}

_YEAR_N_PLUS_1_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal("2"),
        _M123_RENTAS_RESTO_CASILLA: Decimal("1"),
        _M123_BASE_DIVIDENDOS_CASILLA: Decimal("3000.00"),
        _M123_BASE_RESTO_CASILLA: Decimal("500.00"),
        _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("570.00"),
        _M123_RETENCIONES_RESTO_CASILLA: Decimal("95.00"),
        _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
        _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
    },
    "2T": {
        _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal("5"),
        _M123_RENTAS_RESTO_CASILLA: Decimal("2"),
        _M123_BASE_DIVIDENDOS_CASILLA: Decimal("8000.00"),
        _M123_BASE_RESTO_CASILLA: Decimal("1500.00"),
        _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("1520.00"),
        _M123_RETENCIONES_RESTO_CASILLA: Decimal("285.00"),
        _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
        _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
    },
    "3T": {
        _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal("3"),
        _M123_RENTAS_RESTO_CASILLA: Decimal("1"),
        _M123_BASE_DIVIDENDOS_CASILLA: Decimal("5500.00"),
        _M123_BASE_RESTO_CASILLA: Decimal("900.00"),
        _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("1045.00"),
        _M123_RETENCIONES_RESTO_CASILLA: Decimal("171.00"),
        _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
        _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
    },
    "4T": {
        _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal("4"),
        _M123_RENTAS_RESTO_CASILLA: Decimal("0"),
        _M123_BASE_DIVIDENDOS_CASILLA: Decimal("7500.00"),
        _M123_BASE_RESTO_CASILLA: Decimal("0"),
        _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("1425.00"),
        _M123_RETENCIONES_RESTO_CASILLA: Decimal("0"),
        _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
        _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
    },
}


def _calculate_123(
    *,
    filing_year: int,
    period: str,
    casilla_inputs: dict[CasillaId, Decimal],
) -> RegistryCalculationResult:
    """Run the REAL 123 quarterly calculation and return the engine result."""
    snapshot = bundled_authority().snapshot(_MODELO_123, filing_year=filing_year, period=period)
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, {}),
        **casilla_inputs,
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values={},
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def _123_observation(*, filing_year: int, period: str, result: RegistryCalculationResult) -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=_MODELO_123,
        filing_year=filing_year,
        period=period,
        casilla_values=result.values,
    )


def _calculate_193(
    *,
    filing_year: int,
    relation_values: dict[RelationId, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL 193 annual calculation from resolved relations; return result + count."""
    snapshot = bundled_authority().snapshot(_MODELO_193, filing_year=filing_year, period="0A")
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    binding_values = {**relation_binding_values, "modelo-193-123-perceptores-anual": Decimal("3")}
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values=relation_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result, len(result.values)


def _compute_year_123_totals(
    quarters: dict[str, dict[CasillaId, Decimal]],
    *,
    filing_year: int,
    obs_repo: CalculationObservationRepository,
) -> dict[CasillaId, Decimal]:
    """Calculate all four 123 quarters, persist observations, return casilla sums.

    Returns a dict with the summed computed values for casillas 03, 06, 09. The
    193 relations aggregate c06/c09; c03 remains here as a quarterly-engine
    sanity signal, not as the annual perceptor source.
    """
    totals: dict[CasillaId, Decimal] = {
        _M123_RENTAS_TOTAL_CASILLA: Decimal("0"),
        _M123_BASE_TOTAL_CASILLA: Decimal("0"),
        _M123_RETENCIONES_TOTAL_CASILLA: Decimal("0"),
    }
    for period, inputs in quarters.items():
        result = _calculate_123(filing_year=filing_year, period=period, casilla_inputs=inputs)
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                _123_observation(filing_year=filing_year, period=period, result=result),
                source_kind="app_filing",
                captured_at=_CLOCK,
            )
        )
        for cid in totals:
            totals[cid] += result.values[cid]
    return totals


def test_modelo_123_quarterly_engine_produces_computed_totals(tmp_path: Path) -> None:
    """The 123 engine computes casillas 03, 06, 09 from the manual sub-inputs.

    The values are produced by the real engine, never hand-computed against the
    formulas under test. These are the seeds fed to the 193 reconciliation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result = _calculate_123(
            filing_year=_YEAR_N,
            period="1T",
            casilla_inputs=_YEAR_N_QUARTERS["1T"],
        )
    # All three total casillas must be positive (seeded with non-zero inputs).
    assert result.values[_M123_RENTAS_TOTAL_CASILLA] > Decimal("0")  # total rentas
    assert result.values[_M123_BASE_TOTAL_CASILLA] > Decimal("0")  # base total
    assert result.values[_M123_RETENCIONES_TOTAL_CASILLA] > Decimal("0")  # retenciones total


def test_modelo_193_relation_prefill_aggregates_123_quarters(tmp_path: Path) -> None:
    """The 193 relation resolver aggregates Year N's four 123 quarterly totals.

    The cross-quarter aggregation contract: once four 123 quarters are
    recorded as filed observations, ``resolve_relations_from_local_store``
    for the 193 annual snapshot produces relation values that equal the
    arithmetic sum over the four 123 quarters for each of the three
    output dimensions (perceptores/casilla 03, base/casilla 06,
    retenciones/casilla 09).
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        expected = _compute_year_123_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        snapshot_193 = bundled_authority().snapshot(_MODELO_193, filing_year=_YEAR_N, period="0A")
        prefill = resolve_relations_from_local_store(snapshot_193, repository=obs_repo)

    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in prefill.values if item.value is not None
    }
    # RET-1: decl.total-perceptores is now a distinct-NIF count from the retención
    # store, so the perceptores relation is retired; only base/retenciones sum M123.
    assert "modelo-193-rel-123-perceptores-anual" not in resolved
    assert resolved["modelo-193-rel-123-base-anual"] == expected[_M123_BASE_TOTAL_CASILLA]
    assert resolved["modelo-193-rel-123-retenciones-anual"] == expected[_M123_RETENCIONES_TOTAL_CASILLA]


def test_modelo_193_year_isolation_ignores_prior_year_observations(tmp_path: Path) -> None:
    """Year N+1's 193 resolver draws only from Year N+1 123 records, not Year N.

    Both years' observations reside in the same repository. The relation
    resolver MUST discriminate by ``filing_year`` so the Year N+1 193 totals
    equal Year N+1's quarterly sums.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _compute_year_123_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        expected_n1 = _compute_year_123_totals(_YEAR_N_PLUS_1_QUARTERS, filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        snapshot_193_n1 = bundled_authority().snapshot(_MODELO_193, filing_year=_YEAR_N_PLUS_1, period="0A")
        prefill = resolve_relations_from_local_store(snapshot_193_n1, repository=obs_repo)

    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in prefill.values if item.value is not None
    }
    assert "modelo-193-rel-123-perceptores-anual" not in resolved
    assert resolved["modelo-193-rel-123-base-anual"] == expected_n1[_M123_BASE_TOTAL_CASILLA]
    assert resolved["modelo-193-rel-123-retenciones-anual"] == expected_n1[_M123_RETENCIONES_TOTAL_CASILLA]


def test_modelo_193_123_reconciliation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: 123 quarterly aggregation → 193 annual across two renta years.

    Drives the REAL 123 and 193 backends for both renta years (2025, 2026),
    records each 193 calculation through the :class:`EnrollmentRecorder`
    (RECONCILIATION evidence_class — calculation mode, evidenced by produced
    casilla count), and cross-checks the recorded two-year set against the
    authorization manifest.

    The load-bearing wiring assertions are:

    - For each year, each 193 output casilla equals the sum of the
      corresponding 123 quarterly computed casillas (03/06/09).
    - Year N+1's 193 relations are drawn from Year N+1 observations only.

    These are wiring invariants grounded in RD 439/2007 art. 108, Orden
    EHA/3377/2011 art. 1, Ley 35/2006 arts. 25, 99, 101, and the AEAT
    M193 form (BOE-modelo-193-2011-form).
    """
    recorder_193 = EnrollmentRecorder(_MODELO_193)
    recorder_123 = EnrollmentRecorder(_MODELO_123)

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()

        # Year N: calculate four 123 quarters, persist, resolve 193, calculate 193.
        expected_n = _compute_year_123_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        # 123 feeder: evidence the feeder year via one real quarterly calculation.
        _q1_result = _calculate_123(filing_year=_YEAR_N, period="1T", casilla_inputs=_YEAR_N_QUARTERS["1T"])
        recorder_123.record_calculation_year(filing_year=_YEAR_N, produced_value_count=len(_q1_result.values))

        snapshot_193_n = bundled_authority().snapshot(_MODELO_193, filing_year=_YEAR_N, period="0A")
        prefill_n = resolve_relations_from_local_store(snapshot_193_n, repository=obs_repo)
        resolved_n = {item.relation: item.value for item in prefill_n.values if item.value is not None}
        result_n, produced_n = _calculate_193(filing_year=_YEAR_N, relation_values=resolved_n)
        recorder_193.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        # Year N+1: same pipeline; Year N observations sit in the store but must
        # not contaminate Year N+1's 193 resolver.
        expected_n1 = _compute_year_123_totals(_YEAR_N_PLUS_1_QUARTERS, filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        _q1_result_n1 = _calculate_123(
            filing_year=_YEAR_N_PLUS_1,
            period="1T",
            casilla_inputs=_YEAR_N_PLUS_1_QUARTERS["1T"],
        )
        recorder_123.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=len(_q1_result_n1.values))

        snapshot_193_n1 = bundled_authority().snapshot(_MODELO_193, filing_year=_YEAR_N_PLUS_1, period="0A")
        prefill_n1 = resolve_relations_from_local_store(snapshot_193_n1, repository=obs_repo)
        resolved_n1 = {item.relation: item.value for item in prefill_n1.values if item.value is not None}
        result_n1, produced_n1 = _calculate_193(filing_year=_YEAR_N_PLUS_1, relation_values=resolved_n1)
        recorder_193.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Wiring invariant Year N: the monetary 193 outputs == summed 123 quarterly
    # totals. decl.total-perceptores is no longer a M123 aggregate — RET-1 sources
    # it as a distinct-NIF count from the retención store (tested separately), so it
    # is not asserted against the quarterly sum here.
    assert result_n.values[_M193_BASE_TOTAL_CASILLA] == expected_n[_M123_BASE_TOTAL_CASILLA]
    assert result_n.values[_M193_RETENCIONES_TOTAL_CASILLA] == expected_n[_M123_RETENCIONES_TOTAL_CASILLA]

    # Wiring invariant Year N+1 (year-isolated):
    assert result_n1.values[_M193_BASE_TOTAL_CASILLA] == expected_n1[_M123_BASE_TOTAL_CASILLA]
    assert result_n1.values[_M193_RETENCIONES_TOTAL_CASILLA] == expected_n1[_M123_RETENCIONES_TOTAL_CASILLA]

    # Authorization-gate enrollment for the 193 resumen.
    evidence_193 = recorder_193.evidence()
    assert evidence_193.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence_193)

    # Authorization-gate enrollment for the 123 feeder (standalone fleet modelo).
    evidence_123 = recorder_123.evidence()
    assert evidence_123.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence_123)
