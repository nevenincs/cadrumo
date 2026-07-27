"""Modelo 190 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _MODELO_190_SYNTHETIC_FIXTURE,
    CasillaId,
    Decimal,
    _expected_casilla_values,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

# The three amounts the fixture prints. They are DISTINCT from one another
# because the specimen this replaced printed the sanitiser's single redaction
# constant into both money boxes, so a target that crossed
# ``percepciones-total`` with ``retenciones-total`` read the same number and
# this assertion held anyway.
_M190_EXPECTED_VALUES: dict[CasillaId, Decimal] = _expected_casilla_values(
    {
        "decl.total-percepciones": Decimal("1"),
        "decl.percepciones-total": Decimal("12345.60"),
        "decl.retenciones-total": Decimal("1851.84"),
    },
)


def test_parser_extracts_modelo_190_targets_from_declaration_copy() -> None:
    filing = parse_declaracion(
        _MODELO_190_SYNTHETIC_FIXTURE,
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
