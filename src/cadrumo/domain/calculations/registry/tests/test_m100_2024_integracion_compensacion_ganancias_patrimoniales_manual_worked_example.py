"""Oracle test for M100 2024 capital-gains-and-losses integration and intra-year
compensation grounded against the AEAT manual's own worked example (integracion
y compensacion de ganancias y perdidas patrimoniales, base general y base del
ahorro).

Ground truth (bundled AEAT Manual practico de Renta 2024, Parte 1, Capitulo 12
"Integracion y compensacion de rentas", "Caso practico" de don A.P.G.):

    raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L43871-L43946

Raw 2024 ganancias/perdidas patrimoniales quoted verbatim (L43876-43881):
    - Ganancia patrimonial a integrar en la base imponible general: 4.500
    - Perdida patrimonial a integrar en la base imponible general: 9.600
    - Ganancia patrimonial a integrar en la base imponible del ahorro: 5.600
    - Perdida patrimonial a integrar en la base imponible del ahorro: 1.600

Solucion, each netting subtotal quoted verbatim:
    Base imponible general (L43907-43910):
        "Ganancias: 4.500 / Perdidas: 9.600 / Saldo neto negativo de ganancias
         y perdidas del ejercicio 2024 (4.500 -9.600) = -5.100"
    Base imponible del ahorro (L43925-43928):
        "Ganancias: 5.600 / Perdidas: 1.600 / Saldo neto positivo de ganancias
         y perdidas del ejercicio 2024: (5.600 - 1.600) = 4.000"

Scope: this test grounds the INTRA-YEAR integration and compensation of 2024
ganancias against 2024 perdidas patrimoniales - the saldo netting the manual
prints in steps 1b and 2a. It deliberately does NOT ground the manual's
downstream base imponible general (39.600) or base del ahorro (200), which fold
in prior-year (2020/2021) and capital-mobiliario compensations (the remanente
casillas) this scenario does not supply. The per-transmission gain COMPUTATION
(valor de transmision/adquisicion -> ganancia reducida) is grounded separately
in test_m100_2024_ganancias_patrimoniales_transmision_inmueble_manual_worked_example.py;
this test grounds the aggregation and netting layer above it.

Registry mapping (M100 2024 revision, gains/losses saldo casillas):
    0418 "Ganancias patrimoniales base general (suma)" = 4.500,00.
    0419 "Perdidas patrimoniales base general (suma)" = 9.600,00.
    0421 "Saldo neto negativo de ganancias y perdidas base general"
      = max(0419 - 0418, 0) = 5.100,00.
    0422 "Ganancias patrimoniales base del ahorro (suma)" = 5.600,00.
    0423 "Perdidas patrimoniales base del ahorro (suma)" = 1.600,00.
    0424 "Saldo neto positivo de ganancias y perdidas base del ahorro"
      = max(0422 - 0423, 0) = 4.000,00.

Anti-tautology: this test does not hand-compute any figure from the saldo
formulas under test. It supplies only the four raw ganancia/perdida amounts the
manual quotes (each at a raw-input gain/loss leaf: base general ganancia 0266 /
perdida 0305, base ahorro ganancia 0316 / perdida 0322) and asserts the six
aggregate/saldo casillas equal the manual's own printed subtotals. A companion
test raises the base-general perdida above the ganancia-plus-existing gap and
asserts the base-general saldo flips from the negative slot (0421) to the
positive slot (0420), proving the max/subtract netting is actually evaluated
rather than a constant returned.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from ..authority import ValidatedRegistryAuthority
from ._modelo_100_registry_support import _m100_2024_deduccion_maternidad_bindings
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    RegistryScenarioRunReport,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)
from .manual_oracle_support import oracle_declared_figures

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()

# Raw-input gain/loss leaves the four manual amounts are injected at; each flows
# identity into its aggregate suma casilla (0418/0419/0422/0423).
_GANANCIA_BASE_GENERAL_LEAF: CasillaId = validated_casilla_id("0266", surface="0266")
_PERDIDA_BASE_GENERAL_LEAF: CasillaId = validated_casilla_id("0305", surface="0305")
_GANANCIA_BASE_AHORRO_LEAF: CasillaId = validated_casilla_id("0316", surface="0316")
_PERDIDA_BASE_AHORRO_LEAF: CasillaId = validated_casilla_id("0322", surface="0322")

_SOURCE_REFS = ("lirpf-cuota-chain-authority",)
_GP_REFS = ("ley-35-2006:art-33", "ley-35-2006:art-34", "ley-35-2006:art-37", "ley-35-2006:art-50")
_GP_AHORRO_REFS = ("ley-35-2006:art-33", "ley-35-2006:art-34", "ley-35-2006:art-37", "ley-35-2006:art-49")

_GROUNDED_OUTPUTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("0418", "4500.00", _GP_REFS),
    ("0419", "9600.00", _GP_REFS),
    ("0421", "5100.00", ("ley-35-2006:art-50",)),
    ("0422", "5600.00", _GP_AHORRO_REFS),
    ("0423", "1600.00", _GP_AHORRO_REFS),
    ("0424", "4000.00", ("ley-35-2006:art-49", "ley-35-2006:art-50")),
)

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


_ORACLE_PAYLOAD_NAME = "modelo-100-2024-integracion-compensacion-ganancias-patrimoniales.json"


def _scenario(
    *,
    ganancia_general: str | None = None,
    perdida_general: str | None = None,
    scenario_id: str,
    grounded: bool,
) -> RegistryCalculationScenario:
    expected_outputs = (
        tuple(
            RegistryScenarioExpectedOutput(
                target_casilla_id=validated_casilla_id(casilla_id, surface=casilla_id),
                value=Decimal(value),
                legal_refs=legal_refs,
                source_refs=_SOURCE_REFS,
            )
            for casilla_id, value, legal_refs in _GROUNDED_OUTPUTS
        )
        if grounded
        else (
            # Harmless CCAA/scenario-invariant placeholder so the harness's
            # non-empty expected_outputs requirement is met for the anti-tautology
            # scenario, whose report is only read (never assert-matched).
            RegistryScenarioExpectedOutput(
                target_casilla_id=validated_casilla_id("0422", surface="0422"),
                value=Decimal("5600.00"),
                legal_refs=_GP_AHORRO_REFS,
                source_refs=_SOURCE_REFS,
            ),
        )
    )
    # The manual's own four figures by default; a caller overrides the two general
    # legs only to build a scenario the example does NOT state, so a departure from
    # the printed case is visible at the call site rather than buried in a literal.
    inputs = oracle_declared_figures(_ORACLE_PAYLOAD_NAME)
    if ganancia_general is not None:
        inputs[_GANANCIA_BASE_GENERAL_LEAF] = Decimal(ganancia_general)
    if perdida_general is not None:
        inputs[_PERDIDA_BASE_GENERAL_LEAF] = Decimal(perdida_general)
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2024",
        filing_year=2024,
        period="0A",
        inputs=inputs,
        binding_values=_BASE_BINDINGS_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2024,
        date_context={"filing_period": date(2024, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=expected_outputs,
        notes=("raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L43871-L43946",),
    )


def test_integracion_compensacion_ganancias_patrimoniales_manual_worked_example() -> None:
    """The gains/losses aggregation and intra-year netting reproduces the manual exactly.

    Oracle: AEAT Manual practico de Renta 2024, Parte 1, Cap. 12, "Caso
    practico" de don A.P.G. Base-general ganancias 4.500 (0418) / perdidas 9.600
    (0419) net to saldo negativo 5.100 (0421); base-ahorro ganancias 5.600
    (0422) / perdidas 1.600 (0423) net to saldo positivo 4.000 (0424) - every
    figure quoted verbatim from the manual's own solucion.
    """
    scenario = _scenario(
        scenario_id="m100-2024-integracion-compensacion-ganancias-patrimoniales",
        grounded=True,
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    assert_registry_scenario_matches(report)


def test_integracion_compensacion_anti_tautology_saldo_slot_flips() -> None:
    """A base-general ganancia exceeding the perdida must move the saldo to the positive slot.

    Anti-tautology: the base-general saldo is split across two casillas -
    0420 (saldo positivo = max(ganancias - perdidas, 0)) and 0421 (saldo
    negativo = max(perdidas - ganancias, 0)). The grounded caso has a net loss
    (0421 = 5.100, 0420 = 0). This check swaps the ganancia and perdida so the
    net is positive and asserts the two slots swap (0420 becomes positive, 0421
    becomes zero), proving the max/subtract netting is actually evaluated. It
    does not hand-compute the swapped figures; only the slot flip is asserted.
    """
    net_loss = _scenario(
        scenario_id="m100-2024-gp-net-loss",
        grounded=True,
    )
    net_gain = _scenario(
        ganancia_general="9600.00",
        perdida_general="4500.00",
        scenario_id="m100-2024-gp-net-gain",
        grounded=False,
    )
    net_loss_report = run_registry_calculation_scenario(
        net_loss, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT
    )
    assert_registry_scenario_matches(net_loss_report)
    net_gain_report = run_registry_calculation_scenario(
        net_gain, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT
    )

    def _value(report: RegistryScenarioRunReport, casilla_id: str) -> Decimal | None:
        return report.calculation.values.get(validated_casilla_id(casilla_id, surface=casilla_id))

    saldo_negativo_casilla = validated_casilla_id("0421", surface="0421")
    saldo_positivo_casilla = validated_casilla_id("0420", surface="0420")

    net_loss_negative = net_loss_report.calculation.values[saldo_negativo_casilla]
    assert net_loss_negative is not None
    assert net_loss_negative > Decimal("0")
    assert net_loss_report.calculation.values[saldo_positivo_casilla] == Decimal("0")
    net_gain_positive = _value(net_gain_report, "0420")
    assert net_gain_positive is not None
    assert net_gain_positive > Decimal("0")
    assert _value(net_gain_report, "0421") == Decimal("0")


def test_gains_losses_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of the gains/losses saldo chain is enrolled, not just computed.

    The symmetric registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``) proves the
    ``externally_grounded_casilla_ids`` declaration is backed by the bundled
    ``corpus/manual_oracles/modelo-100-2024-integracion-compensacion-ganancias-patrimoniales.json``
    evidence. This test proves the other end of the wire: that every grounded
    saldo casilla reaches the live, validated
    :class:`RegistryVerificationPolicy` fold, so it raises
    ``independently_grounded_fraction`` rather than sitting inert in TOML.
    """
    authority = registry_authority
    snapshot = authority.snapshot("100", filing_year=2024, period="0A")
    policy = snapshot.verification_policy()

    grounded_casilla_ids = {
        validated_casilla_id(casilla_id, surface=casilla_id) for casilla_id, *_ in _GROUNDED_OUTPUTS
    }
    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids

    for casilla_id in grounded_casilla_ids:
        assert casilla_id in policy.externally_grounded_casilla_ids
        assert casilla_id in reconciled_casilla_ids

    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    assert grounded_casilla_ids <= externally_grounded
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )
    assert independently_grounded_fraction > 0.0
