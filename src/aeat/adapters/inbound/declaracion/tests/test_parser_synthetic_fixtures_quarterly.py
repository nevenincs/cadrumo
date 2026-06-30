"""Quarterly synthetic declaration parser fixture tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _MODELO_115_SYNTHETIC_FIXTURE,
    _MODELO_131_SYNTHETIC_FIXTURE,
    _expected_period,
    parse_declaracion,
)
from ._parser_synthetic_quarterly_support import _M115_EXPECTED_VALUES, _M131_EXPECTED_VALUES

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_extracts_modelo_115_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M115 synthetic fixture through the production parser."""
    filing = parse_declaracion(
        _MODELO_115_SYNTHETIC_FIXTURE,
        modelo_override="115",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "115"
    assert filing.period == _expected_period(2024, "1T")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "115"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == _M115_EXPECTED_VALUES


def test_parser_extracts_modelo_131_casillas_from_synthetic_fixture() -> None:
    """Round-trip the M131 2026 synthetic fixture through the bbox_anchored profile."""
    filing = parse_declaracion(
        _MODELO_131_SYNTHETIC_FIXTURE,
        modelo_override="131",
        año_override=2026,
        template_revision_override="2026",
        period_override="1T",
    )

    assert filing.modelo == "131"
    assert filing.period == _expected_period(2026, "1T")
    assert filing.tax_id == "Y0000001S", f"expected tax_id='Y0000001S', got {filing.tax_id!r}"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "131"
    assert filing.registry_snapshot_ref.modelo_year == 2026
    assert {value.casilla_id: value.printed_value for value in filing.values} == _M131_EXPECTED_VALUES
