"""Modelo 193 parser boundary synthetic fixture tests."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import (
    _MODELO_193_SYNTHETIC_FIXTURE,
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
_M193_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    _DECL_TOTAL_PERCEPTORES_CASILLA: Decimal("2"),
    _DECL_BASE_TOTAL_CASILLA: Decimal("8000.00"),
    _DECL_RETENCIONES_TOTAL_CASILLA: Decimal("1520.00"),
}


def test_parser_extracts_modelo_193_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M193 synthetic fixture through the parser.

    Ground truth is the AEAT-published Modelo 193 record design for tipo 1
    declarante totals: numero total de perceptores, base total, and
    retenciones total.
    """
    filing = parse_declaracion(
        _MODELO_193_SYNTHETIC_FIXTURE,
        modelo_override="193",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "193"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "193"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"

    assert {value.casilla_id: value.printed_value for value in filing.values} == _M193_EXPECTED_VALUES
