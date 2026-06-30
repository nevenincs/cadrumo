"""Behavioural regression guards for the Modelo 100 cuota chain.

These tests assert that the chain produces the right numeric outputs for
non-trivial synthetic inputs, not just that the formulas are registered.
They exercise the registry calculator on curated profiles and assert
specific numeric outcomes that would change if any chain formula were
silently dropped, swapped, or short-circuited.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path

# Importing the renta package registers the first-slice routing cross-domain
# snapshot check required by Modelo 100 parity scenarios run via _scenarios.
from .. import CasillaId, validated_casilla_id
from .._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test_renta_chain_behaviour casilla id")
    except ValueError as exc:
        raise AssertionError(f"scenario fixture casilla key {value!r} is not a canonical casilla.id") from exc


_C0003 = _casilla_id("0003")
_C0426 = _casilla_id("0426")
_C0429 = _casilla_id("0429")
_C0432 = _casilla_id("0432")
_C0433 = _casilla_id("0433")
_C0435 = _casilla_id("0435")
_C0461 = _casilla_id("0461")
_C0467 = _casilla_id("0467")
_C0468 = _casilla_id("0468")
_C0500 = _casilla_id("0500")
_C0501 = _casilla_id("0501")
_C0505 = _casilla_id("0505")
_C0506 = _casilla_id("0506")
_C0507 = _casilla_id("0507")
_C0511 = _casilla_id("0511")
_C0513 = _casilla_id("0513")
_C0514 = _casilla_id("0514")
_C0515 = _casilla_id("0515")
_C0516 = _casilla_id("0516")
_C0517 = _casilla_id("0517")
_C0518 = _casilla_id("0518")
_C0519 = _casilla_id("0519")
_C0521 = _casilla_id("0521")
_C0522 = _casilla_id("0522")
_C0544 = _casilla_id("0544")
_C0549 = _casilla_id("0549")
_C0554 = _casilla_id("0554")
_C0555 = _casilla_id("0555")
_C0556 = _casilla_id("0556")
_C0557 = _casilla_id("0557")
_C0558 = _casilla_id("0558")
_C0559 = _casilla_id("0559")
_C0564 = _casilla_id("0564")
_C0565 = _casilla_id("0565")
_C0566 = _casilla_id("0566")
_C0568 = _casilla_id("0568")
_C0569 = _casilla_id("0569")
_C0572 = _casilla_id("0572")
_C0574 = _casilla_id("0574")
_C0577 = _casilla_id("0577")
_C0579 = _casilla_id("0579")
_C0584 = _casilla_id("0584")
_C1389 = _casilla_id("1389")
_C1585 = _casilla_id("1585")

_RELATION_ZERO_VALUES_2025 = {
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-190-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
}


def _base_2025_inputs() -> dict[CasillaId, Decimal]:
    return {
        _C0003: Decimal("0"),
        _C0429: Decimal("0"),
        # 0424 is now computed via the ganancias-patrimoniales saldo formula
        # (max(0422-0423, 0)) and cannot be supplied as input.
        # 0461 is now computed via renta-2025-reduccion-art-84-conjunta
        # (declaration_type + minor_children_in_unit binding) and cannot be supplied as input.
        _C0501: Decimal("0"),
        _C0506: Decimal("0"),
        _C0507: Decimal("0"),
        # 0511 and 0512 are now computed via lookup_parameter against
        # renta-2025-minimo-contribuyente-base-2025 (state and per-CCAA
        # autonomic), and cannot be supplied as inputs.
        _C0513: Decimal("0"),
        _C0514: Decimal("0"),
        _C0515: Decimal("0"),
        _C0516: Decimal("0"),
        _C0517: Decimal("0"),
        _C0518: Decimal("0"),
        # 0505 is now computed via renta-2025-base-liquidable-general-sometida-a-gravamen
        # (max(0, 0500 - 0527)) and cannot be supplied as input.
        # 0528, 0529, 0530, and 0531 are now computed via lookup_bracket
        # / lookup_bracket_by_ccaa against the state and Madrid autonomic
        # bracket parameters; they cannot be supplied as inputs.
        # 0536, 0538, and 0540 are now computed via the art.66 ahorro-base
        # estatal escala (lookup_bracket / subtract); 0537, 0539, and 0541
        # via the art.76 ahorro-base autonomica escala; they cannot be
        # supplied as inputs.
        _C0544: Decimal("0"),
        _C0549: Decimal("0"),
        _C0554: Decimal("0"),
        _C0555: Decimal("0"),
        _C0556: Decimal("0"),
        _C0557: Decimal("0"),
        _C0558: Decimal("0"),
        _C0559: Decimal("0"),
        _C0564: Decimal("0"),
        _C0565: Decimal("0"),
        _C0566: Decimal("0"),
        _C0584: Decimal("0"),
        _C0568: Decimal("0"),
        _C0569: Decimal("0"),
        _C0572: Decimal("0"),
        _C0574: Decimal("0"),
        _C0577: Decimal("0"),
        _C0579: Decimal("0"),
    }


def _scenario_2025(
    scenario_id: str,
    overrides: dict[CasillaId, Decimal],
    expected: tuple[RegistryScenarioExpectedOutput, ...],
) -> RegistryCalculationScenario:
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
            # declaration_type = 1 (individual) → 0461 = 0 by default in all base scenarios
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            # not married → marriage casillas = 0
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            # BIN-pendiente fresh-filer baseline (2025 binding).
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values=_RELATION_ZERO_VALUES_2025,
        # Age 44 at year-end 2025 → no age increment → 0511 = 5,550 base only.
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
        expected_outputs=expected,
    )


def test_minimo_personal_y_familiar_aggregates_all_four_components_estatal() -> None:
    """0519's registry formula declares an op=sum of the four mínimos casillas.

    Structural assertion only — verifies the formula's expression tree
    shape (op + operand wiring) rather than re-summing the operands and
    asserting the arithmetic matches. The runtime's arithmetic is
    covered by the live Renta WEB Open replay parity tests.
    """

    from .._loader import load_registry_tree

    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "100")
    revision = modelo.revisions["2025"]
    formula = next(f for f in revision.formulas if f.target_casilla_id == _C0519)
    expression = formula.expression.model_dump(exclude_none=True)
    assert expression.get("op") == "sum"
    operand_casillas = {arg.get("casilla_id") for arg in expression.get("args", []) if arg.get("casilla_id")}
    assert operand_casillas == {_C0511, _C0513, _C0515, _C0517}


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
        overrides={_C0003: Decimal("1000.00")},
        expected=(
            RegistryScenarioExpectedOutput(target_casilla_id=_C0500, value=Decimal("1000.00")),
            RegistryScenarioExpectedOutput(target_casilla_id=_C0505, value=Decimal("1000.00")),
            RegistryScenarioExpectedOutput(target_casilla_id=_C0519, value=expected_minimo),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_C0521,
                value=Decimal("1000.00"),
                operand_refs=(_C0505, _C0519),
                operand_casilla_refs=(_C0505, _C0519),
            ),
            # 0522 = min(0519 - 0521, 0510) = min(5550 - 1000, 0) = 0 (0510 default 0)
            RegistryScenarioExpectedOutput(target_casilla_id=_C0522, value=Decimal("0.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_base_imponible_general_subtracts_negative_capital_gains_balance() -> None:
    """0435 = max(0, 0432 - 0433 - 1389) where 0433 is the AEAT-positive cap on the G/P loss."""
    # AEAT convention (per 2025 record-design dictionary HSALDO3 entry):
    # 0421 = max(0, 0419 - 0418) — positive magnitude of the net G/P loss balance
    # 0433 = min(0421, 25% of 0432) — capped portion that integrates into the base
    # 0435 = max(0, 0432 - 0433 - 1389) — base imponible general after subtracting
    #   the cap AND the art. 48 prior-negative-base compensation applied (1389),
    #   which is zero here (no prior negative general base seeded).
    # Inputs: 1585 = 5000 propagates through 1607 → 0419 → 0421 → 0433.
    #   1607 = sum(1585) = 5000 → 0419 = sum(1607, 0307) = 5000
    #   0421 = max(0, 0419 - 0418) = 5000
    #   0433 = min(0421, 25% of 0432) = min(5000, 7500) = 5000
    # Expected: 0435 = 30000 - 5000 - 0 = 25000.
    scenario = _scenario_2025(
        "base-imponible-with-negative-capital-gains",
        overrides={
            _C0003: Decimal("30000.00"),  # trabajo income → propagates to 0025 → 0432
            _C1585: Decimal("5000.00"),  # G/P pérdidas → 1607 → 0419 → 0421 → 0433 cap
        },
        expected=(
            RegistryScenarioExpectedOutput(target_casilla_id=_C0432, value=Decimal("30000.00")),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_C0435,
                value=Decimal("25000.00"),
                operand_refs=(_C0432, _C0433, _C1389),
                operand_casilla_refs=(_C0432, _C0433, _C1389),
            ),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_base_liquidable_general_applies_reductions() -> None:
    """0500 = 0435 - 0461 - 0501 — reducciones (tributación conjunta, bases negativas) reduce base liquidable.

    0461 is now computed by renta-2025-reduccion-art-84-conjunta from binding values.
    declaration_type = 2 (conjunta) + minor_children_in_unit = 0 (tipo-1 matrimonio) → 0461 = €3,400.
    """
    base_inputs = _base_2025_inputs()
    base_inputs.update(
        {
            _C0003: Decimal("40000.00"),  # → 0432 = 40000 → 0435 = 40000
            _C0501: Decimal("1000.00"),  # compensación bases liquidables negativas
        },
    )
    scenario = RegistryCalculationScenario(
        id="base-liquidable-with-reductions",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs=base_inputs,
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            # declaration_type = 2 (conjunta) + minor_children_in_unit = 0 → 0461 = 3400
            "renta-2025-profile-declaration-type": Decimal("2"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            # married full year (required by marriage-axis formulas in revision)
            "renta-2025-profile-marriage-full-year": Decimal("1"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            # BIN-pendiente fresh-filer baseline (2025 binding).
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values=_RELATION_ZERO_VALUES_2025,
        # Age 44 at year-end 2025 → no age increment → 0511 = 5,550 base only.
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(target_casilla_id=_C0435, value=Decimal("40000.00")),
            RegistryScenarioExpectedOutput(target_casilla_id=_C0461, value=Decimal("3400.00")),
            # 0500 = 0435 - 0461 - 0501 = 40000 - 3400 - 1000 = 35600
            RegistryScenarioExpectedOutput(target_casilla_id=_C0500, value=Decimal("35600.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_plan_de_empleo_reduccion_below_caps_full_amount() -> None:
    """0468 = min(0467, 10000, 30% * 0432) — aportación below both caps, full reducción applies.

    Oracle derivation (Art. 52 LIRPF, AEAT Renta 2025 Manual Parte 1):
      trabajo rendimientos (0003) = 56,500 → 0025 = 0432 = 56,500
      30% cap = 0.30 * 56,500 = 16,950
      plan de empleo aportación (0426) = 4,200 → 0467 = 4,200
      0468 = min(4200, 10000, 16950) = 4,200   (below both caps)
      0435 = 56,500 (no negative G/P balance)
      0461 = 0 (individual declaration)
      0501 = 0 (no prior negative bases)
      0500 = 56,500 - 4,200 - 0 - 0 = 52,300
    """
    scenario = _scenario_2025(
        "plan-empleo-reduccion-below-caps",
        overrides={
            _C0003: Decimal("56500.00"),  # trabajo → 0432 = 56,500
            _C0426: Decimal("4200.00"),  # plan de empleo aportación → 0467 = 4,200
        },
        expected=(
            RegistryScenarioExpectedOutput(target_casilla_id=_C0467, value=Decimal("4200.00")),
            RegistryScenarioExpectedOutput(target_casilla_id=_C0468, value=Decimal("4200.00")),
            RegistryScenarioExpectedOutput(target_casilla_id=_C0500, value=Decimal("52300.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_plan_de_empleo_reduccion_capped_at_10000() -> None:
    """0468 capped at €10,000 absolute limit when aportación exceeds the cap.

    Oracle derivation (Art. 52 LIRPF):
      trabajo rendimientos (0003) = 80,000 → 0432 = 80,000
      30% cap = 0.30 * 80,000 = 24,000
      plan de empleo aportación (0426) = 15,000 → 0467 = 15,000
      0468 = min(15000, 10000, 24000) = 10,000   (€10k absolute cap applies)
      0500 = 80,000 - 10,000 = 70,000
    """
    scenario = _scenario_2025(
        "plan-empleo-reduccion-capped-10k",
        overrides={
            _C0003: Decimal("80000.00"),  # trabajo → 0432 = 80,000
            _C0426: Decimal("15000.00"),  # plan de empleo aportación → 0467 = 15,000
        },
        expected=(
            RegistryScenarioExpectedOutput(target_casilla_id=_C0467, value=Decimal("15000.00")),
            # 0468 = min(15000, 10000, 24000) = 10,000
            RegistryScenarioExpectedOutput(target_casilla_id=_C0468, value=Decimal("10000.00")),
            RegistryScenarioExpectedOutput(target_casilla_id=_C0500, value=Decimal("70000.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)
