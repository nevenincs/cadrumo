"""E2E reconciliation continuity: Modelo 190 (annual) ← Modelo 111 (quarterly).

Modelo 111 is the quarterly retención-rendimientos del trabajo autoliquidación
(Orden EHA/586/2011, RD 439/2007 arts. 80, 86, 95): an employer-retainer
files 1T–4T each year, declaring nine perception categories (trabajo
dinerario, especie, actividades económicas dinerario, especie, premios
dinerario, especie, ganancias forestales dinerario, especie, cesión derechos
imagen) with a perceptor count and payment amount per category, plus total
retenciones (casilla 28, computed). Modelo 190 is the annual resumen: it
aggregates the four quarters' 19 casillas via ``source = "previous_filing"``
relations (``annual_summary``, ``op=sum``), then computes three output casillas:

- ``decl.total-percepciones`` = sum of nine perception-count relations
- ``decl.percepciones-total`` = sum of nine importe relations
- ``decl.retenciones-total`` = copy of the retenciones relation

(RD 439/2007 art. 109, Orden EHA/3127/2009 art. 1, Orden HAC/1431/2025 art. 2,
Ley 35/2006 arts. 99, 101.)

The source casillas for the 190 relations are 01, 04, 07, 10, 13, 16, 19, 22,
25 (perception counts) and 02, 05, 08, 11, 14, 17, 20, 23, 26 (importes) and
28 (retenciones).

This module is the multi-year-renta authorization enrollment for Modelo 190.
It drives the REAL backend (real encrypted-SQLite observation store, the real
registry authority, the real calculation engine, the real relation resolver —
no mocks) across two distinct renta years (2025, 2026). The simplest non-zero
111 scenario populates only the ``trabajo dinerario`` category (casillas
01-03) plus total retenciones (casilla 28 is computed from sub-totals) and
zeroes the remaining eight categories. Both calculated resumen years are
recorded through the :class:`EnrollmentRecorder` and cross-checked against
the authorization manifest via :func:`assert_enrollment_matches_manifest`.

Grounding (non-tautological): the 111 casilla 28 (total retenciones) is
computed by the engine as the sum over all retention sub-totals. The 190
assertion is the *wiring* invariant — the three 190 output casillas equal the
aggregate of the corresponding 111 quarterly casillas — grounded in the AEAT
form instructions and the form BOE-modelo-190-2025-form. Distinct per-quarter
values per year ensure cross-contamination fails loudly.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    RegistryCalculationResult,
    RegistryModeloObservation,
    RelationId,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_bound_inputs_by_casilla_id,
    validated_casilla_id,
)
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo ids this module exercises.
_MODELO_111 = "111"
_MODELO_190 = "190"

#: Two distinct renta years.
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

_CLOCK = datetime(2027, 1, 20, 9, 0, 0, tzinfo=UTC)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M190/111 reconciliation fixture casilla key {value!r} is not a CasillaId") from exc


def _casilla_ids(*values: object) -> list[CasillaId]:
    return [_casilla_id(value) for value in values]


_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: CasillaId = _casilla_id("02")
_M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_M111_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("28")
_M190_TOTAL_PERCEPCIONES_CASILLA: CasillaId = _casilla_id("decl.total-percepciones")
_M190_PERCEPCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.percepciones-total")
_M190_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")

# ---------------------------------------------------------------------------
# 111 quarterly scenarios — a trabajo-dinerario-only filer.
#
# Casilla 01 = trabajo dinerario: número de perceptores (integer, manual)
# Casilla 02 = trabajo dinerario: importe dinerario (money, manual)
# Casilla 03 = trabajo dinerario: retenciones dinerario (money, manual)
# Casillas 04-27 = eight remaining categories, all zero.
# Casilla 28 = total retenciones (computed: sum of sub-total retenciones).
#
# Only casillas 01, 02, 03, 28 are sourced by the 190 relations we test
# (01 → percepciones-count for trabajo-dinerario; 02 → importe for
# trabajo-dinerario; 28 → retenciones-total copy). Zeroing all other
# categories keeps the scenario minimal and the wiring assertion tight.
# ---------------------------------------------------------------------------

# Source casilla ids the 190 binding/relation machinery aggregates.
# The perception-count relations source odd casillas 01,04,07,10,13,16,19,22,25.
# The importe relations source even casillas 02,05,08,11,14,17,20,23,26.
# The retenciones relation sources casilla 28.
_PERCEPTION_COUNT_CASILLAS: list[CasillaId] = _casilla_ids("01", "04", "07", "10", "13", "16", "19", "22", "25")
_IMPORTE_CASILLAS: list[CasillaId] = _casilla_ids("02", "05", "08", "11", "14", "17", "20", "23", "26")

# All 111 manual-input casillas not driven by the scenario are zero.
_ZERO_CASILLAS: list[CasillaId] = _casilla_ids(
    "04",
    "05",
    "06",  # trabajo especie
    "07",
    "08",
    "09",  # actividades econ dinerario
    "10",
    "11",
    "12",  # actividades econ especie
    "13",
    "14",
    "15",  # premios dinerario
    "16",
    "17",
    "18",  # premios especie
    "19",
    "20",
    "21",  # ganancias forestales dinerario
    "22",
    "23",
    "24",  # ganancias forestales especie
    "25",
    "26",
    "27",  # cesión derechos imagen
    "29",  # resultado anteriores autoliquidaciones
)

_YEAR_N_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("5"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("12000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2280.00"),
    },
    "2T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("6"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("14000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2660.00"),
    },
    "3T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("4"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("10500.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("1995.00"),
    },
    "4T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("5"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("13000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2470.00"),
    },
}

_YEAR_N_PLUS_1_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("3"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("9000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("1710.00"),
    },
    "2T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("4"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("11000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2090.00"),
    },
    "3T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("5"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("15000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2850.00"),
    },
    "4T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("4"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("12500.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2375.00"),
    },
}


def _calculate_111(
    *,
    filing_year: int,
    period: str,
    casilla_inputs: dict[CasillaId, Decimal],
) -> RegistryCalculationResult:
    """Run the REAL 111 quarterly calculation and return the engine result."""
    snapshot = resources().modelos.authority.snapshot(_MODELO_111, filing_year=filing_year, period=period)
    # Supply all manual-input zero casillas plus the scenario inputs.
    zero_inputs = {cid: Decimal("0") for cid in _ZERO_CASILLAS}
    inputs = {
        **resolve_bound_inputs_by_casilla_id(snapshot.revision, {}),
        **zero_inputs,
        **casilla_inputs,
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values={},
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def _111_observation(*, filing_year: int, period: str, result: RegistryCalculationResult) -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=_MODELO_111,
        filing_year=filing_year,
        period=period,
        casilla_values=result.values,
    )


def _calculate_190(
    *,
    filing_year: int,
    relation_values: dict[RelationId, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL 190 annual calculation from resolved relations; return result + count."""
    snapshot = resources().modelos.authority.snapshot(_MODELO_190, filing_year=filing_year, period="0A")
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    binding_values = {**relation_binding_values}
    inputs = {
        **resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values=relation_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result, len(result.values)


def _compute_year_111_totals(
    quarters: dict[str, dict[CasillaId, Decimal]],
    *,
    filing_year: int,
    obs_repo: CalculationObservationRepository,
) -> dict[CasillaId, Decimal]:
    """Calculate all four 111 quarters, persist observations, return casilla sums.

    Returns a dict with the summed values for the casillas the 190 relations
    aggregate: perception-count casillas 01 (trabajo-dinerario only in this
    scenario) plus importe casilla 02 and retenciones casilla 28.
    All other perception-count and importe casillas are zero in this scenario.
    """
    totals: dict[CasillaId, Decimal] = {
        cid: Decimal("0")
        for cid in _PERCEPTION_COUNT_CASILLAS + _IMPORTE_CASILLAS + [_M111_RETENCIONES_TOTAL_CASILLA]
    }
    for period, inputs in quarters.items():
        result = _calculate_111(filing_year=filing_year, period=period, casilla_inputs=inputs)
        obs_repo.save_observation(
            _111_observation(filing_year=filing_year, period=period, result=result),
            source_kind="app_filing",
            captured_at=_CLOCK,
        )
        for cid in totals:
            if cid in result.values:
                totals[cid] += result.values[cid]
    return totals


def test_modelo_111_quarterly_engine_produces_retenciones_casilla(tmp_path: Path) -> None:
    """The 111 engine computes total retenciones (casilla 28) from sub-totals.

    The value is produced by the real engine, never hand-computed. This is
    the seed fed to the 190 reconciliation for the retenciones relation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result = _calculate_111(
            filing_year=_YEAR_N,
            period="1T",
            casilla_inputs=_YEAR_N_QUARTERS["1T"],
        )
    assert result.values[_M111_RETENCIONES_TOTAL_CASILLA] > Decimal("0")
    assert (
        result.values[_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
        == _YEAR_N_QUARTERS["1T"][_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
    )


def test_modelo_190_relation_prefill_aggregates_111_quarters(tmp_path: Path) -> None:
    """The 190 relation resolver aggregates Year N's four 111 quarterly casillas.

    The cross-quarter aggregation contract for the trabajo-dinerario scenario:
    ``resolve_relations_from_local_store`` for the 190 annual snapshot produces
    relation values that equal the arithmetic sum over the four 111 quarters
    for each targeted casilla (01 perception count, 02 importe, 28 retenciones).
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        expected = _compute_year_111_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        snapshot_190 = resources().modelos.authority.snapshot(_MODELO_190, filing_year=_YEAR_N, period="0A")
        prefill = resolve_relations_from_local_store(snapshot_190, repository=obs_repo)

    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in prefill.values if item.value is not None
    }
    # trabajo-dinerario perception count (source: casilla 01)
    assert (
        resolved["modelo-190-rel-111-trabajo-dinerario-percepciones-anual"]
        == expected[_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
    )
    # trabajo-dinerario importe (source: casilla 02)
    assert (
        resolved["modelo-190-rel-111-trabajo-dinerario-importe-anual"]
        == expected[_M111_TRABAJO_DINERARIO_IMPORTE_CASILLA]
    )
    # total retenciones (source: casilla 28)
    assert resolved["modelo-190-rel-111-retenciones-anual"] == expected[_M111_RETENCIONES_TOTAL_CASILLA]


def test_modelo_190_year_isolation_ignores_prior_year_observations(tmp_path: Path) -> None:
    """Year N+1's 190 resolver draws only from Year N+1 111 records, not Year N.

    Both years' observations reside in the same repository. The relation
    resolver MUST discriminate by ``filing_year`` so the Year N+1 190 totals
    equal Year N+1's quarterly sums and do not absorb Year N's larger values.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _compute_year_111_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        expected_n1 = _compute_year_111_totals(_YEAR_N_PLUS_1_QUARTERS, filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        snapshot_190_n1 = resources().modelos.authority.snapshot(_MODELO_190, filing_year=_YEAR_N_PLUS_1, period="0A")
        prefill = resolve_relations_from_local_store(snapshot_190_n1, repository=obs_repo)

    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in prefill.values if item.value is not None
    }
    assert (
        resolved["modelo-190-rel-111-trabajo-dinerario-percepciones-anual"]
        == expected_n1[_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
    )
    assert (
        resolved["modelo-190-rel-111-trabajo-dinerario-importe-anual"]
        == expected_n1[_M111_TRABAJO_DINERARIO_IMPORTE_CASILLA]
    )
    assert resolved["modelo-190-rel-111-retenciones-anual"] == expected_n1[_M111_RETENCIONES_TOTAL_CASILLA]


def test_modelo_190_111_reconciliation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: 111 quarterly aggregation → 190 annual across two renta years.

    Drives the REAL 111 and 190 backends for both renta years (2025, 2026),
    records each 190 calculation through the :class:`EnrollmentRecorder`
    (RECONCILIATION evidence_class — calculation mode, evidenced by produced
    casilla count), and cross-checks the recorded two-year set against the
    authorization manifest.

    The load-bearing wiring assertions are:

    - For each year, ``decl.total-percepciones`` equals the sum of all nine
      perception-count relations (here: all zero except trabajo-dinerario).
    - For each year, ``decl.percepciones-total`` equals the sum of all nine
      importe relations (here: all zero except trabajo-dinerario importe).
    - For each year, ``decl.retenciones-total`` equals the retenciones relation
      (casilla 28 aggregated over 1T-4T).
    - Year N+1's 190 relations are drawn from Year N+1 observations only.

    These are wiring invariants grounded in RD 439/2007 art. 109, Orden
    EHA/3127/2009 art. 1, and the AEAT M190 form (BOE-modelo-190-2025-form).
    """
    recorder_190 = EnrollmentRecorder(_MODELO_190)
    recorder_111 = EnrollmentRecorder(_MODELO_111)

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()

        # Year N: calculate four 111 quarters, persist, resolve 190, calculate 190.
        expected_n = _compute_year_111_totals(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo)
        # 111 feeder: evidence the feeder year via one real quarterly calculation.
        _q1_result = _calculate_111(filing_year=_YEAR_N, period="1T", casilla_inputs=_YEAR_N_QUARTERS["1T"])
        recorder_111.record_calculation_year(filing_year=_YEAR_N, produced_value_count=len(_q1_result.values))

        snapshot_190_n = resources().modelos.authority.snapshot(_MODELO_190, filing_year=_YEAR_N, period="0A")
        prefill_n = resolve_relations_from_local_store(snapshot_190_n, repository=obs_repo)
        resolved_n = {item.relation: item.value for item in prefill_n.values if item.value is not None}
        result_n, produced_n = _calculate_190(filing_year=_YEAR_N, relation_values=resolved_n)
        recorder_190.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        # Year N+1: same pipeline.
        expected_n1 = _compute_year_111_totals(_YEAR_N_PLUS_1_QUARTERS, filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        _q1_result_n1 = _calculate_111(
            filing_year=_YEAR_N_PLUS_1,
            period="1T",
            casilla_inputs=_YEAR_N_PLUS_1_QUARTERS["1T"],
        )
        recorder_111.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=len(_q1_result_n1.values))

        snapshot_190_n1 = resources().modelos.authority.snapshot(_MODELO_190, filing_year=_YEAR_N_PLUS_1, period="0A")
        prefill_n1 = resolve_relations_from_local_store(snapshot_190_n1, repository=obs_repo)
        resolved_n1 = {item.relation: item.value for item in prefill_n1.values if item.value is not None}
        result_n1, produced_n1 = _calculate_190(filing_year=_YEAR_N_PLUS_1, relation_values=resolved_n1)
        recorder_190.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Wiring invariant Year N:
    # total-percepciones = sum of perception-count relations; in this
    # trabajo-only scenario all others are zero, so total = 111 casilla 01 sum.
    assert (
        result_n.values[_M190_TOTAL_PERCEPCIONES_CASILLA]
        == expected_n[_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
    )
    # percepciones-total = sum of importe relations; trabajo-dinerario only.
    assert result_n.values[_M190_PERCEPCIONES_TOTAL_CASILLA] == expected_n[_M111_TRABAJO_DINERARIO_IMPORTE_CASILLA]
    # retenciones-total = aggregated casilla 28 over 1T-4T.
    assert result_n.values[_M190_RETENCIONES_TOTAL_CASILLA] == expected_n[_M111_RETENCIONES_TOTAL_CASILLA]

    # Wiring invariant Year N+1 (year-isolated):
    assert (
        result_n1.values[_M190_TOTAL_PERCEPCIONES_CASILLA]
        == expected_n1[_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
    )
    assert (
        result_n1.values[_M190_PERCEPCIONES_TOTAL_CASILLA]
        == expected_n1[_M111_TRABAJO_DINERARIO_IMPORTE_CASILLA]
    )
    assert result_n1.values[_M190_RETENCIONES_TOTAL_CASILLA] == expected_n1[_M111_RETENCIONES_TOTAL_CASILLA]

    # Authorization-gate enrollment for the 190 resumen.
    evidence_190 = recorder_190.evidence()
    assert evidence_190.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence_190)

    # Authorization-gate enrollment for the 111 feeder (standalone fleet modelo).
    evidence_111 = recorder_111.evidence()
    assert evidence_111.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence_111)
