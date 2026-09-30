"""Bracket-table coverage is demanded from the support floor, and in full inside the envelope."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision, SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.schema_formula import BracketEntry, ParameterDefinition

from ..validate_parameter_temporal import validate_bracket_table_temporal_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORT = SupportedFilingYearsCatalogue(floor=2022, horizon=2026)


def _bracket(valid_from: date, valid_to: date | None) -> BracketEntry:
    return BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.2"),
        valid_from=valid_from,
        valid_to=valid_to,
    )


def _revision(valid_from: date, valid_to: date | None, *brackets: BracketEntry) -> ModeloRevision:
    parameter = ParameterDefinition.model_construct(
        id="test.reduccion-escala",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=brackets,
        values=(),
    )
    return ModeloRevision.model_construct(
        id="2019-2023",
        valid_from=valid_from,
        valid_to=valid_to,
        parameters=(parameter,),
    )


def test_an_edition_straddling_the_floor_owes_no_bracket_below_it() -> None:
    """The support declaration claims nothing before the floor, so no window is owed there."""
    revision = _revision(date(2019, 1, 1), date(2023, 12, 31), _bracket(date(2022, 1, 1), date(2023, 12, 31)))

    assert validate_bracket_table_temporal_coverage("m", revision, support=_SUPPORT) == []


def test_the_same_edition_without_a_support_declaration_owes_its_whole_range() -> None:
    """The clamp comes from the declaration: absent one, the gap before 2022 is still refused."""
    revision = _revision(date(2019, 1, 1), date(2023, 12, 31), _bracket(date(2022, 1, 1), date(2023, 12, 31)))

    failures = validate_bracket_table_temporal_coverage("m", revision, support=None)

    assert len(failures) == 1
    assert "[2019-01-01, 2021-12-31]" in failures[0]


def test_a_gap_inside_the_envelope_is_still_refused() -> None:
    """Clamping at the floor never weakens coverage above it."""
    revision = _revision(
        date(2019, 1, 1),
        date(2023, 12, 31),
        _bracket(date(2019, 1, 1), date(2021, 12, 31)),
        _bracket(date(2023, 1, 1), date(2023, 12, 31)),
    )

    failures = validate_bracket_table_temporal_coverage("m", revision, support=_SUPPORT)

    assert len(failures) == 1
    assert "[2022-01-01, 2022-12-31]" in failures[0]


def test_an_edition_wholly_below_the_floor_has_nothing_to_cover() -> None:
    revision = _revision(date(2015, 1, 1), date(2018, 12, 31), _bracket(date(2016, 1, 1), date(2018, 12, 31)))

    assert validate_bracket_table_temporal_coverage("m", revision, support=None)
    assert validate_bracket_table_temporal_coverage("m", revision, support=_SUPPORT) == []


def test_an_open_edition_starting_at_the_floor_is_judged_as_before() -> None:
    revision = _revision(date(2024, 1, 1), None, _bracket(date(2025, 1, 1), None))

    failures = validate_bracket_table_temporal_coverage("m", revision, support=_SUPPORT)

    assert len(failures) == 1
    assert "[2024-01-01, 2024-12-31]" in failures[0]
