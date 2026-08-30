"""Oracle tests for M100 2025 casilla 1039 — Comunidad de Madrid deducción
"Por nacimiento o adopción de hijos" (DL 1/2010 arts. 4 y 18.1).

Ground truth (bundled AEAT Renta 2025 manual, parte 2, deducciones autonómicas):

    Cuantía: 721,70 € por cada hijo nacido o adoptado (regulación vigente desde
    1-1-2023). Doble límite de la suma de bases imponibles general y del ahorro
    (casillas [0435] + [0460]):
      - Contribuyente: ≤ 30.930 € (individual) / ≤ 37.322,20 € (conjunta).
      - Unidad familiar: ≤ 61.860 €.
    Prorrateo por partes iguales cuando el hijo convive con ambos padres que
    tributan de forma individual.

The registry formula ``renta-2025-deduccion-madrid-nacimiento-adopcion`` receives
the prorrateo-weighted eligible-descendant count and the unidad-familiar
otros-miembros base through two profile bindings the ``_inject_derived_autonomic_
deduccion_facts`` injector supplies; here the bindings are supplied directly so
the formula's income-gate and amount arithmetic are exercised in isolation.

Anti-tautology: the amount 721,70 is derived from the bundled manual, not
hand-computed; flipping the unidad-familiar base above 61.860 € must drive 1039
from 721,70 € to 0 (the income gate blocks), and doubling the eligible count must
double the amount (a constant-returning formula would fail both).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from ..authority import ValidatedRegistryAuthority
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()
_CASILLA_1039: CasillaId = validated_casilla_id("1039", surface="_CASILLA_1039")
_LEGAL_REFS = ("ley-35-2006:art-77", "madrid-dl-1-2010:art-4", "madrid-dl-1-2010:art-18")
_SOURCE_REFS = (
    "aeat-renta-2025-manual-deducciones-autonomicas",
    "boe-modelo-100-2025-form",
    "aeat-dr-100-2025-dictionary",
)

_BASE_BINDINGS = {
    # The production profile resolver supplies this predicate as 1/0 from
    # taxpayer_type.irpf_income_categories; the scenario models a directa filer.
    "renta-2025-profile-has-economic-activity": Decimal("1"),
    "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
    "renta-2025-profile-marriage-full-year": Decimal("0"),
    "renta-2025-profile-marriage-month-start": Decimal("0"),
    "renta-2025-profile-marriage-month-end": Decimal("0"),
    "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
}

_REL = {
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
}


def _scenario(
    scenario_id: str,
    *,
    declaration_type: Decimal,
    eligible_count: Decimal,
    unidad_familiar_otros_miembros_base: Decimal,
    expected_1039: Decimal,
    ccaa: str = "madrid",
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={},
        binding_values={
            **_BASE_BINDINGS,
            "renta-2025-profile-declaration-type": declaration_type,
            "renta-2025-profile-madrid-nacimiento-adopcion-eligible-count": eligible_count,
            "renta-2025-profile-unidad-familiar-otros-miembros-base": unidad_familiar_otros_miembros_base,
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": ccaa},
        relation_values=_REL,
        date_context={"filing_period": date(2025, 12, 31)},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_1039,
                value=expected_1039,
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
    )


def _run(scenario: RegistryCalculationScenario) -> None:
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


@pytest.mark.parametrize(
    ("scenario_id", "eligible_count", "unidad_familiar_otros_miembros_base", "expected_1039"),
    [
        pytest.param(
            "m100-2025-1039-single-child-721-70",
            Decimal("1"),
            Decimal("0"),
            Decimal("721.70"),
            # Oracle: DL 1/2010 art. 4 — 721,70 € por cada hijo nacido o adoptado.
            id="1039_single_eligible_child_yields_721_70",
        ),
        pytest.param(
            "m100-2025-1039-two-children-1443-40",
            Decimal("2"),
            Decimal("0"),
            Decimal("1443.40"),
            # DL 1/2010 art. 4 — anti-tautology: two eligible children doubles the amount.
            id="1039_two_eligible_children_yields_1443_40",
        ),
        pytest.param(
            "m100-2025-1039-prorrateo-360-85",
            Decimal("0.5"),
            Decimal("0"),
            Decimal("360.85"),
            # DL 1/2010 art. 4 — prorrateo por partes iguales cuando el hijo convive
            # con ambos padres que tributan de forma individual (custodia compartida).
            id="1039_shared_custody_prorrateo_half_yields_360_85",
        ),
        pytest.param(
            "m100-2025-1039-no-children-zero",
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            # No in-window cohabiting descendants -> deducción does not apply.
            id="1039_no_eligible_children_yields_zero",
        ),
        pytest.param(
            "m100-2025-1039-uf-over-limit-zero",
            Decimal("1"),
            Decimal("62000"),
            Decimal("0"),
            # DL 1/2010 art. 18.1 — límite de la unidad familiar 61.860 € blocks the
            # deducción. Anti-tautology: identical to the eligible scenario except the
            # unidad-familiar base term crosses 61.860 €, driving 1039 from 721,70 € to 0.
            id="1039_unidad_familiar_base_over_limit_blocks_deduccion",
        ),
    ],
)
def test_1039_deduccion_madrid_nacimiento_adopcion(
    scenario_id: str,
    eligible_count: Decimal,
    unidad_familiar_otros_miembros_base: Decimal,
    expected_1039: Decimal,
) -> None:
    """1039 casilla amounts across cuantía, prorrateo, and límite scenarios.

    Oracle: DL 1/2010 arts. 4 y 18.1 (bundled AEAT Renta 2025 manual figures —
    see module docstring). Each param's inline comment carries its own citation.
    """
    _run(
        _scenario(
            scenario_id,
            declaration_type=Decimal("1"),
            eligible_count=eligible_count,
            unidad_familiar_otros_miembros_base=unidad_familiar_otros_miembros_base,
            expected_1039=expected_1039,
        ),
    )


def test_1039_non_madrid_resident_yields_zero() -> None:
    """A non-Madrid resident with the count binding at 0 (injector Madrid-scope) → 0."""
    _run(
        _scenario(
            "m100-2025-1039-non-madrid-zero",
            declaration_type=Decimal("1"),
            eligible_count=Decimal("0"),
            unidad_familiar_otros_miembros_base=Decimal("0"),
            expected_1039=Decimal("0"),
            ccaa="cataluna",
        ),
    )


def test_cuantia_parameter_is_721_70_grounded_in_the_madrid_law(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The per-child cuantía is 721,70 € grounded to art-77 + Madrid DL 1/2010 art. 4.

    Not hand-computed: the figure is the bundled AEAT manual value and the legal
    catalogue entry's corpus cross-check (enforced at registry load) resolves
    against that bundled authoritative manual.
    """
    authority = registry_authority
    snapshot = authority.snapshot("100", filing_year=2025, period="0A")
    revision = snapshot.revision

    cuantia = next(
        parameter
        for parameter in revision.parameters
        if parameter.id == "renta-2025-deduccion-madrid-nacimiento-adopcion-cuantia"
    )
    assert [value.value for value in cuantia.values] == [Decimal("721.70")]
    assert "ley-35-2006:art-77" in cuantia.legal_refs
    assert "madrid-dl-1-2010:art-4" in cuantia.legal_refs

    art_4 = snapshot.legal["madrid-dl-1-2010:art-4"]
    assert art_4.corpus_ref.startswith("corpus/manuals/renta/2025/part2-deducciones-autonomicas/")
    assert any("721,70 euros por cada hijo nacido o adoptado" in text for text in art_4.required_text)

    art_18 = snapshot.legal["madrid-dl-1-2010:art-18"]
    assert any("30.930 euros en tributación individual" in text for text in art_18.required_text)
    assert any("61.860 euros" in text for text in art_18.required_text)

    casilla = next(casilla for casilla in revision.casillas if casilla.id == "1039")
    assert casilla.input_kind is not None
    assert "madrid-dl-1-2010:art-4" in casilla.legal_refs
