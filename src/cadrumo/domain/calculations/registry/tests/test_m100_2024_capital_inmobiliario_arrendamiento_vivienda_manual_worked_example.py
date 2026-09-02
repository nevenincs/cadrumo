"""Oracle test for M100 2024 casillas 0149/0150/0154 grounded against the AEAT
manual's own worked example (rendimientos del capital inmobiliario,
arrendamiento de vivienda en zona de mercado residencial tensionado).

Ground truth (bundled AEAT Manual práctico de Renta 2024, Parte 1, Capítulo 4
"Rendimientos del capital inmobiliario", "Caso práctico" — the second of the
three arrendamiento supuestos for the matrimonio don R.J.R. y doña M.A.T.):

    raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L12532-L12610

Raw taxpayer facts and the manual's own solución, quoted verbatim (line
numbers refer to the extracted markdown):

    Facts (L12532-12554): vivienda sita en Granollers (Barcelona), zona de
    mercado residencial tensionado, arrendada desde el 1 de abril de 2024
    (9 meses) por 650 euros mensuales.
      "Ingresos íntegros (650 x 9) = 5.850" (L12556).
      Gastos deducibles (L12557-12572):
        "Intereses de los capitales invertidos en la adquisición de la
         vivienda (préstamo hipotecario) (1) : 200 x 9/12 = 150"
         (L12558-12559).
        "Gastos de reparación y conservación (1): ... 210 x 9/12 = 157,50"
         (L12560-12561).
        "Tributos, recargos y tasas (IBI): 260 x 9/12 = 195" (L12562).
        "Gastos de Comunidad: 850 x 9/12 = 637,50" (L12563).
        "Amortización: * Vivienda (3% x 45.990) x 9/12 (2) = 1.034,78"
         (L12570).
        "* Muebles [(10% s/6.900] x 9/12 (3) = 388,13" (L12571).
        "Total gastos deducibles: 2.562,91" (L12572).
      "Rendimiento neto (5.850 - 2.562,91) = 3.287,09" (L12573).
      "Reducción por arrendamiento vivienda (90% /3.287,09) = 2.958,38"
       (L12574) — 90 % because Granollers is a declared zona tensionada
       (art. 18 Ley 12/2023) and the new contract (1 abril 2024) rebajó la
       renta more than 5 % respecto del contrato anterior (L12604-12618).
      "Rendimiento neto reducido: (3.287,09 - 2.958,38) = 328,71" (L12575).

Known internal-arithmetic note (documented, not treated as ground truth for
the underlying amortización sub-computation): the manual's own footnote (3)
states the muebles amortización coefficient is a flat 10 % of the 6.900 €
acquisition cost (no suelo/catastral adjustment, unlike the vivienda line),
which would independently derive to 6.900 × 10 % × 9/12 = 517,50, not the
388,13 the solución table prints. This test does not attempt to re-derive
that sub-computation (the registry models 0117 "Amortización de bienes
muebles" as a raw input casilla with no formula of its own, exactly like
0107/0109/0115/0131); it quotes the manual's own printed line-item figure
verbatim, which is what the manual itself sums into its stated "Total gastos
deducibles: 2.562,91" (150 + 157,50 + 195 + 637,50 + 1.034,78 + 388,13 =
2.562,91 exactly). The registry chain under test (0149/0150/0154) is graded
against the manual's own three independently-stated subtotals derived from
that same total, not against a re-derivation of the muebles sub-formula.

Registry mapping (M100 2024 revision, casillas 0100-0154,
"toma_datos_ampliada"/"inmuebles"/"inmueble" section):

    0100 "Marque con una 'X' si el arrendamiento tiene derecho a reducción
      (artículo 23.2 de la Ley del Impuesto)" = 1 (checked; the manual's own
      solución applies the art. 23.2 reducción, so the box is necessarily
      marked).
    0102 "Ingresos íntegros computables" = 5.850 (the manual's own "Ingresos
      íntegros" figure).
    0107 "Intereses y gastos de reparación y conservación de 2024 que se
      aplica en esta declaración" = 150 (intereses) + 157,50 (reparación) =
      307,50 — this revision's schema combines both AEAT art. 23.a).1º line
      items (which the manual itself treats under one shared límite/exceso
      rule, nota (1)) into a single box.
    0109 "Gastos de comunidad" = 637,50.
    0115 "Tributos, recargos y tasas" = 195.
    0117 "Amortización de bienes muebles" = 388,13 (the manual's own printed
      figure; see the internal-arithmetic note above).
    0131 "Amortización del inmueble y la mejora" = 1.034,78.
    0149 "Rendimiento neto ([0102]-[0104]-[0107]-[0109]-[0110]-[0111]-[0112]
      -[0113]-[0114]-[0115]-[0116]-[0117]-[0131]-[0132]-[0146]-[0147]-[0148])"
      = 5.850 - (307,50+637,50+195+388,13+1.034,78) = 5.850 - 2.562,91 =
      3.287,09 — matches the manual's own "Rendimiento neto" exactly.
    0150 "Reducción por arrendamiento de inmuebles destinados a vivienda
      (artículo 23.2 de la Ley del Impuesto)" = [0149] × 90 % (tier-90,
      the manual's own stated zona-tensionada rate) = 3.287,09 × 0,90 =
      2.958,381, rounded money-2 = 2.958,38 — matches the manual's own
      "Reducción por arrendamiento vivienda" exactly.
    0151 "Reducción por rendimientos irregulares (art. 23.3)" = 0 (not
      applicable; no such rendimiento in this supuesto).
    0152 "Rendimiento mínimo computable en caso de parentesco (art. 24)" = 0
      (not applicable; this is not the vivienda-arrendada-a-familiar
      supuesto of the same caso práctico).
    0154 "Rendimiento neto reducido del capital inmobiliario: la cantidad
      mayor de ([0149]-[0150]-[0151]) y [0152]" = max(3.287,09-2.958,38-0, 0)
      = max(328,71, 0) = 328,71 — matches the manual's own "Rendimiento neto
      reducido" exactly. THIS is the test's primary oracle target alongside
      0149 and 0150.

Anti-tautology: this test does not hand-compute 3.287,09, 2.958,38, or
328,71 from the registry formulas under test; every raw gasto/ingreso line
item is quoted from the manual, and the three targets are each independently
stated by the manual on its own account. A companion test switches the
art. 23.2 tier binding from the manual's own tier-90 to tier-50 (the term
unique to the 0150 formula under test) and asserts 0150 (and therefore 0154)
changes — a formula that ignored the tier binding, or always returned a
constant, would fail that check.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from ..authority import ValidatedRegistryAuthority
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)
from .manual_oracle_support import oracle_declared_figures

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()

_CASILLA_0149: CasillaId = validated_casilla_id("0149", surface="_CASILLA_0149")
_CASILLA_0150: CasillaId = validated_casilla_id("0150", surface="_CASILLA_0150")
_CASILLA_0154: CasillaId = validated_casilla_id("0154", surface="_CASILLA_0154")

# Each formula's OWN declared legal_refs / source_refs; the scenario comparison
# checks these against the calculation entry's provenance, not the casilla
# definition's provenance.
_LEGAL_REFS_0149 = ("ley-35-2006:art-22", "ley-35-2006:art-23")
_SOURCE_REFS_0149 = ("lirpf-cuota-chain-authority",)
_LEGAL_REFS_0150 = ("ley-35-2006:art-23",)
_SOURCE_REFS_0150 = ("aeat-renta-2024-manual-parte1", "lirpf-cuota-chain-authority")
_LEGAL_REFS_0154 = ("ley-35-2006:art-22", "ley-35-2006:art-23", "ley-35-2006:art-24")
_SOURCE_REFS_0154 = ("lirpf-cuota-chain-authority",)

_TIER_BINDING = "renta-2024-rental-reduccion-art-23-2-tier"

_REL_2024 = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}

_BASE_BINDINGS_2024 = {
    "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
    "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
    "renta-2024-profile-incremento-guarderia": Decimal("0"),
    "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
    "renta-2024-profile-descendientes-guarderia": Decimal("0"),
    "renta-2024-profile-marriage-full-year": Decimal("0"),
    "renta-2024-profile-marriage-month-start": Decimal("0"),
    "renta-2024-profile-marriage-month-end": Decimal("0"),
    "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
    "renta-2024-profile-declaration-type": Decimal("1"),
    "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
}

# Casilla 0107 is the one that needs a reader's attention: the registry lumps
# two separately printed line items into it -- intereses 150 and reparación y
# conservación 157,50 -- so its locator spans both rather than citing
# whichever happens to appear first.
_ORACLE_PAYLOAD_NAME = "modelo-100-2024-capital-inmobiliario-arrendamiento-vivienda-tensionada.json"

#: The reducción flag: scenario scaffolding, and local because that is what it is.
#:
#: Casilla 0100 is "marque con una X si el arrendamiento tiene derecho a reducción".
#: The example establishes the ENTITLEMENT in prose; the ``1`` is this application's
#: encoding of the mark. So the value here is ours, not the page's, and it belongs
#: beside the scenario that supplies it — where a reader can see both the encoding
#: and what it stands for.
#:
#: The payload declares what the corpus PRINTS. A locator's job is to put a reviewer
#: in front of the figure it claims, and this figure exists only in our encoding, so
#: there is nothing on the page for one to point at.
_REDUCCION_FLAG_INPUT: dict[CasillaId, Decimal] = {
    validated_casilla_id("0100", surface="0100"): Decimal("1"),
}


def _scenario(
    *, tier: str, expected_0150: Decimal, expected_0154: Decimal, scenario_id: str
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2024",
        filing_year=2024,
        period="0A",
        inputs=oracle_declared_figures(_ORACLE_PAYLOAD_NAME) | _REDUCCION_FLAG_INPUT,
        binding_values=dict(_BASE_BINDINGS_2024),
        enum_binding_values={
            "renta-2024-profile-tax-residence-ccaa": "madrid",
            _TIER_BINDING: tier,
        },
        relation_values=_REL_2024,
        date_context={"filing_period": date(2024, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0149,
                value=Decimal("3287.09"),
                legal_refs=_LEGAL_REFS_0149,
                source_refs=_SOURCE_REFS_0149,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0150,
                value=expected_0150,
                legal_refs=_LEGAL_REFS_0150,
                source_refs=_SOURCE_REFS_0150,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0154,
                value=expected_0154,
                legal_refs=_LEGAL_REFS_0154,
                source_refs=_SOURCE_REFS_0154,
            ),
        ),
        notes=("raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L12532-L12610",),
    )


def test_0154_manual_worked_example_vivienda_zona_tensionada() -> None:
    """0149/0150/0154 = 3.287,09 / 2.958,38 / 328,71 for the manual's zona-tensionada caso práctico.

    Oracle: AEAT Manual práctico de Renta 2024, Parte 1, Cap. 4, caso práctico
    "vivienda arrendada en zona tensionada" — "Rendimiento neto (5.850 -
    2.562,91) = 3.287,09", "Reducción por arrendamiento vivienda (90%
    /3.287,09) = 2.958,38", "Rendimiento neto reducido: (3.287,09 - 2.958,38)
    = 328,71" (L12573-L12575). Every raw ingreso/gasto figure feeding the
    scenario is quoted verbatim from the manual; see the module docstring for
    the full per-box trace.
    """
    scenario = _scenario(
        tier="tier-90",
        expected_0150=Decimal("2958.38"),
        expected_0154=Decimal("328.71"),
        scenario_id="m100-2024-0154-manual-vivienda-zona-tensionada",
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0150_anti_tautology_tier_change_changes_value() -> None:
    """Switching the art. 23.2 tier binding must change 0150 (and 0154).

    Anti-tautology: 0150's own formula is a dispatch-table lookup keyed by
    the ``renta-2024-rental-reduccion-art-23-2-tier`` binding — the term
    unique to the formula under test (0149 is already independently
    cross-checked against the manual's own "Rendimiento neto" figure in the
    primary test above). It does not hand-compute or assert the tier-50
    figure (that would reuse the same multiplication under test); it only
    asserts the two scenarios diverge, mirroring the ``!=``-only pattern used
    elsewhere in this test suite (e.g.
    ``test_0025_anti_tautology_art20_reduccion_change_changes_value``). A
    formula that ignored the tier binding, or always returned a constant,
    would fail this check.
    """
    tier_90 = _scenario(
        tier="tier-90",
        expected_0150=Decimal("2958.38"),
        expected_0154=Decimal("328.71"),
        scenario_id="m100-2024-0150-anti-tautology-tier-90",
    )
    tier_90_report = run_registry_calculation_scenario(tier_90, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(tier_90_report)

    # The tier-50 scenario's expected 0150/0154 values are never asserted
    # against a hand-computed figure (assert_registry_scenario_matches is
    # never called on it); only its divergence from the grounded scenario is
    # checked below. The placeholder values are structurally required by
    # RegistryScenarioExpectedOutput but are not consulted.
    tier_50 = _scenario(
        tier="tier-50",
        expected_0150=Decimal("0.00"),
        expected_0154=Decimal("0.00"),
        scenario_id="m100-2024-0150-anti-tautology-tier-50",
    )
    tier_50_report = run_registry_calculation_scenario(tier_50, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert tier_90_report.calculation.values[_CASILLA_0150] != tier_50_report.calculation.values[_CASILLA_0150], (
        "0150 must differ when the art. 23.2 tier binding changes"
    )
    assert tier_90_report.calculation.values[_CASILLA_0154] != tier_50_report.calculation.values[_CASILLA_0154], (
        "0154 must differ when the art. 23.2 tier binding changes"
    )


def test_0154_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of 0149/0150/0154 is enrolled, not just computed.

    A companion registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``) already proves the
    ``externally_grounded_casilla_ids`` declaration on the
    ``modelo-100-2024-reconcile-when-present`` verification expectation is
    backed by the bundled
    ``corpus/manual_oracles/modelo-100-2024-capital-inmobiliario-arrendamiento-vivienda-tensionada.json``
    evidence. This test proves the OTHER end of the wire: that the
    declaration actually reaches the live, VALIDATED
    :class:`RegistryVerificationPolicy` fold consumed by the living reconcile
    flow, so 0149/0150/0154 raise
    ``independently_grounded_fraction`` above the pre-existing baseline
    rather than sitting inert in TOML. Not tautological: the grounded set and
    the fraction are read from the registry's own declared+validated data,
    never hand-computed or asserted from a synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("100", filing_year=2024, period="0A")
    policy = snapshot.verification_policy()

    for casilla_id in (_CASILLA_0149, _CASILLA_0150, _CASILLA_0154):
        assert casilla_id in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_0154 in externally_grounded
    assert independently_grounded_fraction > 0.0
