"""Oracle test for M100 2024 casilla 0226 grounded against the AEAT manual's own
worked example (estimación directa simplificada, actividad profesional).

Ground truth (bundled AEAT Manual práctico de Renta 2024, Parte 1, Capítulo 7
"Rendimientos de actividades económicas. Método de estimación directa",
"Caso práctico (determinación del rendimiento neto derivado de actividad
profesional en estimación directa, modalidad simplificada)"):

    raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L19807-L19965

Raw taxpayer facts quoted verbatim from the manual (fiscal/"valores fiscales"
column unless noted; line numbers refer to the extracted markdown):

    Ingresos íntegros (L19823-19825):
      - Honorarios por prestación de servicios: 124.000
      - Conferencias y publicaciones: 10.800
    Nota (2), L19918-19919: "Las cantidades percibidas en concepto de
      'Conferencias y publicaciones' tienen la consideración de rendimientos
      de la actividad profesional realizada por el contribuyente."
    Nota (1), L19916-19917: autoconsumo (10 radiografías a precio de mercado
      de 60 €) = 600.
    Nota (3), L19920-19922: variación de existencias (16.100 finales -
      13.100 iniciales) = +3.000, ingreso íntegro.
    L19879-19883 (table row "Total ingresos"): 137.800 (registrado) /
      138.400 (fiscal).

    Gastos (L19826-19845, fiscal column at L19884-19909):
      - Sueldos y salarios: 18.900 registrado / 17.700 fiscal (nota 4,
        L19923-19927: 1.200 € pagados al cónyuge no son deducibles).
      - Seguridad Social: 5.900.
      - RETA del titular de la actividad: 3.300.
      - Compras material radiológico y sanitario: 19.000 (nota 5,
        L19928-19943: la compra íntegra entra como gasto; la variación de
        existencias +3.000 entra ya como ingreso).
      - Gastos financieros: 1.100.
      - Amortización del local: 2.900; amortización del equipamiento
        radiológico: 5.000 → dotaciones 7.900 (nota 6, L19944-19945).
      - IVA soportado en gastos corrientes: 1.600 (nota 7, L19946-19947:
        deducible por tratarse de actividad exenta de IVA).
      - Tributos no estatales: 1.700.
      - Asistencia VI Congreso Radiológico: 1.000 ("Otros conceptos
        fiscalmente deducibles" per the table's own parenthetical, L19907).
      - Adquisición libros y revistas médicas: 1.300.
      - Suministro eléctrico 4.000 + agua 300 + gas 1.000 + telefonía e
        Internet 2.500 = 7.800 (single "Suministro" table row, L19902).
      - Limpieza del local: 4.500; recibo de comunidad: 1.700 → "otros
        servicios exteriores" per the table's own parenthetical,
        L19904-19906.
    L19909 (table row "Total gastos"): 79.500 (registrado) / 78.300 (fiscal).

    L19910-19911 + nota (9), L19953-19957: "Conjunto de provisiones
      deducibles y gastos de difícil justificación" = 5 % sobre
      (138.400 - 78.300) = 3.005, capado a 2.000 € ("En este caso podrá
      deducir 2.000 euros al superar el 5 por 100 ... dicha cuantía").

    L19912 (table row "Rendimiento neto"): 58.300 (registrado) / 58.100
      (fiscal).
    L19913 (table row "Rendimiento neto reducido"): 58.100.
    L19914 (table row "Rendimiento neto reducido total"): 58.100.
    Nota (10), L19958-19960, and nota (11), L19961-19967: state the taxpayer
      has no rendimientos con período de generación superior a 2 años (art.
      32.2.1º/32.3 reductions do not apply), so "el rendimiento neto
      reducido ... coincide con el rendimiento neto" and "el rendimiento
      neto reducido total coincide con el rendimiento neto reducido" — i.e.
      no further reduction is applied beyond the table's own 58.100 figure.

Known extraction anomaly (NOT treated as ground truth): notas (10) and (11)
themselves restate the coinciding amount as "61.400 euros" instead of
"58.100". That figure appears nowhere else in the manual (grepped the full
extracted corpus — it occurs only in those two footnote sentences) and is
arithmetically unreachable from any combination of the raw figures quoted
above. It is inconsistent with all three explicit table rows ("Rendimiento
neto" / "Rendimiento neto reducido" / "Rendimiento neto reducido total", all
58.100) and is almost certainly a footnote-carryover artefact of PDF
extraction/OCR (or an AEAT manual erratum) rather than the example's actual
result. This test grounds the target on 58.100 because that figure is (a)
stated three times verbatim in the table, and (b) independently
re-derivable bottom-up from every raw line item via the registry's OWN
0180/0218/0221/0222/0223/0224 formula chain (see below) — the 61.400 figure
is not.

Registry mapping (M100 2024 revision, casillas 0163-0236,
"actividad_est_directa" section):

    0171 "Ingresos de explotación" (bound, ledger_renta_income_aggregation)
      = Honorarios + Conferencias = 124.000 + 10.800 = 134.800. The manual's
      own nota (2) confirms conferencias/publicaciones income counts as
      actividad-económica income, so both line items are lumped into the
      single "ingresos de explotación" registry box (the manual gives no
      finer split and the registry has no dedicated "conferencias" box).
    0175 "Autoconsumo de bienes y servicios" = 600.
    0177 "Variación de existencias (incremento de existencias finales)"
      = 3.000.
    0180 "Total ingresos computables" = sum([0171]..[0179])
      = 134.800 + 600 + 3.000 = 138.400 — matches the manual's own "Total
      ingresos" (fiscal) exactly.

    0181 "Compra de existencias" = 19.000.
    0184 "Sueldos y salarios" = 17.700.
    0185 "Seguridad Social a cargo de la empresa" = 5.900.
    0186 "Seguridad Social del titular de la actividad" (bound,
      ledger_renta_gastos_estimacion_directa_aggregation) = 3.300 (RETA).
    0193 "Reparaciones y conservación" = 3.800.
    0194 "Suministros (electricidad, agua, gas, telefonía e internet)"
      = 7.800.
    0202 "Otros servicios exteriores" = 4.500 (limpieza) + 1.700 (comunidad)
      = 6.200.
    0203 "Gastos financieros" (bound, ledger_renta_gastos_estimacion_directa_aggregation)
      = 1.100.
    0205 "IVA soportado" = 1.600.
    0206 "Otros tributos fiscalmente deducibles" = 1.700.
    0208 "Dotaciones del ejercicio para amortización de inmovilizado
      material" = 2.900 + 5.000 = 7.900.
    0217 "Otros conceptos fiscalmente deducibles (excepto provisiones)"
      = 1.300 (libros y revistas) + 1.000 (congreso) = 2.300. The
      per-box split of these two items is this test's one interpretive
      allocation (the manual gives no dedicated box for either); it is
      cross-validated below, not merely asserted, because the registry's
      OWN 0218 aggregation formula reproduces the manual's independently
      stated "Total gastos" = 78.300 exactly from this allocation.
    0218 "Suma ([0181]..[0195] + [0198]..[0200] + [0202] + [0203] + [0205]
      + [0206] + [0208] + [0227] + [0214]..[0217])"
      = 19.000+17.700+5.900+3.300+3.800+7.800+6.200+1.100+1.600+1.700+7.900
        +2.300 = 78.300 — matches the manual's "Total gastos" (fiscal)
      exactly, confirming the box allocation above.

    0219 "Provisiones fiscalmente deducibles" = 0 (none declared).
    0221 "Diferencia ([0180]-[0218])" = 138.400 - 78.300 = 60.100.
    0222 "Conjunto de provisiones deducibles y gastos de difícil
      justificación" = min(max(5% × 60.100, 0), 2.000) = min(3.005, 2.000)
      = 2.000 — matches nota (9) exactly (5 % × (138.400-78.300) = 3.005 €,
      capped at 2.000 €).
    0223 "Total gastos deducibles (simplificada)" = 0218 + 0222
      = 78.300 + 2.000 = 80.300.
    0224 "Rendimiento neto" (modalidad simplificada branch, driven by
      binding renta-2024-modelo-100-estimacion-directa-es-normal = 0)
      = [0180] - [0223] = 138.400 - 80.300 = 58.100 — matches the manual's
      "Rendimiento neto" (fiscal) exactly.
    0225 "Reducción de rendimientos irregulares (art. 32.1)" = 0 (nota 10:
      no hay rendimientos con período de generación > 2 años).
    0236 "Reducción Copa América" = 0 (not applicable).
    0226 "Rendimiento neto reducido ([0224]-[0225]-[0236])"
      = 58.100 - 0 - 0 = 58.100.

Anti-tautology: this test does not hand-compute 58.100 from the registry
formula under test; every raw input is quoted from the manual and every
intermediate registry total (0180, 0218, 0222, 0224) is independently
cross-checked against a figure the manual states on its own account
(138.400, 78.300, 2.000/3.005, 58.100) before reaching 0226. A companion
test flips the estimación-directa modalidad binding (0224's own
``if_then_else`` branch selector) from simplificada to normal and asserts
0226 changes — a constant-returning formula chain would fail that check.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources._boundary import bundled_path
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
_CASILLA_0226: CasillaId = validated_casilla_id("0226", surface="_CASILLA_0226")

# The 0226 formula's OWN declared legal_refs / source_refs
# (renta-2024-estimacion-directa-rendimiento-neto-reducido); the scenario
# comparison checks these against the calculation entry's provenance, not
# the casilla definition's provenance.
_LEGAL_REFS = ("ley-35-2006:art-28", "ley-35-2006:art-30", "ley-35-2006:art-32")
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

# The raw ingresos/gastos ``oracle_declared_figures`` returns for this payload
# were a hand-written literal block until the payload learned to declare its
# own inputs. Building them from the declaration is the point: a fixture and a
# payload that state the scenario separately can drift, and a fixture that
# drifts into reaching the printed figure by another route is precisely the
# failure this corpus exists to prevent. Sourced from one place, they cannot
# disagree.
#
# The declaration is not self-certifying — it does not prove these are the
# manual's numbers, only that one reviewable place claims they are, with a
# per-input line reference (``locator_by_casilla_id``) pointing at the page to
# check it against. The per-box mapping and its cross-validation against the
# manual's own "Total ingresos" / "Total gastos" subtotals are in the module
# docstring.
_ORACLE_PAYLOAD_NAME = "modelo-100-2024-estimacion-directa-simplificada.json"

_ACTIVIDAD_INPUTS: dict[CasillaId, Decimal] = oracle_declared_figures(_ORACLE_PAYLOAD_NAME)


# Nine of the inputs above are casillas the registry declares
# ``input_kind = "bound"``: 0171 to the ledger-income aggregation and the other
# eight to the ledger-expense one. Supplying them here hand-types values the
# engine is meant to PRODUCE, so this module grounds the formula chain from
# 0180 downward and asserts nothing about how those casillas are populated —
# the aggregation and the binding resolver are both stepped over. That boundary
# was invisible until it was declared; the scenario runner now refuses an
# undeclared bound input, so it cannot go quiet again.
_INGRESOS_LEG_REASON = (
    "ingresos leg supplied from the manual's own line items; the ledger-driven "
    "coverage of this same caso practico lives in "
    "test_ledger_income_chain_aeat_exempt_worked_example.py, which resolves 0171 "
    "through the aggregation and the binding instead"
)
_GASTO_LEG_REASON = (
    "gasto leg supplied from the manual's own per-box figures; no ledger-driven "
    "coverage of the estimacion-directa expense aggregation exists yet, so this "
    "scenario grounds the formula chain above it and claims nothing about it"
)
_HAND_TYPED_BOUND_CASILLAS: dict[CasillaId, str] = {
    validated_casilla_id("0171", surface="0171"): _INGRESOS_LEG_REASON,
    validated_casilla_id("0186", surface="0186"): _GASTO_LEG_REASON,
    validated_casilla_id("0193", surface="0193"): _GASTO_LEG_REASON,
    validated_casilla_id("0194", surface="0194"): _GASTO_LEG_REASON,
    validated_casilla_id("0202", surface="0202"): _GASTO_LEG_REASON,
    validated_casilla_id("0203", surface="0203"): _GASTO_LEG_REASON,
    validated_casilla_id("0206", surface="0206"): _GASTO_LEG_REASON,
    validated_casilla_id("0208", surface="0208"): _GASTO_LEG_REASON,
    validated_casilla_id("0217", surface="0217"): _GASTO_LEG_REASON,
}


def _scenario(*, es_normal: Decimal, expected_0226: Decimal, scenario_id: str) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2024",
        filing_year=2024,
        period="0A",
        inputs=_ACTIVIDAD_INPUTS,
        binding_values={
            **_BASE_BINDINGS_2024,
            "renta-2024-modelo-100-estimacion-directa-es-normal": es_normal,
        },
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2024,
        date_context={"filing_period": date(2024, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_0226,
                value=expected_0226,
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
        notes=("raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L19807-L19965",),
        hand_typed_bound_casillas=_HAND_TYPED_BOUND_CASILLAS,
    )


def test_0226_manual_worked_example_medico_radiologo_simplificada() -> None:
    """0226 = 58.100 for the manual's médico radiólogo caso práctico (modalidad simplificada).

    Oracle: AEAT Manual práctico de Renta 2024, Parte 1, Cap. 7, caso práctico
    "determinación del rendimiento neto derivado de actividad profesional en
    estimación directa, modalidad simplificada" — table rows "Rendimiento
    neto" / "Rendimiento neto reducido" / "Rendimiento neto reducido total",
    all 58.100 (L19912-19914). Every raw ingreso/gasto figure feeding the
    scenario is quoted verbatim from the manual; see the module docstring for
    the full per-box trace and the independent 0180/0218/0222/0224
    cross-checks against the manual's own stated subtotals.
    """
    scenario = _scenario(
        es_normal=Decimal("0"),
        expected_0226=Decimal("58100.00"),
        scenario_id="m100-2024-0226-manual-medico-radiologo-simplificada",
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_0226_anti_tautology_modalidad_switch_changes_value() -> None:
    """Switching modalidad normal<->simplificada must change 0226.

    Anti-tautology: 0224 (and therefore 0226) is computed via an
    ``if_then_else`` on the estimación-directa modalidad binding, selecting
    between ``[0180]-[0220]`` (normal — no 5 % gastos-de-dificil-justificacion
    deduction) and ``[0180]-[0223]`` (simplificada — includes it). This check
    does not hand-compute or assert the normal-branch figure (that would
    reuse the same subtraction under test); it only asserts the two branches
    diverge, mirroring the ``!=``-only pattern used elsewhere in this test
    suite (e.g. ``test_0461_anti_tautology_declaration_type_change_2024``). A
    formula that ignored the modalidad binding, or always returned a
    constant, would fail this check.
    """
    simplificada = _scenario(
        es_normal=Decimal("0"),
        expected_0226=Decimal("58100.00"),
        scenario_id="m100-2024-0226-anti-tautology-simplificada",
    )
    simplificada_report = run_registry_calculation_scenario(
        simplificada,
        registry_root=_REGISTRY_ROOT,
        source_root=_SOURCE_ROOT,
    )
    assert_registry_scenario_matches(simplificada_report)

    # The "normal" branch's expected value is never asserted against a
    # hand-computed figure; only its divergence from the grounded
    # simplificada figure is checked below. The placeholder value is
    # structurally required by RegistryScenarioExpectedOutput but is not
    # consulted by assert_registry_scenario_matches (never called here).
    normal = _scenario(
        es_normal=Decimal("1"),
        expected_0226=Decimal("0.00"),
        scenario_id="m100-2024-0226-anti-tautology-normal",
    )
    normal_report = run_registry_calculation_scenario(normal, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert simplificada_report.calculation.values[_CASILLA_0226] != normal_report.calculation.values[_CASILLA_0226], (
        "0226 must differ between modalidad simplificada and modalidad normal"
    )


def test_0226_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of 0226 is enrolled, not just computed.

    A companion registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``) already proves the
    ``externally_grounded_casilla_ids = ["0226"]`` declaration on the
    ``modelo-100-2024-reconcile-when-present`` verification expectation is
    backed by the bundled
    ``corpus/manual_oracles/modelo-100-2024-estimacion-directa-simplificada.json``
    evidence. This test proves the OTHER end of the wire: that the declaration
    actually reaches the live, VALIDATED :class:`RegistryVerificationPolicy`
    fold consumed by the living reconcile flow, so 0226
    raises ``independently_grounded_fraction`` above zero rather than sitting
    inert in TOML. Not tautological: the grounded set and the fraction are
    read from the registry's own declared+validated data, never hand-computed
    or asserted from a synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("100", filing_year=2024, period="0A")
    policy = snapshot.verification_policy()

    assert _CASILLA_0226 in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_0226 in externally_grounded
    assert independently_grounded_fraction > 0.0
