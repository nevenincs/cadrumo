"""Structural wiring test for the M100 CCAA-deduction / final-settlement
chain, anchored on the Renta 2024 manual's Aragon worked example: cuota
integra -> cuota liquida (estatal + autonomica) -> cuota liquida total ->
cuota resultante de la autoliquidacion -> cuota diferencial -> resultado de
la declaracion. The chain's identities in every supported year are covered by
the development registry's support-year tests; this module keeps the figures
the manual prints for its own ejercicio.

Grounding posture (see aeat-quality-gates and
no-silent-under-declaration): the bundled AEAT Manual practico
de Renta 2024 corpus is Parte 1 only. Its Capitulo 18 states the DEFINITIONAL
identities of the final-settlement chain verbatim - "la cuota resultante de la
autoliquidacion es el resultado de aplicar sobre la cuota liquida total ..."
(source.pdf.extracted.md#L58455), cuota liquida = cuota integra menos
deducciones, cuota diferencial = cuota resultante menos pagos a cuenta,
resultado = cuota diferencial menos los impuestos negativos - but Parte 1 does
NOT carry a single forward-computable caso practico that prints a full cuota
liquida -> cuota diferencial -> resultado liquidation from raw inputs (that
comprehensive caso and the per-Comunidad autonomic-deduction casos live in the
unbundled Parte 2). Per-casilla NUMERIC oracle grounding of those figures
therefore awaits the Parte 2 corpus and is NOT claimed here (these casillas are
deliberately not enrolled in externally_grounded_casilla_ids).

What this test DOES ground is the CHAIN STRUCTURE against Capitulo 18's stated
identities, anchored on the cuota integra figures that ARE manual-grounded in
the sibling test_m100_2024_cuotas_integras_escala_aragon_manual_worked_example
(cuota integra estatal 2.406,50 casilla 0545 / autonomica 2.360,64 casilla
0546). It runs the same Aragon single-filer scenario through the settlement
chain and asserts the manual's definitional identities hold end to end:

    - cuota liquida estatal 0570 == cuota integra estatal 0545 and cuota liquida
      autonomica 0571 == cuota integra autonomica 0546 when no deductions apply
      (cuota liquida = cuota integra - deducciones, deducciones = 0);
    - cuota liquida incrementada total 0587 == 0570 + 0571;
    - cuota resultante de la autoliquidacion 0595 == 0587 when no further
      deductions apply;
    - cuota diferencial 0610 == cuota resultante 0595 - total pagos a cuenta
      0609;
    - resultado de la declaracion 0670 == cuota diferencial 0610 when no
      impuestos negativos (maternidad / familia numerosa) apply.

An anti-tautology companion feeds a retencion (pago a cuenta) and asserts the
cuota diferencial and resultado drop by exactly that amount, proving the
pagos-a-cuenta subtraction is actually evaluated rather than a passthrough
constant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    manual_editions_printing,
    revision_covering,
    supported_authored_exercises,
)
from cadrumo.domain.calculations.registry.tests.modelo_100_registry_support import (
    M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
    M100_NO_LET_PROPERTY_BINDINGS,
)
from cadrumo.domain.calculations.registry.tests.scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The line the Aragon worked example prints its cuota integra estatal on.
_ANCHOR_LINE = "Cuota íntegra estatal (2.140,50 + 266) = 2.406,50"
#: Every authored ejercicio whose bundled Renta manual prints the worked example the anchor figures reproduce.
_MANUAL_EJERCICIOS = tuple(
    ejercicio
    for ejercicio in manual_editions_printing("renta", "2.406,50", "2.360,64")
    if ejercicio in supported_authored_exercises("100")
)


def _evidence_locator(ejercicio: int) -> str:
    relative = f"corpus/manuals/renta/{ejercicio}/part1/source.pdf.extracted.md"
    lines = (bundled_path() / relative).read_text(encoding="utf-8").splitlines()
    (line,) = (number for number, text in enumerate(lines, start=1) if text.strip() == _ANCHOR_LINE)
    return f"{relative}#L{line}"


_CUOTA_INTEGRA_ESTATAL: CasillaId = validated_casilla_id("0545", surface="0545")
_CUOTA_INTEGRA_AUTONOMICA: CasillaId = validated_casilla_id("0546", surface="0546")
_CUOTA_LIQUIDA_ESTATAL: CasillaId = validated_casilla_id("0570", surface="0570")
_CUOTA_LIQUIDA_AUTONOMICA: CasillaId = validated_casilla_id("0571", surface="0571")
_CUOTA_LIQUIDA_TOTAL: CasillaId = validated_casilla_id("0587", surface="0587")
_CUOTA_RESULTANTE: CasillaId = validated_casilla_id("0595", surface="0595")
_TOTAL_PAGOS_A_CUENTA: CasillaId = validated_casilla_id("0609", surface="0609")
_CUOTA_DIFERENCIAL: CasillaId = validated_casilla_id("0610", surface="0610")
_RESULTADO_DECLARACION: CasillaId = validated_casilla_id("0670", surface="0670")

_BASE_LIQUIDABLE_GENERAL_LEAF: CasillaId = validated_casilla_id("0156", surface="0156")
# The savings base is computed from its income (0429 = max(0041, 0)), so the
# scenario keys the same amount as income from other financial assets, an input leaf.
_OTROS_ACTIVOS_FINANCIEROS_LEAF: CasillaId = validated_casilla_id("0031", surface="0031")
_RETENCION_TRABAJO: CasillaId = validated_casilla_id("0596", surface="0596")


def _bindings(revision_id: str) -> dict[str, Decimal]:
    """Return the neutral scenario bindings the edition declares; an edition without one has nothing to neutralise."""
    with bundled_indexed_authority().operation() as operation:
        declared = {str(binding.id) for binding in operation.revision("100", revision_id).bindings}
    neutral = {
        # Art. 81.1 is profile-derived at the application boundary. This
        # direct registry scenario has no profile facts, so it supplies the
        # resolved no-descendant scalar just as the profile resolver would.
        **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
        "renta-profile-incremento-guarderia": Decimal("0"),
        # The 2025 Madrid birth or adoption deducción (casilla 1039) reads these two; a filer with no descendants
        # has no eligible descendant and no other member of the unit.
        "renta-profile-madrid-nacimiento-adopcion-eligible-count": Decimal("0"),
        "renta-profile-unidad-familiar-otros-miembros-base": Decimal("0"),
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-gyp-ahorro-em2-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-gyp-ahorro-em1-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-rcm-ahorro-em3-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-rcm-ahorro-em2-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-rcm-ahorro-em1-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
        "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-family-minor-children-in-unit": Decimal("0"),
        "renta-profile-has-economic-activity": Decimal("1"),
        "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
        "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
        **M100_NO_LET_PROPERTY_BINDINGS,
        "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
        "renta-profile-estimacion-directa": Decimal("1"),
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("0"),
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
        # No ascendant rows: the mínimo por ascendientes aggregates and the Madrid count are zero.
        "renta-profile-minimo-ascendientes-estatal": Decimal("0"),
        "renta-profile-minimo-ascendientes-autonomico": Decimal("0"),
        "renta-profile-deduccion-madrid-cuidado-ascendientes-count": Decimal("0"),
    }
    return {binding_id: value for binding_id, value in neutral.items() if binding_id in declared}


_RELATION_VALUES: dict[str, Decimal] = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}


def _scenario(ejercicio: int, *, retencion: str, scenario_id: str) -> RegistryCalculationScenario:
    revision_id = str(revision_covering("100", ejercicio).id)
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision=revision_id,
        filing_year=ejercicio,
        period="0A",
        inputs={
            _BASE_LIQUIDABLE_GENERAL_LEAF: Decimal("23900.00"),
            _OTROS_ACTIVOS_FINANCIEROS_LEAF: Decimal("2800.00"),
            _RETENCION_TRABAJO: Decimal(retencion),
        },
        hand_typed_bound_casillas={
            _BASE_LIQUIDABLE_GENERAL_LEAF: (
                "the general base leaf is the let properties' reduced net yield, which the edition totals from "
                "the property rows; the scenario carries no property, so it keys that total directly"
            ),
            _RETENCION_TRABAJO: (
                "the salary certificate is an operator-keyed source: its binding names this casilla "
                "as the value it fills, so the scenario keys the certified amount directly"
            ),
        },
        binding_values=_bindings(revision_id),
        enum_binding_values={"renta-profile-tax-residence-ccaa": "aragon"},
        relation_values=_RELATION_VALUES,
        date_context={"filing_period": date(ejercicio, 12, 31)},
        date_binding_values={"renta-profile-taxpayer-birth-date": date(1980, 6, 15)},
        # The harness requires at least one expected output; anchor it on the
        # manual-grounded cuota integra estatal (2.406,50, grounded in the
        # sibling escala test) so this scenario's own upstream anchor is
        # asserted before the structural identities below are read.
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CUOTA_INTEGRA_ESTATAL,
                value=Decimal("2406.50"),
                legal_refs=("ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-66"),
                source_refs=("lirpf-cuota-chain-authority",),
            ),
        ),
        notes=(f"raw_evidence_locator: {_evidence_locator(ejercicio)}",),
    )


def _values(scenario: RegistryCalculationScenario) -> dict[CasillaId, Decimal | None]:
    report = run_registry_calculation_scenario(scenario)
    return dict(report.calculation.values)


def _required_value(values: dict[CasillaId, Decimal | None], casilla_id: CasillaId) -> Decimal:
    value = values[casilla_id]
    assert value is not None, f"scenario left required casilla {casilla_id} unresolved"
    return value


@pytest.mark.parametrize("ejercicio", _MANUAL_EJERCICIOS)
def test_final_settlement_chain_composes_manual_definitional_identities(ejercicio: int) -> None:
    """The final-settlement chain composes the Chapter-18 identities end to end.

    Anchored on the manual-grounded cuota integra estatal 2.406,50 (0545) /
    autonomica 2.360,64 (0546), the settlement chain reproduces AEAT Manual
    Cap. 18's definitional identities with no deductions or pagos a cuenta:
    cuota liquida = cuota integra, cuota liquida total = estatal + autonomica,
    cuota resultante = cuota liquida total, cuota diferencial = cuota resultante
    - pagos a cuenta, resultado = cuota diferencial.
    """
    values = _values(_scenario(ejercicio, retencion="0", scenario_id="m100-final-settlement-no-pagos"))

    cuota_integra_estatal = _required_value(values, _CUOTA_INTEGRA_ESTATAL)
    cuota_integra_autonomica = _required_value(values, _CUOTA_INTEGRA_AUTONOMICA)
    assert cuota_integra_estatal == Decimal("2406.50")
    assert cuota_integra_autonomica == Decimal("2360.64")

    # cuota liquida = cuota integra - deducciones (deducciones = 0 here)
    assert values[_CUOTA_LIQUIDA_ESTATAL] == cuota_integra_estatal
    assert values[_CUOTA_LIQUIDA_AUTONOMICA] == cuota_integra_autonomica

    # cuota liquida total = estatal + autonomica
    assert values[_CUOTA_LIQUIDA_TOTAL] == _required_value(values, _CUOTA_LIQUIDA_ESTATAL) + _required_value(
        values,
        _CUOTA_LIQUIDA_AUTONOMICA,
    )

    # cuota resultante de la autoliquidacion = cuota liquida total (no further deductions)
    assert values[_CUOTA_RESULTANTE] == values[_CUOTA_LIQUIDA_TOTAL]

    # cuota diferencial = cuota resultante - total pagos a cuenta (pagos = 0)
    assert values[_TOTAL_PAGOS_A_CUENTA] == Decimal("0.00")
    assert values[_CUOTA_DIFERENCIAL] == _required_value(values, _CUOTA_RESULTANTE) - _required_value(
        values,
        _TOTAL_PAGOS_A_CUENTA,
    )

    # resultado de la declaracion = cuota diferencial (no impuestos negativos)
    assert values[_RESULTADO_DECLARACION] == values[_CUOTA_DIFERENCIAL]


@pytest.mark.parametrize("ejercicio", _MANUAL_EJERCICIOS)
def test_final_settlement_pagos_a_cuenta_subtraction_is_wired(ejercicio: int) -> None:
    """A retencion (pago a cuenta) must reduce cuota diferencial and resultado by its amount.

    Anti-tautology / wiring proof: feeding a 1.000 euro certified salary
    retencion must raise total pagos a cuenta 0609 to 1.000 and lower cuota
    diferencial 0610 and resultado 0670 by exactly that amount relative to the
    no-pagos scenario, proving the pagos-a-cuenta subtraction is evaluated and
    not a passthrough constant.
    """
    baseline = _values(_scenario(ejercicio, retencion="0", scenario_id="m100-settlement-baseline"))
    with_retencion = _values(_scenario(ejercicio, retencion="1000", scenario_id="m100-settlement-retencion"))

    assert baseline[_TOTAL_PAGOS_A_CUENTA] == Decimal("0.00")
    assert with_retencion[_TOTAL_PAGOS_A_CUENTA] == Decimal("1000.00")

    cuota_resultante = baseline[_CUOTA_RESULTANTE]
    assert cuota_resultante is not None
    assert with_retencion[_CUOTA_RESULTANTE] == cuota_resultante  # resultante is upstream of pagos a cuenta

    assert with_retencion[_CUOTA_DIFERENCIAL] == _required_value(
        baseline,
        _CUOTA_DIFERENCIAL,
    ) - Decimal("1000.00")
    assert with_retencion[_RESULTADO_DECLARACION] == _required_value(
        baseline,
        _RESULTADO_DECLARACION,
    ) - Decimal("1000.00")
