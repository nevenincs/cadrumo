"""Compiler coverage for bracket-table temporal gap detection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema_formula import BracketEntry, ParameterDefinition

from ..compiler.validate_parameter_temporal import bracket_coverage_gaps

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_coverage_validator_fires_on_deliberate_gap() -> None:
    """The compiler must detect a bracket table whose 2024 window is absent."""
    bracket_2025 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.17"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    gapped_parameter = ParameterDefinition.model_construct(
        id="test.gapped-bracket-table",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(bracket_2025,),
        values=(),
    )
    gaps = bracket_coverage_gaps(gapped_parameter, revision_from=date(2024, 1, 1), revision_to=date(2024, 12, 31))
    assert gaps, "bracket_coverage_gaps must detect the 2024 gap when brackets start at 2025"
    assert gaps[0][0] == date(2024, 1, 1), "gap must start at the revision's valid_from (2024-01-01)"


def test_coverage_validator_passes_when_no_gap() -> None:
    """The compiler must accept contiguous bracket windows."""
    bracket_2024 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.23"),
        valid_from=date(2024, 1, 1),
        valid_to=date(2024, 12, 31),
    )
    bracket_2025 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.17"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    covered_parameter = ParameterDefinition.model_construct(
        id="test.covered-bracket-table",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(bracket_2024, bracket_2025),
        values=(),
    )
    gaps = bracket_coverage_gaps(covered_parameter, revision_from=date(2024, 1, 1), revision_to=date(2025, 12, 31))
    assert not gaps, "bracket_coverage_gaps must not flag a parameter whose windows cover the full revision range"
