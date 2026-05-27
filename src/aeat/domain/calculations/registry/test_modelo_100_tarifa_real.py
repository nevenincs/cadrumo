"""Regression test for Modelo 100 2024 cuota íntegra — Cluster T fix (S115).

Cluster T root cause: casillas 0511/0512 (mínimo del contribuyente
estatal/autonómica) lacked a formula in the 2024 registry revision, so the
engine silently defaulted them to 0.  The fix (S114) adds parameter
``renta-2024-minimo-contribuyente-base-2024`` (5,550 EUR, LIRPF Art. 57) and
two computed formulas that populate 0511/0512.

This test uses a Pere-shape profile (single taxpayer, Catalonia, base liquidable
general 35,400 EUR, no ahorro base) and asserts the cuota íntegra values derived
from the published LIRPF 2024 tax tables — not from re-running the formula engine.

Expected values are derived from the official LIRPF 2024 escala general and the
AEAT Renta 2024 Manual worked examples cross-checked against Ley 35/2006.

Calculation authority:
- LIRPF Art. 62–63 (escala estatal base general)
- LIRPF Art. 57 (mínimo del contribuyente: 5,550 EUR flat)
- LIRPF Art. 74–75 (escala autonómica, Cataluña 2024)
- AEAT Renta 2024 Manual, Part 1, "Liquidación del impuesto"
- BOE Orden HAC-563-2024 (confirming 5,550 EUR unchanged for 2024)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from . import calculate_registry_snapshot
from ._authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

# -----------------------------------------------------------------------
# Expected values — derived from LIRPF 2024 tables, not engine output.
#
# Base liquidable general: 35,400 EUR (Pere shape per S115 spec).
#
# Escala estatal (LIRPF Art. 63, unchanged 2024):
#   0–12,450        @ 9.500% → 1,182.75
#   12,450–20,200   @ 12.00% → 930.00   (cumul 2,112.75)
#   20,200–35,200   @ 15.00% → 2,250.00 (cumul 4,362.75)
#   35,200–35,400   @ 18.50% → 37.00    (cumul 4,399.75)
#
# Mínimo del contribuyente (LIRPF Art. 57): 5,550 EUR.
# Tarifa on mínimo (escala estatal, same brackets):
#   0–5,550 @ 9.500% = 527.25
#
# Cuota íntegra estatal (LIRPF Art. 62):
#   0545 = 4,399.75 − 527.25 = 3,872.50
#
# Escala autonómica Cataluña 2024 (LIRPF Art. 74, Ley Cataluña 5/2020):
#   0–12,450.00       @ 10.500% → 1,307.25
#   12,450–17,707.20  @ 12.000% → 630.86   (cumul 1,938.11)
#   17,707.20–21,000  @ 14.000% → 460.99   (cumul 2,399.10)
#   21,000–33,007.20  @ 15.000% → 1,801.08 (cumul 4,200.18)
#   33,007.20–35,400  @ 18.800% → 449.85   (cumul 4,650.03)
#
# Mínimo del contribuyente (same 5,550 EUR, autonómica):
#   0–5,550 @ 10.500% = 582.75
#
# Cuota íntegra autonómica (LIRPF Art. 75):
#   0546 = 4,650.03 − 582.75 = 4,067.28
# -----------------------------------------------------------------------

_BASE_LIQUIDABLE_GENERAL = Decimal("35400")
_EXPECTED_CUOTA_INTEGRA_ESTATAL = Decimal("3872.50")
_EXPECTED_CUOTA_INTEGRA_AUTONOMICA = Decimal("4067.28")
_EXPECTED_MINIMO_CONTRIBUYENTE = Decimal("5550.00")
_TOLERANCE = Decimal("0.01")


@pytest.fixture
def m100_2024_snapshot(registry_authority: ValidatedRegistryAuthority):
    return registry_authority.snapshot("100", filing_year=2024, period="0A")


def test_m100_2024_minimo_contribuyente_computed_not_zero(m100_2024_snapshot) -> None:
    """After S114 fix, casilla 0511 must equal the LIRPF Art. 57 base value.

    This is the regression guard for Cluster T: before S114, casilla 0511
    defaulted to 0 (no formula, no binding in 2024 revision). After S114 it
    is computed from the parameter ``renta-2024-minimo-contribuyente-base-2024``.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0505": _BASE_LIQUIDABLE_GENERAL},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values={
            "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        },
    )

    assert result.values["0511"] == _EXPECTED_MINIMO_CONTRIBUYENTE, (
        f"casilla 0511 (mínimo contribuyente estatal) is {result.values['0511']!r}; "
        f"expected {_EXPECTED_MINIMO_CONTRIBUYENTE!r} per LIRPF Art. 57. "
        f"If this is 0.00 the Cluster-T regression has re-appeared: "
        f"check 2024/formulas/0166-renta-2024-minimo-contribuyente-estatal.toml "
        f"and 2024/parameters/0030-renta-2024-minimo-contribuyente-base-2024.toml."
    )
    assert result.values["0512"] == _EXPECTED_MINIMO_CONTRIBUYENTE, (
        f"casilla 0512 (mínimo contribuyente autonómica) is {result.values['0512']!r}; "
        f"expected {_EXPECTED_MINIMO_CONTRIBUYENTE!r} per LIRPF Art. 57 / Art. 74."
    )


def test_m100_2024_cuota_integra_estatal_matches_lirpf_tables(m100_2024_snapshot) -> None:
    """Cuota íntegra estatal (0545) must equal the LIRPF 2024 table result.

    Expected derivation (LIRPF Art. 62–63, escala estatal 2024):
      tarifa(35400) − tarifa(5550) = 4399.75 − 527.25 = 3,872.50 EUR.

    This was previously over-stated as 3,132.75 EUR (Cluster T: mínimo personal
    = 0, so the mínimo deduction step was silently skipped).
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0505": _BASE_LIQUIDABLE_GENERAL},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values={
            "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        },
    )

    cuota_estatal = result.values["0545"]
    assert abs(cuota_estatal - _EXPECTED_CUOTA_INTEGRA_ESTATAL) <= _TOLERANCE, (
        f"cuota íntegra estatal (0545) = {cuota_estatal!r}; "
        f"expected {_EXPECTED_CUOTA_INTEGRA_ESTATAL!r} per LIRPF 2024 tables. "
        f"Cluster T regression: if 0545 = 3132.75 the mínimo personal deduction "
        f"is not being applied (0511/0512 zero)."
    )


def test_m100_2024_cuota_integra_autonomica_cataluna_matches_lirpf_tables(
    m100_2024_snapshot,
) -> None:
    """Cuota íntegra autonómica (0546) must equal the Cataluña 2024 table result.

    Expected derivation (LIRPF Art. 74–75, Ley 5/2020 Cataluña escala 2024):
      tarifa_cat(35400) − tarifa_cat(5550) = 4650.03 − 582.75 = 4,067.28 EUR.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0505": _BASE_LIQUIDABLE_GENERAL},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values={
            "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        },
    )

    cuota_autonomica = result.values["0546"]
    assert abs(cuota_autonomica - _EXPECTED_CUOTA_INTEGRA_AUTONOMICA) <= _TOLERANCE, (
        f"cuota íntegra autonómica (0546) = {cuota_autonomica!r}; "
        f"expected {_EXPECTED_CUOTA_INTEGRA_AUTONOMICA!r} per LIRPF 2024 / Cataluña tables."
    )


def test_m100_2024_cuota_integra_estatal_is_positive(m100_2024_snapshot) -> None:
    """Any non-zero base liquidable general must produce positive cuota íntegra.

    This is the weakest possible guard: cuota must be > 0 for a taxpayer
    with a taxable base above the mínimo personal threshold (35,400 > 5,550).
    Cluster T manifested precisely here — the cuota was reported as zero or
    massively understated because the mínimo deduction was 0.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0505": _BASE_LIQUIDABLE_GENERAL},
        date_context={"filing_period": date(2024, 12, 31)},
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "cataluna"},
        binding_values={
            "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        },
    )

    assert result.values["0545"] > Decimal("0"), (
        "cuota íntegra estatal (0545) must be positive for base_liquidable > mínimo"
    )
    assert result.values["0546"] > Decimal("0"), (
        "cuota íntegra autonómica (0546) must be positive for base_liquidable > mínimo"
    )
