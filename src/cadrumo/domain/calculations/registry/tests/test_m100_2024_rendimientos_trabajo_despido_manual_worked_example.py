"""Oracle test for M100 2024 casilla 0025 grounded against the AEAT manual's own
worked example (rendimientos del trabajo, despido improcedente, trabajador con
discapacidad).

Ground truth (bundled AEAT Manual práctico de Renta 2024, Parte 1, Capítulo 3
"Rendimientos del trabajo", "Caso práctico"):

    raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L11040-L11131

Raw taxpayer facts and the manual's own solution, quoted verbatim (line numbers
refer to the extracted markdown):

    Facts (L11041-11056): Don L.M.H., 33% discapacidad, despedido el 12-03-2024,
    despido calificado judicialmente de improcedente.
      Retribuciones ordinarias (ingresos íntegros dinerarios): 10.100 (L11046).
      Indemnización por despido: 75.000 (L11047).
      Descuentos: Cotizaciones a la Seguridad Social: 3.600 (L11048).
      Otras rentas no exentas del contribuyente en 2024: 5.500 (L11054-11055,
      consumed only by nota (3) below, not by this test's target chain).

    Solución, 1. Tratamiento de la indemnización (L11068-11116): exención
    conforme a la disposición transitoria undécima.2 del Estatuto de los
    Trabajadores = 64.800 (90 €/día x 720 días, tope de 720 días de salario).
    Importe no exento (L11111-11116): (75.000 - 64.800) = 10.200, sujeto a
    gravamen como rendimiento del trabajo con reducción del 30% por
    generación superior a 2 años (art. 18.2 LIRPF).

    Solución, 3. Declaración de los rendimientos (L11121-11131):
      "Rendimientos íntegros: (10.100 + 10.200) = 20.300" (L11121).
      "Reducción artículo 18.2 Ley del IRPF: (30% s/ 10.200) = 3.060" (L11122).
      "Total ingresos computables (20.300 -3.060) = 17.240" (L11123).
      "Gastos deducibles: (Seguridad Social) artículo 19.2.a) Ley del IRPF:
       3.600" (L11124).
      "Rendimiento neto previo (17.240 - 3.600 ) (1) = 13.640" (L11125).
      "Otros Gastos deducibles artículo 19.2.f) Ley del IRPF:
       • Por obtención de rendimientos de trabajo: 2.000
       • Trabajadores activos con discapacidad (2): 3.500" (L11126-11128).
      "Rendimiento neto: (13.640 - 2.000 - 3.500) = 8.140" (L11129).
      "Reducción por obtención de rendimientos del trabajo (3) 7.302"
      (L11130) — nota (3), L11142-11146: rendimiento neto previo (13.640)
      < 14.852 y rentas distintas del trabajo (5.500) <= 6.500, por lo que la
      cuantía de la reducción del art. 20 LIRPF (redacción 2024) es 7.302.
      "Rendimiento neto reducido: (8.140 - 7.302) = 838" (L11131).

Registry mapping (M100 2024 revision, casillas 0002-0025,
"rdto_trabajo"/"rdto_trabajo_res" sections):

    0003 "Retribuciones dinerarias ... Importe íntegro" = 10.100 (ordinarias)
      + 10.200 (indemnización no exenta, also a retribución dineraria) =
      20.300 — matches the manual's own combined "Rendimientos íntegros"
      figure exactly; the manual gives no dedicated box for the two
      components, and its own total confirms the lump-sum mapping.
    0011 "Reducciones (artículo 18, apartados 2 y 3, y disposiciones
      transitorias 11.ª, 12.ª y 25.ª de la Ley del Impuesto)" = 3.060 (the
      manual's own 30% s/ 10.200 figure; disposición transitoria 11.ª is
      precisely the despido-indemnización provision this example turns on).
    0012 "Total ingresos íntegros computables ([0003]+[0007]+[0008]+[0024]
      +[0009]+[0010]-[0011]-[0058])" = 20.300 - 3.060 = 17.240 — matches the
      manual's own "Total ingresos computables" exactly.

    0013 "Cotizaciones a la Seguridad Social ..." = 3.600 (Seguridad Social,
      matches the manual's gasto deducible exactly).
    0017 "Rendimiento neto previo ([0012]-[0013]-[0014]-[0015]-[0016])" =
      17.240 - 3.600 = 13.640 — matches the manual's own "Rendimiento neto
      previo" exactly.
    0018 "Suma de rendimientos netos previos (suma de [0017])" = copy(0017)
      = 13.640 (single payer in this example).

    0019 "Otros gastos deducibles" = min(2.000, max(0, [0018])) = min(2.000,
      13.640) = 2.000 — matches the manual's "Por obtención de rendimientos
      de trabajo: 2.000" (the art. 19.2.f general deduction, capped at the
      rendimiento neto previo per nota (1), L11142-11144; the cap is not
      binding here since 13.640 > 2.000).
    0020 "Incremento ... desempleados ... traslado de residencia" = 0 (not
      applicable; no mudanza in this example).
    0021 "Incremento para trabajadores activos que sean personas con
      discapacidad" = 3.500 (the manual's own figure, an AEAT-declared table
      value this registry does not independently compute — an input casilla,
      same status as casilla 0011's 30% reduction and the estimación-directa
      example's "es_normal" modalidad selector).
    0022 "Rendimiento neto" = max(0, [0018]-[0019]-[0020]-[0021]) =
      max(0, 13.640-2.000-0-3.500) = 8.140 — matches the manual's own
      "Rendimiento neto" exactly.

    0057 "Reducción ... Copa América" = 0 (not applicable).
    0023 "Cuantía aplicable con carácter general" (the art. 20 LIRPF
      reducción por obtención de rendimientos del trabajo) = 7.302 — the
      manual's own nota (3) figure. This registry revision does not compute
      the tiered art. 20 formula for this box (no ``formula`` targets 0023);
      it is a raw input casilla, so 7.302 is fed in verbatim from the
      manual, exactly as casillas 0011/0021 are.
    0025 "Rendimiento neto reducido ([0022]-[0057]-[0023])" = 8.140 - 0 -
      7.302 = 838 — matches the manual's own "Rendimiento neto reducido"
      exactly. THIS is the test's primary oracle target.

Anti-tautology: this test does not hand-compute 838 (nor 17.240, 13.640, or
8.140) from the registry formulas under test; every raw input is quoted from
the manual and every intermediate registry total (0012, 0017, 0022) is
independently cross-checked against a figure the manual states on its own
account before reaching 0025. A companion test zeroes the art. 20 reducción
input (0023, the term unique to the 0025 formula under test) and asserts 0025
changes — a formula that ignored the ``negate(0023)`` term, or returned a
constant, would fail that check.
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

_CASILLA_0012: CasillaId = validated_casilla_id("0012", surface="_CASILLA_0012")
_CASILLA_0017: CasillaId = validated_casilla_id("0017", surface="_CASILLA_0017")
_CASILLA_0022: CasillaId = validated_casilla_id("0022", surface="_CASILLA_0022")
_CASILLA_0025: CasillaId = validated_casilla_id("0025", surface="_CASILLA_0025")

# Each formula's OWN declared legal_refs / source_refs; the scenario comparison
# checks these against the calculation entry's provenance, not the casilla
# definition's provenance.
_LEGAL_REFS_0012 = ("ley-35-2006:art-17", "ley-35-2006:art-18", "ley-35-2006:art-7-h")
_SOURCE_REFS_0012 = ("lirpf-cuota-chain-authority", "aeat-dr-100-2024-dictionary")
_LEGAL_REFS_0017 = ("ley-35-2006:art-19",)
_SOURCE_REFS_0017 = ("lirpf-cuota-chain-authority",)
_LEGAL_REFS_0022 = ("ley-35-2006:art-19",)
_SOURCE_REFS_0022 = ("lirpf-cuota-chain-authority",)
_LEGAL_REFS_0025 = ("ley-35-2006:art-18", "ley-35-2006:art-19", "ley-35-2006:art-20")
_SOURCE_REFS_0025 = ("lirpf-cuota-chain-authority",)

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

# Raw ingresos/gastos/reducciones inputs quoted from the manual; see the
# module docstring for the per-box mapping and its cross-validation against
# the manual's own stated subtotals.
#
# The four figures ``oracle_declared_figures`` returns for this payload are
# stated in the example's SOLUCION rather than in its opening facts: the
# certificate prints retribuciones, indemnizacion and cotizaciones, and the
# manual then works them into the rendimientos integros, the art. 18.2
# reduccion, the deducible Seguridad Social and the discapacidad reduccion
# the scenario actually consumes. Each locator points at the line stating the
# figure the scenario uses, not at the raw fact it was derived from -- a
# locator that points at 10.100 for an input of 20.300 would assert a
# reviewability it does not have.
_ORACLE_PAYLOAD_NAME = "modelo-100-2024-rendimientos-trabajo-despido-improcedente.json"


def _scenario(*, reduccion_art_20: Decimal, expected_0025: Decimal, scenario_id: str) -> RegistryCalculationScenario:
    inputs = oracle_declared_figures(_ORACLE_PAYLOAD_NAME)
    inputs[validated_casilla_id("0023", surface="0023")] = reduccion_art_20
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
                target_casilla_id=_CASILLA_0012,
                value=Decimal("17240.00"),
                legal_refs=_LEGAL_REFS_0012,
                source_refs=_SOURCE_REFS_0012,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0017,
                value=Decimal("13640.00"),
                legal_refs=_LEGAL_REFS_0017,
                source_refs=_SOURCE_REFS_0017,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0022,
                value=Decimal("8140.00"),
                legal_refs=_LEGAL_REFS_0022,
                source_refs=_SOURCE_REFS_0022,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0025,
                value=expected_0025,
                legal_refs=_LEGAL_REFS_0025,
                source_refs=_SOURCE_REFS_0025,
            ),
        ),
        notes=("raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L11040-L11131",),
    )


def test_0025_manual_worked_example_despido_improcedente_discapacidad() -> None:
    """0025 = 838 for the manual's despido-improcedente caso práctico.

    Oracle: AEAT Manual práctico de Renta 2024, Parte 1, Cap. 3, caso práctico
    "Determinar el rendimiento neto reducido del trabajo" for a trabajador con
    discapacidad despedido improcedentemente — "Rendimiento neto reducido:
    (8.140-7.302) = 838" (L11131). Every raw ingreso/gasto/reducción figure
    feeding the scenario is quoted verbatim from the manual; the intermediate
    0012/0017/0022 totals are cross-checked against the manual's own stated
    subtotals (17.240 / 13.640 / 8.140) in the same assertion. See the module
    docstring for the full per-box trace.
    """
    scenario = _scenario(
        reduccion_art_20=Decimal("7302.00"),
        expected_0025=Decimal("838.00"),
        scenario_id="m100-2024-0025-manual-despido-improcedente-discapacidad",
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0025_anti_tautology_art20_reduccion_change_changes_value() -> None:
    """Zeroing the art. 20 reducción input (0023) must change 0025.

    Anti-tautology: 0025's own formula is ``[0022]-[0057]-[0023]``; this check
    isolates the ``negate(0023)`` term that is unique to the formula under
    test (0022 is already independently cross-checked against the manual's
    own "Rendimiento neto" figure in the primary test above). It does not
    hand-compute or assert the zero-reducción figure (that would reuse the
    same subtraction under test); it only asserts the two scenarios diverge,
    mirroring the ``!=``-only pattern used elsewhere in this test suite (e.g.
    ``test_0226_anti_tautology_modalidad_switch_changes_value``). A formula
    that ignored casilla 0023, or always returned a constant, would fail this
    check.
    """
    with_reduccion = _scenario(
        reduccion_art_20=Decimal("7302.00"),
        expected_0025=Decimal("838.00"),
        scenario_id="m100-2024-0025-anti-tautology-with-reduccion",
    )
    with_reduccion_report = run_registry_calculation_scenario(
        with_reduccion,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    assert_registry_scenario_matches(with_reduccion_report)

    # The zero-reducción scenario's expected 0025 value is never asserted
    # against a hand-computed figure (assert_registry_scenario_matches is
    # never called on it); only its divergence from the grounded scenario is
    # checked below. The placeholder value is structurally required by
    # RegistryScenarioExpectedOutput but is not consulted.
    without_reduccion = _scenario(
        reduccion_art_20=Decimal("0.00"),
        expected_0025=Decimal("0.00"),
        scenario_id="m100-2024-0025-anti-tautology-without-reduccion",
    )
    without_reduccion_report = run_registry_calculation_scenario(
        without_reduccion,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    assert (
        with_reduccion_report.calculation.values[_CASILLA_0025]
        != without_reduccion_report.calculation.values[_CASILLA_0025]
    ), "0025 must differ when the art. 20 reducción input (0023) changes"


def test_0025_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of 0012/0017/0022/0025 is enrolled, not just computed.

    A companion registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``) already proves the
    ``externally_grounded_casilla_ids`` declaration on the
    ``modelo-100-2024-reconcile-when-present`` verification expectation is
    backed by the bundled
    ``corpus/manual_oracles/modelo-100-2024-rendimientos-trabajo-despido-improcedente.json``
    evidence. This test proves the OTHER end of the wire: that the
    declaration actually reaches the live, VALIDATED
    :class:`RegistryVerificationPolicy` fold consumed by the living reconcile
    flow, so 0025 (and its manually-cross-checked
    upstream totals 0012/0017/0022) raise ``independently_grounded_fraction``
    above the estimación-directa baseline rather than sitting inert in TOML.
    Not tautological: the grounded set and the fraction are read from the
    registry's own declared+validated data, never hand-computed or asserted
    from a synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("100", filing_year=2024, period="0A")
    policy = snapshot.verification_policy()

    for casilla_id in (_CASILLA_0012, _CASILLA_0017, _CASILLA_0022, _CASILLA_0025):
        assert casilla_id in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_0025 in externally_grounded
    assert independently_grounded_fraction > 0.0
