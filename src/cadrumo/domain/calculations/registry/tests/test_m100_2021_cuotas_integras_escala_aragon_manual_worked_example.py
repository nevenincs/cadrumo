"""Oracle tests for the M100 2021 cuota-integra chain.

The independent oracle is the bundled AEAT Manual practico de Renta 2021
worked example for a taxpayer resident in Aragon.  This revision is exercised
with its own input shape: 0511 and 0512, together with 0515-0518, are manual
casillas, so the scenario supplies those values directly rather than importing
a later profile/formula chain.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from ..authority import ValidatedRegistryAuthority
from ..schema_input_kind import InputKind
from ._manual_oracle_support import oracle_declared_figures, read_manual_worked_example
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()

_SOURCE_REFS_CUOTA = ("lirpf-cuota-chain-authority",)
_SOURCE_REFS_0529 = ("aeat-renta-2021-manual-parte1", "boe-modelo-100-2021-form")

_GROUNDED_OUTPUT_REFS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("0519", ("ley-35-2006:art-56",), _SOURCE_REFS_CUOTA),
    ("0520", ("ley-35-2006:art-56", "ley-35-2006:art-73"), _SOURCE_REFS_CUOTA),
    ("0528", ("ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-64"), _SOURCE_REFS_CUOTA),
    ("0529", ("ley-35-2006:art-73", "ley-35-2006:art-74", "ley-35-2006:art-75-2015"), _SOURCE_REFS_0529),
    ("0532", ("ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-64"), _SOURCE_REFS_CUOTA),
    ("0533", ("ley-35-2006:art-73", "ley-35-2006:art-74", "ley-35-2006:art-75-2015"), _SOURCE_REFS_CUOTA),
    ("0545", ("ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-66-2021"), _SOURCE_REFS_CUOTA),
    ("0546", ("ley-35-2006:art-73", "ley-35-2006:art-74", "ley-35-2006:art-76-2021"), _SOURCE_REFS_CUOTA),
)
"""The grounded casillas and the provenance each carries.

The FIGURES are deliberately absent: they live in the oracle payload, which is the
only place a manual-printed number belongs. Keeping them here too is what made this
test and its payload two independent transcriptions of one page.
"""

_FORMULA_BY_CASILLA: Mapping[str, str] = {
    "0519": "renta-2021-minimo-personal-y-familiar-estatal",
    "0520": "renta-2021-minimo-personal-y-familiar-autonomica",
    "0528": "renta-2021-cuota-escala-estatal-sobre-base-liquidable-general",
    "0529": "renta-2021-cuota-escala-autonomica-sobre-base-liquidable-general",
    "0532": "renta-2021-cuota-base-liquidable-general-estatal",
    "0533": "renta-2021-cuota-base-liquidable-general-autonomica",
    "0545": "renta-2021-cuota-integra-estatal",
    "0546": "renta-2021-cuota-integra-autonomica",
}

_ORACLE_PAYLOAD_NAME = "modelo-100-2021-cuotas-integras-escala-aragon.json"


#: Mínimo components the manual does NOT print, supplied as scenario scaffolding.
#:
#: Deliberately NOT in the payload's ``declared_inputs``. The manual states one total
#: mínimo personal y familiar of 5.550 and never mentions these component boxes, so
#: declaring them as manual facts would attach a corpus locator to a figure the corpus
#: does not carry — the payload declares what the page prints, and the scenario supplies
#: what the engine additionally needs to run.
_STRUCTURAL_ZERO_INPUTS: dict[CasillaId, Decimal] = {
    validated_casilla_id("0515", surface="0515"): Decimal("0.00"),
    validated_casilla_id("0516", surface="0516"): Decimal("0.00"),
    validated_casilla_id("0517", surface="0517"): Decimal("0.00"),
    validated_casilla_id("0518", surface="0518"): Decimal("0.00"),
}

_BASE_BINDINGS_2021: dict[str, Decimal] = {
    "renta-2021-modelo-111-retenciones-periodicas": Decimal("0"),
    "renta-2021-modelo-123-retenciones-periodicas": Decimal("0"),
    "renta-2021-modelo-100-estimacion-directa-es-normal": Decimal("0"),
    "renta-2021-profile-anualidades-sin-minimo-descendientes": Decimal("0"),
    "renta-2021-profile-minimo-descendientes-estatal": Decimal("0"),
    "renta-2021-profile-minimo-descendientes-autonomico": Decimal("0"),
}

_REL_2021: dict[str, Decimal] = {
    "renta-2021-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2021-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2021-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2021-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2021-rel-131-pagos-fraccionados": Decimal("0"),
}


def _scenario(*, ccaa: str, scenario_id: str, grounded: bool) -> RegistryCalculationScenario:
    expected_by_casilla_id = read_manual_worked_example(_ORACLE_PAYLOAD_NAME).expected_by_casilla_id
    expected_outputs = (
        tuple(
            RegistryScenarioExpectedOutput(
                target_casilla_id=validated_casilla_id(casilla_id, surface=casilla_id),
                # The FIGURE comes from the oracle payload; only the provenance the
                # scenario comparison checks against the calculation entry stays local,
                # because legal_refs and source_refs are registry facts rather than
                # anything the manual prints.
                value=Decimal(expected_by_casilla_id[casilla_id]),
                legal_refs=legal_refs,
                source_refs=source_refs,
            )
            for casilla_id, legal_refs, source_refs in _GROUNDED_OUTPUT_REFS
        )
        if grounded
        else (
            RegistryScenarioExpectedOutput(
                target_casilla_id=validated_casilla_id("0500", surface="0500"),
                value=Decimal("23900.00"),
                legal_refs=("ley-35-2006:art-50", "ley-35-2006:art-52"),
                source_refs=("lirpf-cuota-chain-authority",),
            ),
        )
    )
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2021",
        filing_year=2021,
        period="0A",
        inputs={**oracle_declared_figures(_ORACLE_PAYLOAD_NAME), **_STRUCTURAL_ZERO_INPUTS},
        binding_values=_BASE_BINDINGS_2021,
        enum_binding_values={"renta-2021-profile-tax-residence-ccaa": ccaa},
        relation_values=_REL_2021,
        date_context={"filing_period": date(2021, 12, 31)},
        expected_outputs=expected_outputs,
        notes=("raw_evidence_locator: corpus/manuals/renta/2021/part1/source.pdf.extracted.md#L34681-L34721",),
    )


def test_cuotas_integras_escala_aragon_manual_worked_example() -> None:
    """The 2021 cuota-integra chain reproduces the official Aragon example."""
    scenario = _scenario(ccaa="aragon", scenario_id="m100-2021-cuotas-integras-escala-aragon", grounded=True)
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_cuotas_integras_anti_tautology_autonomic_tariff_changes_value() -> None:
    """Changing CCAA changes autonomic values while state values stay fixed."""
    aragon = _scenario(ccaa="aragon", scenario_id="m100-2021-cuotas-aragon", grounded=True)
    madrid = _scenario(ccaa="madrid", scenario_id="m100-2021-cuotas-madrid", grounded=False)
    aragon_report = run_registry_calculation_scenario(aragon, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(aragon_report)
    madrid_report = run_registry_calculation_scenario(madrid, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)

    aragon_values = aragon_report.calculation.values
    madrid_values = madrid_report.calculation.values

    def _value(values: Mapping[CasillaId, Decimal | None], casilla_id: str) -> Decimal | None:
        return values.get(validated_casilla_id(casilla_id, surface=casilla_id))

    for autonomic_casilla in ("0529", "0533", "0546"):
        assert _value(aragon_values, autonomic_casilla) != _value(madrid_values, autonomic_casilla), (
            f"autonomic cuota {autonomic_casilla} must differ between Aragon and Madrid residence"
        )
    for state_casilla in ("0528", "0532", "0545"):
        assert _value(aragon_values, state_casilla) == _value(madrid_values, state_casilla), (
            f"state cuota {state_casilla} must be identical across residences"
        )


def test_cuota_chain_formula_targets_are_double_wired(registry_authority: ValidatedRegistryAuthority) -> None:
    """Each grounded computed casilla points back to its exact formula target."""
    snapshot = registry_authority.snapshot("100", filing_year=2021, period="0A")
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    formulas = {formula.id: formula for formula in snapshot.revision.formulas}

    for casilla_id, formula_id in _FORMULA_BY_CASILLA.items():
        casilla = casillas[casilla_id]
        assert casilla.input_kind is InputKind.COMPUTED
        assert casilla.formula == formula_id
        assert formulas[formula_id].target_casilla_id == casilla_id


def test_cuota_chain_manual_grounding_is_enrolled(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Every manual-grounded value reaches the live validated policy fold."""
    snapshot = registry_authority.snapshot("100", filing_year=2021, period="0A")
    policy = snapshot.verification_policy()
    grounded_casilla_ids = {
        validated_casilla_id(casilla_id, surface=casilla_id) for casilla_id, *_ in _GROUNDED_OUTPUT_REFS
    }
    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids

    for casilla_id in grounded_casilla_ids:
        assert casilla_id in policy.externally_grounded_casilla_ids
        assert casilla_id in reconciled_casilla_ids

    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    assert grounded_casilla_ids <= externally_grounded
    assert len(externally_grounded) > 0
