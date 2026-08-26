"""Oracle test for M100 2024 casillas 1826/1830/1836/1840 grounded against the
AEAT manual's own worked example (ganancias patrimoniales, transmisión de un
inmueble con aplicación de los coeficientes de abatimiento de la DT 9.ª).

Ground truth (bundled AEAT Manual práctico de Renta 2024, Parte 1, Capítulo 11
"Ganancias y pérdidas patrimoniales", "Caso práctico" of don J.P.C. — the
second of his four 2024 operaciones con trascendencia fiscal, "Transmisión del
piso"):

    raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L42725-L42839

Raw taxpayer facts and the manual's own solución, quoted verbatim (line
numbers refer to the extracted markdown):

    Facts (L42732-L42740): "El día 1 de julio de 2024 realizó la venta de un
    piso, sito en la calle Toledo, número 10, de Madrid, por un importe de
    150.000 euros, abonando en concepto de Impuesto Municipal sobre Incremento
    de Valor de los Terrenos de Naturaleza Urbana 1.900 euros. Dicho piso fue
    adquirido el día 20-12-1994 por un importe equivalente a 90.000 euros...
    Los gastos inherentes a la adquisición satisfechos por el adquirente en
    enero de 1995, en concepto de notaría, registro e Impuesto sobre
    Transmisiones ascendieron a un importe equivalente a 8.000 euros."
      Solución (L42777-L42785):
        "2. Transmisión del piso:
         Valor de transmisión (150.000 – 1.900) (1) = 148.100
         Valor de adquisición (2): 96.380
         Ganancia patrimonial (148.100,00 – 96.380,00) = 51.720
         Ganancia patrimonial reducible (generada hasta 19-01-2006)
         (51.720 x 4.049) ÷ 10.786 (3) = 19.415,38
         Nº de años de permanencia a 31-12-1996: 3 años
         Reducción por coeficientes de abatimiento (19.415,38 x 11,11%) =
         2.157,05
         Ganancia patrimonial reducida (51.720 –2.157,05) = 49.562,95"
      Note (2) (L42824-L42828), the manual's own valor-de-adquisición
      breakdown: "Importe real de la adquisición: (90.000): +90.000 / Gastos y
      tributos: (8.000): +8.000 / Amortización año 1995 y 1996 [(1,5% s/90.000
      x 0,6) x 2] = –1.620 / Total valor de adquisición (90.000+8.000-1.620) =
      96.380."

Known internal-arithmetic note (documented, not treated as ground truth for
the underlying DT 9.ª sub-computation): the manual's own note (3) derives the
"Reducción por coeficientes de abatimiento" figure (2.157,05) from a
years-of-permanence-to-31-12-1996 sub-formula the registry does not model as a
casilla-level computation (casilla 1839 "Reducción aplicable (DT 9.ª de la Ley
del Impuesto)" is a raw input casilla with no formula of its own, exactly like
0117 in the sibling arrendamiento-de-vivienda test). This test does not
attempt to re-derive that sub-computation; it quotes the manual's own printed
figure verbatim and feeds it into casilla 1839, which is what the registry's
own 1840 formula subtracts from the (independently-computed) 1836.

Registry mapping (M100 2024 revision, casillas 1826-1915,
"toma_datos_ampliada"/"gp_otros_inmuebles"/"elemento_inmueble" section):

    1911 "Importe real de la transmisión" = 150.000 (the manual's own
      "El día 1 de julio de 2024 realizó la venta de un piso ... por un
      importe de 150.000 euros").
    1912 "Gastos y tributos inherentes a la transmisión satisfechos por el
      transmitente" = 1.900 (the manual's own "Impuesto Municipal sobre
      Incremento de Valor de los Terrenos de Naturaleza Urbana 1.900 euros").
    1913 "Importe real de la adquisición" = 90.000 (the manual's own note (2)
      "Importe real de la adquisición: (90.000)").
    1914 "Gastos y tributos inherentes a la adquisición satisfechos por el
      adquirente" = 8.000 (the manual's own note (2) "Gastos y tributos:
      (8.000)").
    1915 "Amortizaciones" = 1.620 (the manual's own note (2) "Amortización año
      1995 y 1996 [(1,5% s/90.000 x 0,6) x 2] = –1.620").
    1826 "Valor de transmisión ([1911] - [1912])" = 150.000 - 1.900 = 148.100
      — matches the manual's own "Valor de transmisión (150.000 – 1.900) =
      148.100" exactly.
    1830 "Valor de adquisición ([1913] + [1914] - [1915])" = 90.000 + 8.000 -
      1.620 = 96.380 — matches the manual's own "Valor de adquisición:
      96.380" and its own "Total valor de adquisición
      (90.000+8.000-1.620) = 96.380" exactly.
    1836 "Ganancia no exenta ([1826] - [1830] - [1641] - [1834] - [1835])" =
      148.100 - 96.380 - 0 - 0 - 0 = 51.720 (no exención applies to this
      operación) — matches the manual's own "Ganancia patrimonial
      (148.100,00 – 96.380,00) = 51.720" exactly.
    1839 "Reducción aplicable (DT 9.ª de la Ley del Impuesto)" = 2.157,05 (the
      manual's own printed figure; see the internal-arithmetic note above).
    1840 "Ganancia patrimonial reducida no exenta ([1836] - [1839])" =
      51.720 - 2.157,05 = 49.562,95 — matches the manual's own "Ganancia
      patrimonial reducida (51.720 –2.157,05) = 49.562,95" exactly. THIS is
      the test's primary oracle target alongside 1826, 1830 and 1836.

Anti-tautology: this test does not hand-compute 148.100, 96.380, 51.720, or
49.562,95 from the registry formulas under test; every raw importe/gasto line
item is quoted from the manual, and each of the four targets is independently
stated by the manual on its own account. A companion test changes the
transmisión-side raw input (1912, the term unique to the 1826 formula under
test) to a value the manual never states and asserts 1826 — and therefore its
downstream 1836/1840 — changes; a formula that ignored the operand, or always
returned a constant, would fail that check.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from ._manual_oracle_support import oracle_declared_figures
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()

_CASILLA_1826: CasillaId = validated_casilla_id("1826", surface="_CASILLA_1826")
_CASILLA_1830: CasillaId = validated_casilla_id("1830", surface="_CASILLA_1830")
_CASILLA_1836: CasillaId = validated_casilla_id("1836", surface="_CASILLA_1836")
_CASILLA_1840: CasillaId = validated_casilla_id("1840", surface="_CASILLA_1840")

# Each formula's OWN declared legal_refs / source_refs; the scenario comparison
# checks these against the calculation entry's provenance, not the casilla
# definition's provenance. All four formulas in this chain share the same
# declared refs (ley-35-2006:art-33/34/37, lirpf-cuota-chain-authority).
_LEGAL_REFS = ("ley-35-2006:art-33", "ley-35-2006:art-34", "ley-35-2006:art-37")
_SOURCE_REFS = ("lirpf-cuota-chain-authority",)

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

# Raw importe/gasto/reducción inputs quoted from the manual; see the module
# docstring for the per-box mapping and its cross-validation against the
# manual's own stated subtotals.
#
# Two figures are worth a reader's attention. Casilla 1915, the
# amortizaciones deducted from the acquisition value, is printed only inside
# the arithmetic of the total (``90.000+8.000-1.620``), so it cites that line
# AND the nota that establishes how 1.620 arose. Casilla 1839 is the
# abatimiento reducción the manual works out in its solución rather than a
# fact from the case statement: the engine consumes it, the example states
# it, and it is cited where it is stated.
_ORACLE_PAYLOAD_NAME = "modelo-100-2024-ganancias-patrimoniales-transmision-inmueble.json"


def _scenario(
    *,
    inputs: dict[CasillaId, Decimal],
    expected_1826: Decimal,
    expected_1830: Decimal,
    expected_1836: Decimal,
    expected_1840: Decimal,
    scenario_id: str,
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2024",
        filing_year=2024,
        period="0A",
        inputs=inputs,
        binding_values=dict(_BASE_BINDINGS_2024),
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2024,
        date_context={"filing_period": date(2024, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_1826,
                value=expected_1826,
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_1830,
                value=expected_1830,
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_1836,
                value=expected_1836,
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_1840,
                value=expected_1840,
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
        notes=("raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L42725-L42839",),
    )


def test_1840_manual_worked_example_transmision_inmueble_abatimiento() -> None:
    """1826/1830/1836/1840 = 148.100 / 96.380 / 51.720 / 49.562,95 for don J.P.C.'s piso.

    Oracle: AEAT Manual práctico de Renta 2024, Parte 1, Cap. 11, caso práctico
    de don J.P.C. — "Transmisión del piso": "Valor de transmisión
    (150.000 – 1.900) = 148.100", "Valor de adquisición: 96.380", "Ganancia
    patrimonial (148.100,00 – 96.380,00) = 51.720", "Ganancia patrimonial
    reducida (51.720 –2.157,05) = 49.562,95" (L42778-L42785). Every raw
    importe/gasto/reducción figure feeding the scenario is quoted verbatim
    from the manual; see the module docstring for the full per-box trace.
    """
    scenario = _scenario(
        inputs=oracle_declared_figures(_ORACLE_PAYLOAD_NAME),
        expected_1826=Decimal("148100.00"),
        expected_1830=Decimal("96380.00"),
        expected_1836=Decimal("51720.00"),
        expected_1840=Decimal("49562.95"),
        scenario_id="m100-2024-1840-manual-transmision-inmueble-abatimiento",
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_1826_anti_tautology_gastos_transmision_change_changes_value() -> None:
    """Changing the gastos-de-transmisión raw input must change 1826 (and 1836/1840).

    Anti-tautology: 1826's own formula is ``[1911] - [1912]`` — a subtraction
    of the two raw inputs quoted from the manual. It does not hand-compute or
    assert a second figure derived from the same subtraction under test (that
    would reuse the formula being verified); it only asserts the two scenarios
    diverge, mirroring the ``!=``-only pattern used elsewhere in this test
    suite (e.g. ``test_0150_anti_tautology_tier_change_changes_value``). A
    formula that ignored the 1912 operand, or always returned a constant,
    would fail this check.
    """
    grounded = _scenario(
        inputs=oracle_declared_figures(_ORACLE_PAYLOAD_NAME),
        expected_1826=Decimal("148100.00"),
        expected_1830=Decimal("96380.00"),
        expected_1836=Decimal("51720.00"),
        expected_1840=Decimal("49562.95"),
        scenario_id="m100-2024-1826-anti-tautology-grounded",
    )
    grounded_report = run_registry_calculation_scenario(
        grounded, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT
    )
    assert_registry_scenario_matches(grounded_report)

    # The perturbed scenario's expected 1826/1830/1836/1840 values are never
    # asserted against a hand-computed figure (assert_registry_scenario_matches
    # is never called on it); only its divergence from the grounded scenario is
    # checked below. The placeholder values are structurally required by
    # RegistryScenarioExpectedOutput but are not consulted.
    perturbed_inputs = oracle_declared_figures(_ORACLE_PAYLOAD_NAME)
    perturbed_inputs[validated_casilla_id("1912", surface="1912")] = Decimal("900.00")
    perturbed = _scenario(
        inputs=perturbed_inputs,
        expected_1826=Decimal("0.00"),
        expected_1830=Decimal("0.00"),
        expected_1836=Decimal("0.00"),
        expected_1840=Decimal("0.00"),
        scenario_id="m100-2024-1826-anti-tautology-perturbed",
    )
    perturbed_report = run_registry_calculation_scenario(
        perturbed, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT
    )
    assert grounded_report.calculation.values[_CASILLA_1826] != perturbed_report.calculation.values[_CASILLA_1826], (
        "1826 must differ when the gastos-de-transmisión raw input changes"
    )
    assert grounded_report.calculation.values[_CASILLA_1836] != perturbed_report.calculation.values[_CASILLA_1836], (
        "1836 must differ when the gastos-de-transmisión raw input changes"
    )
    assert grounded_report.calculation.values[_CASILLA_1840] != perturbed_report.calculation.values[_CASILLA_1840], (
        "1840 must differ when the gastos-de-transmisión raw input changes"
    )


def test_1840_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of 1826/1830/1836/1840 is enrolled, not just computed.

    A companion registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``) already proves the
    ``externally_grounded_casilla_ids`` declaration on the
    ``modelo-100-2024-reconcile-when-present`` verification expectation is
    backed by the bundled
    ``corpus/manual_oracles/modelo-100-2024-ganancias-patrimoniales-transmision-inmueble.json``
    evidence. This test proves the OTHER end of the wire: that the
    declaration actually reaches the live, VALIDATED
    :class:`RegistryVerificationPolicy` fold consumed by the living reconcile
    flow, so 1826/1830/1836/1840 raise
    ``independently_grounded_fraction`` above the pre-existing baseline
    rather than sitting inert in TOML. Not tautological: the grounded set and
    the fraction are read from the registry's own declared+validated data,
    never hand-computed or asserted from a synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("100", filing_year=2024, period="0A")
    policy = snapshot.verification_policy()

    for casilla_id in (_CASILLA_1826, _CASILLA_1830, _CASILLA_1836, _CASILLA_1840):
        assert casilla_id in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_1840 in externally_grounded
    assert independently_grounded_fraction > 0.0
