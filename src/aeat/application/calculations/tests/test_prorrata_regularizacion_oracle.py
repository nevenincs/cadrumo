"""AEAT Manual practico IVA oracle proof for prorrata-general regularizacion.

Ground truth: bundled AEAT Manual practico IVA 2025, Capitulo 5, prorrata
general worked example, `corpus/manuals/iva/2025/source.pdf#Pag.137-138`,
declared in `corpus/manual_oracles/modelo-303-prorrata-general-regularizacion.json`.

The test seeds the manual's raw inputs, not values produced by the formula under
test: prior-year operations 32.000/12.000 produce the manual's provisional 73%;
current-year operations 25.000/20.000 produce the manual's definitive 56%; first
three quarters carry 1.280 EUR supported IVA and the fourth quarter carries
160 EUR. The expected values asserted below are the manual's own stated figures:
934,40; 716,80; 217,60; 89,60; -128,00; and the bundled casilla figures.

See Also:
    :func:`~application.calculations._prorrata_regularizacion.project_prorrata_regularizacion_feed`
        Projection whose casilla-44 output is pinned to the manual oracle.
    :func:`~domain.iva.compute_prorrata_general`
        Domain percentage compute used to reproduce the manual's prior-year
        provisional percentage from raw operation volumes.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Registry execution path used to derive the current-year definitive
        percentage from Modelo 303 annual volume casillas.
    :class:`~domain.iva.RegularizacionProrrataDireccion`
        Direction type asserted so the oracle distinguishes ingreso from
        deduccion complementaria.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core.resources import bundled_path, resources
from ....domain.calculations.registry import (
    CasillaId,
    calculate_registry_snapshot,
    resolve_bound_inputs_by_casilla_id,
    validated_casilla_id,
)
from ....domain.iva import (
    InputClassification,
    ProrrataInputs,
    ProrrataKind,
    RegularizacionProrrataDireccion,
    classify_input_deduction,
    compute_prorrata_general,
)
from .._prorrata_regularizacion import project_prorrata_regularizacion_feed

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORACLE_PATH = Path(
    bundled_path("corpus", "manual_oracles", "modelo-303-prorrata-general-regularizacion.json"),
)
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_CASILLA_44_ID: CasillaId = validated_casilla_id("44", surface="test casilla id")

_PRIOR_YEAR_CON_DERECHO = Decimal("32000.00")
_PRIOR_YEAR_SIN_DERECHO = Decimal("12000.00")
_FIRST_THREE_QUARTERS_INPUT_IVA = Decimal("1280.00")
_FOURTH_QUARTER_INPUT_IVA = Decimal("160.00")

_MANUAL_PROVISIONAL_PERCENTAGE = Decimal("73")
_MANUAL_FIRST_THREE_QUARTERS_DEDUCTION = Decimal("934.40")
_MANUAL_FIRST_THREE_QUARTERS_CORRECT_DEDUCTION = Decimal("716.80")
_MANUAL_EXCESS_DEDUCTION = Decimal("217.60")
_MANUAL_FOURTH_QUARTER_CURRENT_DEDUCTION = Decimal("89.60")
_MANUAL_FOURTH_QUARTER_NET_DEDUCTION = Decimal("-128.00")
_MANUAL_ANNUAL_DEDUCTION = Decimal("806.40")


def _oracle_payload() -> dict[str, Any]:
    return json.loads(_ORACLE_PATH.read_text(encoding="utf-8"))


def _oracle_expected(payload: dict[str, Any], casilla_id: CasillaId) -> Decimal:
    raw = payload["expected_by_casilla_id"][str(casilla_id)]
    return Decimal(raw)


def _m303_zero_bindings() -> dict[str, Decimal]:
    return {
        "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        # Criterio-de-caja informational bindings (LIVA arts. 163 decies ff.)
        # for casillas 62/63/74/75; zero — no cash-accounting rows in the
        # AEAT manual oracle scenario.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }


def _m303_prorrata_percentage_from_manual_annual_volumes(payload: dict[str, Any]) -> Decimal:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=payload["filing_year"], period="4T")
    binding_values = _m303_zero_bindings()
    manual_volume_inputs = {
        _VOLUMEN_TOTAL_ID: _oracle_expected(payload, _VOLUMEN_TOTAL_ID),
        _VOLUMEN_CON_DERECHO_ID: _oracle_expected(payload, _VOLUMEN_CON_DERECHO_ID),
    }
    inputs = {
        **resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        **manual_volume_inputs,
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(payload["filing_year"], 12, 31)},
    )
    return result.values[_PORCENTAJE_ID]


def test_m303_prorrata_regularizacion_reproduces_aeat_manual_oracle() -> None:
    """The real registry/domain chain reproduces the bundled AEAT manual figures.

    See Also:
        :func:`~application.calculations._prorrata_regularizacion.project_prorrata_regularizacion_feed`
            Application projection under test for the signed Modelo 303 casilla
            44 regularizacion value.
        :class:`~domain.iva.RegularizacionProrrataResult`
            Result carrier whose provisional, definitive, importe, and direction
            fields are compared against the manual figures.
    """
    payload = _oracle_payload()

    definitive_percentage = _m303_prorrata_percentage_from_manual_annual_volumes(payload)
    assert definitive_percentage == _oracle_expected(payload, _PORCENTAJE_ID)

    provisional = compute_prorrata_general(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=_PRIOR_YEAR_CON_DERECHO,
            operaciones_sin_derecho_deduccion=_PRIOR_YEAR_SIN_DERECHO,
        ),
        year=payload["filing_year"] - 1,
        kind=ProrrataKind.PROVISIONAL,
        period="Q4",
    )
    assert provisional.percentage == _MANUAL_PROVISIONAL_PERCENTAGE

    projection = project_prorrata_regularizacion_feed(
        cuotas_soportadas_deducibles=_FIRST_THREE_QUARTERS_INPUT_IVA,
        prorrata_provisional_pct=provisional.percentage,
        prorrata_definitiva_pct=definitive_percentage,
        operaciones_sin_derecho_deduccion=(
            _oracle_expected(payload, _VOLUMEN_TOTAL_ID) - _oracle_expected(payload, _VOLUMEN_CON_DERECHO_ID)
        ),
    )
    result = projection.result
    assert result.direccion is RegularizacionProrrataDireccion.INGRESO
    assert result.deduccion_provisional == _MANUAL_FIRST_THREE_QUARTERS_DEDUCTION
    assert result.deduccion_definitiva == _MANUAL_FIRST_THREE_QUARTERS_CORRECT_DEDUCTION
    assert -result.importe == _MANUAL_EXCESS_DEDUCTION
    assert projection.modelo_303_casilla_44_id == _CASILLA_44_ID
    assert projection.modelo_303_casilla_44_value == _oracle_expected(payload, _CASILLA_44_ID)

    fourth_quarter = classify_input_deduction(
        InputClassification.COMMON,
        _FOURTH_QUARTER_INPUT_IVA,
        definitive_percentage,
    )
    assert fourth_quarter.deductible_amount == _MANUAL_FOURTH_QUARTER_CURRENT_DEDUCTION
    assert projection.modelo_303_casilla_44_value + fourth_quarter.deductible_amount == (
        _MANUAL_FOURTH_QUARTER_NET_DEDUCTION
    )
    assert result.deduccion_definitiva + fourth_quarter.deductible_amount == _MANUAL_ANNUAL_DEDUCTION
