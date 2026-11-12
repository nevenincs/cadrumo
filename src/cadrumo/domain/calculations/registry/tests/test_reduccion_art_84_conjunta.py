"""Oracle tests for M100 casilla 0461 — reducción Art. 84 LIRPF por tributación conjunta.

Ground truth: Art. 84 Ley 35/2006 (LIRPF) — reducción en base imponible por
tributación conjunta:

    Art. 84.2.3º, first modality (spouses, Art. 82.1.1ª, with or without
    children): €3,400 reducción.
    Art. 84.2.4º, second modality (single parent, Art. 82.1.2ª): €2,150, which
    "no se aplicará ... cuando el contribuyente conviva con el padre o la madre
    de alguno de los hijos que forman parte de su unidad familiar".
    Individual (declaration_type != 2): €0.

The formula ``renta-reduccion-art-84-conjunta`` derives the reducción from
three profile bindings:
  - ``renta-profile-declaration-type`` (Decimal "1"=individual, "2"=conjunta)
  - ``renta-profile-family-situacion-familiar`` (Art. 82 situation token,
    ``casado`` = first modality)
  - ``renta-profile-family-convive-otro-progenitor`` (yes/no, read only for the
    second modality; unstated keeps the box unresolved)

Anti-tautology: flipping declaration_type from "2" to "1" must change 0461 from
€3,400 to €0. A formula that returns a constant would produce a false negative
for both values, but not a sign-change.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .authored_editions import newest_authored_editions

# Importing the renta package registers the first-slice routing cross-domain
# snapshot check required by Modelo 100 parity scenarios run via scenarios.
from .scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The two newest Modelo 100 editions the registry authors; each ships its own binding
# set, and Art. 84 LIRPF fixes the same reducción in both.
_PRIOR_EDITION, _REVIEWED_EDITION = newest_authored_editions("100", 2)

_REDUCCION_ART_84_CASILLA: CasillaId = validated_casilla_id("0461", surface="_REDUCCION_ART_84_CASILLA")
# Art. 82 LIRPF family-situation tokens: casado forms the first unit, soltero the second.
_SOLTERO = "soltero"
_CASADO = "casado"
_ART_84_LEGAL_REFS = ("ley-35-2006:art-82", "ley-35-2006:art-83", "ley-35-2006:art-84")

_ZERO_RELATIONS = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}

_PRIOR_EDITION_BINDINGS = {
    "renta-profile-has-economic-activity": Decimal("1"),
    "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
    "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
    "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
    "renta-profile-estimacion-directa": Decimal("1"),
    "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    # Art. 81.2 LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
    "renta-profile-incremento-guarderia": Decimal("0"),
    # matrimonio-sobrevenido bindings — 0 means marriage pre-dates filing year (full year)
    "renta-profile-marriage-full-year": Decimal("0"),
    "renta-profile-marriage-month-start": Decimal("0"),
    "renta-profile-marriage-month-end": Decimal("0"),
    # BIN-pendiente fresh-filer baseline: previous_filing binding for
    # casilla 1388 (LIRPF Art. 48) resolves to zero with no prior filing.
    "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
    "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
}

_REVIEWED_EDITION_BINDINGS = {
    "renta-profile-has-economic-activity": Decimal("1"),
    "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
    "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
    "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
    "renta-profile-estimacion-directa": Decimal("1"),
    "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    # matrimonio-sobrevenido bindings — 0 means marriage pre-dates filing year (full year)
    "renta-profile-marriage-full-year": Decimal("0"),
    "renta-profile-marriage-month-start": Decimal("0"),
    "renta-profile-marriage-month-end": Decimal("0"),
    # BIN-pendiente fresh-filer baseline (reviewed-edition binding).
    "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
    "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
}


_EDITIONS = {
    _PRIOR_EDITION: _PRIOR_EDITION_BINDINGS,
    _REVIEWED_EDITION: _REVIEWED_EDITION_BINDINGS,
}


def _art_84_source_refs(filing_year: int) -> tuple[str, ...]:
    """The edition's own record design, BOE form and AEAT manual ground the reducción."""
    return (
        f"aeat-dr-100-{filing_year}-dictionary",
        f"boe-modelo-100-{filing_year}-form",
        f"aeat-renta-{filing_year}-manual-parte1",
    )


def test_0461_casilla_grounding_uses_art84_not_base_liquidable_art50() -> None:
    """Casilla 0461 itself is the Art. 84 joint-taxation reduction amount."""
    from .registry_tree import bundled_modelo_components

    modelo, catalogues = bundled_modelo_components("100")
    art_84 = catalogues.legal["ley-35-2006:art-84"]
    assert any("3.400 euros" in text for text in art_84.required_text)
    assert any("2.150 euros" in text for text in art_84.required_text)

    for revision_id in (str(year) for year in _EDITIONS):
        revision = modelo.revisions[revision_id]
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _REDUCCION_ART_84_CASILLA)
        formula = next(
            formula for formula in revision.formulas if formula.target_casilla_id == _REDUCCION_ART_84_CASILLA
        )

        assert "ley-35-2006:art-84" in casilla.legal_refs
        assert "ley-35-2006:art-50" not in casilla.legal_refs
        assert "ley-35-2006:art-84" in formula.legal_refs


def _scenario(
    filing_year: int,
    scenario_label: str,
    declaration_type: Decimal,
    situacion_familiar: str,
    expected_0461: Decimal,
    convive_otro_progenitor: Decimal | None = None,
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=f"m100-{filing_year}-0461-{scenario_label}",
        modelo="100",
        revision=str(filing_year),
        filing_year=filing_year,
        period="0A",
        inputs={},
        binding_values={
            **_EDITIONS[filing_year],
            "renta-profile-declaration-type": declaration_type,
            "renta-profile-family-minor-children-in-unit": Decimal(situacion_familiar != _CASADO),
            **(
                {}
                if convive_otro_progenitor is None
                else {"renta-profile-family-convive-otro-progenitor": convive_otro_progenitor}
            ),
        },
        enum_binding_values={
            "renta-profile-tax-residence-ccaa": "madrid",
            "renta-profile-family-situacion-familiar": situacion_familiar,
        },
        relation_values=_ZERO_RELATIONS,
        date_context={"filing_period": date(filing_year, 12, 31)},
        date_binding_values={"renta-profile-taxpayer-birth-date": date(filing_year - 45, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target_casilla_id=_REDUCCION_ART_84_CASILLA,
                value=expected_0461,
                legal_refs=_ART_84_LEGAL_REFS,
                source_refs=_art_84_source_refs(filing_year),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Oracle tests, run against both authored editions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filing_year", tuple(_EDITIONS))
def test_0461_conjunta_tipo_1_matrimonio_yields_3400(filing_year: int) -> None:
    """declaration_type=2 (conjunta) + family situation casado (tipo-1 matrimonio) → 0461 = €3,400.

    Oracle: Art. 84.2.3º LIRPF — unidad familiar tipo 1 (matrimonio) electing
    tributación conjunta receives reducción €3,400 in base imponible general.
    Source: the edition's AEAT Renta Manual, section Tributación conjunta, cuadro.
    """
    scenario = _scenario(
        filing_year,
        "conjunta-tipo-1-3400",
        declaration_type=Decimal("2"),
        situacion_familiar=_CASADO,
        expected_0461=Decimal("3400.00"),
    )
    report = run_registry_calculation_scenario(scenario)
    assert_registry_scenario_matches(report)


@pytest.mark.parametrize("filing_year", tuple(_EDITIONS))
def test_0461_individual_yields_0(filing_year: int) -> None:
    """declaration_type=1 (individual) → 0461 = €0.

    Oracle: Art. 84 LIRPF applies only to tributación conjunta (declaration_type=2).
    Individual declarations receive no reducción por unidad familiar.
    """
    scenario = _scenario(
        filing_year,
        "individual-zero",
        declaration_type=Decimal("1"),
        situacion_familiar=_CASADO,
        expected_0461=Decimal("0.00"),
    )
    report = run_registry_calculation_scenario(scenario)
    assert_registry_scenario_matches(report)


@pytest.mark.parametrize("filing_year", tuple(_EDITIONS))
def test_0461_conjunta_tipo_2_monoparental_yields_2150(filing_year: int) -> None:
    """declaration_type=2 (conjunta) + single parent not living with the other parent → 0461 = €2,150.

    Oracle: Art. 84.2.4º LIRPF — unidad familiar tipo 2 (monoparental, soltero/separado
    con hijos a cargo) electing tributación conjunta receives reducción €2,150 in the
    base imponible general via casilla 0461.
    Source: the edition's AEAT Renta Manual, section Tributación conjunta, cuadro reducción.
    """
    scenario = _scenario(
        filing_year,
        "conjunta-tipo-2-monoparental-2150",
        declaration_type=Decimal("2"),
        situacion_familiar=_SOLTERO,
        convive_otro_progenitor=Decimal("0"),
        expected_0461=Decimal("2150.00"),
    )
    report = run_registry_calculation_scenario(scenario)
    assert_registry_scenario_matches(report)


@pytest.mark.parametrize("filing_year", tuple(_EDITIONS))
def test_0461_anti_tautology_declaration_type_change(filing_year: int) -> None:
    """Changing declaration_type from 2 to 1 must flip 0461 from €3,400 to €0.

    Anti-tautology: a formula that returns a constant cannot pass both this
    and test_0461_conjunta_tipo_1_matrimonio_yields_3400 simultaneously.
    """
    conjunta_scenario = _scenario(
        filing_year,
        "anti-tautology-conjunta",
        declaration_type=Decimal("2"),
        situacion_familiar=_CASADO,
        expected_0461=Decimal("3400.00"),
    )
    individual_scenario = _scenario(
        filing_year,
        "anti-tautology-individual",
        declaration_type=Decimal("1"),
        situacion_familiar=_CASADO,
        expected_0461=Decimal("0.00"),
    )
    for scenario in (conjunta_scenario, individual_scenario):
        report = run_registry_calculation_scenario(scenario)
        assert_registry_scenario_matches(report)

    conjunta_report = run_registry_calculation_scenario(conjunta_scenario)
    individual_report = run_registry_calculation_scenario(individual_scenario)
    assert (
        conjunta_report.calculation.values[_REDUCCION_ART_84_CASILLA]
        != individual_report.calculation.values[_REDUCCION_ART_84_CASILLA]
    ), "0461 must differ between declaration_type=2 and declaration_type=1"


@pytest.mark.parametrize("filing_year", tuple(_EDITIONS))
def test_0461_tipo_2_living_with_the_other_parent_yields_0(filing_year: int) -> None:
    """A single parent who lives with the other parent of a child gets no reducción.

    Oracle: Art. 84.2.4º LIRPF, last sentence: the €2,150 "no se aplicará esta
    reducción cuando el contribuyente conviva con el padre o la madre de alguno
    de los hijos que forman parte de su unidad familiar".
    """
    scenario = _scenario(
        filing_year,
        "conjunta-tipo-2-convive-0",
        declaration_type=Decimal("2"),
        situacion_familiar=_SOLTERO,
        convive_otro_progenitor=Decimal("1"),
        expected_0461=Decimal("0.00"),
    )
    report = run_registry_calculation_scenario(scenario)
    assert_registry_scenario_matches(report)


@pytest.mark.parametrize("filing_year", tuple(_EDITIONS))
def test_0461_tipo_2_with_cohabitation_unstated_stays_unresolved(filing_year: int) -> None:
    """Without the cohabitation fact a single-parent unit's reducción is unknown, never €2,150 or €0."""
    scenario = _scenario(
        filing_year,
        "conjunta-tipo-2-convive-unstated",
        declaration_type=Decimal("2"),
        situacion_familiar=_SOLTERO,
        expected_0461=Decimal("2150.00"),
    )
    report = run_registry_calculation_scenario(scenario)

    assert _REDUCCION_ART_84_CASILLA not in report.calculation.values
    assert report.status == "mismatch"


@pytest.mark.parametrize("filing_year", tuple(_EDITIONS))
def test_0461_tipo_1_does_not_read_the_cohabitation_fact(filing_year: int) -> None:
    """The married unit's €3,400 does not depend on the single-parent cohabitation fact."""
    scenario = _scenario(
        filing_year,
        "conjunta-tipo-1-convive-ignored",
        declaration_type=Decimal("2"),
        situacion_familiar=_CASADO,
        convive_otro_progenitor=Decimal("1"),
        expected_0461=Decimal("3400.00"),
    )
    report = run_registry_calculation_scenario(scenario)
    assert_registry_scenario_matches(report)
