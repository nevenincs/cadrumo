"""The inclusive date-range invariant refuses an empty window.

A ``since``/``until`` pair is a closed interval. A reversed pair selects
nothing, so every consumer built on it reports zero observations — which is
byte-identical to a genuinely quiet window. The bounds are parsed
independently at each call site, so the invariant is a property of the pair
and has exactly one home here.

Each refusal is paired with the valid value it accepts, so a validator that
started refusing everything is distinguishable from one refusing the right
thing.
"""

from __future__ import annotations

from datetime import date

import pytest

from ...errors.hierarchy import CoreValidationError
from ..date_range import validate_inclusive_date_range, validate_inclusive_iso_date_range

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EARLY = date(2026, 1, 1)
_LATE = date(2026, 2, 1)


class TestDateBounds:
    def test_reversed_pair_is_refused(self) -> None:
        with pytest.raises(CoreValidationError):
            validate_inclusive_date_range(_LATE, _EARLY)

    def test_ordered_pair_is_accepted(self) -> None:
        validate_inclusive_date_range(_EARLY, _LATE)

    def test_equal_bounds_are_a_valid_single_day_window(self) -> None:
        """A one-day query is legitimate; the bound is strict inequality."""
        validate_inclusive_date_range(_EARLY, _EARLY)

    @pytest.mark.parametrize(
        ("since", "until"),
        [(None, None), (_EARLY, None), (None, _LATE), (_LATE, None), (None, _EARLY)],
    )
    def test_open_bounds_are_accepted(self, since: date | None, until: date | None) -> None:
        """An absent bound is "unbounded on that side", never an ordering violation."""
        validate_inclusive_date_range(since, until)


class TestIsoBounds:
    def test_reversed_iso_pair_is_refused(self) -> None:
        with pytest.raises(CoreValidationError):
            validate_inclusive_iso_date_range("2026-02-01", "2026-01-01")

    def test_ordered_iso_pair_is_accepted(self) -> None:
        validate_inclusive_iso_date_range("2026-01-01", "2026-02-01")

    def test_equal_iso_bounds_are_accepted(self) -> None:
        validate_inclusive_iso_date_range("2026-01-01", "2026-01-01")

    @pytest.mark.parametrize("bad", ["not-a-date", "2026-13-01", "01/01/2026", "2026-01"])
    def test_non_iso_text_is_refused(self, bad: str) -> None:
        """The bounds are compared as dates, so unparseable text cannot pass silently."""
        with pytest.raises(CoreValidationError):
            validate_inclusive_iso_date_range(bad, "2026-02-01")
        with pytest.raises(CoreValidationError):
            validate_inclusive_iso_date_range("2026-01-01", bad)

    @pytest.mark.parametrize(
        ("since", "until"),
        [(None, None), ("2026-01-01", None), (None, "2026-02-01")],
    )
    def test_open_iso_bounds_are_accepted(self, since: str | None, until: str | None) -> None:
        validate_inclusive_iso_date_range(since, until)

    def test_ordering_is_by_date_not_by_string(self) -> None:
        """Hyphenated ISO text happens to sort correctly; the check must not rely on it.

        ``date.fromisoformat`` also accepts the compact ``YYYYMMDD`` form, whose
        text ordering disagrees with its date ordering: ``"2026-02-01"`` sorts
        *before* ``"20260101"`` as text because ``"-"`` precedes ``"0"``. A
        string comparison would therefore refuse this genuinely-ordered window.
        """
        validate_inclusive_iso_date_range("20260101", "2026-02-01")
        assert "2026-02-01" < "20260101", "the discriminating premise of this test"
        with pytest.raises(CoreValidationError):
            validate_inclusive_iso_date_range("20260301", "2026-02-01")
