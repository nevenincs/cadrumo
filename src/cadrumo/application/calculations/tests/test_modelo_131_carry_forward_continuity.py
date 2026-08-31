"""E2E continuity: Modelo 131 estimación-objetiva prior-quarter saldo carry-forward.

Modelo 131 (IRPF pago fraccionado estimación objetiva / módulos — RD 439/2007
art. 110) is filed quarterly by autónomos under the módulos (estimación
objetiva) regime. Like Modelo 130, it implements a cross-quarter carry-forward
for negative quarterly results: when the quarterly difference (casilla 10) is
negative, its absolute value is carried forward as ``saldo-negativo-fin-periodo``
(casilla saldo) into the next quarter's casilla 11 ("Resultados negativos de
trimestres anteriores del mismo ejercicio").

The carry-forward binding ``modelo-131-2024-resultados-negativos-anteriores``
uses ``source_period_offset_from_target = -1`` with ``max_year_delta = 0``:
the 4T→1T transition wraps across the year boundary only within the same
ejercicio (max_year_delta=0 prevents cross-year carry). The ≥2-renta
cross-renta hook is therefore at the **annual exercicio boundary**: two
consecutive ejercicios (2024 Q1 and 2025 Q1) each run through the real engine,
demonstrating the engine operates independently per year (no inter-year carry).

Grounding note on módulo coefficients: the M131 registry parameters are the
**statutory 2% fractional payment rates** (RD 439/2007 art. 110, casillas 04
and 06) applied to operator-supplied volumes (casillas 03 and 05). The
per-activity módulo coefficients (signos × índices correctores per the annual
Orden de módulos — Orden HFP/1359/2023 for 2024, Orden HAC/1347/2024 for 2025)
are computed externally by the operator and entered as manual rendimiento-neto
inputs (casilla 01/03/05). The registry engine does not author those
coefficients; they are not registry parameters. There is therefore no
corpus-grounding gap at the registry layer for this enrollment.

The scenario: a carpentry workshop autónomo (módulo: personal empleado ×
índice corrector) files a loss-making 1T in ejercicio 2024 (retenciones exceed
the 2% fractional payment, producing a negative casilla 10), then files a
profitable 1T in ejercicio 2025. The 2024 4T→2025 1T cross-year carry is NOT
expected (max_year_delta=0 prevents it); the saldo carries only within the
same ejercicio. The enrollment assertion is that both años run through the
real engine, producing non-zero casilla outputs, across two distinct renta
años grounded in RD 439/2007 art. 110.

Both años are recorded through the :class:`EnrollmentRecorder` and
cross-checked against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ..binding_prefill import resolve_bindings_from_local_store
from ..multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "131"
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025

_CLOCK = datetime(2026, 2, 1, 9, 0, 0, tzinfo=UTC)

# Carry-forward binding id (same pattern as M130).
_CARRY_BINDING = "modelo-131-2024-resultados-negativos-anteriores"
_CARRY_BINDING_2025 = "modelo-131-2025-resultados-negativos-anteriores"


_M131_RENDIMIENTO_MODULOS_CASILLA: CasillaId = validated_casilla_id("01")
_M131_PAGO_PREVIO_CASILLA: CasillaId = validated_casilla_id("02")
_M131_VOLUME_SIN_DATOS_BASE_CASILLA: CasillaId = validated_casilla_id("03")
_M131_PAYMENT_SIN_DATOS_BASE_CASILLA: CasillaId = validated_casilla_id("04")
_M131_VOLUME_AGRARIO_CASILLA: CasillaId = validated_casilla_id("05")
_M131_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("08")
_M131_RETENCIONES_SOPORTADAS_CASILLA: CasillaId = validated_casilla_id("09")
_M131_RESULTADO_CASILLA: CasillaId = validated_casilla_id("10")
_M131_DEDUCCION_CASILLA: CasillaId = validated_casilla_id("12")
_M131_RESULTADO_EJERCICIOS_ANTERIORES_CASILLA: CasillaId = validated_casilla_id("14")
_M131_SALDO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")

# ---------------------------------------------------------------------------
# Loss-making 1T/2024 scenario:
#   casilla 03 (volumen actividades sin datos base) = 20000
#   casilla 04 (2% of 03) = 400 [computed]
#   casilla 08 (ingresos a cuenta) = 600 (retenciones > 2% payment → negative)
#   casilla 10 = 07 - 08 - 09 = 400 - 600 - 0 = -200
#   saldo-negativo-fin-periodo = max(0, -(-200)) = 200
#
# The saldo value is produced by the real engine, never hand-computed against
# the formula under test. The wiring assertion is: the saldo equals 200 from
# the engine's own evaluation of max(0, -casilla10).
# ---------------------------------------------------------------------------
_Q1_2024_INPUTS: dict[CasillaId, Decimal] = {
    _M131_RENDIMIENTO_MODULOS_CASILLA: Decimal("0"),  # rendimiento neto módulos con datos base
    _M131_PAGO_PREVIO_CASILLA: Decimal("0"),  # pago fraccionado previo con datos base
    _M131_VOLUME_SIN_DATOS_BASE_CASILLA: Decimal("20000.00"),  # volumen actividades sin datos base (manual)
    _M131_VOLUME_AGRARIO_CASILLA: Decimal("0"),  # volumen agrario
    _M131_RETENCIONES_CASILLA: Decimal("600.00"),  # ingresos a cuenta / retenciones practicadas
    _M131_RETENCIONES_SOPORTADAS_CASILLA: Decimal("0"),  # retenciones soportadas
    _M131_DEDUCCION_CASILLA: Decimal("0"),  # deducción por discapacidad / familia numerosa
    _M131_RESULTADO_EJERCICIOS_ANTERIORES_CASILLA: Decimal("0"),  # resultado ejercicios anteriores
}
_Q1_2024_CARRY_BINDING = {
    _CARRY_BINDING: Decimal("0"),  # Q1 has no prior quarter
    "modelo-131-volumen-ingresos-agrario": Decimal("0"),
}

_EXPECTED_Q1_2024_SALDO = Decimal("200.00")

# ---------------------------------------------------------------------------
# Profitable 1T/2025 scenario (same activity, better year):
#   casilla 03 = 30000
#   casilla 04 (2%) = 600
#   casilla 08 = 100 (retenciones below 2% payment → positive result)
#   casilla 10 = 600 - 100 - 0 = 500
#   saldo = max(0, -500) = 0 (no carry needed)
# ---------------------------------------------------------------------------
_Q1_2025_INPUTS: dict[CasillaId, Decimal] = {
    _M131_RENDIMIENTO_MODULOS_CASILLA: Decimal("0"),
    _M131_PAGO_PREVIO_CASILLA: Decimal("0"),
    _M131_VOLUME_SIN_DATOS_BASE_CASILLA: Decimal("30000.00"),
    _M131_VOLUME_AGRARIO_CASILLA: Decimal("0"),
    _M131_RETENCIONES_CASILLA: Decimal("100.00"),
    _M131_RETENCIONES_SOPORTADAS_CASILLA: Decimal("0"),
    _M131_DEDUCCION_CASILLA: Decimal("0"),
    _M131_RESULTADO_EJERCICIOS_ANTERIORES_CASILLA: Decimal("0"),
}
_Q1_2025_CARRY_BINDING = {
    _CARRY_BINDING_2025: Decimal("0"),  # Q1 has no prior quarter
    "modelo-131-volumen-ingresos-agrario": Decimal("0"),
}


def _calculate_131(
    *,
    filing_year: int,
    period: str,
    casilla_inputs: dict[CasillaId, Decimal],
    carry_binding: dict[str, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL M131 engine for one quarter; return result + produced-value count."""
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=period)
    bound = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, carry_binding)
    inputs = {**bound, **casilla_inputs}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=carry_binding,
        date_context={"filing_period": snapshot.revision.valid_from},
    )
    return result, len(result.values)


def _131_observation(*, filing_year: int, period: str, result: RegistryCalculationResult) -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=filing_year,
        period=period,
        casilla_values=result.values,
    )


def test_q1_2024_loss_produces_carry_forward_saldo(tmp_path: Path) -> None:
    """A loss-making Q1/2024 produces a positive saldo-negativo-fin-periodo.

    retenciones (600) exceed the 2% fractional payment on 20,000 (400),
    so casilla 10 = -200 and saldo = max(0, 200) = 200. The value is
    produced by the real engine from the loss scenario, never hand-computed.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, _ = _calculate_131(
            filing_year=_YEAR_N,
            period="1T",
            casilla_inputs=_Q1_2024_INPUTS,
            carry_binding=_Q1_2024_CARRY_BINDING,
        )
    assert result.values[_M131_RESULTADO_CASILLA] == Decimal("-200.00")
    assert result.values[_M131_SALDO_NEGATIVO_CASILLA] == _EXPECTED_Q1_2024_SALDO


def test_q1_2025_profitable_produces_zero_saldo(tmp_path: Path) -> None:
    """A profitable Q1/2025 produces a zero saldo (no carry needed).

    The 2% payment (600) exceeds retenciones (100), giving casilla 10 = 500.
    saldo = max(0, -500) = 0. Each año's engine runs independently.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, _ = _calculate_131(
            filing_year=_YEAR_N_PLUS_1,
            period="1T",
            casilla_inputs=_Q1_2025_INPUTS,
            carry_binding=_Q1_2025_CARRY_BINDING,
        )
    assert result.values[_M131_RESULTADO_CASILLA] == Decimal("500.00")
    assert result.values[_M131_SALDO_NEGATIVO_CASILLA] == Decimal("0.00")


def test_q2_2024_carry_forward_resolves_from_q1_2024_saldo(tmp_path: Path) -> None:
    """Q2/2024's casilla 11 auto-resolves to Q1/2024's persisted saldo.

    The within-ejercicio carry-forward contract (max_year_delta=0, offset=-1):
    once Q1/2024 is recorded as a prior-period observation, the
    ``previous_filing`` resolver populates Q2/2024's casilla-11 binding with
    Q1/2024's saldo-negativo-fin-periodo.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        q1, _ = _calculate_131(
            filing_year=_YEAR_N,
            period="1T",
            casilla_inputs=_Q1_2024_INPUTS,
            carry_binding=_Q1_2024_CARRY_BINDING,
        )
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                _131_observation(filing_year=_YEAR_N, period="1T", result=q1),
                source_kind="app_filing",
                captured_at=_CLOCK,
            )
        )
        q2_snapshot = bundled_authority().snapshot(_MODELO, filing_year=_YEAR_N, period="2T")
        report = resolve_bindings_from_local_store(q2_snapshot, repository=obs_repo)

    assert report.binding_values.get(_CARRY_BINDING) == _EXPECTED_Q1_2024_SALDO


def test_modelo_131_modules_continuity_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: M131 estimación-objetiva across two renta years (2024, 2025).

    Drives the REAL M131 engine for Q1 of each renta year (real registry
    authority, real formula evaluation — no mocks), records each through the
    :class:`EnrollmentRecorder` (calculation mode, evidenced by produced casilla
    count), and cross-checks via :func:`assert_enrollment_matches_manifest`.

    Load-bearing assertions:
    - Q1/2024 produces a positive saldo (loss scenario, 2% rate from registry).
    - Q1/2025 produces zero saldo (profitable scenario, same 2% rate from registry).
    - Produced-value counts are strictly positive in both years.

    Coefficient-grounding note: the 2% rates (RD 439/2007 art. 110) are the only
    registry parameters exercised here. The per-activity módulo coefficients
    (signos × índices correctores per Orden HFP/1359/2023 for 2024,
    Orden HAC/1347/2024 for 2025) are operator-computed and entered as manual
    inputs (casillas 01/03/05) — not registry parameters. No coefficient corpus
    gap exists at the registry layer.
    """
    recorder = EnrollmentRecorder(_MODELO)

    with isolated_runtime_profile(tmp_path=tmp_path):
        # Year N (2024): loss-making Q1, produces saldo.
        result_n, produced_n = _calculate_131(
            filing_year=_YEAR_N,
            period="1T",
            casilla_inputs=_Q1_2024_INPUTS,
            carry_binding=_Q1_2024_CARRY_BINDING,
        )
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        # Year N+1 (2025): profitable Q1, zero saldo.
        result_n1, produced_n1 = _calculate_131(
            filing_year=_YEAR_N_PLUS_1,
            period="1T",
            casilla_inputs=_Q1_2025_INPUTS,
            carry_binding=_Q1_2025_CARRY_BINDING,
        )
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Year N wiring: 2% rate from registry parameter applied to 20,000.
    assert result_n.values[_M131_PAYMENT_SIN_DATOS_BASE_CASILLA] == Decimal("400.00")  # 2% x 20000
    assert result_n.values[_M131_RESULTADO_CASILLA] == Decimal("-200.00")
    assert result_n.values[_M131_SALDO_NEGATIVO_CASILLA] == _EXPECTED_Q1_2024_SALDO

    # Year N+1 wiring: 2% rate from 2025 registry parameter applied to 30,000.
    assert result_n1.values[_M131_PAYMENT_SIN_DATOS_BASE_CASILLA] == Decimal("600.00")  # 2% x 30000
    assert result_n1.values[_M131_RESULTADO_CASILLA] == Decimal("500.00")
    assert result_n1.values[_M131_SALDO_NEGATIVO_CASILLA] == Decimal("0.00")

    # Authorization-gate enrollment.
    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
