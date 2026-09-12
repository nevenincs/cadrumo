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

from .._loader_internals import _selector_periods_for_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MONTHS: Final = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
_QUARTERS: Final = ("1T", "2T", "3T", "4T")
_YEARS: Final = (2024, 2025, 2026, 2027)


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
    periods = _selector_periods_for_year(_raw(selector), year)
    assert isinstance(periods, list)
    return tuple(str(token) for token in periods)


@pytest.mark.parametrize("year", _YEARS)
def test_the_two_readers_agree_without_an_override(year: int) -> None:
    selector = PeriodSelector(year_from=2024, periods=_QUARTERS)

    assert _read(selector, year) == selector.periods_for_year(year)


@pytest.mark.parametrize("year", _YEARS)
def test_the_two_readers_agree_with_an_override(year: int) -> None:
    selector = PeriodSelector(
        year_from=2024,
        periods=(*_MONTHS, *_QUARTERS),
        period_overrides=(PeriodOverride(year=2026, periods=(*_MONTHS[1:], "2T", "3T", "4T")),),
    )

    assert _read(selector, year) == selector.periods_for_year(year)


def test_the_override_year_is_the_one_that_differs() -> None:
    """Without this the parity above would hold on two identical flat reads."""
    selector = PeriodSelector(
        year_from=2024,
        periods=(*_MONTHS, *_QUARTERS),
        period_overrides=(PeriodOverride(year=2026, periods=(*_MONTHS[1:], "2T", "3T", "4T")),),
    )

    assert _read(selector, 2026) != _read(selector, 2025)
    assert "1T" not in _read(selector, 2026)
    assert "1T" in _read(selector, 2025)


@pytest.mark.parametrize("year", _YEARS)
def test_a_second_override_year_is_matched_by_year_not_by_position(year: int) -> None:
    selector = PeriodSelector(
        years=_YEARS,
        periods=_QUARTERS,
        period_overrides=(
            PeriodOverride(year=2025, periods=("2T", "3T", "4T")),
            PeriodOverride(year=2027, periods=("1T",)),
        ),
    )

    assert _read(selector, year) == selector.periods_for_year(year)
