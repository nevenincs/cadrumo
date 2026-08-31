"""Oracle tests for M100 casilla 0461 — reducción Art. 84 LIRPF por tributación conjunta.

Ground truth: Art. 84 Ley 35/2006 (LIRPF) — reducción en base imponible por
tributación conjunta:

    Unidad familiar tipo 1 (matrimonio, Art. 82.1.1°): €3,400 reducción.
    Unidad familiar tipo 2 (monoparental, Art. 82.1.2°): €2,150 reducción.
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

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path

# Importing the renta package registers the first-slice routing cross-domain
# snapshot check required by Modelo 100 parity scenarios run via _scenarios.
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()
_REDUCCION_ART_84_CASILLA: CasillaId = validated_casilla_id("0461", surface="_REDUCCION_ART_84_CASILLA")
_ART_84_LEGAL_REFS = ("ley-35-2006:art-82", "ley-35-2006:art-83", "ley-35-2006:art-84")
_ART_84_SOURCE_REFS_2024 = (
    "aeat-dr-100-2024-dictionary",
    "boe-modelo-100-2024-form",
    "aeat-renta-2024-manual-parte1",
)
_ART_84_SOURCE_REFS_2025 = (
    "aeat-dr-100-2025-dictionary",
    "boe-modelo-100-2025-form",
    "aeat-renta-2025-manual-parte1",
)

_REL_2024 = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}

_REL_2025 = {
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
}

_BASE_BINDINGS_2024 = {
    "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
    # Art. 81.2 LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
    "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
    "renta-2024-profile-incremento-guarderia": Decimal("0"),
    "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
    "renta-2024-profile-descendientes-guarderia": Decimal("0"),
    # matrimonio-sobrevenido bindings — 0 means marriage pre-dates filing year (full year)
    "renta-2024-profile-marriage-full-year": Decimal("0"),
    "renta-2024-profile-marriage-month-start": Decimal("0"),
    "renta-2024-profile-marriage-month-end": Decimal("0"),
    # BIN-pendiente fresh-filer baseline: previous_filing binding for
    # casilla 1388 (LIRPF Art. 48) resolves to zero with no prior filing.
    "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
}

_BASE_BINDINGS_2025 = {
    "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
    # matrimonio-sobrevenido bindings — 0 means marriage pre-dates filing year (full year)
    "renta-2025-profile-marriage-full-year": Decimal("0"),
    "renta-2025-profile-marriage-month-start": Decimal("0"),
    "renta-2025-profile-marriage-month-end": Decimal("0"),
    # BIN-pendiente fresh-filer baseline (2025 binding).
    "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
}


def test_0461_casilla_grounding_uses_art84_not_base_liquidable_art50() -> None:
    """Casilla 0461 itself is the Art. 84 joint-taxation reduction amount."""
    from ._registry_schema_support import _committed_modelo

    modelo, catalogues = _committed_modelo("100")
    art_84 = catalogues.legal["ley-35-2006:art-84"]
    assert any("3.400 euros" in text for text in art_84.required_text)
    assert any("2.150 euros" in text for text in art_84.required_text)

    for revision_id in ("2024", "2025"):
        revision = modelo.revisions[revision_id]
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _REDUCCION_ART_84_CASILLA)
        formula = next(
            formula for formula in revision.formulas if formula.target_casilla_id == _REDUCCION_ART_84_CASILLA
        )

        assert "ley-35-2006:art-84" in casilla.legal_refs
        assert "ley-35-2006:art-50" not in casilla.legal_refs
        assert "ley-35-2006:art-84" in formula.legal_refs


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
                target_casilla_id=_REDUCCION_ART_84_CASILLA,
                value=expected_0461,
                legal_refs=_ART_84_LEGAL_REFS,
                source_refs=_ART_84_SOURCE_REFS_2024,
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
                target_casilla_id=_REDUCCION_ART_84_CASILLA,
                value=expected_0461,
                legal_refs=_ART_84_LEGAL_REFS,
                source_refs=_ART_84_SOURCE_REFS_2025,
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


def test_0461_conjunta_tipo_2_monoparental_yields_2150_2024() -> None:
    """declaration_type=2 (conjunta) + minor_children_in_unit=1 (tipo-2 monoparental) → 0461 = €2,150.

    Oracle: Art. 84.2.2° LIRPF — unidad familiar tipo 2 (monoparental, soltero/separado
    con hijos a cargo) electing tributación conjunta receives reducción €2,150 in the
    base imponible general via casilla 0461.
    Source: AEAT Renta 2024 Manual, section Tributación conjunta, cuadro reducción.
    """
    scenario = _scenario_2024(
        "m100-2024-0461-conjunta-tipo-2-monoparental-2150",
        declaration_type=Decimal("2"),
        minor_children_in_unit=Decimal("1"),
        expected_0461=Decimal("2150.00"),
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
    assert (
        conjunta_report.calculation.values[_REDUCCION_ART_84_CASILLA]
        != individual_report.calculation.values[_REDUCCION_ART_84_CASILLA]
    ), "0461 must differ between declaration_type=2 and declaration_type=1"


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


def test_0461_conjunta_tipo_2_monoparental_yields_2150_2025() -> None:
    """declaration_type=2 + minor_children_in_unit=1 (tipo-2 monoparental) → 0461 = €2,150 in 2025.

    Oracle: Art. 84.2.2° LIRPF — same €2,150 reducción applies to the 2025 revision.
    """
    scenario = _scenario_2025(
        "m100-2025-0461-conjunta-tipo-2-monoparental-2150",
        declaration_type=Decimal("2"),
        minor_children_in_unit=Decimal("1"),
        expected_0461=Decimal("2150.00"),
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
    assert (
        conjunta_report.calculation.values[_REDUCCION_ART_84_CASILLA]
        != individual_report.calculation.values[_REDUCCION_ART_84_CASILLA]
    ), "0461 must differ between declaration_type=2 and declaration_type=1"
