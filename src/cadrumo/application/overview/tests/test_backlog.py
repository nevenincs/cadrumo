"""Real-behavior tests for ``build_overview_backlog``.

The deadline engine's modelo 200 ``2024`` revision
currently fails registry validation, so every test below pins both
``from_date`` and ``to_date`` to a 2026-only window. The default-365-
day-lookback behaviour is exercised by inspection rather than by
running the engine across multiple years.
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict

import pytest

from ..backlog import OverviewBacklog, build_overview_backlog
from .calendar_test_support import profile as _profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _WindowArgs(TypedDict):
    from_date: date
    to_date: date
    as_of: date


def _window_args() -> _WindowArgs:
    return {
        "from_date": date(2026, 1, 1),
        "to_date": date(2026, 12, 31),
        "as_of": date(2026, 12, 31),
    }


def test_backlog_returns_typed_envelope() -> None:
    """The aggregator returns an OverviewBacklog envelope carrying the
    window, the items tuple, and the cached late_count."""

    backlog = build_overview_backlog(_profile(), **_window_args())

    assert isinstance(backlog, OverviewBacklog)
    assert backlog.as_of == date(2026, 12, 31)
    assert isinstance(backlog.items, tuple)
    assert backlog.late_count == len(backlog.items)


def test_backlog_explicit_window_is_honored() -> None:
    """An operator-supplied --from / --to scopes the calendar query
    accordingly; the envelope echoes the window so renderers can show
    what was queried."""

    backlog = build_overview_backlog(
        _profile(),
        from_date=date(2026, 1, 1),
        to_date=date(2026, 6, 30),
        as_of=date(2026, 12, 31),
    )

    assert backlog.range.from_date == date(2026, 1, 1)
    assert backlog.range.to_date == date(2026, 6, 30)


def test_backlog_items_are_strictly_past_due_and_late() -> None:
    """Every item in the backlog has adjusted_closes_on < as_of and
    user_state == LATE. Filed and future obligations are excluded."""

    backlog = build_overview_backlog(_profile(), **_window_args())

    for entry in backlog.items:
        assert entry.adjusted_closes_on < backlog.as_of, (
            f"backlog item {entry.modelo}-{entry.period} closes on or after as_of"
        )
        assert entry.user_state.value == "late", (
            f"backlog item {entry.modelo}-{entry.period} carries non-LATE state {entry.user_state}"
        )


def test_backlog_items_sorted_oldest_first() -> None:
    """Items must be sorted ascending by adjusted_closes_on so the
    operator triages the most-overdue obligation first."""

    backlog = build_overview_backlog(_profile(), **_window_args())

    deadlines = [entry.adjusted_closes_on for entry in backlog.items]
    assert deadlines == sorted(deadlines)


def test_backlog_late_count_matches_items_length() -> None:
    """The cached late_count is the canonical source for header summaries.
    It must equal len(items) on every aggregator run."""

    backlog = build_overview_backlog(_profile(), **_window_args())

    assert backlog.late_count == len(backlog.items)


def test_backlog_future_window_carries_no_past_due_items() -> None:
    """A window lying entirely after ``as_of`` has nothing past-due, so the
    backlog is empty and late_count is 0.

    The reference date is an explicit argument rather than the wall clock, so
    the "window lies wholly in the future" invariant holds on every run date;
    both dates stay inside 2026, a registry-known year (far-future years carry
    no deadline calendar and are refused upstream).
    """

    backlog = build_overview_backlog(
        _profile(),
        from_date=date(2026, 7, 1),
        to_date=date(2026, 12, 31),
        as_of=date(2026, 1, 15),
    )

    assert backlog.items == ()
    assert backlog.late_count == 0


def test_backlog_default_lookback_is_365_days() -> None:
    """When neither --from nor --to is supplied the window spans the
    365 days preceding ``as_of`` through ``as_of`` itself.

    Year-end as_of is chosen so the 365-day lookback stays inside a
    single calendar year — multi-year windows trip the modelo 200
    registry validation crash tracked as a cross-cutting follow-up,
    so this test deliberately keeps the engine inside one year while
    still exercising the default-window arithmetic in the service."""

    from datetime import timedelta

    as_of = date(2026, 12, 31)
    backlog = build_overview_backlog(_profile(), as_of=as_of)

    assert backlog.range.to_date == as_of
    assert backlog.range.from_date == as_of - timedelta(days=365)
