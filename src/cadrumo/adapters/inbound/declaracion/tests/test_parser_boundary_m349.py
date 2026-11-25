"""Modelo 349 parser boundary synthetic fixture tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId
from ..parser import parse_declaracion
from .parser_boundary_casillas import (
    M349_IMPORTE_OPERACIONES_CASILLA,
    M349_IMPORTE_RECTIFICACIONES_CASILLA,
    M349_NUMERO_OPERADORES_CASILLA,
    M349_NUMERO_RECTIFICACIONES_CASILLA,
)
from .parser_boundary_support import (
    MODELO_349_SYNTHETIC_FIXTURE,
    expected_period,
    specimen_period,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

_SPECIMEN_PERIOD = specimen_period(MODELO_349_SYNTHETIC_FIXTURE)

_M349_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    M349_NUMERO_OPERADORES_CASILLA: Decimal("5"),
    M349_IMPORTE_OPERACIONES_CASILLA: Decimal("1234.56"),
    M349_NUMERO_RECTIFICACIONES_CASILLA: Decimal("0"),
    M349_IMPORTE_RECTIFICACIONES_CASILLA: Decimal("0.00"),
}


def test_parser_extracts_modelo_349_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M349 synthetic fixture through the parser.

    Ground truth is the AEAT-published instructions PDF at:
      src/cadrumo/_data/corpus/aeat_official/instructions/modelo_349/files/instr_mod_349.pdf
    pages 8-9, CUMPLIMENTACION DE LA HOJA-RESUMEN. The fixture prints those
    source labels so the named_label parser captures the trailing value token
    on each line.
    """
    filing = parse_declaracion(
        MODELO_349_SYNTHETIC_FIXTURE,
        modelo_override="349",
        año_override=_SPECIMEN_PERIOD.filing_year,
        period_override="1T",
    )

    assert filing.modelo == "349"
    assert filing.period == expected_period(_SPECIMEN_PERIOD.filing_year, "1T")
    assert filing.tax_id == "Y0001006P"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "349"
    assert filing.registry_snapshot_ref.modelo_year == _SPECIMEN_PERIOD.filing_year
    assert filing.registry_snapshot_ref.period == "1T"

    assert {value.casilla_id: value.printed_value for value in filing.values} == _M349_EXPECTED_VALUES
