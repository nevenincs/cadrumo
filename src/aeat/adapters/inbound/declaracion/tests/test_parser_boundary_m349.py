"""Modelo 349 parser boundary synthetic fixture tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_part2_support import (
    _M349_IMPORTE_OPERACIONES_CASILLA,
    _M349_IMPORTE_RECTIFICACIONES_CASILLA,
    _M349_NUMERO_OPERADORES_CASILLA,
    _M349_NUMERO_RECTIFICACIONES_CASILLA,
)
from ._parser_boundary_support import (
    _MODELO_349_SYNTHETIC_FIXTURE,
    CasillaId,
    Decimal,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M349_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    _M349_NUMERO_OPERADORES_CASILLA: Decimal("5"),
    _M349_IMPORTE_OPERACIONES_CASILLA: Decimal("1234.56"),
    _M349_NUMERO_RECTIFICACIONES_CASILLA: Decimal("0"),
    _M349_IMPORTE_RECTIFICACIONES_CASILLA: Decimal("0.00"),
}


def test_parser_extracts_modelo_349_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M349 synthetic fixture through the parser.

    Ground truth is the AEAT-published instructions PDF at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_349/files/instr_mod_349.pdf
    pages 8-9, CUMPLIMENTACION DE LA HOJA-RESUMEN. The fixture prints those
    source labels so the named_label parser captures the trailing value token
    on each line.
    """
    filing = parse_declaracion(
        _MODELO_349_SYNTHETIC_FIXTURE,
        modelo_override="349",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "349"
    assert filing.period == _expected_period(2024, "1T")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "349"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"

    assert {value.casilla_id: value.printed_value for value in filing.values} == _M349_EXPECTED_VALUES
