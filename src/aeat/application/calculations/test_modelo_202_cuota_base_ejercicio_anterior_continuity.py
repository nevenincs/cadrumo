"""E2E enrollment: Modelo 202 modalidad 40.2 prior-year cuota-base carry.

The Impuesto sobre Sociedades instalment (Modelo 202) modalidad art. 40.2
LIS computes the instalment base (casilla 01) from the cuota líquida of a
prior Modelo 200 (IS annual) filing. The 2P (October) and 3P (December)
instalments take the immediately prior year's M200 cuota líquida
(``DP200014B:00592``, semantic_role ``is_cuota_liquida``); the cross-model
relation ``modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p`` declares
``filing_year_delta = -1`` for those periods and feeds the new binding
``modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior`` that casilla
01 consumes. Casilla 03 ("Mod. 40.2 a ingresar") is the pre-existing formula
``subtract(percent(01, is.modalidad_cuota.percentage), 02)`` — the 18% rate
of LIS art. 40.2 — so once casilla 01 is bound from the prior year, 03
recomputes automatically.

This module is the multi-year-renta authorization enrollment for Modelo 202
(CALC evidence class). It drives the REAL M200 and M202 registry backends
across two distinct renta (annual) years, records each year through the
:class:`EnrollmentRecorder`, and cross-checks the recorded two-year set
against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.

Grounding (non-tautological): the prior M200 cuota líquida is a manual input
the test supplies (no formula under test produces it), and the assertions are
the cross-year WIRING invariants — 2P casilla 01 equals the prior year's M200
cuota líquida, year-isolated, and 03 = 18% of 01 − 02 — grounded in LIS art.
40.2 and the AEAT Modelo 202 instructions, not a reproduction of a formula's
arithmetic against itself.

The 1P (April) instalment binds two years back (``filing_year_delta = -2``)
because the prior-year M200's July deadline has not elapsed in April. That
coverage is guarded explicitly below by seeding historical M200 observations:
the resolver must bind the target year minus two and must not silently use the
nearer prior year. The two-year enrollment still exercises the 2P cross-year
hook, which is the >=2-distinct-renta-years gate contract.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...core.resources import resources
from ...domain.calculations.registry import (
    CasillaObservation,
    RegistryCalculationResult,
    RegistryModeloObservation,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_bound_casilla_inputs,
)
from ...tests.secure_sql import isolated_runtime_profile
from ._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ._observations_repository import CalculationObservationRepository
from ._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_MODELO_200 = "200"
_MODELO_202 = "202"

#: The M200 source casilla the 40.2 base copies (cuota líquida).
_M200_CUOTA_LIQUIDA = "DP200014B:00592"

#: The 18% modalidad 40.2 rate (LIS art. 40.2, parameter
#: ``is.modalidad_cuota.percentage``). Used only to express the wiring
#: assertion for casilla 03; the value the engine applies comes from the
#: registry parameter, not from this constant.
_MODALIDAD_40_2_RATE = Decimal("0.18")

#: Two distinct renta (target) years the M202 2P enrollment spans. The
#: prior-year delta (-1) makes them source M200 of 2025 and 2026 respectively.
_TARGET_YEAR_N = 2026
_TARGET_YEAR_N_PLUS_1 = 2027

#: Distinct prior-year M200 cuota líquida per source year so a cross-year
#: contamination surfaces as a mismatch.
_M200_CUOTA_BY_SOURCE_YEAR: dict[int, Decimal] = {
    2025: Decimal("48000.00"),
    2026: Decimal("63000.00"),
}
_TARGET_YEAR_1P = 2025
_M200_1P_SOURCE_TWO_BACK = Decimal("37000.00")
_M200_1P_NEAR_PRIOR = Decimal("99000.00")

_CLOCK = datetime(2028, 1, 20, 9, 0, 0, tzinfo=UTC)


def _seed_m200_cuota_liquida(*, source_year: int, cuota: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Record a prior-year M200 cuota líquida as a filed observation."""
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=_MODELO_200,
            filing_year=source_year,
            period="0A",
            observations=(CasillaObservation(casilla_id=_M200_CUOTA_LIQUIDA, value=cuota),),
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def _seed_m202_1p(
    *, filing_year: int, pago: Decimal, base: Decimal, obs_repo: CalculationObservationRepository
) -> None:
    """Record the same-year M202 1P filing the 2P self-pago relation cumulates.

    The 2P instalment cumulates the 1P pago already realised that ejercicio
    (casilla 34) via the pre-existing self-pago relation. Seeding a 1P filing
    lets the 2P relation batch resolve; without it the resolver refuses the
    whole batch (the self-pago requirement is unmet) and every 2P relation —
    including the prior-M200 cuota-base hook under test — downgrades to blank.
    Casilla 01 is included because this helper records an already-filed 1P
    observation; the live 1P auto-bind from target year minus two is covered
    separately.
    """
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=_MODELO_202,
            filing_year=filing_year,
            period="1P",
            observations=(
                CasillaObservation(casilla_id="01", value=base),
                CasillaObservation(casilla_id="34", value=pago),
            ),
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def _calculate_202_2p(
    *,
    filing_year: int,
    relation_values: dict[str, Decimal],
    casilla_02: Decimal,
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL M202 2P calculation from the resolved prior-cuota relation."""
    snapshot = resources().modelos.authority.snapshot(_MODELO_202, filing_year=filing_year, period="2P")
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="2P")
    binding_values = {**relation_binding_values}
    inputs = {
        **resolve_bound_casilla_inputs(snapshot.revision, binding_values),
        # Casilla 02 (deductions/withholdings of the period) is a manual input;
        # zero keeps the 03 wiring assertion a clean 18% of the bound base.
        "02": casilla_02,
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values=relation_values,
        date_context={"filing_period": date(filing_year, 10, 20)},
    )
    return result, len(result.values)


def _resolve_202_relations(
    *, filing_year: int, period: str = "2P", obs_repo: CalculationObservationRepository
) -> dict[str, Decimal]:
    snapshot = resources().modelos.authority.snapshot(_MODELO_202, filing_year=filing_year, period=period)
    prefill = resolve_relations_from_local_store(snapshot, repository=obs_repo)
    return {item.relation: item.value for item in prefill.values if item.value is not None}


def test_modelo_202_1p_base_resolves_from_two_years_back_m200_cuota(tmp_path: Path) -> None:
    """1P casilla 01 auto-resolves from target year minus two, not minus one."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_cuota_liquida(
            source_year=_TARGET_YEAR_1P - 2,
            cuota=_M200_1P_SOURCE_TWO_BACK,
            obs_repo=obs_repo,
        )
        _seed_m200_cuota_liquida(
            source_year=_TARGET_YEAR_1P - 1,
            cuota=_M200_1P_NEAR_PRIOR,
            obs_repo=obs_repo,
        )
        resolved = _resolve_202_relations(
            filing_year=_TARGET_YEAR_1P,
            period="1P",
            obs_repo=obs_repo,
        )

    assert resolved["modelo-202-2025-y-siguientes-rel-cuota-base-1p"] == _M200_1P_SOURCE_TWO_BACK
    assert resolved["modelo-202-2025-y-siguientes-rel-cuota-base-1p"] != _M200_1P_NEAR_PRIOR
    assert "modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p" not in resolved


def test_modelo_202_2p_base_resolves_from_prior_year_m200_cuota(tmp_path: Path) -> None:
    """2P casilla 01 auto-resolves to the immediately prior year's M200 cuota líquida.

    The cross-year continuity contract: once the prior M200 is recorded, the
    2P/3P relation (filing_year_delta = -1) populates casilla 01 from that
    prior cuota líquida — the operator does not re-key the prior-year cuota.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_cuota_liquida(source_year=2025, cuota=_M200_CUOTA_BY_SOURCE_YEAR[2025], obs_repo=obs_repo)
        _seed_m202_1p(filing_year=_TARGET_YEAR_N, pago=Decimal("5000.00"), base=Decimal("48000.00"), obs_repo=obs_repo)
        resolved = _resolve_202_relations(filing_year=_TARGET_YEAR_N, obs_repo=obs_repo)
        result, _ = _calculate_202_2p(filing_year=_TARGET_YEAR_N, relation_values=resolved, casilla_02=Decimal("0"))
    assert result.values["01"] == _M200_CUOTA_BY_SOURCE_YEAR[2025]


def test_modelo_202_2p_a_ingresar_recomputes_from_bound_base(tmp_path: Path) -> None:
    """Casilla 03 (a ingresar) recomputes as 18% of the bound base minus deductions.

    With casilla 01 bound from the prior M200 cuota and casilla 02 = 0, the
    pre-existing 40.2 formula yields 03 = 18% × 01. The 18% comes from the
    registry parameter; the assertion confirms the bound base flows into the
    instalment, not the rate's arithmetic against itself.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_cuota_liquida(source_year=2025, cuota=_M200_CUOTA_BY_SOURCE_YEAR[2025], obs_repo=obs_repo)
        _seed_m202_1p(filing_year=_TARGET_YEAR_N, pago=Decimal("5000.00"), base=Decimal("48000.00"), obs_repo=obs_repo)
        resolved = _resolve_202_relations(filing_year=_TARGET_YEAR_N, obs_repo=obs_repo)
        result, _ = _calculate_202_2p(filing_year=_TARGET_YEAR_N, relation_values=resolved, casilla_02=Decimal("0"))
    expected_03 = (_M200_CUOTA_BY_SOURCE_YEAR[2025] * _MODALIDAD_40_2_RATE).quantize(Decimal("0.01"))
    assert result.values["03"] == expected_03


def test_modelo_202_2p_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: M202 2P prior-cuota carry across two renta years.

    Drives the REAL M202 2P backend for two distinct target renta years
    (2026, 2027), each sourcing the immediately prior M200 cuota líquida
    (2025, 2026), records each calculation through the
    :class:`EnrollmentRecorder` (CALC evidence class), and cross-checks the
    recorded two-year set against the authorization manifest. Year N's M200 is
    in the store but must not contaminate Year N+1's resolver (year isolation).
    A single-year or stub run raises at :func:`assert_enrollment_matches_manifest`,
    turning the gate RED.
    """
    recorder = EnrollmentRecorder(_MODELO_202)

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_cuota_liquida(source_year=2025, cuota=_M200_CUOTA_BY_SOURCE_YEAR[2025], obs_repo=obs_repo)
        _seed_m200_cuota_liquida(source_year=2026, cuota=_M200_CUOTA_BY_SOURCE_YEAR[2026], obs_repo=obs_repo)
        # Each target year cumulates its own 1P pago (distinct per year so a
        # cross-year self-pago contamination would surface).
        _seed_m202_1p(filing_year=_TARGET_YEAR_N, pago=Decimal("5000.00"), base=Decimal("48000.00"), obs_repo=obs_repo)
        _seed_m202_1p(
            filing_year=_TARGET_YEAR_N_PLUS_1, pago=Decimal("6200.00"), base=Decimal("63000.00"), obs_repo=obs_repo
        )

        resolved_n = _resolve_202_relations(filing_year=_TARGET_YEAR_N, obs_repo=obs_repo)
        result_n, produced_n = _calculate_202_2p(
            filing_year=_TARGET_YEAR_N, relation_values=resolved_n, casilla_02=Decimal("0")
        )
        recorder.record_calculation_year(filing_year=_TARGET_YEAR_N, produced_value_count=produced_n)

        resolved_n1 = _resolve_202_relations(filing_year=_TARGET_YEAR_N_PLUS_1, obs_repo=obs_repo)
        result_n1, produced_n1 = _calculate_202_2p(
            filing_year=_TARGET_YEAR_N_PLUS_1, relation_values=resolved_n1, casilla_02=Decimal("0")
        )
        recorder.record_calculation_year(filing_year=_TARGET_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Wiring invariant: each target year's 2P base equals the immediately prior
    # M200 cuota líquida, year-isolated.
    assert result_n.values["01"] == _M200_CUOTA_BY_SOURCE_YEAR[2025]
    assert result_n1.values["01"] == _M200_CUOTA_BY_SOURCE_YEAR[2026]

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_TARGET_YEAR_N, _TARGET_YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
