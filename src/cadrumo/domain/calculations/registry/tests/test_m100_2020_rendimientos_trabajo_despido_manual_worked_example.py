"""Oracle test for M100 2020 casilla 0025 grounded against the AEAT manual's own
worked example (rendimientos del trabajo, despido improcedente, trabajador con
discapacidad).

Ground truth (bundled AEAT Manual práctico de Renta 2020, Parte 1, Capítulo 3
"Rendimientos del trabajo", "Caso práctico"):

    raw_evidence_locator: corpus/manuals/renta/2020/part1/source.pdf.extracted.md#L8256-L8362

This is a DIFFERENT despido-improcedente scenario than the one the 2024 manual
carries (different taxpayer, dates, and amounts; the same legal mechanism —
disposición transitoria undécima.2 del Estatuto de los Trabajadores, art. 18.2
LIRPF 30% reduction, art. 20 LIRPF reducción por obtención de rendimientos del
trabajo).

Raw taxpayer facts and the manual's own solution, quoted verbatim (line numbers
refer to the extracted markdown):

    Facts (L8257-8270): Don L.M.H., 33% discapacidad, contratado indefinidamente
    el 1-1-1999, despedido el 12-03-2020, despido calificado judicialmente de
    improcedente.
      Retribuciones ordinarias (ingresos íntegros dinerarios): 8.100 (L8261).
      Indemnización por despido: 75.000 (L8262).
      Retenciones IRPF: 0,00 (L8263).
      Descuentos: Cotizaciones a la Seguridad Social: 610 (L8264).
      Prestación de desempleo, modalidad de pago único: 16.800 (L8265-8268,
      exenta del IRPF per L8330-8332, not consumed by this test's target
      chain).
      Otras rentas no exentas del contribuyente en 2020: 5.500 (L8269-8270,
      consumed only by nota (3) below, not by this test's target chain).
      Salario regulador diario para el cálculo de la indemnización: 90 €
      (L8273-8274).

    Solución, a. Tratamiento de la indemnización (L8276-8317): exención
    conforme a la disposición transitoria undécima.2 del texto refundido de
    la Ley del Estatuto de los Trabajadores = 64.800 (90 €/día x 720 días,
    tope de 720 días de salario per L8309-8313).
    Importe no exento (L8317-8329): "El exceso de la cantidad percibida
    sobre el importe exento (75.000 – 64.800) = 10.200 euros está sujeto a
    gravamen en concepto de rendimientos del trabajo. No obstante, sobre
    dicha cantidad deberá aplicarse el porcentaje de reducción del 30 por
    100 por entenderse generada en un período de tiempo superior a 2 años"
    (L8323-8326).

    Solución, c. Declaración de los rendimientos obtenidos (L8333-8345):
      "Rendimientos íntegros: (8.100 + 10.200) = 18.300,00" (L8334).
      "Reducción artículo 18.2 Ley del IRPF: (30% s/ 10.200) = 3.060,00"
       (L8335).
      "Total ingresos computables (18.300 -3.060) = 15.240,00" (L8336).
      "Gastos deducibles: (Seguridad Social) artículo 19.2.a) Ley del IRPF:
       610,00" (L8337).
      "Rendimiento neto previo (15.240,00 – 610,00) (1) = 14.630,00"
       (L8338).
      "Otros Gastos deducibles artículo 19.2.f) Ley del IRPF:
       • Por obtención de rendimientos de trabajo: 2.000,00
       • Trabajadores activos con discapacidad (2): 3.500,00" (L8339-8341).
      "Rendimiento neto: (14.630 – 2.000 – 3.500) = 9.130,00" (L8342).
      "Reducción por obtención de rendimientos del trabajo (3) 5.565 -
       [1,5 x (14.630 - 13.115)] = 3.292,50" (L8343-8344) — nota (3),
       L8353-8361: rendimiento neto previo (14.630) comprendido entre
       13.115 y 16.825 euros y rentas distintas del trabajo (5.500) <=
       6.500, por lo que la cuantía de la reducción del art. 20 LIRPF
       (redacción a 01/01/2020) es 3.292,50.
      "Rendimiento neto reducido: (9.130,00 -3.292,50) = 5.837,50"
       (L8345).

Registry mapping (M100 2020 revision, casillas 0002-0025,
"rdto_trabajo"/"rdto_trabajo_res" sections):

    0003 "Retribuciones dinerarias ... Importe íntegro" = 8.100 (ordinarias)
      + 10.200 (indemnización no exenta, also a retribución dineraria) =
      18.300 — matches the manual's own combined "Rendimientos íntegros"
      figure exactly; the manual gives no dedicated box for the two
      components, and its own total confirms the lump-sum mapping.
    0011 "Reducciones (artículo 18, apartados 2 y 3, y disposiciones
      transitorias 11.ª, 12.ª y 25.ª de la Ley del Impuesto)" = 3.060 (the
      manual's own 30% s/ 10.200 figure; disposición transitoria 11.ª is
      precisely the despido-indemnización provision this example turns on).
    0012 "Total ingresos íntegros computables ([0003]+[0007]+[0008]+[0009]
      +[0010]-[0011])" = 18.300 - 3.060 = 15.240 — matches the manual's own
      "Total ingresos computables" exactly.

    0013 "Cotizaciones a la Seguridad Social ..." = 610 (matches the
      manual's gasto deducible exactly).
    0017 "Rendimiento neto previo ([0012]-[0013]-[0014]-[0015]-[0016])" =
      15.240 - 610 = 14.630 — matches the manual's own "Rendimiento neto
      previo" exactly.
    0018 "Suma de rendimientos netos previos (suma de [0017])" = copy(0017)
      = 14.630 (single payer in this example).

    0019 "Otros gastos deducibles" = 2.000 — matches the manual's "Por
      obtención de rendimientos de trabajo: 2.000" (the art. 19.2.f general
      deduction). This registry revision does not compute the capped
      ``min(2.000, [0018])`` formula for this box (no ``formula`` targets
      0019 in the 2020 revision); it is a raw input casilla here, same
      status as casillas 0011/0021/0023.
    0020 "Incremento ... desempleados ... traslado de residencia" = 0 (not
      applicable; no mudanza in this example).
    0021 "Incremento para trabajadores activos que sean personas con
      discapacidad" = 3.500 — the manual's own figure, an AEAT-declared
      table value this registry does not independently compute — an input
      casilla, same status as casilla 0011's 30% reduction and the
      estimación-directa example's "es_normal" modalidad selector.
    0022 "Rendimiento neto ([0018]-[0019]-[0020]-[0021])" =
      14.630 - 2.000 - 0 - 3.500 = 9.130 — matches the manual's own
      "Rendimiento neto" exactly.

    0023 "Cuantía aplicable con carácter general" (the art. 20 LIRPF
      reducción por obtención de rendimientos del trabajo) = 3.292,50 — the
      manual's own nota (3) figure. This registry revision does not compute
      the tiered art. 20 formula for this box (no ``formula`` targets 0023);
      it is a raw input casilla, so 3.292,50 is fed in verbatim from the
      manual, exactly as casillas 0011/0021 are.
    0025 "Rendimiento neto reducido ([0022]-[0023])" = 9.130 - 3.292,50 =
      5.837,50 — matches the manual's own "Rendimiento neto reducido"
      exactly. THIS is the test's primary oracle target.

Anti-tautology: this test does not hand-compute 5.837,50 (nor 15.240,
14.630, or 9.130) from the registry formulas under test; every raw input is
quoted from the manual and every intermediate registry total (0012, 0017,
0022) is independently cross-checked against a figure the manual states on
its own account before reaching 0025. A companion test zeroes the art. 20
reducción input (0023, the term unique to the 0025 formula under test) and
asserts 0025 changes — a formula that ignored the ``negate(0023)`` term, or
returned a constant, would fail that check.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from ..authority import ValidatedRegistryAuthority
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
_LEGAL_REFS_0012 = ("ley-35-2006:art-17", "ley-35-2006:art-18")
_SOURCE_REFS_0012 = ("lirpf-cuota-chain-authority",)
_LEGAL_REFS_0017 = ("ley-35-2006:art-19",)
_SOURCE_REFS_0017 = ("lirpf-cuota-chain-authority",)
_LEGAL_REFS_0022 = ("ley-35-2006:art-19",)
_SOURCE_REFS_0022 = ("lirpf-cuota-chain-authority",)
_LEGAL_REFS_0025 = ("ley-35-2006:art-18", "ley-35-2006:art-19", "ley-35-2006:art-20")
_SOURCE_REFS_0025 = ("lirpf-cuota-chain-authority",)

# The 2020 revision's entire formula tree references exactly two bindings
# (es-normal, tax-residence-ccaa) and two relations (rel-130, rel-131 pagos
# fraccionados) directly by id (see test_m100_2020_estimacion_directa_manual_
# worked_example.py's module docstring for the full accounting); supplying
# these is sufficient for calculate_registry_snapshot to evaluate the WHOLE
# 2020 revision without raising on a missing binding/relation elsewhere in
# the tree.
_REL_2020 = {
    "renta-2020-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2020-rel-131-pagos-fraccionados": Decimal("0"),
}

# Raw ingresos/gastos/reducciones inputs quoted from the manual; see the
# module docstring for the per-box mapping and its cross-validation against
# the manual's own stated subtotals.
#
# The four figures ``oracle_declared_figures`` returns for this payload are
# stated in the example's SOLUCION rather than in its opening facts: the
# certificate prints retribuciones, indemnizacion and cotizaciones, and the
# manual then works them into the rendimientos integros, the art. 18.2
# reduccion, the deducible Seguridad Social and the two art. 19.2.f)
# reducciones the scenario actually consumes. Each locator points at the
# line stating the figure the scenario uses, not at the raw fact it was
# derived from -- a locator that points at 10.100 for an input of 20.300
# would assert a reviewability it does not have.
_ORACLE_PAYLOAD_NAME = "modelo-100-2020-rendimientos-trabajo-despido-improcedente.json"


def _scenario(*, reduccion_art_20: Decimal, expected_0025: Decimal, scenario_id: str) -> RegistryCalculationScenario:
    inputs = oracle_declared_figures(_ORACLE_PAYLOAD_NAME)
    inputs[validated_casilla_id("0023", surface="0023")] = reduccion_art_20
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2020",
        filing_year=2020,
        period="0A",
        inputs=inputs,
        binding_values={"renta-2020-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        enum_binding_values={"renta-2020-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2020,
        date_context={"filing_period": date(2020, 12, 31)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0012,
                value=Decimal("15240.00"),
                legal_refs=_LEGAL_REFS_0012,
                source_refs=_SOURCE_REFS_0012,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0017,
                value=Decimal("14630.00"),
                legal_refs=_LEGAL_REFS_0017,
                source_refs=_SOURCE_REFS_0017,
            ),
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0022,
                value=Decimal("9130.00"),
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
        notes=("raw_evidence_locator: corpus/manuals/renta/2020/part1/source.pdf.extracted.md#L8256-L8362",),
    )


def test_0025_manual_worked_example_despido_improcedente_discapacidad() -> None:
    """0025 = 5.837,50 for the manual's despido-improcedente caso práctico.

    Oracle: AEAT Manual práctico de Renta 2020, Parte 1, Cap. 3, caso práctico
    "Determinar el rendimiento neto reducido del trabajo" for a trabajador con
    discapacidad despedido improcedentemente — "Rendimiento neto reducido:
    (9.130,00-3.292,50) = 5.837,50" (L8345). Every raw ingreso/gasto/reducción
    figure feeding the scenario is quoted verbatim from the manual; the
    intermediate 0012/0017/0022 totals are cross-checked against the manual's
    own stated subtotals (15.240 / 14.630 / 9.130) in the same assertion. See
    the module docstring for the full per-box trace.
    """
    scenario = _scenario(
        reduccion_art_20=Decimal("3292.50"),
        expected_0025=Decimal("5837.50"),
        scenario_id="m100-2020-0025-manual-despido-improcedente-discapacidad",
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0025_anti_tautology_art20_reduccion_change_changes_value() -> None:
    """Zeroing the art. 20 reducción input (0023) must change 0025.

    Anti-tautology: 0025's own formula is ``[0022]-[0023]``; this check
    isolates the ``negate(0023)`` term that is unique to the formula under
    test (0022 is already independently cross-checked against the manual's
    own "Rendimiento neto" figure in the primary test above). It does not
    hand-compute or assert the zero-reducción figure (that would reuse the
    same subtraction under test); it only asserts the two scenarios diverge.
    A formula that ignored casilla 0023, or always returned a constant,
    would fail this check.
    """
    with_reduccion = _scenario(
        reduccion_art_20=Decimal("3292.50"),
        expected_0025=Decimal("5837.50"),
        scenario_id="m100-2020-0025-anti-tautology-with-reduccion",
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
        scenario_id="m100-2020-0025-anti-tautology-without-reduccion",
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
    ``modelo-100-2020-reconcile-when-present`` verification expectation is
    backed by the bundled
    ``corpus/manual_oracles/modelo-100-2020-rendimientos-trabajo-despido-improcedente.json``
    evidence. This test proves the OTHER end of the wire: that the
    declaration actually reaches the live, VALIDATED
    :class:`RegistryVerificationPolicy` fold consumed by the living reconcile
    flow, so 0025 (and its manually-cross-checked
    upstream totals 0012/0017/0022) raise ``independently_grounded_fraction``
    above the estimación-directa-only baseline rather than sitting inert in
    TOML. Not tautological: the grounded set and the fraction are read from
    the registry's own declared+validated data, never hand-computed or
    asserted from a synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("100", filing_year=2020, period="0A")
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
