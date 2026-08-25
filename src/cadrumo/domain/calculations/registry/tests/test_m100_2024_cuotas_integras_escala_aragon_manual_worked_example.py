"""Oracle test for M100 2024 cuota-integra / escala / minimo chain grounded
against the AEAT manual's own worked example (calculo de las cuotas integras
estatal y autonomica, contribuyente residente en Aragon).

Ground truth (bundled AEAT Manual practico de Renta 2024, Parte 1, Capitulo 15
"Calculo del impuesto: determinacion de las cuotas integras", "Ejemplo
practico: calculo de las cuotas integras estatal y autonomica" de don A.B.C.,
residente en la Comunidad Autonoma de Aragon):

    raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L48602-L48643

Givens quoted verbatim (L48604-48607):
    - Base liquidable general: 23.900
    - Base liquidable del ahorro: 2.800
    - Minimo personal y familiar: 5.550

Solucion, each subtotal quoted verbatim from the manual:
    1. Escala de gravamen sobre la base liquidable general (23.900):
         a. Escala general (estatal): "Hasta 20.200 = 2.112,75 / Resto: 3.700
            al 15% = 555 / Cuota 1 resultante (2.112,75 + 555) = 2.667,75"
            (L48612-48614) -> casilla 0528.
         b. Escala autonomica de Aragon: "Hasta 21.210 = 2.218,39 / Resto:
            2.690 al 15,00% = 403,5 / Cuota 2 resultante = 2.218,39 + 403,5 =
            2.621,89" (L48622-48624) -> casilla 0529.
    2. Escala sobre la base liquidable general correspondiente al minimo
       personal y familiar (5.550): "5.550 al 9,50% = 527,25" (both escalas,
       L48630-48635) -> Cuota 3 / Cuota 4 (intermediate, not separately
       enrolled casillas).
    3. Cuota integra general:
         "Cuota integra general estatal (Cuota 1 - Cuota 3): 2.667,75 - 527,25
          = 2.140,50" (L48637) -> casilla 0532.
         "Cuota integra general autonomica (Cuota 2 - Cuota 4): 2.621,89 -
          527,25 = 2.094,64" (L48638) -> casilla 0533.
    4. Gravamen de la base liquidable del ahorro (2.800): "Gravamen estatal
       2.800 x 9,50% = 266 / Gravamen autonomico 2.800 x 9,50% = 266"
       (L48640-48641) -> intermediate ahorro cuota.
    5. Cuota integra:
         "Cuota integra estatal (2.140,50 + 266) = 2.406,50" (L48642)
          -> casilla 0545.
         "Cuota integra autonomica (2.094,64 + 266) = 2.360,64" (L48643)
          -> casilla 0546.

The minimo personal y familiar 5.550 the manual states as a given (L48607) is
the LIRPF art. 57 base minimo del contribuyente, which the registry computes
independently for a single filer under 65 into casillas 0519 (estatal) and
0520 (autonomica) via the 0166->0511->0072/0073 chain.

Registry mapping (M100 2024 revision, cuota-chain casillas):
    0519 "Minimo personal y familiar estatal" (0072 = sum 0511+0513+0515+0517)
      = 5.550,00 (single filer under 65, no descendientes/ascendientes/
      discapacidad; 0511 minimo del contribuyente = parametro base 5.550).
    0520 "Minimo personal y familiar autonomica" = 5.550,00 (Aragon applies no
      autonomic minimo variation for 2024).
    0528 "Cuota escala estatal sobre base liquidable general" = 2.667,75.
    0529 "Cuota escala autonomica sobre base liquidable general" = 2.621,89.
    0532 "Cuota base liquidable general estatal" (Cuota 1 - Cuota 3) = 2.140,50.
    0533 "Cuota base liquidable general autonomica" (Cuota 2 - Cuota 4)
      = 2.094,64.
    0545 "Cuota integra estatal" (0532 + gravamen ahorro estatal 266)
      = 2.406,50.
    0546 "Cuota integra autonomica" (0533 + gravamen ahorro autonomico 266)
      = 2.360,64.

Anti-tautology: this test does not hand-compute any figure from the escala
formulas under test. The scenario supplies only the base liquidable general
(23.900, via leaf 0102), the base liquidable del ahorro (2.800, via leaf 0429)
and a single-filer profile that yields the LIRPF base minimo (5.550); every
grounded casilla value is quoted verbatim from the manual's own solucion. A
companion test switches the residence Comunidad Autonoma from Aragon to Madrid
and asserts the autonomic cuotas (0529/0533/0546) change (the two autonomic
tariffs differ), proving the autonomic escala parameter is actually consulted
rather than a constant returned.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .. import (
    ValidatedRegistryAuthority,
)
from ._manual_oracle_support import oracle_declared_figures, read_manual_worked_example
from ._modelo_100_registry_support import _m100_2024_deduccion_maternidad_bindings
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()

# The manual's givens, injected at the nearest raw-input leaf so the engine
# computes the whole cuota chain forward. 0102 is a base-general ganancia leaf
# that flows identity into base liquidable general (0500); 0429 is a base-ahorro
# leaf that flows identity into base liquidable del ahorro (0510).
_SOURCE_REFS_CUOTA = ("lirpf-cuota-chain-authority",)
_SOURCE_REFS_0529 = ("aeat-renta-2024-manual-parte1", "boe-modelo-100-2024-form")

_GROUNDED_OUTPUT_REFS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("0519", ("ley-35-2006:art-56",), _SOURCE_REFS_CUOTA),
    ("0520", ("ley-35-2006:art-56", "ley-35-2006:art-73"), _SOURCE_REFS_CUOTA),
    ("0528", ("ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-64"), _SOURCE_REFS_CUOTA),
    ("0529", ("ley-35-2006:art-73", "ley-35-2006:art-74", "ley-35-2006:art-75-2015"), _SOURCE_REFS_0529),
    ("0532", ("ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-64"), _SOURCE_REFS_CUOTA),
    ("0533", ("ley-35-2006:art-73", "ley-35-2006:art-74", "ley-35-2006:art-75-2015"), _SOURCE_REFS_CUOTA),
    ("0545", ("ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-66"), _SOURCE_REFS_CUOTA),
    ("0546", ("ley-35-2006:art-73", "ley-35-2006:art-74", "ley-35-2006:art-76"), _SOURCE_REFS_CUOTA),
)
"""The grounded casillas and the provenance each carries.

The FIGURES live in the oracle payload, which is the only place a manual-printed
number belongs. Keeping them here too made this test and its payload two independent
transcriptions of one page, agreeing by nothing.
"""

_ORACLE_PAYLOAD_NAME = "modelo-100-2024-cuotas-integras-escala-aragon.json"


# A single filer under 65 in the target Comunidad: every profile-derived minimo
# and retencion binding at its neutral value so the base minimo del
# contribuyente (LIRPF art. 57 = 5.550) is the only minimo in play.
_BASE_BINDINGS_2024: dict[str, Decimal] = {
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
    "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("0"),
    **_m100_2024_deduccion_maternidad_bindings(),
    "renta-2024-profile-minimo-descendientes-estatal": Decimal("0"),
    "renta-2024-profile-minimo-descendientes-autonomico": Decimal("0"),
}

_REL_2024: dict[str, Decimal] = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}


def _scenario(*, ccaa: str, scenario_id: str, grounded: bool) -> RegistryCalculationScenario:
    expected_by_casilla_id = read_manual_worked_example(_ORACLE_PAYLOAD_NAME).expected_by_casilla_id
    expected_outputs = (
        tuple(
            RegistryScenarioExpectedOutput(
                target_casilla_id=validated_casilla_id(casilla_id, surface=casilla_id),
                # The FIGURE comes from the oracle payload; only the provenance the
                # scenario comparison checks against the calculation entry stays local.
                value=Decimal(expected_by_casilla_id[casilla_id]),
                legal_refs=legal_refs,
                source_refs=source_refs,
            )
            for casilla_id, legal_refs, source_refs in _GROUNDED_OUTPUT_REFS
        )
        if grounded
        else (
            # The comparison harness requires at least one expected output; the
            # non-grounded (Madrid) scenario in the anti-tautology check is never
            # asserted via assert_registry_scenario_matches, its values are only
            # read for the cross-residence divergence comparison. Use the
            # CCAA-invariant base liquidable general (0500 = 23.900) as a harmless,
            # true placeholder.
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
        revision="2024",
        filing_year=2024,
        period="0A",
        inputs=oracle_declared_figures(_ORACLE_PAYLOAD_NAME),
        binding_values=_BASE_BINDINGS_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": ccaa},
        relation_values=_REL_2024,
        date_context={"filing_period": date(2024, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=expected_outputs,
        notes=("raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L48602-L48643",),
    )


def test_cuotas_integras_escala_aragon_manual_worked_example() -> None:
    """The cuota-integra chain reproduces the manual's Aragon caso practico exactly.

    Oracle: AEAT Manual practico de Renta 2024, Parte 1, Cap. 15, "Ejemplo
    practico: calculo de las cuotas integras estatal y autonomica" de don
    A.B.C. (Aragon). Base liquidable general 23.900 + base liquidable del
    ahorro 2.800 + minimo personal y familiar 5.550 yield cuota escala estatal
    2.667,75 (0528) / autonomica 2.621,89 (0529), cuota integra general estatal
    2.140,50 (0532) / autonomica 2.094,64 (0533), and cuota integra estatal
    2.406,50 (0545) / autonomica 2.360,64 (0546) - every figure quoted verbatim
    from the manual's own solucion.
    """
    scenario = _scenario(ccaa="aragon", scenario_id="m100-2024-cuotas-integras-escala-aragon", grounded=True)
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_cuotas_integras_anti_tautology_autonomic_tariff_changes_value() -> None:
    """Switching the residence Comunidad Autonoma must move the autonomic cuotas.

    Anti-tautology: the autonomic cuota casillas (0529/0533/0546) are computed
    from the residence-CCAA-selected autonomic tariff parameter. This check does
    not hand-compute the Madrid-branch figures (that would reuse the escala
    under test); it only asserts the Aragon and Madrid autonomic cuotas diverge,
    proving the autonomic escala parameter is actually consulted. The state
    cuotas (0528/0545), by contrast, MUST stay identical across the two
    residences (the state tariff is CCAA-invariant) - asserted here too, so a
    formula that ignored the CCAA binding entirely would also fail.
    """
    aragon = _scenario(ccaa="aragon", scenario_id="m100-2024-cuotas-aragon", grounded=True)
    madrid = _scenario(ccaa="madrid", scenario_id="m100-2024-cuotas-madrid", grounded=False)
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
    for state_casilla in ("0528", "0545"):
        assert _value(aragon_values, state_casilla) == _value(madrid_values, state_casilla), (
            f"state cuota {state_casilla} must be identical across residences (state tariff is CCAA-invariant)"
        )


def test_cuota_chain_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of the cuota chain is enrolled, not just computed.

    The symmetric registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``) proves the
    ``externally_grounded_casilla_ids`` declaration is backed by the bundled
    ``corpus/manual_oracles/modelo-100-2024-cuotas-integras-escala-aragon.json``
    evidence. This test proves the other end of the wire: that every grounded
    cuota casilla reaches the live, validated
    :class:`RegistryVerificationPolicy` fold consumed by the living reconcile flow, so
    it raises ``independently_grounded_fraction`` rather than sitting inert in
    TOML. Not tautological: the grounded set and the fraction are read from the
    registry's own declared+validated data, never hand-computed.
    """
    authority = registry_authority
    snapshot = authority.snapshot("100", filing_year=2024, period="0A")
    policy = snapshot.verification_policy()

    grounded_casilla_ids = {
        validated_casilla_id(casilla_id, surface=casilla_id) for casilla_id, *_ in _GROUNDED_OUTPUT_REFS
    }
    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids

    for casilla_id in grounded_casilla_ids:
        assert casilla_id in policy.externally_grounded_casilla_ids
        assert casilla_id in reconciled_casilla_ids

    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )
    assert grounded_casilla_ids <= externally_grounded
    assert independently_grounded_fraction > 0.0
