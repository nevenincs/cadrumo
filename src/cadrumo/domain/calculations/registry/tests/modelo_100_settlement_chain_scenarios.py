"""Scenario bodies for test_modelo_100_settlement_chain, called by its authored-source and published-authority tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..formula_runtime import calculate_registry_snapshot
from ..ids import BindingId, RelationId
from ..schema import RegistrySnapshot
from .modelo_100_registry_support import M100_NO_DESCENDANT_MATERNIDAD_BINDINGS

# ---------------------------------------------------------------------------
# Oracle constants derived from LIRPF 2024 + Madrid escala 2024 — see module
# docstring for full step-by-step derivation.
# ---------------------------------------------------------------------------
# The 0003 leaf input feeds 0018 (rendimiento íntegro), which casilla 0019
# ("otros gastos", art. 19.2.f LIRPF) reduces by min(2.000, 0018) before 0432 /
# 0500. 57,500 nets to the intended 55,500 EUR base liquidable general.
BASE_LIQUIDABLE_GENERAL = Decimal("57500")

RETENCIONES_ARRENDAMIENTOS = Decimal("1824")

DATE_BINDINGS_2024: dict[BindingId, date] = {"renta-profile-taxpayer-birth-date": date(1975, 6, 15)}

M100_TRABAJO_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id(
    "0003",
    surface="M100_TRABAJO_RENDIMIENTO_NETO_CASILLA",
)

M100_RETENCIONES_ARRENDAMIENTOS_CASILLA: CasillaId = validated_casilla_id(
    "0153",
    surface="M100_RETENCIONES_ARRENDAMIENTOS_CASILLA",
)

M100_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA_CASILLA: CasillaId = validated_casilla_id(
    "0585",
    surface="M100_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA_CASILLA",
)

M100_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA_CASILLA: CasillaId = validated_casilla_id(
    "0586",
    surface="M100_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA_CASILLA",
)

M100_CUOTA_LIQUIDA_TOTAL_CASILLA: CasillaId = validated_casilla_id("0587", surface="M100_CUOTA_LIQUIDA_TOTAL_CASILLA")

M100_CUOTA_RESULTANTE_CASILLA: CasillaId = validated_casilla_id("0595", surface="M100_CUOTA_RESULTANTE_CASILLA")

M100_RETENCIONES_ARRENDAMIENTOS_URBANOS_CASILLA: CasillaId = validated_casilla_id(
    "0598",
    surface="M100_RETENCIONES_ARRENDAMIENTOS_URBANOS_CASILLA",
)

M100_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id(
    "0609",
    surface="M100_TOTAL_PAGOS_A_CUENTA_CASILLA",
)

M100_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id("0610", surface="M100_CUOTA_DIFERENCIAL_CASILLA")

M100_RESULTADO_DECLARACION_CASILLA: CasillaId = validated_casilla_id(
    "0670",
    surface="M100_RESULTADO_DECLARACION_CASILLA",
)


# 0585: cuota líquida estatal incrementada = cuota íntegra estatal (no deducciones/incrementos)
#   = tarifa_estatal(55500) - tarifa_estatal(5550) = 8118.25 - 527.25 = 7591.00
EXPECTED_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA = Decimal("7591.00")


# 0586: cuota líquida autonómica incrementada (Madrid 2024)
#   = tarifa_madrid(55500) - tarifa_madrid(5956.65) = 7334.35 - 506.32 = 6828.03
EXPECTED_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA = Decimal("6828.03")


# 0587: cuota líquida incrementada total = 0585 + 0586
EXPECTED_0587 = EXPECTED_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA + EXPECTED_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA

# = 7591.00 + 6828.03 = 14419.03

# 0595: cuota resultante (no special deductions 0588/0589/0590/0591)
EXPECTED_0595 = EXPECTED_0587


# 0598: retenciones arrendamientos urbanos = copy of 0153
EXPECTED_0598 = RETENCIONES_ARRENDAMIENTOS


# 0609: total pagos a cuenta = 0598 (only retenciones source supplied)
EXPECTED_0609 = RETENCIONES_ARRENDAMIENTOS


# 0610: cuota diferencial = 0595 - 0609
EXPECTED_0610 = EXPECTED_0595 - EXPECTED_0609

# = 14419.03 - 1824.00 = 12595.03

# 0670: resultado declaración = 0610 (no further adjustments in simple case)
EXPECTED_0670 = EXPECTED_0610


TOLERANCE = Decimal("0.02")


RELATION_VALUES_2024: dict[RelationId, Decimal] = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}


def binding_values() -> dict[BindingId, Decimal]:
    return {
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        # declaration_type = 1 (individual) → 0461 computed = 0
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-family-minor-children-in-unit": Decimal("0"),
        # Art. 81.2 LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
        "renta-profile-incremento-guarderia": Decimal("0"),
        "renta-profile-cotizaciones-ss-madre": Decimal("0"),
        **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline.
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
    }


def casilla_inputs(*, retenciones: Decimal = RETENCIONES_ARRENDAMIENTOS) -> dict[CasillaId, Decimal]:
    return {
        M100_TRABAJO_RENDIMIENTO_NETO_CASILLA: BASE_LIQUIDABLE_GENERAL,
        M100_RETENCIONES_ARRENDAMIENTOS_CASILLA: retenciones,
    }


def check_0587_cuota_liquida_total_is_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract, casilla 0587 must equal 0585 + 0586 (not stay at zero).

    contract regression guard: before the fix, 0587 had no formula in the 2024
    revision and defaulted to 0.  After contract the formula
    ``renta-cuota-liquida-incrementada-total`` computes 0587 = 0585 + 0586.

    Oracle: LIRPF 2024 Art. 63 estatal + Madrid CAM 2024 autonomic escala.
    See module docstring for step-by-step derivation.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        # 0003 is the leaf manual trabajo casilla; with all reductions zero the
        # chain produces 0500 = 0505 = 55500 (same technique as contract tests).
        inputs=casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values(),
        relation_values=RELATION_VALUES_2024,
        date_binding_values=DATE_BINDINGS_2024,
    )

    assert result.values[M100_CUOTA_LIQUIDA_TOTAL_CASILLA] != Decimal("0"), (
        "casilla 0587 (cuota líquida total) is 0.00; "
        "the formula regression has re-appeared: check "
        "2024/formulas/0169-renta-cuota-liquida-incrementada-total.toml "
        "and 2024/casillas/c0587.toml (input_kind must be 'computed')."
    )
    assert abs(result.values[M100_CUOTA_LIQUIDA_TOTAL_CASILLA] - EXPECTED_0587) <= TOLERANCE, (
        f"casilla 0587 = {result.values[M100_CUOTA_LIQUIDA_TOTAL_CASILLA]!r}; "
        f"expected {EXPECTED_0587!r} "
        f"(0585={result.values[M100_CUOTA_LIQUIDA_ESTATAL_INCREMENTADA_CASILLA]!r} + "
        f"0586={result.values[M100_CUOTA_LIQUIDA_AUTONOMICA_INCREMENTADA_CASILLA]!r}). "
        f"Oracle: LIRPF 2024 Art. 63 estatal (7591.00) + Madrid CAM 2024 autonomic (6828.03)."
    )


def check_0609_total_pagos_a_cuenta_computed_from_0598(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract, casilla 0609 must aggregate retenciones including 0598.

    The formula ``renta-total-pagos-a-cuenta`` sums 0592-0606.  With only
    0153 (arrendamientos retenciones) supplied, 0598 = 1,824 (copy formula
    renta-retenciones-arrendamientos-urbanos) and 0609 = 0598 = 1,824.

    Oracle: direct — 0153 is the leaf manual retenciones casilla for
    capital inmobiliario arrendamientos urbanos.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values(),
        relation_values=RELATION_VALUES_2024,
        date_binding_values=DATE_BINDINGS_2024,
    )

    assert result.values[M100_RETENCIONES_ARRENDAMIENTOS_URBANOS_CASILLA] == EXPECTED_0598, (
        f"casilla 0598 = {result.values[M100_RETENCIONES_ARRENDAMIENTOS_URBANOS_CASILLA]!r}; "
        f"expected {EXPECTED_0598!r}. "
        f"Formula renta-retenciones-arrendamientos-urbanos should copy casilla 0153."
    )
    assert result.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == EXPECTED_0609, (
        f"casilla 0609 (total pagos a cuenta) = {result.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA]!r}; "
        f"expected {EXPECTED_0609!r}. "
        f"Formula renta-total-pagos-a-cuenta sums 0592-0606; "
        f"with only 0598 non-zero the result must equal 0598."
    )


def check_0610_cuota_diferencial_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract, casilla 0610 must equal 0595 - 0609.

    Oracle (see module docstring):
      0595 = 14,419.03 (cuota resultante = 0587 with no deductions)
      0609 =  1,824.00 (arrendamientos retenciones)
      0610 = 12,595.03
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values(),
        relation_values=RELATION_VALUES_2024,
        date_binding_values=DATE_BINDINGS_2024,
    )

    assert abs(result.values[M100_CUOTA_DIFERENCIAL_CASILLA] - EXPECTED_0610) <= TOLERANCE, (
        f"casilla 0610 (cuota diferencial) = {result.values[M100_CUOTA_DIFERENCIAL_CASILLA]!r}; "
        f"expected {EXPECTED_0610!r}. "
        f"Formula: 0595 ({result.values[M100_CUOTA_RESULTANTE_CASILLA]!r}) - "
        f"0609 ({result.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA]!r})."
    )


def check_0670_resultado_declaracion_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract, casilla 0670 must equal 0610 for a taxpayer with no adjustments.

    For a simple landlord with no instalment payments (0611-0669 all zero),
    0670 = 0610.

    Oracle: 0610 = 12,595.03 (derived from LIRPF 2024 + Madrid escala 2024,
    see module docstring).
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values(),
        relation_values=RELATION_VALUES_2024,
        date_binding_values=DATE_BINDINGS_2024,
    )

    assert abs(result.values[M100_RESULTADO_DECLARACION_CASILLA] - EXPECTED_0670) <= TOLERANCE, (
        f"casilla 0670 (resultado declaración) = {result.values[M100_RESULTADO_DECLARACION_CASILLA]!r}; "
        f"expected {EXPECTED_0670!r}. "
        f"For no additional adjustments (0611-0669 all zero) 0670 must equal 0610."
    )


def check_settlement_chain_not_zero_for_non_zero_base(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Any non-zero base liquidable general must produce non-zero settlement chain.

    This is the weakest regression guard: before contract, every one of
    0587/0595/0609/0610/0670 was 0 regardless of inputs, because no formula
    existed in the 2024 revision.  After contract, the chain must produce non-zero
    values for a taxpayer with taxable base above the mínimo personal threshold.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values(),
        relation_values=RELATION_VALUES_2024,
        date_binding_values=DATE_BINDINGS_2024,
    )

    assert result.values[M100_CUOTA_LIQUIDA_TOTAL_CASILLA] > Decimal("0"), (
        "casilla 0587 must be positive for base liquidable 55,500 > mínimo personal 5,550. "
        "If 0587 = 0 the formula regression has re-appeared."
    )
    assert result.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA] > Decimal("0"), (
        "casilla 0609 must be positive when retenciones 0153 = 1,824 > 0."
    )
    assert result.values[M100_CUOTA_DIFERENCIAL_CASILLA] > Decimal("0"), (
        "casilla 0610 (cuota diferencial) must be positive when cuota exceeds retenciones."
    )
    assert result.values[M100_RESULTADO_DECLARACION_CASILLA] > Decimal("0"), (
        "casilla 0670 (resultado) must be positive when cuota exceeds retenciones."
    )


def check_anti_tautology_retenciones_change_affects_chain(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Anti-tautology: different retenciones must produce different 0609/0610/0670.

    If the 0153 → 0598 → 0609 → 0610 chain is not wired, both scenarios
    (1,824 and 3,000 retenciones) yield the same 0610.  This test catches that
    broken-chain failure.

    The delta is 3,000 - 1,824 = 1,176 EUR: 0610 must decrease by exactly 1,176
    when retenciones increase from 1,824 to 3,000.
    """
    result_low = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=casilla_inputs(),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values(),
        relation_values=RELATION_VALUES_2024,
        date_binding_values=DATE_BINDINGS_2024,
    )
    _higher_retenciones = Decimal("3000")
    result_high = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs=casilla_inputs(retenciones=_higher_retenciones),
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values(),
        relation_values=RELATION_VALUES_2024,
        date_binding_values=DATE_BINDINGS_2024,
    )

    cuota_diferencial_low = result_low.values[M100_CUOTA_DIFERENCIAL_CASILLA]
    cuota_diferencial_high = result_high.values[M100_CUOTA_DIFERENCIAL_CASILLA]

    assert cuota_diferencial_high < cuota_diferencial_low, (
        f"cuota diferencial with higher retenciones ({cuota_diferencial_high!r}) "
        f"must be less than with lower retenciones ({cuota_diferencial_low!r}). "
        f"If equal, the 0153 → 0598 → 0609 → 0610 chain is not wired."
    )

    expected_delta = _higher_retenciones - RETENCIONES_ARRENDAMIENTOS  # = 1176
    actual_delta = cuota_diferencial_low - cuota_diferencial_high
    assert abs(actual_delta - expected_delta) <= TOLERANCE, (
        f"cuota diferencial delta = {actual_delta!r}; "
        f"expected {expected_delta!r} (3000 - 1824 = 1176 EUR). "
        f"The 0153 → 0609 → 0610 subtraction must flow through cleanly."
    )
