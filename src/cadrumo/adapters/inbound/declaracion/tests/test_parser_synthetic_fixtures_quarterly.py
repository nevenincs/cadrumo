"""Quarterly synthetic declaration parser fixture tests."""

from __future__ import annotations

import pytest

from .....domain.calculations.registry.tests.authored_editions import split_exercise_revisions
from ..parser import parse_declaracion
from .parser_boundary_support import (
    MODELO_115_SYNTHETIC_FIXTURE,
    MODELO_131_SYNTHETIC_FIXTURE,
    expected_period,
    specimen_period,
)
from .parser_synthetic_quarterly_support import M115_EXPECTED_VALUES, M131_EXPECTED_VALUES

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

_M115_PERIOD = specimen_period(MODELO_115_SYNTHETIC_FIXTURE)
# The fixture is forced onto the first design of the exercise the registry authors in two designs.
_M131_FIRST_DESIGN = split_exercise_revisions("131", early_period="2T", late_period="3T")[0]
_M131_EXERCISE = _M131_FIRST_DESIGN.valid_from.year


def test_parser_extracts_modelo_115_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M115 synthetic fixture through the production parser."""
    filing = parse_declaracion(
        MODELO_115_SYNTHETIC_FIXTURE,
        modelo_override="115",
        año_override=_M115_PERIOD.filing_year,
        period_override="1T",
    )

    assert filing.modelo == "115"
    assert filing.period == expected_period(_M115_PERIOD.filing_year, "1T")
    assert filing.tax_id == "Y0001006P"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "115"
    assert filing.registry_snapshot_ref.modelo_year == _M115_PERIOD.filing_year
    assert filing.registry_snapshot_ref.period == "1T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == M115_EXPECTED_VALUES


def test_parser_extracts_modelo_131_casillas_from_synthetic_fixture() -> None:
    """Round-trip the M131 2026 synthetic fixture through the bbox_anchored profile."""
    filing = parse_declaracion(
        MODELO_131_SYNTHETIC_FIXTURE,
        modelo_override="131",
        año_override=_M131_EXERCISE,
        template_revision_override=str(_M131_FIRST_DESIGN.id),
        period_override="1T",
    )

    assert filing.modelo == "131"
    assert filing.period == expected_period(_M131_EXERCISE, "1T")
    assert filing.tax_id == "Y0001006P", f"expected tax_id='Y0001006P', got {filing.tax_id!r}"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "131"
    assert filing.registry_snapshot_ref.modelo_year == _M131_EXERCISE
    assert {value.casilla_id: value.printed_value for value in filing.values} == M131_EXPECTED_VALUES
