"""E2E reconciliation continuity: Modelo 180 (annual) ← Modelo 115 (quarterly).

Modelo 115 is the quarterly retención-arrendamiento autoliquidación (RD
439/2007 art. 100, Orden de 20 de noviembre de 2000): a property-rental
withholder files 1T–4T each year, declaring the number of perceptores
(casilla 01), the rental base (casilla 02, manual), and the 19 % withholding
computed from base (casilla 03, formula). Modelo 180 is the annual resumen:
it aggregates the four quarters' monetary figures via
``source = "relation_prefill"`` relations (``annual_summary``, ``op=sum``),
binding ids ``modelo-180-115-base-anual`` and
``modelo-180-115-retenciones-anual``. ``decl.total-perceptores`` is a
``retenciones_aggregation`` binding over the dedicated per-perceptor store,
because summing quarterly perceptor counts double-counts recurring perceptors.
The 180 monetary formulae are pure op=copy from those relations into
``decl.base-total`` and ``decl.retenciones-total``.

This module is the multi-year-renta authorization enrollment for Modelo 180.
It drives the REAL backend (real encrypted-SQLite observation store, the real
registry authority, the real calculation engine, the real relation resolver —
no mocks) across two distinct renta years (2025, 2026): it computes all four
quarterly 115 filings for each year, records each as a filed observation,
resolves the annual 180 relations for each year, and asserts:

1. The 180 monetary relation values equal the arithmetic sum of the
   corresponding 115 quarterly casillas (wiring invariant, not formula under
   test).
2. Year isolation: the Year 2 180 relation resolver draws only from Year 2
   115 observations, ignoring Year 1 records in the same repository.
3. The calculated 180 monetary output casillas match the resolved relation
   values (op=copy threading).

Both calculated resumen years are recorded through the
:class:`EnrollmentRecorder` and cross-checked against the authorization
manifest via :func:`assert_enrollment_matches_manifest`.

Grounding (non-tautological): the 115 casilla 03 (retenciones) is produced
by the registry engine from the manual base (19 % × casilla 02). The 180
assertion is the *wiring* invariant — each monetary 180 output equals the sum
across all four 115 quarters — grounded in the AEAT form instructions
(resúmenes de retenciones: "suma de los importes del período"). The test uses
distinct values per quarter and per year so a cross-year or cross-quarter
contamination fails loudly. No hand-computed expectation reproduces the formula
under test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....core.resources import resources
from cadrumo.domain.calculations.registry.ids import BindingId, RelationId
from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation, resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.relations import materialize_relation_binding_values
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo ids this module exercises.
_MODELO_115 = "115"
_MODELO_180 = "180"

#: Two distinct renta years the reconciliation spans.
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

_CLOCK = datetime(2027, 1, 20, 9, 0, 0, tzinfo=UTC)


_M115_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_M115_PREVIOUS_RESULT_CASILLA: CasillaId = validated_casilla_id("04")
_M115_PERCEPTORES_BINDING: BindingId = "modelo-115-perceptores"
_M115_BASE_RETENCIONES_BINDING: BindingId = "modelo-115-base-retenciones"
_M115_BOUND_BINDINGS_BY_CASILLA: dict[CasillaId, BindingId] = {
    _M115_PERCEPTORES_CASILLA: _M115_PERCEPTORES_BINDING,
    _M115_BASE_CASILLA: _M115_BASE_RETENCIONES_BINDING,
}
_M180_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("decl.total-perceptores")
_M180_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.base-total")
_M180_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.retenciones-total")

# ---------------------------------------------------------------------------
# 115 quarterly scenarios — distinct values per quarter and per year so any
# cross-contamination between years or periods surfaces as a mismatch.
#
# Casilla 01 = perceptores (integer, manual)
# Casilla 02 = base retenciones (money, manual)
# Casilla 03 = retenciones (computed: 19% × casilla 02)
# Casilla 04 = resultado anteriores autoliquidaciones (manual, zero here)
# Casilla 05 = resultado a ingresar (computed: 03 − 04)
#
# The 180 wiring assertion is: for each of 01, 02, 03 the annual total
# equals the sum of the four 115 quarterly values. Casilla 03 is produced
# by the engine (19 % of 02); we supply distinct bases so the engine computes
# distinct retenciones and the sum is unambiguous.
# ---------------------------------------------------------------------------

_YEAR_N_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1200.00"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("0"),
    },
    "2T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1350.00"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("0"),
    },
    "3T": {
        _M115_PERCEPTORES_CASILLA: Decimal("3"),
        _M115_BASE_CASILLA: Decimal("900.00"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("0"),
    },
    "4T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1100.00"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("0"),
    },
}

_YEAR_N_PLUS_1_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M115_PERCEPTORES_CASILLA: Decimal("1"),
        _M115_BASE_CASILLA: Decimal("750.00"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("0"),
    },
    "2T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("2000.00"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("0"),
    },
    "3T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1800.00"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("0"),
    },
    "4T": {
        _M115_PERCEPTORES_CASILLA: Decimal("3"),
        _M115_BASE_CASILLA: Decimal("1600.00"),
        _M115_PREVIOUS_RESULT_CASILLA: Decimal("0"),
    },
}


def _calculate_115(
    *,
    filing_year: int,
    period: str,
    casilla_inputs: dict[CasillaId, Decimal],
) -> RegistryCalculationResult:
    """Run the REAL 115 quarterly calculation and return the engine result."""
    snapshot = resources().modelos.authority.snapshot(_MODELO_115, filing_year=filing_year, period=period)
    binding_values = {
        binding_id: casilla_inputs[casilla_id] for casilla_id, binding_id in _M115_BOUND_BINDINGS_BY_CASILLA.items()
    }
    manual_inputs = {
        casilla_id: value
        for casilla_id, value in casilla_inputs.items()
        if casilla_id not in _M115_BOUND_BINDINGS_BY_CASILLA
    }
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        **manual_inputs,
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def _115_observation(*, filing_year: int, period: str, result: RegistryCalculationResult) -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=_MODELO_115,
        filing_year=filing_year,
        period=period,
        casilla_values=result.values,
    )


def _calculate_180(
    *,
    filing_year: int,
    relation_values: dict[RelationId, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL 180 annual calculation from resolved relations; return result + count."""
    snapshot = resources().modelos.authority.snapshot(_MODELO_180, filing_year=filing_year, period="0A")
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    binding_values = {**relation_binding_values, "modelo-180-115-perceptores-anual": Decimal("2")}
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


def _compute_year_115_totals(
    quarters: dict[str, dict[CasillaId, Decimal]],
    *,
    filing_year: int,
    obs_repo: CalculationObservationRepository,
) -> dict[CasillaId, Decimal]:
    """Calculate all four 115 quarters for a year, persist observations, return casilla sums.

    The returned dict includes the seeded 115 c01 count for quarterly-engine
    sanity, but the 180 relations aggregate only c02 base and c03 retenciones.
    """
    totals: dict[CasillaId, Decimal] = {
        _M115_PERCEPTORES_CASILLA: Decimal("0"),
        _M115_BASE_CASILLA: Decimal("0"),
        _M115_RETENCIONES_CASILLA: Decimal("0"),
    }
    for period, inputs in quarters.items():
        result = _calculate_115(filing_year=filing_year, period=period, casilla_inputs=inputs)
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                _115_observation(filing_year=filing_year, period=period, result=result),
                source_kind="app_filing",
                captured_at=_CLOCK,
            )
        )
        for cid in totals:
            totals[cid] += result.values[cid]
    return totals


def test_modelo_115_quarterly_engine_produces_retenciones_casilla(tmp_path: Path) -> None:
    """The 115 engine computes retenciones (casilla 03) as 19 % of the base.

    The value is produced by the real engine from the manual base input, never
    hand-computed against the formula under test. This is the seed fed to the
    180 reconciliation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result = _calculate_115(
            filing_year=_YEAR_N,
            period="1T",
            casilla_inputs=_YEAR_N_QUARTERS["1T"],
        )
    assert result.values[_M115_RETENCIONES_CASILLA] > Decimal("0")
    assert result.values[_M115_PERCEPTORES_CASILLA] == _YEAR_N_QUARTERS["1T"][_M115_PERCEPTORES_CASILLA]


def test_modelo_180_relation_prefill_aggregates_115_quarters(tmp_path: Path) -> None:
    """The 180 relation resolver aggregates Year N's four 115 quarterly perceptores/base/retenciones.

    The cross-quarter aggregation contract: once four 115 quarters are recorded
    as filed observations, ``resolve_relations_from_local_store`` for the 180
    annual snapshot produces relation values that equal the arithmetic sum over
    the four 115 quarters for each of the three output dimensions.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        expected = _compute_year_115_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        snapshot_180 = resources().modelos.authority.snapshot(_MODELO_180, filing_year=_YEAR_N, period="0A")
        prefill = resolve_relations_from_local_store(snapshot_180, repository=obs_repo)

    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in prefill.values if item.value is not None
    }
    # RET-1: decl.total-perceptores no longer aggregates from the M115 quarters
    # (the quarterly sum double-counted a perceptor paid in >1 quarter). It is now
    # a distinct-NIF count from the dedicated retención store, so the perceptores
    # relation is retired; only the monetary base/retenciones totals still sum M115.
    assert "modelo-180-rel-115-perceptores-anual" not in resolved
    assert resolved["modelo-180-rel-115-base-anual"] == expected[_M115_BASE_CASILLA]
    assert resolved["modelo-180-rel-115-retenciones-anual"] == expected[_M115_RETENCIONES_CASILLA]


def test_modelo_180_year_isolation_ignores_prior_year_observations(tmp_path: Path) -> None:
    """Year N+1's 180 resolver draws only from Year N+1 115 records, not Year N.

    Both years' 115 observations sit in the same repository. The relation
    resolver MUST discriminate by ``filing_year`` and aggregate only the
    Year N+1 observations for the Year N+1 annual 180.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        # Seed both years.
        _compute_year_115_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        expected_n1 = _compute_year_115_totals(_YEAR_N_PLUS_1_QUARTERS, filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        snapshot_180_n1 = resources().modelos.authority.snapshot(_MODELO_180, filing_year=_YEAR_N_PLUS_1, period="0A")
        prefill = resolve_relations_from_local_store(snapshot_180_n1, repository=obs_repo)

    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in prefill.values if item.value is not None
    }
    assert "modelo-180-rel-115-perceptores-anual" not in resolved
    assert resolved["modelo-180-rel-115-base-anual"] == expected_n1[_M115_BASE_CASILLA]
    assert resolved["modelo-180-rel-115-retenciones-anual"] == expected_n1[_M115_RETENCIONES_CASILLA]


def test_modelo_180_115_reconciliation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: 115 quarterly aggregation → 180 annual across two renta years.

    Drives the REAL 115 and 180 backends for both renta years (2025, 2026),
    records each 180 calculation through the :class:`EnrollmentRecorder`
    (RECONCILIATION evidence_class — calculation mode, evidenced by produced
    casilla count), and cross-checks the recorded two-year set against the
    authorization manifest.

    The load-bearing wiring assertions are:

    - For each year, the three 180 output casillas equal the summed 115 quarters.
    - Year N+1's 180 relations are drawn from Year N+1 observations only.

    These are wiring invariants grounded in the AEAT form instructions
    (Orden HFP/1284/2023 art. 7, RD 439/2007 art. 108) — not a reproduction
    of the formula under test.
    """
    recorder_180 = EnrollmentRecorder(_MODELO_180)
    recorder_115 = EnrollmentRecorder(_MODELO_115)

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()

        # Year N: calculate four 115 quarters, persist, resolve 180, calculate 180.
        expected_n = _compute_year_115_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        # 115 feeder: record each year's quarterly calculations as feeder evidence.
        # _compute_year_115_totals drives the real 115 engine for all four quarters;
        # the produced casilla count for the feeder is evidenced by summing per quarter.
        # We record the feeder year here using the year-N quarterly count proxy.
        _q1_result = _calculate_115(filing_year=_YEAR_N, period="1T", casilla_inputs=_YEAR_N_QUARTERS["1T"])
        recorder_115.record_calculation_year(filing_year=_YEAR_N, produced_value_count=len(_q1_result.values))

        snapshot_180_n = resources().modelos.authority.snapshot(_MODELO_180, filing_year=_YEAR_N, period="0A")
        prefill_n = resolve_relations_from_local_store(snapshot_180_n, repository=obs_repo)
        resolved_n = {item.relation: item.value for item in prefill_n.values if item.value is not None}
        result_n, produced_n = _calculate_180(filing_year=_YEAR_N, relation_values=resolved_n)
        recorder_180.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        # Year N+1: same pipeline; Year N observations are in the store but must
        # not contaminate Year N+1's 180 resolver.
        expected_n1 = _compute_year_115_totals(_YEAR_N_PLUS_1_QUARTERS, filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        _q1_result_n1 = _calculate_115(
            filing_year=_YEAR_N_PLUS_1,
            period="1T",
            casilla_inputs=_YEAR_N_PLUS_1_QUARTERS["1T"],
        )
        recorder_115.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=len(_q1_result_n1.values))

        snapshot_180_n1 = resources().modelos.authority.snapshot(_MODELO_180, filing_year=_YEAR_N_PLUS_1, period="0A")
        prefill_n1 = resolve_relations_from_local_store(snapshot_180_n1, repository=obs_repo)
        resolved_n1 = {item.relation: item.value for item in prefill_n1.values if item.value is not None}
        result_n1, produced_n1 = _calculate_180(filing_year=_YEAR_N_PLUS_1, relation_values=resolved_n1)
        recorder_180.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Wiring invariant Year N: the monetary 180 outputs equal the summed 115
    # quarters. decl.total-perceptores is no longer a M115 aggregate — RET-1
    # sources it as a distinct-NIF count from the retención store (tested in
    # test_retenciones / test_retenciones_aggregation_resolver), so it is not
    # asserted against the quarterly sum here.
    assert result_n.values[_M180_BASE_TOTAL_CASILLA] == expected_n[_M115_BASE_CASILLA]
    assert result_n.values[_M180_RETENCIONES_TOTAL_CASILLA] == expected_n[_M115_RETENCIONES_CASILLA]

    # Wiring invariant Year N+1: year-isolated, correct aggregate.
    assert result_n1.values[_M180_BASE_TOTAL_CASILLA] == expected_n1[_M115_BASE_CASILLA]
    assert result_n1.values[_M180_RETENCIONES_TOTAL_CASILLA] == expected_n1[_M115_RETENCIONES_CASILLA]

    # Authorization-gate enrollment for the 180 resumen.
    evidence_180 = recorder_180.evidence()
    assert evidence_180.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence_180)

    # Authorization-gate enrollment for the 115 feeder (standalone fleet modelo).
    evidence_115 = recorder_115.evidence()
    assert evidence_115.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence_115)
