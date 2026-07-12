"""Modelo 036 parser boundary synthetic fixture tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_casillas import _M036_EVENT_KIND_CASILLA
from ._parser_boundary_support import (
    _MODELO_036_SYNTHETIC_FIXTURE,
    CasillaId,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M036_EXPECTED_VALUES: dict[CasillaId, str] = {
    _M036_EVENT_KIND_CASILLA: "Alta",
}


def test_parser_extracts_modelo_036_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M036 synthetic fixture through the parser.

    Ground truth is the AEAT-published practical guide for Modelo 036, PAGINA 1,
    section heading "Causas de presentacion de la declaracion". The fixture uses
    that source heading with the enum value on the same line.
    """
    filing = parse_declaracion(
        _MODELO_036_SYNTHETIC_FIXTURE,
        modelo_override="036",
        año_override=2025,
        period_override="alta",
    )

    assert filing.modelo == "036"
    assert filing.period == _expected_period(2025, "AD-HOC")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "036"
    assert filing.registry_snapshot_ref.modelo_year == 2025
    assert filing.registry_snapshot_ref.period == "ALTA"

    assert {value.casilla_id: value.printed_value for value in filing.values} == _M036_EXPECTED_VALUES
