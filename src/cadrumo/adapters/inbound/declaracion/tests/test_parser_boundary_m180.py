"""Modelo 180 parser boundary synthetic fixture tests."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import (
    _MODELO_180_SYNTHETIC_FIXTURE,
    CasillaId,
    Decimal,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id(
    "decl.total-perceptores", surface="declaracion_parser_boundary.casilla"
)
_DECL_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.base-total", surface="declaracion_parser_boundary.casilla"
)
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.retenciones-total", surface="declaracion_parser_boundary.casilla"
)
_M180_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    _DECL_TOTAL_PERCEPTORES_CASILLA: Decimal("3"),
    _DECL_BASE_TOTAL_CASILLA: Decimal("12000.00"),
    _DECL_RETENCIONES_TOTAL_CASILLA: Decimal("2280.00"),
}


def test_parser_extracts_modelo_180_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M180 synthetic fixture through the parser.

    Ground truth is the AEAT-published printed-form template and Orden
    HAP/1732/2014 record design for total perceptores, base total, and
    retenciones total labels.
    """
    filing = parse_declaracion(
        _MODELO_180_SYNTHETIC_FIXTURE,
        modelo_override="180",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "180"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "180"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"

    assert {value.casilla_id: value.printed_value for value in filing.values} == _M180_EXPECTED_VALUES
