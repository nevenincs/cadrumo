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

from aeat.core.resources import bundled_path

from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")

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
        # 0511 and 0512 are now computed via lookup_parameter against
        # renta-2025-minimo-contribuyente-base-2025 (state and per-CCAA
        # autonomic), and cannot be supplied as inputs.
        "0513": Decimal("0"),
        "0514": Decimal("0"),
        "0515": Decimal("0"),
        "0516": Decimal("0"),
        "0517": Decimal("0"),
        "0518": Decimal("0"),
        # 0505 is now computed via renta-2025-base-liquidable-general-sometida-a-gravamen
        # (max(0, 0500 - 0527)) and cannot be supplied as input.
        # 0528, 0529, 0530, and 0531 are now computed via lookup_bracket
        # / lookup_bracket_by_ccaa against the state and Madrid autonomic
        # bracket parameters; they cannot be supplied as inputs.
        # 0536, 0538, and 0540 are now computed via the art.66 ahorro-base
        # estatal escala (lookup_bracket / subtract); 0537, 0539, and 0541
        # via the art.76 ahorro-base autonomica escala; they cannot be
        # supplied as inputs.
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
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values=_RELATION_ZERO_VALUES_2025,
        expected_outputs=expected,
    )


def test_minimo_personal_y_familiar_aggregates_all_four_components_estatal() -> None:
    """0519's registry formula declares an op=sum of the four mínimos casillas.

    Structural assertion only — verifies the formula's expression tree
    shape (op + operand wiring) rather than re-summing the operands and
    asserting the arithmetic matches. The runtime's arithmetic is
    covered by the live Renta WEB Open replay parity tests.
    """

    from ._loader import load_registry_tree

    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "100")
    revision = modelo.revisions["2025"]
    formula = next(f for f in revision.formulas if f.target == "0519")
    expression = formula.expression.model_dump(exclude_none=True)
    assert expression.get("op") == "sum"
    operand_casillas = {arg.get("casilla") for arg in expression.get("args", []) if arg.get("casilla")}
    assert operand_casillas == {"0511", "0513", "0515", "0517"}


def test_minimo_personal_split_min_uses_smaller_of_base_liquidable_and_total_minimo() -> None:
    """0521 = min(0505, 0519) — when mínimo > base liquidable, uses base liquidable.

    0511 (estatal mínimo contribuyente) is computed by the registry from the
    LIRPF art. 57 parameter ``renta-2025-minimo-contribuyente-base-2025`` =
    €5,550. The other contributing casillas (0513/0515/0517) default to 0
    for a contributor with no age/discapacidad/descendientes mínimos, so
    0519 = 5550.

    0505 is computed as max(0, 0500 - 0527). Supplying 0003 (rendimientos trabajo)
    = 1000 with all reductions and anualidades at 0 produces 0505 = 1000.
    With 0505 = 1000 < 0519 = 5550, 0521 must clip to 0505 = 1000.
    """
    expected_minimo = Decimal("5550.00")
    scenario = _scenario_2025(
        "minimo-clip-to-base-liquidable",
        # 0003 → 0025 → 0432 = 1000 → 0435 = 1000 → 0500 = 1000 (no reductions)
        # → 0505 = max(0, 1000 - 0) = 1000  (0527 anualidades alimentos = 0)
        overrides={"0003": Decimal("1000.00")},
        expected=(
            RegistryScenarioExpectedOutput(target="0500", value=Decimal("1000.00")),
            RegistryScenarioExpectedOutput(target="0505", value=Decimal("1000.00")),
            RegistryScenarioExpectedOutput(target="0519", value=expected_minimo),
            RegistryScenarioExpectedOutput(target="0521", value=Decimal("1000.00"), operand_refs=("0505", "0519")),
            # 0522 = min(0519 - 0521, 0510) = min(5550 - 1000, 0) = 0 (0510 default 0)
            RegistryScenarioExpectedOutput(target="0522", value=Decimal("0.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_base_imponible_general_subtracts_negative_capital_gains_balance() -> None:
    """0435 = 0432 - 0433 where 0433 is the AEAT-positive cap on the G/P loss."""
    # AEAT convention (per 2025 record-design dictionary HSALDO3 entry):
    # 0421 = max(0, 0419 - 0418) — positive magnitude of the net G/P loss balance
    # 0433 = min(0421, 25% of 0432) — capped portion that integrates into the base
    # 0435 = 0432 - 0433 — base imponible general after subtracting the cap
    # Inputs: 1585 = 5000 propagates through 1607 → 0419 → 0421 → 0433.
    #   1607 = sum(1585) = 5000 → 0419 = sum(1607, 0307) = 5000
    #   0421 = max(0, 0419 - 0418) = 5000
    #   0433 = min(0421, 25% of 0432) = min(5000, 7500) = 5000
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
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
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
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)
