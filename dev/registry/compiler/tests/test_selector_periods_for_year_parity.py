"""The loader's raw-table period reader agrees with the typed selector method.

Inheritance runs before typed construction, so the loader reimplements
``PeriodSelector.periods_for_year`` against the raw TOML table. Two copies of
one rule drift silently, and the drift would be invisible: an inherited
period-scoped member is individually valid whichever surface admitted it. This
compares the two on the same declaration, with and without an override.
"""

from __future__ import annotations

from typing import Final

import pytest

from cadrumo.domain.calculations.registry.schema_references import PeriodOverride, PeriodSelector
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..keyed_family_period_scope import selector_periods_for_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MONTHS: Final = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
_QUARTERS: Final = ("1T", "2T", "3T", "4T")
_FIRST_YEAR: Final = filing_year_envelope().floor
_YEARS: Final = tuple(_FIRST_YEAR + offset for offset in range(4))
_OVERRIDE_YEAR: Final = _YEARS[2]


def _raw(selector: PeriodSelector) -> dict[str, object]:
    """The raw TOML table an author writes for ``selector``."""
    table: dict[str, object] = {"periods": list(selector.periods)}
    if selector.years:
        table["years"] = list(selector.years)
    if selector.year_from is not None:
        table["year_from"] = selector.year_from
    if selector.year_to is not None:
        table["year_to"] = selector.year_to
    if selector.period_overrides:
        table["period_overrides"] = [
            {"year": override.year, "periods": list(override.periods)} for override in selector.period_overrides
        ]
    return table


def _read(selector: PeriodSelector, year: int) -> tuple[str, ...]:
    """The loader's answer for ``year``, normalised to the typed method's shape."""
    periods = selector_periods_for_year(_raw(selector), year)
    assert isinstance(periods, list)
    return tuple(str(token) for token in periods)


@pytest.mark.parametrize("year", _YEARS)
def test_the_two_readers_agree_without_an_override(year: int) -> None:
    selector = PeriodSelector(year_from=_FIRST_YEAR, periods=_QUARTERS)

    assert _read(selector, year) == selector.periods_for_year(year)


@pytest.mark.parametrize("year", _YEARS)
def test_the_two_readers_agree_with_an_override(year: int) -> None:
    selector = PeriodSelector(
        year_from=_FIRST_YEAR,
        periods=(*_MONTHS, *_QUARTERS),
        period_overrides=(PeriodOverride(year=_OVERRIDE_YEAR, periods=(*_MONTHS[1:], "2T", "3T", "4T")),),
    )

    assert _read(selector, year) == selector.periods_for_year(year)


def test_the_override_year_is_the_one_that_differs() -> None:
    """Without this the parity above would hold on two identical flat reads."""
    selector = PeriodSelector(
        year_from=_FIRST_YEAR,
        periods=(*_MONTHS, *_QUARTERS),
        period_overrides=(PeriodOverride(year=_OVERRIDE_YEAR, periods=(*_MONTHS[1:], "2T", "3T", "4T")),),
    )

    assert _read(selector, _OVERRIDE_YEAR) != _read(selector, _YEARS[1])
    assert "1T" not in _read(selector, _OVERRIDE_YEAR)
    assert "1T" in _read(selector, _YEARS[1])


@pytest.mark.parametrize("year", _YEARS)
def test_a_second_override_year_is_matched_by_year_not_by_position(year: int) -> None:
    selector = PeriodSelector(
        years=_YEARS,
        periods=_QUARTERS,
        period_overrides=(
            PeriodOverride(year=_YEARS[1], periods=("2T", "3T", "4T")),
            PeriodOverride(year=_YEARS[3], periods=("1T",)),
        ),
    )

    assert _read(selector, year) == selector.periods_for_year(year)
