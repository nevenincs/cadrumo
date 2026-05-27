"""Oracle tests for M100 casilla 0511 — mínimo del contribuyente (parte estatal).

Ground truth: Art. 57.1.b LIRPF + AEAT renta manual (both 2024 and 2025
editions).  Age is reckoned at 31 December of the filing year (year-end).

    Under 65         →  5 550,00 €  (base only, Art. 57.1.a)
    Age 65-74        ->  6 700,00 EUR  (5 550 + 1 150, Art. 57.1.b primer tramo)
    Age ≥ 75         →  8 100,00 €  (5 550 + 1 150 + 1 400, Art. 57.1.b segundo tramo)

Anti-tautology: a birth_date that crosses an age threshold must change the
computed 0511 value; the test verifies strict inequality so a broken formula
that always returns the same value cannot pass.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.resources import bundled_path

from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()

# Shared relation values required by the 2024 snapshot (zero - not exercised).
_REL_2024 = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-115-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}

# Shared relation values required by the 2025 snapshot (zero - not exercised).
_REL_2025 = {
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-115-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
}


def _scenario_2024(
    scenario_id: str,
    birth_date: date,
    expected_0511: Decimal,
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2024",
        filing_year=2024,
        period="0A",
        inputs={},
        binding_values={
            "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            # declaration_type = 1 (individual) → 0461 computed = 0
            "renta-2024-profile-declaration-type": Decimal("1"),
            "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
        },
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2024,
        date_context={"filing_period": date(2024, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": birth_date},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0511",
                value=expected_0511,
                legal_refs=(
                    "ley-35-2006:art-56",
                    "ley-35-2006:art-57",
                ),
            ),
        ),
    )


def _scenario_2025(
    scenario_id: str,
    birth_date: date,
    expected_0511: Decimal,
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={},
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            # declaration_type = 1 (individual) → 0461 computed = 0
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2025,
        date_context={"filing_period": date(2025, 12, 31)},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": birth_date},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0511",
                value=expected_0511,
                legal_refs=(
                    "ley-35-2006:art-56",
                    "ley-35-2006:art-57",
                    "orden-hac-277-2026:art-3",
                ),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# 2024 oracle tests — Art. 57.1.b LIRPF, three age brackets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("birth_date", "expected", "label"),
    [
        # Born 1959-03-15: turns 65 on 15 March 2024 → age at year-end = 65
        (date(1959, 3, 15), Decimal("6700.00"), "age-65-primer-tramo"),
        # Born 1949-03-15: turns 75 on 15 March 2024 → age at year-end = 75
        (date(1949, 3, 15), Decimal("8100.00"), "age-75-segundo-tramo"),
        # Born 1965-01-01: turns 59 in 2024 → under 65, base only
        (date(1965, 1, 1), Decimal("5550.00"), "under-65-base-only"),
        # Born 1959-12-15: turns 65 on 15 Dec 2024, still 65 at year-end
        (date(1959, 12, 15), Decimal("6700.00"), "age-65-december-born"),
    ],
)
def test_0511_age_bracket_2024(birth_date: date, expected: Decimal, label: str) -> None:
    """Casilla 0511 returns the correct age-derived amount for 2024 filing year.

    Values are grounded in Art. 57.1.b LIRPF and the AEAT renta 2024 manual
    (section Mínimo del contribuyente).  Base 5 550 €, +1 150 € for age ≥ 65,
    +1 400 € additional for age ≥ 75.
    """
    scenario = _scenario_2024(
        f"m100-2024-0511-{label}",
        birth_date=birth_date,
        expected_0511=expected,
    )
    report = run_registry_calculation_scenario(
        scenario,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    assert_registry_scenario_matches(report)


# ---------------------------------------------------------------------------
# 2025 oracle tests — same brackets apply under orden-hac-277-2026
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("birth_date", "expected", "label"),
    [
        (date(1960, 3, 15), Decimal("6700.00"), "age-65-primer-tramo"),
        (date(1950, 3, 15), Decimal("8100.00"), "age-75-segundo-tramo"),
        (date(1966, 1, 1), Decimal("5550.00"), "under-65-base-only"),
    ],
)
def test_0511_age_bracket_2025(birth_date: date, expected: Decimal, label: str) -> None:
    """Casilla 0511 returns the correct age-derived amount for 2025 filing year."""
    scenario = _scenario_2025(
        f"m100-2025-0511-{label}",
        birth_date=birth_date,
        expected_0511=expected,
    )
    report = run_registry_calculation_scenario(
        scenario,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    assert_registry_scenario_matches(report)


# ---------------------------------------------------------------------------
# Anti-tautology: changing birth_date across a threshold changes 0511
# ---------------------------------------------------------------------------


def test_0511_birth_date_change_alters_value_2024() -> None:
    """Moving birth_date across the 65-year threshold changes casilla 0511.

    Proves the formula is genuinely age-sensitive and does not return a
    constant regardless of date input.
    """
    under_65_scenario = _scenario_2024(
        "m100-2024-0511-anti-tautology-under-65",
        birth_date=date(1965, 1, 1),  # 59 at year-end 2024
        expected_0511=Decimal("5550.00"),
    )
    over_65_scenario = _scenario_2024(
        "m100-2024-0511-anti-tautology-over-65",
        birth_date=date(1959, 3, 15),  # 65 at year-end 2024
        expected_0511=Decimal("6700.00"),
    )

    report_under = run_registry_calculation_scenario(
        under_65_scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT
    )
    report_over = run_registry_calculation_scenario(
        over_65_scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT
    )

    value_under_65 = report_under.calculation.values.get("0511")
    value_over_65 = report_over.calculation.values.get("0511")

    assert value_under_65 is not None, "0511 missing from result (under-65 scenario)"
    assert value_over_65 is not None, "0511 missing from result (over-65 scenario)"
    assert value_under_65 != value_over_65, (
        f"0511 must differ across the 65-year threshold: "
        f"under-65={value_under_65}, over-65={value_over_65}"
    )
