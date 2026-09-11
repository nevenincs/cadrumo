"""Regression tests for Modelo 100 2024 settlement-chain tail (contract).

Covers the six casillas added by the renta-2024-final-settlement construct:
  0587 — cuota líquida incrementada total (0585 + 0586)
  0595 — cuota resultante de la autoliquidación (0587 - deducciones)
  0598 — suma retenciones arrendamientos urbanos (copy of 0153)
  0609 — total pagos a cuenta (sum of retenciones operands)
  0610 — cuota diferencial (0595 - 0609)
  0670 — resultado de la declaración (0610 ± ajustes)

Before contract, all six casillas had ``input_kind = "manual"`` and no formula
in the 2024 revision, so they stayed at 0.  After contract they are
``input_kind = "computed"`` with matching formula TOMLs in
``revisions/2024/formulas/0169-0174-*.toml`` and the
``renta-2024-final-settlement`` construct.

Oracle authority
----------------
Expected values are derived from:
  - LIRPF 2024 Art. 63 (escala estatal — unchanged for 2024)
  - Comunidad de Madrid 2024 autonomic escala
    (registry parameter ``renta-2024-escala-autonomica-madrid-base-general``,
    sourced from ``aeat-renta-2024-manual-parte1``)
  - AEAT Renta 2024 Manual Parte 1, "Liquidación del impuesto"

Roberto landlord persona derivation (base liquidable general 55,500 EUR,
Madrid CCAA, arrendamientos urbanos retenciones 1,824 EUR):

  Escala estatal 2024 at 55,500 EUR (LIRPF Art. 63):
    0-12,450      @ 9.50%  = 1,182.75
    12,450-20,200 @ 12.00% = 930.00   (cumul 2,112.75)
    20,200-35,200 @ 15.00% = 2,250.00 (cumul 4,362.75)
    35,200-55,500 @ 18.50% = 3,755.50 (cumul 8,118.25)
  tarifa_estatal(55,500) = 8,118.25
  tarifa_estatal(5,550)  =   527.25  (mínimo contribuyente)
  Cuota íntegra estatal (0545) = 7,591.00
  No deducciones -> cuota líquida estatal (0570) = 7,591.00
  No incrementos  -> cuota líquida estatal incrementada (0585) = 7,591.00

  Madrid 2024 autonomic escala
  (source: registry parameter file
   ``0014-renta-2024-escala-autonomica-madrid-base-general.toml``,
   authority ``aeat-renta-2024-manual-parte1``):
    0-13,362.22       @ 8.50%  = 1,135.79
    13,362.22-19,004.63 @ 10.70% = 603.74  (cumul 1,739.53)
    19,004.63-35,425.68 @ 12.80% = 2,101.89 (cumul 3,841.42)
    35,425.68-57,320.40 @ 17.40%: 55,500-35,425.68 = 20,074.32 @ 17.40% = 3,492.93
    tarifa_madrid(55,500) = 7,334.35
  tarifa_madrid(5,550) = 5,550 * 8.50% = 471.75  (mínimo contribuyente)
  Cuota íntegra autonómica (0546) = 7,334.35 - 471.75 = 6,862.60
  No deducciones → cuota líquida autonómica (0571) = 6,862.60
  No incrementos  → cuota líquida autonómica incrementada (0586) = 6,862.60

  0587 = 0585 + 0586 = 7,591.00 + 6,862.60 = 14,453.60
  0595 = 0587 (no special deductions 0588/0589/0590/0591) = 14,453.60
  0598 = 0153 (copy formula) = 1,824.00
  0609 = 0598 (all other operands zero) = 1,824.00
  0610 = 0595 - 0609 = 14,453.60 - 1,824.00 = 12,629.60
  0670 = 0610 (no further adjustments) = 12,629.60
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..formula_runtime import calculate_registry_snapshot
from ..ids import BindingId, RelationId
from ..schema import RegistrySnapshot
from ._modelo_100_registry_support import _m100_2024_deduccion_maternidad_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Oracle constants derived from LIRPF 2024 + Madrid escala 2024 — see module
# docstring for full step-by-step derivation.
# ---------------------------------------------------------------------------
# The 0003 leaf input feeds 0018 (rendimiento íntegro), which casilla 0019
# ("otros gastos", art. 19.2.f LIRPF) reduces by min(2.000, 0018) before 0432 /
# 0500. 57,500 nets to the intended 55,500 EUR base liquidable general.
_BASE_LIQUIDABLE_GENERAL = Decimal("57500")
_RETENCIONES_ARRENDAMIENTOS = Decimal("1824")
_DATE_BINDINGS_2024: dict[BindingId, date] = {"renta-2024-profile-taxpayer-birth-date": date(1975, 6, 15)}
_M100_TRABAJO_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id(
    "0003",
    surface="_M100_TRABAJO_RENDIMIENTO_NETO_CASILLA",
)
_M100_RETENCIONES_ARRENDAMIENTOS_CASILLA: CasillaId = validated_casilla_id(
    "0153",
    surface="_M100_RETENCIONES_ARRENDAMIENTOS_CASILLA",
)
_M100_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA_CASILLA: CasillaId = validated_casilla_id(
    "0585",
    surface="_M100_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA_CASILLA",
)
_M100_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA_CASILLA: CasillaId = validated_casilla_id(
    "0586",
    surface="_M100_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA_CASILLA",
)
_M100_CUOTA_LIQUIDA_TOTAL_CASILLA: CasillaId = validated_casilla_id("0587", surface="_M100_CUOTA_LIQUIDA_TOTAL_CASILLA")
_M100_CUOTA_RESULTANTE_CASILLA: CasillaId = validated_casilla_id("0595", surface="_M100_CUOTA_RESULTANTE_CASILLA")
_M100_RETENCIONES_ARRENDAMIENTOS_URBANOS_CASILLA: CasillaId = validated_casilla_id(
    "0598",
    surface="_M100_RETENCIONES_ARRENDAMIENTOS_URBANOS_CASILLA",
)
_M100_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id(
    "0609",
    surface="_M100_TOTAL_PAGOS_A_CUENTA_CASILLA",
)
_M100_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id("0610", surface="_M100_CUOTA_DIFERENCIAL_CASILLA")
_M100_RESULTADO_DECLARACION_CASILLA: CasillaId = validated_casilla_id(
    "0670",
    surface="_M100_RESULTADO_DECLARACION_CASILLA",
)

# 0585: cuota líquida estatal incrementada = cuota íntegra estatal (no deducciones/incrementos)
#   = tarifa_estatal(55500) - tarifa_estatal(5550) = 8118.25 - 527.25 = 7591.00
_EXPECTED_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA = Decimal("7591.00")

# 0586: cuota líquida autonómica incrementada (Madrid 2024)
#   = tarifa_madrid(55500) - tarifa_madrid(5550) = 7334.35 - 471.75 = 6862.60
_EXPECTED_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA = Decimal("6862.60")

# 0587: cuota líquida incrementada total = 0585 + 0586
_EXPECTED_0587 = _EXPECTED_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA + _EXPECTED_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA
# = 7591.00 + 6862.60 = 14453.60

# 0595: cuota resultante (no special deductions 0588/0589/0590/0591)
_EXPECTED_0595 = _EXPECTED_0587

# 0598: retenciones arrendamientos urbanos = copy of 0153
_EXPECTED_0598 = _RETENCIONES_ARRENDAMIENTOS

# 0609: total pagos a cuenta = 0598 (only retenciones source supplied)
_EXPECTED_0609 = _RETENCIONES_ARRENDAMIENTOS

# 0610: cuota diferencial = 0595 - 0609
_EXPECTED_0610 = _EXPECTED_0595 - _EXPECTED_0609
# = 14453.60 - 1824.00 = 12629.60

# 0670: resultado declaración = 0610 (no further adjustments in simple case)
_EXPECTED_0670 = _EXPECTED_0610

_TOLERANCE = Decimal("0.02")

_RELATION_VALUES_2024: dict[RelationId, Decimal] = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}


def _binding_values() -> dict[BindingId, Decimal]:
    return {
        "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        # declaration_type = 1 (individual) → 0461 computed = 0
        "renta-2024-profile-declaration-type": Decimal("1"),
        "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
        # Art. 81.2 LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
        "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
        "renta-2024-profile-incremento-guarderia": Decimal("0"),
        "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
        "renta-2024-profile-descendientes-guarderia": Decimal("0"),
        **_m100_2024_deduccion_maternidad_bindings(),
        "renta-2024-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-2024-profile-minimo-descendientes-autonomico": Decimal("0"),
        "renta-2024-profile-marriage-full-year": Decimal("0"),
        "renta-2024-profile-marriage-month-start": Decimal("0"),
        "renta-2024-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline.
        "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
    }


def _casilla_inputs(*, retenciones: Decimal = _RETENCIONES_ARRENDAMIENTOS) -> dict[CasillaId, Decimal]:
    return {
        _M100_TRABAJO_RENDIMIENTO_NETO_CASILLA: _BASE_LIQUIDABLE_GENERAL,
        _M100_RETENCIONES_ARRENDAMIENTOS_CASILLA: retenciones,
    }


def test_0587_cuota_liquida_total_is_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract, casilla 0587 must equal 0585 + 0586 (not stay at zero).

    contract regression guard: before the fix, 0587 had no formula in the 2024
    revision and defaulted to 0.  After contract the formula
    ``renta-2024-cuota-liquida-incrementada-total`` computes 0587 = 0585 + 0586.

    Oracle: LIRPF 2024 Art. 63 estatal + Madrid CAM 2024 autonomic escala.
    See module docstring for step-by-step derivation.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        # 0003 is the leaf manual trabajo casilla; with all reductions zero the
        # chain produces 0500 = 0505 = 55500 (same technique as contract tests).
        inputs=_casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values[_M100_CUOTA_LIQUIDA_TOTAL_CASILLA] != Decimal("0"), (
        "casilla 0587 (cuota líquida total) is 0.00; "
        "the formula regression has re-appeared: check "
        "2024/formulas/0169-renta-2024-cuota-liquida-incrementada-total.toml "
        "and 2024/casillas/c0587.toml (input_kind must be 'computed')."
    )
    assert abs(result.values[_M100_CUOTA_LIQUIDA_TOTAL_CASILLA] - _EXPECTED_0587) <= _TOLERANCE, (
        f"casilla 0587 = {result.values[_M100_CUOTA_LIQUIDA_TOTAL_CASILLA]!r}; "
        f"expected {_EXPECTED_0587!r} "
        f"(0585={result.values[_M100_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA_CASILLA]!r} + "
        f"0586={result.values[_M100_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA_CASILLA]!r}). "
        f"Oracle: LIRPF 2024 Art. 63 estatal (7591.00) + Madrid CAM 2024 autonomic (6862.60)."
    )


def test_0609_total_pagos_a_cuenta_computed_from_0598(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract, casilla 0609 must aggregate retenciones including 0598.

    The formula ``renta-2024-total-pagos-a-cuenta`` sums 0592-0606.  With only
    0153 (arrendamientos retenciones) supplied, 0598 = 1,824 (copy formula
    renta-2024-retenciones-arrendamientos-urbanos) and 0609 = 0598 = 1,824.

    Oracle: direct — 0153 is the leaf manual retenciones casilla for
    capital inmobiliario arrendamientos urbanos.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=_casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values[_M100_RETENCIONES_ARRENDAMIENTOS_URBANOS_CASILLA] == _EXPECTED_0598, (
        f"casilla 0598 = {result.values[_M100_RETENCIONES_ARRENDAMIENTOS_URBANOS_CASILLA]!r}; "
        f"expected {_EXPECTED_0598!r}. "
        f"Formula renta-2024-retenciones-arrendamientos-urbanos should copy casilla 0153."
    )
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == _EXPECTED_0609, (
        f"casilla 0609 (total pagos a cuenta) = {result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA]!r}; "
        f"expected {_EXPECTED_0609!r}. "
        f"Formula renta-2024-total-pagos-a-cuenta sums 0592-0606; "
        f"with only 0598 non-zero the result must equal 0598."
    )


def test_0610_cuota_diferencial_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract, casilla 0610 must equal 0595 - 0609.

    Oracle (see module docstring):
      0595 = 14,453.60 (cuota resultante = 0587 with no deductions)
      0609 =  1,824.00 (arrendamientos retenciones)
      0610 = 12,629.60
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=_casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert abs(result.values[_M100_CUOTA_DIFERENCIAL_CASILLA] - _EXPECTED_0610) <= _TOLERANCE, (
        f"casilla 0610 (cuota diferencial) = {result.values[_M100_CUOTA_DIFERENCIAL_CASILLA]!r}; "
        f"expected {_EXPECTED_0610!r}. "
        f"Formula: 0595 ({result.values[_M100_CUOTA_RESULTANTE_CASILLA]!r}) - "
        f"0609 ({result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA]!r})."
    )


def test_0670_resultado_declaracion_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract, casilla 0670 must equal 0610 for a taxpayer with no adjustments.

    For a simple landlord with no instalment payments (0611-0669 all zero),
    0670 = 0610.

    Oracle: 0610 = 12,629.60 (derived from LIRPF 2024 + Madrid escala 2024,
    see module docstring).
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=_casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert abs(result.values[_M100_RESULTADO_DECLARACION_CASILLA] - _EXPECTED_0670) <= _TOLERANCE, (
        f"casilla 0670 (resultado declaración) = {result.values[_M100_RESULTADO_DECLARACION_CASILLA]!r}; "
        f"expected {_EXPECTED_0670!r}. "
        f"For no additional adjustments (0611-0669 all zero) 0670 must equal 0610."
    )


def test_settlement_chain_not_zero_for_non_zero_base(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Any non-zero base liquidable general must produce non-zero settlement chain.

    This is the weakest regression guard: before contract, every one of
    0587/0595/0609/0610/0670 was 0 regardless of inputs, because no formula
    existed in the 2024 revision.  After contract, the chain must produce non-zero
    values for a taxpayer with taxable base above the mínimo personal threshold.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=_casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values[_M100_CUOTA_LIQUIDA_TOTAL_CASILLA] > Decimal("0"), (
        "casilla 0587 must be positive for base liquidable 55,500 > mínimo personal 5,550. "
        "If 0587 = 0 the formula regression has re-appeared."
    )
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] > Decimal("0"), (
        "casilla 0609 must be positive when retenciones 0153 = 1,824 > 0."
    )
    assert result.values[_M100_CUOTA_DIFERENCIAL_CASILLA] > Decimal("0"), (
        "casilla 0610 (cuota diferencial) must be positive when cuota exceeds retenciones."
    )
    assert result.values[_M100_RESULTADO_DECLARACION_CASILLA] > Decimal("0"), (
        "casilla 0670 (resultado) must be positive when cuota exceeds retenciones."
    )


def test_anti_tautology_retenciones_change_affects_chain(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Anti-tautology: different retenciones must produce different 0609/0610/0670.

    If the 0153 → 0598 → 0609 → 0610 chain is not wired, both scenarios
    (1,824 and 3,000 retenciones) yield the same 0610.  This test catches that
    broken-chain failure.

    The delta is 3,000 - 1,824 = 1,176 EUR: 0610 must decrease by exactly 1,176
    when retenciones increase from 1,824 to 3,000.
    """
    result_low = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=_casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )
    _higher_retenciones = Decimal("3000")
    result_high = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=_casilla_inputs(retenciones=_higher_retenciones),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    cuota_diferencial_low = result_low.values[_M100_CUOTA_DIFERENCIAL_CASILLA]
    cuota_diferencial_high = result_high.values[_M100_CUOTA_DIFERENCIAL_CASILLA]

    assert cuota_diferencial_high < cuota_diferencial_low, (
        f"cuota diferencial with higher retenciones ({cuota_diferencial_high!r}) "
        f"must be less than with lower retenciones ({cuota_diferencial_low!r}). "
        f"If equal, the 0153 → 0598 → 0609 → 0610 chain is not wired."
    )

    expected_delta = _higher_retenciones - _RETENCIONES_ARRENDAMIENTOS  # = 1176
    actual_delta = cuota_diferencial_low - cuota_diferencial_high
    assert abs(actual_delta - expected_delta) <= _TOLERANCE, (
        f"cuota diferencial delta = {actual_delta!r}; "
        f"expected {expected_delta!r} (3000 - 1824 = 1176 EUR). "
        f"The 0153 → 0609 → 0610 subtraction must flow through cleanly."
    )
