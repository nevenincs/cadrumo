"""Regression tests for text-casilla routing in filing draft construction."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import (
    CasillaId,
    Period,
    validated_casilla_id,
)
from ....domain.filing import ModeloValueKind
from .. import build_draft
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TIPO_RENTA_CASILLA: CasillaId = validated_casilla_id("tipo_renta", surface="_TIPO_RENTA_CASILLA")
_RENDIMIENTOS_INTEGROS_CASILLA: CasillaId = validated_casilla_id(
    "rendimientos_integros",
    surface="_RENDIMIENTOS_INTEGROS_CASILLA",
)
_VALOR_CATASTRAL_CASILLA: CasillaId = validated_casilla_id("valor_catastral", surface="_VALOR_CATASTRAL_CASILLA")
_COEFICIENTE_IMPUTACION_CASILLA: CasillaId = validated_casilla_id(
    "coeficiente_imputacion_inmobiliaria",
    surface="_COEFICIENTE_IMPUTACION_CASILLA",
)
_DIAS_IMPUTACION_CASILLA: CasillaId = validated_casilla_id("dias_imputacion", surface="_DIAS_IMPUTACION_CASILLA")
_GASTOS_DEDUCIBLES_CASILLA: CasillaId = validated_casilla_id(
    "gastos_deducibles",
    surface="_GASTOS_DEDUCIBLES_CASILLA",
)
_RETENCION_PRACTICADA_CASILLA: CasillaId = validated_casilla_id(
    "retencion_practicada",
    surface="_RETENCION_PRACTICADA_CASILLA",
)
_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id("base_imponible", surface="_BASE_IMPONIBLE_CASILLA")


def test_build_draft_routes_m210_tipo_renta_as_text_input() -> None:
    """M210 ``tipo_renta`` must not enter the Decimal casilla-input channel."""
    period = Period.from_year_and_code(2025, "EVENT-1")

    draft = build_draft(
        modelo="210",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="M210 text casilla routing"),
        inputs={
            _TIPO_RENTA_CASILLA: "inmobiliaria",
            _RENDIMIENTOS_INTEGROS_CASILLA: Decimal("0"),
            _VALOR_CATASTRAL_CASILLA: Decimal("100000.00"),
            _COEFICIENTE_IMPUTACION_CASILLA: Decimal("0.011"),
            _DIAS_IMPUTACION_CASILLA: Decimal("365"),
            _GASTOS_DEDUCIBLES_CASILLA: Decimal("0"),
            _RETENCION_PRACTICADA_CASILLA: Decimal("0"),
        },
        schema_provider=build_runtime_schema_provider(modelos=("210",), filing_year=2025, period=period),
    )

    values = {value.casilla_id: value for value in draft.values}
    tipo_renta = values[_TIPO_RENTA_CASILLA]

    assert tipo_renta.kind is ModeloValueKind.LITERAL
    assert tipo_renta.value == "inmobiliaria"
    assert values[_BASE_IMPONIBLE_CASILLA].value == Decimal("1100.00")
