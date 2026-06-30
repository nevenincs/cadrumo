"""Modelo 840 parser boundary synthetic fixture tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_part2_support import (
    _M840_EJERCICIO_CASILLA,
    _M840_TIPO_DECLARACION_CASILLA,
)
from ._parser_boundary_support import (
    _MODELO_840_SYNTHETIC_FIXTURE,
    CasillaId,
    Decimal,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M840_EXPECTED_VALUES: dict[CasillaId, Decimal | str] = {
    _M840_EJERCICIO_CASILLA: Decimal("2024"),
    _M840_TIPO_DECLARACION_CASILLA: "Alta",
}


def test_parser_extracts_modelo_840_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M840 synthetic fixture through the parser.

    Ground truth is the AEAT-published printed form PDF at:
      src/aeat/_data/corpus/aeat_official/forms/modelo_840/files/
        01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf

    The fixture reproduces the corpus-confirmed labels "14Ejercicio:" and
    "15Declaracion de:" with sanitized values on the same line.
    """
    filing = parse_declaracion(
        _MODELO_840_SYNTHETIC_FIXTURE,
        modelo_override="840",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "840"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "840"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"

    assert {value.casilla_id: value.printed_value for value in filing.values} == _M840_EXPECTED_VALUES
