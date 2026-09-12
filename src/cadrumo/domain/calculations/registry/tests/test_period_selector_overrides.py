"""Per-year period overrides on a period selector.

A legal boundary that falls inside a filing year rather than between two of
them -- a design applying from one monthly period but only from a later
quarterly one -- cannot be stated by a single flat period tuple. The override
states the transition year's surface on its own, and every year the selector
covers but does not override keeps the flat tuple verbatim.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.period_selector_overlap import period_selectors_overlap
from cadrumo.domain.calculations.registry.schema_references import PeriodOverride, PeriodSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MONTHS = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
_QUARTERS = ("1T", "2T", "3T", "4T")


def _mixed_cadence_selector() -> PeriodSelector:
    """The shape a design applying from 02 monthly and 2T quarterly declares."""
    return PeriodSelector(
        year_from=2026,
        periods=(*_MONTHS, *_QUARTERS),
        period_overrides=(PeriodOverride(year=2026, periods=(*_MONTHS[1:], "2T", "3T", "4T")),),
    )


class TestPerYearSelection:
    def test_the_overridden_year_serves_its_own_surface(self) -> None:
        selector = _mixed_cadence_selector()
        assert selector.periods_for_year(2026) == (
            "02",
            "03",
            "04",
            "05",
            "06",
            "07",
            "08",
            "09",
            "10",
            "11",
            "12",
            "2T",
            "3T",
            "4T",
        )
        assert "01" not in selector.periods_for_year(2026)
        assert "1T" not in selector.periods_for_year(2026)

    def test_every_other_covered_year_serves_the_flat_tuple(self) -> None:
        selector = _mixed_cadence_selector()
        assert selector.periods_for_year(2027) == (*_MONTHS, *_QUARTERS)
        assert selector.periods_for_year(2030) == (*_MONTHS, *_QUARTERS)

    def test_the_predecessor_keeps_the_boundary_periods(self) -> None:
        """The year the transition drops is exactly what the predecessor still serves."""
        predecessor = PeriodSelector(year_from=2023, year_to=2026, periods=("01", "1T"))
        successor = _mixed_cadence_selector()
        assert set(predecessor.periods_for_year(2026)).isdisjoint(successor.periods_for_year(2026))

    def test_a_monthly_only_override_inside_an_open_range(self) -> None:
        """The override year lies inside a ``year_from`` range, not an explicit years tuple."""
        selector = PeriodSelector(
            year_from=2026,
            periods=_MONTHS,
            period_overrides=(PeriodOverride(year=2026, periods=_MONTHS[1:]),),
        )
        assert selector.periods_for_year(2026) == _MONTHS[1:]
        assert selector.periods_for_year(2027) == _MONTHS
        assert selector.includes_year(2026)

    def test_a_selector_without_overrides_is_unchanged(self) -> None:
        selector = PeriodSelector(years=(2025,), periods=_QUARTERS)
        assert selector.period_overrides == ()
        assert selector.periods_for_year(2025) == _QUARTERS
        assert selector.periods_for_year(2099) == _QUARTERS

    def test_declared_periods_unions_every_covered_year(self) -> None:
        selector = PeriodSelector(
            years=(2026, 2027),
            periods=("1T", "2T"),
            period_overrides=(PeriodOverride(year=2026, periods=("2T", "EVENT-N")),),
        )
        assert selector.declared_periods == ("1T", "2T", "EVENT-N")


class TestRefusals:
    def test_an_override_year_outside_an_explicit_years_tuple_refuses(self) -> None:
        with pytest.raises(ValidationError, match="lies outside the selector's covered years"):
            PeriodSelector(
                years=(2026, 2027),
                periods=_QUARTERS,
                period_overrides=(PeriodOverride(year=2025, periods=("2T",)),),
            )

    def test_an_override_year_outside_a_range_refuses(self) -> None:
        with pytest.raises(ValidationError, match="lies outside the selector's covered years"):
            PeriodSelector(
                year_from=2026,
                year_to=2028,
                periods=_QUARTERS,
                period_overrides=(PeriodOverride(year=2029, periods=("2T",)),),
            )

    def test_a_repeated_override_year_refuses(self) -> None:
        with pytest.raises(ValidationError, match="must declare each year once"):
            PeriodSelector(
                year_from=2026,
                periods=_QUARTERS,
                period_overrides=(
                    PeriodOverride(year=2026, periods=("2T",)),
                    PeriodOverride(year=2026, periods=("3T",)),
                ),
            )

    def test_a_repeated_override_period_refuses(self) -> None:
        with pytest.raises(ValidationError, match="period_override periods must be unique"):
            PeriodOverride(year=2026, periods=("2T", "2T"))

    def test_an_empty_override_refuses(self) -> None:
        with pytest.raises(ValidationError, match="periods"):
            PeriodOverride(year=2026, periods=())


class TestRoundTrip:
    def test_the_field_round_trips_through_the_typed_model(self) -> None:
        selector = _mixed_cadence_selector()
        restored = PeriodSelector.model_validate(selector.model_dump())
        assert restored == selector
        assert restored.periods_for_year(2026) == selector.periods_for_year(2026)

    def test_the_field_round_trips_through_json(self) -> None:
        selector = _mixed_cadence_selector()
        restored = PeriodSelector.model_validate_json(selector.model_dump_json())
        assert restored.period_overrides == selector.period_overrides

    def test_the_declared_shape_validates_from_a_manifest_mapping(self) -> None:
        """The exact shape a revision manifest authors, read as TOML would deliver it."""
        selector = PeriodSelector.model_validate(
            {
                "year_from": 2026,
                "periods": (*_MONTHS, *_QUARTERS),
                "period_overrides": ({"year": 2026, "periods": ("02", "2T")},),
            }
        )
        assert selector.periods_for_year(2026) == ("02", "2T")


class TestOverlap:
    """Two selectors collide only where they share a year AND a period in it."""

    def test_the_transition_year_does_not_collide_with_its_predecessor(self) -> None:
        predecessor = PeriodSelector(year_from=2023, year_to=2026, periods=("01", "1T"))
        assert not period_selectors_overlap(predecessor, _mixed_cadence_selector())

    def test_two_overrides_sharing_a_period_in_the_same_year_collide(self) -> None:
        left = PeriodSelector(year_from=2023, year_to=2026, periods=("01", "1T", "2T"))
        right = _mixed_cadence_selector()
        assert period_selectors_overlap(left, right)

    def test_a_shared_unoverridden_year_still_collides(self) -> None:
        left = PeriodSelector(year_from=2026, year_to=2028, periods=("1T",))
        right = _mixed_cadence_selector()
        assert period_selectors_overlap(left, right)
