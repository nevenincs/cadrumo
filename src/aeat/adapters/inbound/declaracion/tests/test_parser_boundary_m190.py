"""Modelo 190 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _REAL_MODELO_190_DECLARATION_COPY,
    CasillaId,
    Decimal,
    _expected_casilla_values,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M190_EXPECTED_VALUES: dict[CasillaId, Decimal] = _expected_casilla_values(
    {
        "decl.total-percepciones": Decimal("1"),
        "decl.percepciones-total": Decimal("1000.00"),
        "decl.retenciones-total": Decimal("1000.00"),
    },
)


def test_parser_extracts_modelo_190_targets_from_real_redacted_declaration_copy() -> None:
    filing = parse_declaracion(
        _REAL_MODELO_190_DECLARATION_COPY,
        modelo_override="190",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "190"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert {value.casilla_id: value.printed_value for value in filing.values} == _M190_EXPECTED_VALUES
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "190"
    assert filing.registry_snapshot_ref.revision_id == "2024-y-siguientes"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"
