"""Structural wiring test for the M100 2024 CCAA-deduction / final-settlement
chain: cuota integra -> cuota liquida (estatal + autonomica) -> cuota liquida
total -> cuota resultante de la autoliquidacion -> cuota diferencial ->
resultado de la declaracion.

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

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from ._modelo_100_registry_support import _m100_2024_deduccion_maternidad_bindings
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()

_CUOTA_INTEGRA_ESTATAL: CasillaId = validated_casilla_id("0545", surface="0545")
_CUOTA_INTEGRA_AUTONOMICA: CasillaId = validated_casilla_id("0546", surface="0546")
_CUOTA_LIQUIDA_ESTATAL: CasillaId = validated_casilla_id("0570", surface="0570")
_CUOTA_LIQUIDA_AUTONOMICA: CasillaId = validated_casilla_id("0571", surface="0571")
_CUOTA_LIQUIDA_TOTAL: CasillaId = validated_casilla_id("0587", surface="0587")
_CUOTA_RESULTANTE: CasillaId = validated_casilla_id("0595", surface="0595")
_TOTAL_PAGOS_A_CUENTA: CasillaId = validated_casilla_id("0609", surface="0609")
_CUOTA_DIFERENCIAL: CasillaId = validated_casilla_id("0610", surface="0610")
_RESULTADO_DECLARACION: CasillaId = validated_casilla_id("0670", surface="0670")

_BASE_LIQUIDABLE_GENERAL_LEAF: CasillaId = validated_casilla_id("0102", surface="0102")
_BASE_LIQUIDABLE_AHORRO_LEAF: CasillaId = validated_casilla_id("0429", surface="0429")


def _bindings(*, retencion: str) -> dict[str, Decimal]:
    return {
        "renta-2024-modelo-111-retenciones-periodicas": Decimal(retencion),
        "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
        # Art. 81.1 is profile-derived at the application boundary. This
        # direct registry scenario has no profile facts, so it supplies the
        # resolved no-descendant scalar just as the profile resolver would.
        **_m100_2024_deduccion_maternidad_bindings(),
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


def _scenario(*, retencion: str, scenario_id: str) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2024",
        filing_year=2024,
        period="0A",
        inputs={
            _BASE_LIQUIDABLE_GENERAL_LEAF: Decimal("23900.00"),
            _BASE_LIQUIDABLE_AHORRO_LEAF: Decimal("2800.00"),
        },
        binding_values=_bindings(retencion=retencion),
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "aragon"},
        relation_values=_REL_2024,
        date_context={"filing_period": date(2024, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 6, 15)},
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
        notes=("raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L58455-L58460",),
    )


def _values(scenario: RegistryCalculationScenario) -> dict[CasillaId, Decimal | None]:
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    return dict(report.calculation.values)


def _required_value(values: dict[CasillaId, Decimal | None], casilla_id: CasillaId) -> Decimal:
    value = values[casilla_id]
    assert value is not None, f"scenario left required casilla {casilla_id} unresolved"
    return value


def test_final_settlement_chain_composes_manual_definitional_identities() -> None:
    """The final-settlement chain composes the Chapter-18 identities end to end.

    Anchored on the manual-grounded cuota integra estatal 2.406,50 (0545) /
    autonomica 2.360,64 (0546), the settlement chain reproduces AEAT Manual
    Cap. 18's definitional identities with no deductions or pagos a cuenta:
    cuota liquida = cuota integra, cuota liquida total = estatal + autonomica,
    cuota resultante = cuota liquida total, cuota diferencial = cuota resultante
    - pagos a cuenta, resultado = cuota diferencial.
    """
    values = _values(_scenario(retencion="0", scenario_id="m100-2024-final-settlement-no-pagos"))

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


def test_final_settlement_pagos_a_cuenta_subtraction_is_wired() -> None:
    """A retencion (pago a cuenta) must reduce cuota diferencial and resultado by its amount.

    Anti-tautology / wiring proof: feeding a 1.000 euro retencion periodica
    (Modelo 111) must raise total pagos a cuenta 0609 to 1.000 and lower cuota
    diferencial 0610 and resultado 0670 by exactly that amount relative to the
    no-pagos scenario, proving the pagos-a-cuenta subtraction is evaluated and
    not a passthrough constant.
    """
    baseline = _values(_scenario(retencion="0", scenario_id="m100-2024-settlement-baseline"))
    with_retencion = _values(_scenario(retencion="1000", scenario_id="m100-2024-settlement-retencion"))

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
