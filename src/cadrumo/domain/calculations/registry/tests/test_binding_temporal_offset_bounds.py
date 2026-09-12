"""``FilingYearOffset`` must refuse a bound that admits no step at all.

``max_years`` bounds how far a repeated offset may reach. A bound smaller than
one step of ``years`` filters out every anchor the member could produce, so the
declaration resolves to nothing while still reading like a live cross-period
coordinate -- an absence with no diagnostic attached to it, which is the exact
shape a filing-bound declaration must not be able to take.

The bound is absolute and the offset is signed, so the comparison is against
``abs(years)``: a backward reach of two years is refused by a one-year bound in
the same way a forward one is.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..binding_temporal import FilingYearOffset

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIODS = ("0A",)


@pytest.mark.parametrize(
    ("years", "max_years"),
    [(-2, 1), (2, 1), (-1, 0), (1, 0), (-3, 2)],
)
def test_bound_below_one_step_is_refused(years: int, max_years: int) -> None:
    """A bound the offset cannot take one step within stops the declaration."""
    with pytest.raises(ValidationError, match="max_years must admit at least one step"):
        FilingYearOffset(years=years, source_periods=_PERIODS, max_years=max_years)


@pytest.mark.parametrize(
    ("years", "max_years"),
    [(-1, 1), (1, 1), (-2, 2), (-2, 5), (3, 3), (-1, None)],
)
def test_bound_admitting_at_least_one_step_is_accepted(years: int, max_years: int | None) -> None:
    """A bound equal to or wider than one step leaves the declaration valid."""
    offset = FilingYearOffset(years=years, source_periods=_PERIODS, max_years=max_years)

    assert offset.years == years
    assert offset.max_years == max_years


def test_negative_bound_keeps_its_own_refusal() -> None:
    """The pre-existing non-negative rule is not subsumed by the new one."""
    with pytest.raises(ValidationError, match="max_years must be non-negative"):
        FilingYearOffset(years=-1, source_periods=_PERIODS, max_years=-1)
