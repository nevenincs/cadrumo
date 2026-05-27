"""Oracle tests for M100 casilla 0461 — reducción Art. 84 LIRPF por tributación conjunta.

Ground truth: Art. 84 Ley 35/2006 (LIRPF) — reducción en base imponible por
tributación conjunta:

    Unidad familiar tipo 1 (matrimonio, Art. 82.1): €3,400 reducción.
    Unidad familiar tipo 2 (monoparental, Art. 82.2): €0 via this casilla
        (tipo-2 reducción €2,150 applies through Art. 81 into a separate casilla).
    Individual (declaration_type != 2): €0.

The formula ``renta-{year}-reduccion-art-84-conjunta`` derives the reducción from
two profile bindings:
  - ``renta-{year}-profile-declaration-type`` (Decimal "1"=individual, "2"=conjunta)
  - ``renta-{year}-profile-family-minor-children-in-unit`` (Decimal "0"=no, "1"=yes)

Anti-tautology: flipping declaration_type from "2" to "1" must change 0461 from
€3,400 to €0. A formula that returns a constant would produce a false negative
for both values, but not a sign-change.
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

_REL_2024 = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-115-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}

_REL_2025 = {
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-115-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
}

_BASE_BINDINGS_2024 = {
    "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
}

_BASE_BINDINGS_2025 = {
    "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
}


def _scenario_2024(
    scenario_id: str,
    declaration_type: Decimal,
    minor_children_in_unit: Decimal,
    expected_0461: Decimal,
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2024",
        filing_year=2024,
        period="0A",
        inputs={},
        binding_values={
            **_BASE_BINDINGS_2024,
            "renta-2024-profile-declaration-type": declaration_type,
            "renta-2024-profile-family-minor-children-in-unit": minor_children_in_unit,
        },
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2024,
        date_context={"filing_period": date(2024, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0461",
                value=expected_0461,
                legal_refs=("ley-35-2006:art-82", "ley-35-2006:art-83", "ley-35-2006:art-84"),
            ),
        ),
    )


def _scenario_2025(
    scenario_id: str,
    declaration_type: Decimal,
    minor_children_in_unit: Decimal,
    expected_0461: Decimal,
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={},
        binding_values={
            **_BASE_BINDINGS_2025,
            "renta-2025-profile-declaration-type": declaration_type,
            "renta-2025-profile-family-minor-children-in-unit": minor_children_in_unit,
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2025,
        date_context={"filing_period": date(2025, 12, 31)},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0461",
                value=expected_0461,
                legal_refs=("ley-35-2006:art-82", "ley-35-2006:art-83", "ley-35-2006:art-84"),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# 2024 oracle tests
# ---------------------------------------------------------------------------


def test_0461_conjunta_tipo_1_matrimonio_yields_3400_2024() -> None:
    """declaration_type=2 (conjunta) + minor_children_in_unit=0 (tipo-1 matrimonio) → 0461 = €3,400.

    Oracle: Art. 84.2.1 LIRPF — unidad familiar tipo 1 (matrimonio) electing
    tributación conjunta receives reducción €3,400 in base imponible general.
    Source: AEAT Renta 2024 Manual, section Tributación conjunta, cuadro.
    """
    scenario = _scenario_2024(
        "m100-2024-0461-conjunta-tipo-1-3400",
        declaration_type=Decimal("2"),
        minor_children_in_unit=Decimal("0"),
        expected_0461=Decimal("3400.00"),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0461_individual_yields_0_2024() -> None:
    """declaration_type=1 (individual) → 0461 = €0.

    Oracle: Art. 84 LIRPF applies only to tributación conjunta (declaration_type=2).
    Individual declarations receive no reducción por unidad familiar.
    """
    scenario = _scenario_2024(
        "m100-2024-0461-individual-zero",
        declaration_type=Decimal("1"),
        minor_children_in_unit=Decimal("0"),
        expected_0461=Decimal("0.00"),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0461_conjunta_tipo_2_monoparental_yields_0_2024() -> None:
    """declaration_type=2 (conjunta) + minor_children_in_unit=1 (tipo-2 monoparental) → 0461 = €0.

    Oracle: Art. 82.2 LIRPF tipo-2 (monoparental) — the €2,150 reducción (Art. 81)
    flows through a separate casilla, not 0461. Casilla 0461 must remain €0 for tipo-2.
    """
    scenario = _scenario_2024(
        "m100-2024-0461-conjunta-tipo-2-monoparental-zero",
        declaration_type=Decimal("2"),
        minor_children_in_unit=Decimal("1"),
        expected_0461=Decimal("0.00"),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0461_anti_tautology_declaration_type_change_2024() -> None:
    """Changing declaration_type from 2 to 1 must flip 0461 from €3,400 to €0.

    Anti-tautology: a formula that returns a constant cannot pass both this
    and test_0461_conjunta_tipo_1_matrimonio_yields_3400_2024 simultaneously.
    """
    conjunta_scenario = _scenario_2024(
        "m100-2024-0461-anti-tautology-conjunta",
        declaration_type=Decimal("2"),
        minor_children_in_unit=Decimal("0"),
        expected_0461=Decimal("3400.00"),
    )
    individual_scenario = _scenario_2024(
        "m100-2024-0461-anti-tautology-individual",
        declaration_type=Decimal("1"),
        minor_children_in_unit=Decimal("0"),
        expected_0461=Decimal("0.00"),
    )
    for scenario in (conjunta_scenario, individual_scenario):
        report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
        assert_registry_scenario_matches(report)

    conjunta_report = run_registry_calculation_scenario(
        conjunta_scenario,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    individual_report = run_registry_calculation_scenario(
        individual_scenario,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    assert conjunta_report.calculation.values["0461"] != individual_report.calculation.values["0461"], (
        "0461 must differ between declaration_type=2 and declaration_type=1"
    )


# ---------------------------------------------------------------------------
# 2025 oracle tests
# ---------------------------------------------------------------------------


def test_0461_conjunta_tipo_1_matrimonio_yields_3400_2025() -> None:
    """declaration_type=2 (conjunta) + minor_children_in_unit=0 (tipo-1 matrimonio) → 0461 = €3,400.

    Oracle: Art. 84.2.1 LIRPF — unidad familiar tipo 1 (matrimonio) electing
    tributación conjunta receives reducción €3,400 in base imponible general.
    Source: AEAT Renta 2025 Manual, section Tributación conjunta, cuadro.
    """
    scenario = _scenario_2025(
        "m100-2025-0461-conjunta-tipo-1-3400",
        declaration_type=Decimal("2"),
        minor_children_in_unit=Decimal("0"),
        expected_0461=Decimal("3400.00"),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0461_individual_yields_0_2025() -> None:
    """declaration_type=1 (individual) → 0461 = €0 in 2025."""
    scenario = _scenario_2025(
        "m100-2025-0461-individual-zero",
        declaration_type=Decimal("1"),
        minor_children_in_unit=Decimal("0"),
        expected_0461=Decimal("0.00"),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0461_conjunta_tipo_2_monoparental_yields_0_2025() -> None:
    """declaration_type=2 + minor_children_in_unit=1 (tipo-2 monoparental) → 0461 = €0 in 2025."""
    scenario = _scenario_2025(
        "m100-2025-0461-conjunta-tipo-2-monoparental-zero",
        declaration_type=Decimal("2"),
        minor_children_in_unit=Decimal("1"),
        expected_0461=Decimal("0.00"),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0461_anti_tautology_declaration_type_change_2025() -> None:
    """Changing declaration_type from 2 to 1 must flip 0461 from €3,400 to €0 in 2025."""
    conjunta_scenario = _scenario_2025(
        "m100-2025-0461-anti-tautology-conjunta",
        declaration_type=Decimal("2"),
        minor_children_in_unit=Decimal("0"),
        expected_0461=Decimal("3400.00"),
    )
    individual_scenario = _scenario_2025(
        "m100-2025-0461-anti-tautology-individual",
        declaration_type=Decimal("1"),
        minor_children_in_unit=Decimal("0"),
        expected_0461=Decimal("0.00"),
    )
    for scenario in (conjunta_scenario, individual_scenario):
        report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
        assert_registry_scenario_matches(report)

    conjunta_report = run_registry_calculation_scenario(
        conjunta_scenario,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    individual_report = run_registry_calculation_scenario(
        individual_scenario,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    assert conjunta_report.calculation.values["0461"] != individual_report.calculation.values["0461"], (
        "0461 must differ between declaration_type=2 and declaration_type=1"
    )
