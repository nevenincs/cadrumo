"""Compiler coverage for bracket-table temporal gap detection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema_formula import BracketEntry, ParameterDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.validate_parameter_temporal import bracket_coverage_gaps

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LATER = filing_year_envelope().horizon
_EARLIER = _LATER - 1


def test_coverage_validator_fires_on_deliberate_gap() -> None:
    """The compiler must detect a bracket table whose earlier window is absent."""
    later_bracket = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.17"),
        valid_from=date(_LATER, 1, 1),
        valid_to=date(_LATER, 12, 31),
    )
    gapped_parameter = ParameterDefinition.model_construct(
        id="test.gapped-bracket-table",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(later_bracket,),
        values=(),
    )
    gaps = bracket_coverage_gaps(
        gapped_parameter, revision_from=date(_EARLIER, 1, 1), revision_to=date(_EARLIER, 12, 31)
    )
    assert gaps, "bracket_coverage_gaps must detect the earlier year's gap when brackets start a year later"
    assert gaps[0][0] == date(_EARLIER, 1, 1), "gap must start at the revision's valid_from"


def test_coverage_validator_passes_when_no_gap() -> None:
    """The compiler must accept contiguous bracket windows."""
    earlier_bracket = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.23"),
        valid_from=date(_EARLIER, 1, 1),
        valid_to=date(_EARLIER, 12, 31),
    )
    later_bracket = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.17"),
        valid_from=date(_LATER, 1, 1),
        valid_to=date(_LATER, 12, 31),
    )
    covered_parameter = ParameterDefinition.model_construct(
        id="test.covered-bracket-table",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(earlier_bracket, later_bracket),
        values=(),
    )
    gaps = bracket_coverage_gaps(
        covered_parameter, revision_from=date(_EARLIER, 1, 1), revision_to=date(_LATER, 12, 31)
    )
    assert not gaps, "bracket_coverage_gaps must not flag a parameter whose windows cover the full revision range"
