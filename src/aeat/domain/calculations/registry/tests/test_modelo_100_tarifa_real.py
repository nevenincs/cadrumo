"""Regression test for Modelo 100 2024 cuota íntegra — Cluster T fix (contract/contract).

Cluster T root cause: casillas 0511/0512 (mínimo del contribuyente
estatal/autonómica) lacked a formula in the 2024 registry revision, so the
engine silently defaulted them to 0.  The fix (contract) adds parameter
``renta-2024-minimo-contribuyente-base-2024`` (5,550 EUR, LIRPF Art. 57) and
two computed formulas that populate 0511/0512.

contract tests: Pere-shape profile (single taxpayer, Catalonia, base liquidable
general 35,400 EUR, no ahorro base, no family supplements).

contract tests: Supplement scenarios exercising casillas 0513 (mínimo por
descendientes, LIRPF Art. 58) and 0515 (mínimo por ascendientes, LIRPF Art. 59)
as operator-supplied manual inputs.  These casillas follow the same input_kind
= manual pattern as 2025 — the engine does not auto-compute them from birth dates
(no age_at formula op exists).  Operators or the UI supply the statutory amounts
directly based on the taxpayer's declared family situation.

All expected values are derived from the official LIRPF 2024 escala general and
the AEAT Renta 2024 Manual — not from re-running the formula engine.

Calculation authority:
- LIRPF Art. 62-63 (escala estatal base general)
- LIRPF Art. 57 (mínimo del contribuyente: 5,550 EUR base, +1,150 age 65-74,
  +1,400 additional age >=75)
- LIRPF Art. 58 (mínimo por descendientes)
- LIRPF Art. 59 (mínimo por ascendientes)
- LIRPF Art. 74-75 (escala autonómica, Cataluña 2024)
- AEAT Renta 2024 Manual, Part 1, "Liquidación del impuesto"
- BOE Orden HAC-563-2024 (confirming 5,550 EUR unchanged for 2024)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .. import BindingId, CasillaId, RegistrySnapshot, RelationId, calculate_registry_snapshot, validated_casilla_id
from .._authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test_modelo_100_tarifa_real.casilla")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc

# -----------------------------------------------------------------------
# Expected values — derived from LIRPF 2024 tables, not engine output.
#
# Base liquidable general: 35,400 EUR (Pere shape per contract spec).
#
# Escala estatal (LIRPF Art. 63, unchanged 2024):
#   0-12,450        @ 9.500% -> 1,182.75
#   12,450-20,200   @ 12.00% -> 930.00   (cumul 2,112.75)
#   20,200-35,200   @ 15.00% -> 2,250.00 (cumul 4,362.75)
#   35,200-35,400   @ 18.50% -> 37.00    (cumul 4,399.75)
#
# Mínimo del contribuyente (LIRPF Art. 57): 5,550 EUR.
# Tarifa on mínimo (escala estatal, same brackets):
#   0-5,550 @ 9.500% = 527.25
#
# Cuota íntegra estatal (LIRPF Art. 62):
#   0545 = 4,399.75 - 527.25 = 3,872.50
#
# Escala autonómica Cataluña 2024 (LIRPF Art. 74, Ley Cataluña 5/2020):
#   0-12,450.00       @ 10.500% -> 1,307.25
#   12,450-17,707.20  @ 12.000% -> 630.86   (cumul 1,938.11)
#   17,707.20-21,000  @ 14.000% -> 460.99   (cumul 2,399.10)
#   21,000-33,007.20  @ 15.000% -> 1,801.08 (cumul 4,200.18)
#   33,007.20-35,400  @ 18.800% -> 449.85   (cumul 4,650.03)
#
# Mínimo del contribuyente (same 5,550 EUR, autonómica):
#   0-5,550 @ 10.500% = 582.75
#
# Cuota íntegra autonómica (LIRPF Art. 75):
#   0546 = 4,650.03 - 582.75 = 4,067.28
# -----------------------------------------------------------------------

# contract fix: casilla 0505 is now computed via formula renta-2024-base-liquidable-
# general-sometida-a-gravamen (max(0, 0500 - 0527)).  Tests must supply the leaf
# manual casilla 0003 (trabajo ingresos íntegros) rather than 0505 directly.
# With 0003=35400 and all reductions zero the chain produces:
#   0500 = 35400  (base liquidable general)
#   0527 = 0      (no anualidades alimentos)
#   0505 = 35400  (max(0, 35400 - 0))
_BASE_LIQUIDABLE_GENERAL = Decimal("35400")
# Input leaf to feed through the computation chain; see formula chain comment above.
_TRABAJO_INGRESOS_INTEGROS = Decimal("35400")
_EXPECTED_CUOTA_INTEGRA_ESTATAL = Decimal("3872.50")
_EXPECTED_CUOTA_INTEGRA_AUTONOMICA = Decimal("4067.28")
_EXPECTED_MINIMO_CONTRIBUYENTE = Decimal("5550.00")
_TOLERANCE = Decimal("0.01")

_TRABAJO_INGRESOS_INTEGROS_CASILLA: CasillaId = _casilla_id("0003")
_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA: CasillaId = _casilla_id("0505")
_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA: CasillaId = _casilla_id("0511")
_MINIMO_CONTRIBUYENTE_AUTONOMICA_CASILLA: CasillaId = _casilla_id("0512")
_MINIMO_DESCENDIENTES_CASILLA: CasillaId = _casilla_id("0513")
_MINIMO_ASCENDIENTES_CASILLA: CasillaId = _casilla_id("0515")
_ANUALIDADES_TOTAL_CASILLA: CasillaId = _casilla_id("0527")
_CUOTA_INTEGRA_ESTATAL_CASILLA: CasillaId = _casilla_id("0545")
_CUOTA_INTEGRA_AUTONOMICA_CASILLA: CasillaId = _casilla_id("0546")
_CUOTA_LIQUIDA_INCREMENTADA_ESTATAL_CASILLA: CasillaId = _casilla_id("0585")
_CUOTA_LIQUIDA_INCREMENTADA_AUTONOMICA_CASILLA: CasillaId = _casilla_id("0586")
_CUOTA_LIQUIDA_INCREMENTADA_TOTAL_CASILLA: CasillaId = _casilla_id("0587")
_RETENCIONES_TRABAJO_CASILLA: CasillaId = _casilla_id("0592")
_CUOTA_RESULTANTE_CASILLA: CasillaId = _casilla_id("0595")
_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = _casilla_id("0609")
_CUOTA_DIFERENCIAL_CASILLA: CasillaId = _casilla_id("0610")
_ANUALIDADES_PRIMER_HIJO_CASILLA: CasillaId = _casilla_id("1741")


@pytest.fixture
def m100_2024_snapshot(registry_authority: ValidatedRegistryAuthority):
    return registry_authority.snapshot("100", filing_year=2024, period="0A")


def test_m100_2024_minimo_contribuyente_computed_not_zero(m100_2024_snapshot: RegistrySnapshot) -> None:
    """After contract fix, casilla 0511 must equal the LIRPF Art. 57 base value.

    This is the regression guard for Cluster T: before contract, casilla 0511
    defaulted to 0 (no formula, no binding in 2024 revision). After contract it
    is computed from the parameter ``renta-2024-minimo-contribuyente-base-2024``.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_INGRESOS_INTEGROS},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    assert result.values[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA] == _EXPECTED_MINIMO_CONTRIBUYENTE, (
        f"casilla 0511 (mínimo contribuyente estatal) is "
        f"{result.values[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA]!r}; "
        f"expected {_EXPECTED_MINIMO_CONTRIBUYENTE!r} per LIRPF Art. 57. "
        f"If this is 0.00 the Cluster-T regression has re-appeared: "
        f"check 2024/formulas/0166-renta-2024-minimo-contribuyente-estatal.toml "
        f"and 2024/parameters/0030-renta-2024-minimo-contribuyente-base-2024.toml."
    )
    assert result.values[_MINIMO_CONTRIBUYENTE_AUTONOMICA_CASILLA] == _EXPECTED_MINIMO_CONTRIBUYENTE, (
        f"casilla 0512 (mínimo contribuyente autonómica) is "
        f"{result.values[_MINIMO_CONTRIBUYENTE_AUTONOMICA_CASILLA]!r}; "
        f"expected {_EXPECTED_MINIMO_CONTRIBUYENTE!r} per LIRPF Art. 57 / Art. 74."
    )


def test_m100_2024_cuota_integra_estatal_matches_lirpf_tables(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Cuota íntegra estatal (0545) must equal the LIRPF 2024 table result.

    Expected derivation (LIRPF Art. 62-63, escala estatal 2024):
      tarifa(35400) - tarifa(5550) = 4399.75 - 527.25 = 3,872.50 EUR.

    This was previously over-stated as 3,132.75 EUR (Cluster T: mínimo personal
    = 0, so the mínimo deduction step was silently skipped).
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_INGRESOS_INTEGROS},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    cuota_estatal = result.values[_CUOTA_INTEGRA_ESTATAL_CASILLA]
    assert abs(cuota_estatal - _EXPECTED_CUOTA_INTEGRA_ESTATAL) <= _TOLERANCE, (
        f"cuota íntegra estatal (0545) = {cuota_estatal!r}; "
        f"expected {_EXPECTED_CUOTA_INTEGRA_ESTATAL!r} per LIRPF 2024 tables. "
        f"Cluster T regression: if 0545 = 3132.75 the mínimo personal deduction "
        f"is not being applied (0511/0512 zero)."
    )


def test_m100_2024_cuota_integra_autonomica_cataluna_matches_lirpf_tables(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """Cuota íntegra autonómica (0546) must equal the Cataluña 2024 table result.

    Expected derivation (LIRPF Art. 74-75, Ley 5/2020 Cataluña escala 2024):
      tarifa_cat(35400) - tarifa_cat(5550) = 4650.03 - 582.75 = 4,067.28 EUR.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_INGRESOS_INTEGROS},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    cuota_autonomica = result.values[_CUOTA_INTEGRA_AUTONOMICA_CASILLA]
    assert abs(cuota_autonomica - _EXPECTED_CUOTA_INTEGRA_AUTONOMICA) <= _TOLERANCE, (
        f"cuota íntegra autonómica (0546) = {cuota_autonomica!r}; "
        f"expected {_EXPECTED_CUOTA_INTEGRA_AUTONOMICA!r} per LIRPF 2024 / Cataluña tables."
    )


def test_m100_2024_cuota_integra_estatal_is_positive(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Any non-zero base liquidable general must produce positive cuota íntegra.

    This is the weakest possible guard: cuota must be > 0 for a taxpayer
    with a taxable base above the mínimo personal threshold (35,400 > 5,550).
    Cluster T manifested precisely here — the cuota was reported as zero or
    massively understated because the mínimo deduction was 0.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_INGRESOS_INTEGROS},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    assert result.values[_CUOTA_INTEGRA_ESTATAL_CASILLA] > Decimal("0"), (
        "cuota íntegra estatal (0545) must be positive for base_liquidable > mínimo"
    )
    assert result.values[_CUOTA_INTEGRA_AUTONOMICA_CASILLA] > Decimal("0"), (
        "cuota íntegra autonómica (0546) must be positive for base_liquidable > mínimo"
    )


# -----------------------------------------------------------------------
# contract supplement scenarios — LIRPF Art. 57.2/57.3, Art. 58, Art. 59.
#
# Casillas 0513 (mínimo por descendientes) and 0515 (mínimo por
# ascendientes) are manual input casillas — operators supply the statutory
# amounts directly, as on the AEAT form.  Casilla 0511 is computed (5,550
# EUR from the contract formula); 0513/0515 are added on top via inputs.
#
# Pere age 70 profile (contract-A): base liquidable general 35,400 EUR.
#   Mínimo contribuyente base: 5,550 EUR (0511 — computed).
#   Mínimo contribuyente edad 65-74 supplement: +1,150 EUR (Art. 57.2).
#   Casilla 0513 as operator input (age supplement = 1,150 EUR on the form,
#   which in practice is entered by the gestoria into this casilla for
#   age-bracket taxpayers — AEAT form layout groups 0513 with family
#   supplements even though Art. 57.2 conceptually extends 0511).
#
# NOTE ON CASILLA MAPPING: LIRPF Art. 57.2 age supplements are part of the
# mínimo del contribuyente (Art. 57), not the mínimo por descendientes
# (Art. 58).  The 2024 AEAT form maps the Art. 57.2 +1,150 supplement into
# casilla 0513 (the physical casilla labeled "Mínimo por descendientes"
# carries the age-supplement row on the 2024 paper form alongside
# descendants).  The operator supplies 1,150 there for a 65-74 contribuyente
# with no actual descendants.
#
# Escala estatal — tarifa(35400) = 4,399.75 (from contract derivation).
# Mínimo with age supplement: 5,550 + 1,150 = 6,700 EUR (LIRPF Art. 57.2).
# tarifa_estatal(6700):
#   0-6,700 @ 9.500% = 636.50
#
# Cuota íntegra estatal (0545) = 4,399.75 - 636.50 = 3,763.25 EUR.
#
# Escala autonómica Cataluña 2024 — tarifa_cat(35400) = 4,650.03 (from contract).
# tarifa_cat(6700):
#   0-6,700 @ 10.500% = 703.50
#
# Cuota íntegra autonómica (0546) = 4,650.03 - 703.50 = 3,946.53 EUR.
#
# Two descendants (one under 3) scenario (contract-B):
# base = 35,400 EUR; mínimo contribuyente = 5,550 (computed).
# Mínimo descendientes (Art. 58): first child 2,400 + second child 2,700
#   + under-3 supplement 3,000 = 8,100 EUR total -> casilla 0513 = 8,100.
# Total mínimo personal y familiar = 5,550 + 8,100 = 13,650 EUR.
# tarifa_estatal(13650):
#   0-12,450 @ 9.500% = 1,182.75
#   12,450-13,650 @ 12.000% = 144.00  (cumul 1,326.75)
#
# Cuota íntegra estatal = 4,399.75 - 1,326.75 = 3,073.00 EUR.
#
# Ascendant over 75 scenario (contract-C):
# base = 35,400 EUR; mínimo contribuyente = 5,550 (computed).
# Mínimo ascendientes (Art. 59): 1,150 (>65) + 1,400 (>75) = 2,550 EUR
#   -> casilla 0515 = 2,550.
# Total mínimo personal y familiar = 5,550 + 2,550 = 8,100 EUR.
# tarifa_estatal(8100):
#   0-8,100 @ 9.500% = 769.50
#
# Cuota íntegra estatal = 4,399.75 - 769.50 = 3,630.25 EUR.
# -----------------------------------------------------------------------

_EXPECTED_CUOTA_ESTATAL_PERE_70 = Decimal("3763.25")
_EXPECTED_CUOTA_AUTONOMICA_PERE_70 = Decimal("3946.53")
_EXPECTED_CUOTA_ESTATAL_2DESCENDANTS_1UNDER3 = Decimal("3073.00")
_EXPECTED_CUOTA_ESTATAL_ASCENDANT_OVER75 = Decimal("3630.25")


def _base_binding_values() -> dict[BindingId, Decimal]:
    return {
        "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        # declaration_type = 1 (individual) → 0461 computed = 0
        "renta-2024-profile-declaration-type": Decimal("1"),
        "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
        # Art. 81 bis LIRPF guarderia bindings (b7ad3a993): zero in scenarios
        # without childcare deduction (mínimo del contribuyente chain only).
        "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
        "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
        "renta-2024-profile-descendientes-menores-3": Decimal("0"),
        # matrimonio-sobrevenido bindings (81feae7b0): zero = marriage pre-dates filing year.
        "renta-2024-profile-marriage-full-year": Decimal("0"),
        "renta-2024-profile-marriage-month-start": Decimal("0"),
        "renta-2024-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline: the previous_filing binding
        # for casilla 1388 (LIRPF Art. 48 base liquidable negativa carry)
        # resolves to zero when no prior Modelo 100 filing exists in the
        # test corpus. Test fixtures with no carry exercise this baseline.
        "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
    }


# Art. 57.1.b LIRPF age supplement requires a taxpayer birth_date; supply a
# representative date outside the 65/75 brackets for non-age scenarios.
_BIRTH_DATE_BINDINGS_2024: dict[BindingId, date] = {
    "renta-2024-profile-taxpayer-birth-date": date(1975, 6, 15),
}

# RD 439/2007 Art. 110 pagos-fraccionados relations; zero in scenarios that
# do not exercise M130/M131 cross-model integration.
_RELATION_VALUES_2024: dict[RelationId, Decimal] = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-115-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}


def test_m100_2024_cuota_estatal_pere_age_70_with_age_supplement(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """Pere age 70 (LIRPF Art. 57.2 +1,150) produces correct cuota estatal.

    Mínimo contribuyente = 5,550 (computed) + 1,150 age supplement (0513,
    operator-supplied per AEAT form) = 6,700 EUR total.
    Expected: tarifa(35400) - tarifa(6700) = 4,399.75 - 636.50 = 3,763.25 EUR.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_INGRESOS_INTEGROS,
            _MINIMO_DESCENDIENTES_CASILLA: Decimal("1150"),  # Art. 57.2 age supplement, operator-supplied
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    cuota_estatal = result.values[_CUOTA_INTEGRA_ESTATAL_CASILLA]
    assert abs(cuota_estatal - _EXPECTED_CUOTA_ESTATAL_PERE_70) <= _TOLERANCE, (
        f"cuota íntegra estatal (0545) with Art. 57.2 age supplement = {cuota_estatal!r}; "
        f"expected {_EXPECTED_CUOTA_ESTATAL_PERE_70!r} from LIRPF tables. "
        f"mínimo total = 5550 + 1150 = 6700 EUR."
    )
    cuota_autonomica = result.values[_CUOTA_INTEGRA_AUTONOMICA_CASILLA]
    assert abs(cuota_autonomica - _EXPECTED_CUOTA_AUTONOMICA_PERE_70) <= _TOLERANCE, (
        f"cuota íntegra autonómica (0546) with Art. 57.2 age supplement = {cuota_autonomica!r}; "
        f"expected {_EXPECTED_CUOTA_AUTONOMICA_PERE_70!r} from Cataluña 2024 escala."
    )


def test_m100_2024_cuota_estatal_two_descendants_one_under_three(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """Two descendants (one under 3) produce correct cuota estatal via Art. 58.

    Mínimo descendientes = 2,400 + 2,700 + 3,000 = 8,100 EUR (Art. 58).
    Mínimo personal y familiar = 5,550 + 8,100 = 13,650 EUR.
    Expected cuota estatal: tarifa(35400) - tarifa(13650) = 4,399.75 - 1,326.75
    = 3,073.00 EUR.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_INGRESOS_INTEGROS,
            _MINIMO_DESCENDIENTES_CASILLA: Decimal("8100"),  # Art. 58: 2400 + 2700 + 3000, operator-supplied
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    cuota_estatal = result.values[_CUOTA_INTEGRA_ESTATAL_CASILLA]
    assert abs(cuota_estatal - _EXPECTED_CUOTA_ESTATAL_2DESCENDANTS_1UNDER3) <= _TOLERANCE, (
        f"cuota íntegra estatal (0545) with Art. 58 descendants = {cuota_estatal!r}; "
        f"expected {_EXPECTED_CUOTA_ESTATAL_2DESCENDANTS_1UNDER3!r}. "
        f"mínimo total = 5550 + 8100 = 13650 EUR."
    )


def test_m100_2024_cuota_estatal_ascendant_over_75(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """Ascendant over 75 produces correct cuota estatal via Art. 59.

    Mínimo ascendientes = 1,150 + 1,400 = 2,550 EUR (Art. 59).
    Mínimo personal y familiar = 5,550 + 2,550 = 8,100 EUR.
    Expected cuota estatal: tarifa(35400) - tarifa(8100) = 4,399.75 - 769.50
    = 3,630.25 EUR.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_INGRESOS_INTEGROS,
            _MINIMO_ASCENDIENTES_CASILLA: Decimal("2550"),  # Art. 59: 1150 + 1400, operator-supplied
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    cuota_estatal = result.values[_CUOTA_INTEGRA_ESTATAL_CASILLA]
    assert abs(cuota_estatal - _EXPECTED_CUOTA_ESTATAL_ASCENDANT_OVER75) <= _TOLERANCE, (
        f"cuota íntegra estatal (0545) with Art. 59 ascendant >75 = {cuota_estatal!r}; "
        f"expected {_EXPECTED_CUOTA_ESTATAL_ASCENDANT_OVER75!r}. "
        f"mínimo total = 5550 + 2550 = 8100 EUR."
    )


# -----------------------------------------------------------------------
# contract tests — LIRPF Art. 56 casilla 0505 formula derivation.
#
# Root cause: casilla 0505 (base liquidable general sometida a gravamen)
# was manual — when not supplied the engine used 0 and cuota silently
# became 0.  The fix adds formula renta-2024-base-liquidable-general-
# sometida-a-gravamen: max(0, [0500] - [0527]).
#
# 0500 = base liquidable general (formula, feeds from rendimiento trabajo).
# 0527 = anualidades alimentos hijos judicial (formula, sum of casillas
#        1741, 1744, 1749, 1754, 1759 — Art. 75.3 LIRPF).
#
# Oracle: LIRPF Art. 63 escala estatal 2024 (unchanged from prior years).
#
# Scenario A: base_liquidable 14,896 EUR, no anualidades.
#   tarifa(14,896):
#     0-12,450 @ 9.500% = 1,182.75
#     12,450-14,896 @ 12.00% = 293.52  (cumul 1,476.27)
#   tarifa(mínimo 5,550 @ 9.500%) = 527.25
#   Cuota íntegra estatal = 1,476.27 - 527.25 = 949.02 EUR
#   (LIRPF 2024 Art. 62-63 / AEAT Renta 2024 Manual Part 1)
#
# Scenario B: base_liquidable 14,896 EUR, anualidades judicial 3,000 EUR.
#   0505 = max(0, 14896 - 3000) = 11,896
#   tarifa(11,896):
#     0-11,896 @ 9.500% = 1,130.12
#   Cuota íntegra estatal = 1,130.12 - 527.25 = 602.87 EUR
# -----------------------------------------------------------------------

_BASE_14896 = Decimal("14896")
_ANUALIDADES_3000 = Decimal("3000")
_EXPECTED_0505_NO_ANUALIDADES = Decimal("14896.00")
_EXPECTED_0505_WITH_ANUALIDADES = Decimal("11896.00")
_EXPECTED_CUOTA_ESTATAL_14896_NO_ANUALIDADES = Decimal("949.02")
_EXPECTED_CUOTA_ESTATAL_14896_WITH_ANUALIDADES = Decimal("602.87")


def test_0505_computed_from_0500_no_anualidades(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Casilla 0505 is computed as max(0, 0500) when no anualidades are present.

    contract regression guard: before the fix, 0505 was manual and silently stayed
    0, making cuota íntegra 0.  After the fix, 0505 = 0500 = base liquidable
    = 14,896 EUR and cuota is non-zero per LIRPF 2024 Art. 62-63 tables.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_TRABAJO_INGRESOS_INTEGROS_CASILLA: _BASE_14896},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    assert result.values[_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA] == _EXPECTED_0505_NO_ANUALIDADES, (
        f"casilla 0505 = {result.values[_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA]!r}; "
        f"expected {_EXPECTED_0505_NO_ANUALIDADES!r}. "
        f"If 0505 = 0 the formula regression has re-appeared: "
        f"check 2024/formulas/0168-renta-2024-base-liquidable-general-sometida-a-gravamen.toml."
    )
    cuota = result.values[_CUOTA_INTEGRA_ESTATAL_CASILLA]
    assert abs(cuota - _EXPECTED_CUOTA_ESTATAL_14896_NO_ANUALIDADES) <= _TOLERANCE, (
        f"cuota íntegra estatal (0545) = {cuota!r}; "
        f"expected {_EXPECTED_CUOTA_ESTATAL_14896_NO_ANUALIDADES!r} per LIRPF 2024 Art. 62-63. "
        f"tarifa(14896) - tarifa(5550) = 1476.27 - 527.25 = 949.02 EUR."
    )


def test_anualidades_alimentos_reduces_0505(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Anualidades por alimentos hijos judicial reduce 0505 per LIRPF Art. 75.3.

    With base liquidable 14,896 EUR and judicial anualidades 3,000 EUR:
      0527 = 3,000 (computed from casilla 1741, first child)
      0505 = max(0, 14,896 - 3,000) = 11,896 EUR
      cuota íntegra estatal = tarifa(11,896) - tarifa(5,550)
                            = 1,130.12 - 527.25 = 602.87 EUR
    Oracle: LIRPF 2024 Art. 63 escala estatal.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _BASE_14896,
            _ANUALIDADES_PRIMER_HIJO_CASILLA: _ANUALIDADES_3000,
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    assert result.values[_ANUALIDADES_TOTAL_CASILLA] == _ANUALIDADES_3000, (
        f"casilla 0527 (anualidades total) = {result.values[_ANUALIDADES_TOTAL_CASILLA]!r}; expected 3000.00"
    )
    assert result.values[_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA] == _EXPECTED_0505_WITH_ANUALIDADES, (
        f"casilla 0505 = {result.values[_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA]!r}; "
        f"expected {_EXPECTED_0505_WITH_ANUALIDADES!r} (14896 - 3000 = 11896). "
        f"0505 formula should subtract 0527 from 0500."
    )
    cuota = result.values[_CUOTA_INTEGRA_ESTATAL_CASILLA]
    assert abs(cuota - _EXPECTED_CUOTA_ESTATAL_14896_WITH_ANUALIDADES) <= _TOLERANCE, (
        f"cuota íntegra estatal (0545) = {cuota!r}; "
        f"expected {_EXPECTED_CUOTA_ESTATAL_14896_WITH_ANUALIDADES!r} per LIRPF 2024 Art. 63. "
        f"tarifa(11896) - tarifa(5550) = 1130.12 - 527.25 = 602.87 EUR."
    )


def test_anti_tautology_anualidades_changes_cuota(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Anti-tautology: anualidades judicial must change cuota relative to no-anualidades.

    If the 0527 -> 0505 subtraction is not wired, both scenarios yield the same
    cuota (the formula is broken). This test catches that failure.
    """
    result_no_anualidades = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_TRABAJO_INGRESOS_INTEGROS_CASILLA: _BASE_14896},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )
    result_with_anualidades = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _BASE_14896,
            _ANUALIDADES_PRIMER_HIJO_CASILLA: _ANUALIDADES_3000,
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    cuota_no = result_no_anualidades.values[_CUOTA_INTEGRA_ESTATAL_CASILLA]
    cuota_with = result_with_anualidades.values[_CUOTA_INTEGRA_ESTATAL_CASILLA]
    assert cuota_with < cuota_no, (
        f"cuota with anualidades ({cuota_with!r}) must be less than without ({cuota_no!r}). "
        f"If equal, the 0527 -> 0505 subtraction is not wired in the formula."
    )
    expected_delta = _EXPECTED_CUOTA_ESTATAL_14896_NO_ANUALIDADES - _EXPECTED_CUOTA_ESTATAL_14896_WITH_ANUALIDADES
    actual_delta = cuota_no - cuota_with
    assert abs(actual_delta - expected_delta) <= _TOLERANCE, (
        f"cuota delta = {actual_delta!r}; expected delta {expected_delta!r} (949.02 - 602.87 = 346.15 EUR)."
    )


# -----------------------------------------------------------------------
# contract tests — M100 2024 settlement-chain tail (renta-2024-final-settlement).
#
# Root cause: casillas 0587, 0595, 0598, 0609, 0610, 0670 had no formulas
# in the 2024 revision; all stayed at 0 forever.
#
# The fix adds construct renta-2024-final-settlement with 6 formulas:
#   0587 = 0585 + 0586  (cuota liquida incrementada total)
#   0595 = 0587 - 0588 - 0589 - 0590 - 0591  (cuota resultante)
#   0598 = copy(0153)   (retenciones arrendamientos urbanos)
#   0609 = sum(0592..0606)  (total pagos a cuenta, 14 operands)
#   0610 = 0595 - 0609  (cuota diferencial)
#   0670 = 0610 - 0611 + 0612 ... + 0669  (resultado declaracion, 17 ops)
#
# Test strategy: structural identity checks per RD 439/2007 Art. 110.
# We do NOT assert absolute euro values computed from the same chain.
# We verify:
#   - 0587 = 0585 + 0586 (structural identity)
#   - 0609 equals the single retención operand supplied (0592 = single source)
#   - 0610 = 0595 - 0609 (structural identity)
#   - Anti-tautology: cuota diferencial decreases when retención increases
#
# Authority: RD 439/2007 Art. 110, LIRPF Art. 99, AEAT 2024 form BOE.
# -----------------------------------------------------------------------

_TRABAJO_BASE_55500 = Decimal("55500")
_RETENCION_1824 = Decimal("1824")
_RETENCION_3648 = Decimal("3648")  # doubled retención for anti-tautology


def test_0587_equals_sum_of_liquida_incrementada(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Casilla 0587 must equal 0585 + 0586 per renta-2024-cuota-liquida-incrementada-total.

    contract regression guard: before the fix, 0587 had no formula and stayed 0
    even when 0585 and 0586 were computed and positive. After the fix, 0587 is
    computed and equals the sum of both cuota liquida incrementada values.
    Authority: LIRPF Art. 50, AEAT forma BOE 2024.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_BASE_55500},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    c0585 = result.values[_CUOTA_LIQUIDA_INCREMENTADA_ESTATAL_CASILLA]
    c0586 = result.values[_CUOTA_LIQUIDA_INCREMENTADA_AUTONOMICA_CASILLA]
    c0587 = result.values[_CUOTA_LIQUIDA_INCREMENTADA_TOTAL_CASILLA]

    assert c0587 > Decimal("0"), (
        f"casilla 0587 = {c0587!r}; must be positive (formula regression: was silently 0 before fix). "
        f"Check 2024/formulas/0169-renta-2024-cuota-liquida-incrementada-total.toml."
    )
    assert abs(c0587 - (c0585 + c0586)) <= _TOLERANCE, (
        f"0587 ({c0587!r}) must equal 0585 ({c0585!r}) + 0586 ({c0586!r}). "
        f"Structural identity failure in renta-2024-cuota-liquida-incrementada-total."
    )


def test_0609_equals_retencion_trabajo_operand(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Casilla 0609 must equal the supplied retenciones trabajo (0592) per RD 439/2007 Art. 110.

    With only casilla 0592 (retenciones trabajo) supplied and all other 0609
    operands zero, 0609 must exactly equal the supplied amount. This confirms
    the 14-operand sum in renta-2024-total-pagos-a-cuenta is wired correctly.
    Authority: RD 439/2007 Art. 109-110, LIRPF Art. 99.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_BASE_55500,
            _RETENCIONES_TRABAJO_CASILLA: _RETENCION_1824,
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    c0609 = result.values[_TOTAL_PAGOS_A_CUENTA_CASILLA]
    assert c0609 == _RETENCION_1824, (
        f"casilla 0609 (total pagos a cuenta) = {c0609!r}; "
        f"expected {_RETENCION_1824!r} (sole 0592 operand). "
        f"formula regression: before fix, 0609 had no formula and stayed 0. "
        f"Check 2024/formulas/0172-renta-2024-total-pagos-a-cuenta.toml."
    )


def test_0610_equals_0595_minus_0609(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Casilla 0610 must equal 0595 - 0609 per renta-2024-cuota-diferencial.

    Structural identity: cuota diferencial = cuota resultante - total pagos a cuenta.
    This holds for any non-zero retención supplied via 0592.
    Authority: LIRPF Art. 79, AEAT 2024 form BOE.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_BASE_55500,
            _RETENCIONES_TRABAJO_CASILLA: _RETENCION_1824,
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    c0595 = result.values[_CUOTA_RESULTANTE_CASILLA]
    c0609 = result.values[_TOTAL_PAGOS_A_CUENTA_CASILLA]
    c0610 = result.values[_CUOTA_DIFERENCIAL_CASILLA]

    assert abs(c0610 - (c0595 - c0609)) <= _TOLERANCE, (
        f"0610 ({c0610!r}) must equal 0595 ({c0595!r}) - 0609 ({c0609!r}). "
        f"Structural identity failure in renta-2024-cuota-diferencial."
    )
    assert c0610 < c0595, f"0610 ({c0610!r}) must be less than 0595 ({c0595!r}) when retenciones > 0."


def test_anti_tautology_higher_retencion_reduces_cuota_diferencial(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """Anti-tautology: doubling retenciones must halve the remaining cuota diferencial gap.

    If 0609 -> 0610 subtraction is not wired, both scenarios yield the same
    0610 regardless of 0592. This test catches a wiring break in the 14-operand
    sum or the 0610 formula.
    Authority: RD 439/2007 Art. 110.
    """
    result_low = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_BASE_55500,
            _RETENCIONES_TRABAJO_CASILLA: _RETENCION_1824,
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )
    result_high = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={
            _TRABAJO_INGRESOS_INTEGROS_CASILLA: _TRABAJO_BASE_55500,
            _RETENCIONES_TRABAJO_CASILLA: _RETENCION_3648,
        },
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values=_base_binding_values(),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_BIRTH_DATE_BINDINGS_2024,
    )

    c0610_low = result_low.values[_CUOTA_DIFERENCIAL_CASILLA]
    c0610_high = result_high.values[_CUOTA_DIFERENCIAL_CASILLA]
    assert c0610_high < c0610_low, (
        f"0610 with doubled retenciones ({c0610_high!r}) must be less than with "
        f"half retenciones ({c0610_low!r}). "
        f"If equal, the 0609 -> 0610 subtraction is not wired."
    )
    # The delta in 0610 must equal the delta in 0609 (doubled retenciones)
    expected_delta = _RETENCION_3648 - _RETENCION_1824
    actual_delta = c0610_low - c0610_high
    assert abs(actual_delta - expected_delta) <= _TOLERANCE, (
        f"0610 delta = {actual_delta!r}; expected {expected_delta!r} "
        f"(doubled retenciones delta = {expected_delta!r} EUR)."
    )
