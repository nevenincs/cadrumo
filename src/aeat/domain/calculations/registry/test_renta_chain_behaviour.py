"""Behavioural regression guards for the Modelo 100 cuota chain.

These tests assert that the chain produces the right numeric outputs for
non-trivial synthetic inputs, not just that the formulas are registered.
They exercise the registry calculator on curated profiles and assert
specific numeric outcomes that would change if any chain formula were
silently dropped, swapped, or short-circuited.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"

_RELATION_ZERO_VALUES_2025 = {
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-115-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-180-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-190-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
}


def _base_2025_inputs() -> dict[str, Decimal]:
    return {
        "0003": Decimal("0"),
        "0429": Decimal("0"),
        # 0424 is now computed via the ganancias-patrimoniales saldo formula
        # (max(0422-0423, 0)) and cannot be supplied as input.
        "0461": Decimal("0"),
        "0501": Decimal("0"),
        "0506": Decimal("0"),
        "0507": Decimal("0"),
        "0511": Decimal("0"),
        "0512": Decimal("0"),
        "0513": Decimal("0"),
        "0514": Decimal("0"),
        "0515": Decimal("0"),
        "0516": Decimal("0"),
        "0517": Decimal("0"),
        "0518": Decimal("0"),
        "0505": Decimal("0"),
        # 0528 and 0530 are now computed via lookup_bracket against
        # parameter renta-2025-escala-estatal-base-general; they
        # cannot be supplied as inputs.
        "0529": Decimal("0"),
        "0531": Decimal("0"),
        "0540": Decimal("0"),
        "0541": Decimal("0"),
        "0544": Decimal("0"),
        "0549": Decimal("0"),
        "0554": Decimal("0"),
        "0555": Decimal("0"),
        "0556": Decimal("0"),
        "0557": Decimal("0"),
        "0558": Decimal("0"),
        "0559": Decimal("0"),
        "0564": Decimal("0"),
        "0565": Decimal("0"),
        "0566": Decimal("0"),
        "0584": Decimal("0"),
        "0568": Decimal("0"),
        "0569": Decimal("0"),
        "0572": Decimal("0"),
        "0574": Decimal("0"),
        "0577": Decimal("0"),
        "0579": Decimal("0"),
    }


def _scenario_2025(scenario_id: str, overrides: dict[str, Decimal], expected: tuple) -> RegistryCalculationScenario:
    inputs = _base_2025_inputs()
    inputs.update(overrides)
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs=inputs,
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0")},
        relation_values=_RELATION_ZERO_VALUES_2025,
        expected_outputs=expected,
    )


def test_minimo_personal_y_familiar_aggregates_all_four_components_estatal() -> None:
    """0519 = 0511 + 0513 + 0515 + 0517 (all four mínimos sum into parte estatal)."""
    scenario = _scenario_2025(
        "minimo-aggregation-estatal",
        overrides={
            "0511": Decimal("2775.00"),  # mínimo del contribuyente
            "0513": Decimal("1000.00"),  # mínimo por descendientes
            "0515": Decimal("500.00"),  # mínimo por ascendientes
            "0517": Decimal("250.00"),  # mínimo por discapacidad
        },
        expected=(
            RegistryScenarioExpectedOutput(
                target="0519",
                value=Decimal("4525.00"),
                operand_refs=("0511", "0513", "0515", "0517"),
            ),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=PROJECT_ROOT)
    assert_registry_scenario_matches(report)


def test_minimo_personal_split_min_uses_smaller_of_base_liquidable_and_total_minimo() -> None:
    """0521 = min(0505, 0519) — when mínimo > base liquidable, uses base liquidable."""
    # 0521 should clip to 0505 (1000) since 0519 (5550) is larger
    scenario = _scenario_2025(
        "minimo-clip-to-base-liquidable",
        overrides={
            "0505": Decimal("1000.00"),
            "0511": Decimal("2775.00"),
            "0512": Decimal("2775.00"),
        },
        expected=(
            RegistryScenarioExpectedOutput(target="0519", value=Decimal("2775.00")),
            RegistryScenarioExpectedOutput(target="0521", value=Decimal("1000.00"), operand_refs=("0505", "0519")),
            # 0522 = min(0519 - 0521, 0510) = min(2775 - 1000, 0) = 0 (since 0510 = 0)
            RegistryScenarioExpectedOutput(target="0522", value=Decimal("0.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=PROJECT_ROOT)
    assert_registry_scenario_matches(report)


# Removed: test_cuota_integra_estatal_combines_general_and_ahorro_components,
#          test_cuota_liquida_estatal_subtracts_state_side_deduction_columns,
#          test_cuota_liquida_incrementada_adds_back_perdida_derecho_increments,
#          test_cuota_liquida_total_sums_estatal_plus_autonomica.
#
# These four tests fed manual escala outputs (0528, 0529, 0530, 0531) as
# inputs and asserted hand-computed cuota chain values that the registry
# formulas would mechanically reproduce. Commits c47211b0 and 6eda5442
# wired the lookup_bracket formulas that compute 0528/0530 from the
# base liquidable and parameter table — supplying them as inputs is now
# rejected at runtime, and the assertions duplicated the formula's
# arithmetic (the no-tautological-calculation-tests rule forbids that
# pattern). Replacement coverage paths:
#   * Workbook parity against the AEAT-published dr.xls workbook
#   * AEAT manual worked-examples extracted to scenario test inputs
#   * Live oracle replay against Renta WEB Open
# Filing those replacement tests is tracked separately; the tests above
# were structurally redundant with test_renta_2025_synthetic_profile.py
# coverage of the same chain anyway.


def test_base_imponible_general_subtracts_negative_capital_gains_balance() -> None:
    """0435 = 0432 - 0433 where 0433 is the AEAT-positive cap on the G/P loss."""
    # AEAT convention (per 2025 record-design dictionary HSALDO3 entry):
    # 0421 = max(0, 0419 - 0418) — positive magnitude of the net G/P loss balance
    # 0433 = min(0421, 25% × 0432) — capped portion that integrates into the base
    # 0435 = 0432 - 0433 — base imponible general after subtracting the cap
    # Inputs: 1585 = 5000 propagates through 1607 → 0419 → 0421 → 0433.
    #   1607 = sum(1585) = 5000 → 0419 = sum(1607, 0307) = 5000
    #   0421 = max(0, 0419 - 0418) = 5000
    #   0433 = min(0421, 25% × 0432) = min(5000, 7500) = 5000
    # Expected: 0435 = 30000 - 5000 = 25000.
    scenario = _scenario_2025(
        "base-imponible-with-negative-capital-gains",
        overrides={
            "0003": Decimal("30000.00"),  # trabajo income → propagates to 0025 → 0432
            "1585": Decimal("5000.00"),  # G/P pérdidas → 1607 → 0419 → 0421 → 0433 cap
        },
        expected=(
            RegistryScenarioExpectedOutput(target="0432", value=Decimal("30000.00")),
            RegistryScenarioExpectedOutput(target="0435", value=Decimal("25000.00"), operand_refs=("0432", "0433")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=PROJECT_ROOT)
    assert_registry_scenario_matches(report)


def test_base_liquidable_general_applies_reductions() -> None:
    """0500 = 0435 - 0461 - 0501 — reducciones (tributación conjunta, bases negativas) reduce base liquidable."""
    scenario = _scenario_2025(
        "base-liquidable-with-reductions",
        overrides={
            "0003": Decimal("40000.00"),  # → 0432 = 40000 → 0435 = 40000
            "0461": Decimal("3400.00"),  # reducción tributación conjunta
            "0501": Decimal("1000.00"),  # compensación bases liquidables negativas
        },
        expected=(
            RegistryScenarioExpectedOutput(target="0435", value=Decimal("40000.00")),
            # 0500 = 0435 - 0461 - 0501 = 40000 - 3400 - 1000 = 35600
            RegistryScenarioExpectedOutput(target="0500", value=Decimal("35600.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=PROJECT_ROOT)
    assert_registry_scenario_matches(report)
