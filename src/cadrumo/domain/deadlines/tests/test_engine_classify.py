"""Focused unit tests for deadlines.engine.classify_obligation_status.

`classify_obligation_status` maps a window's ``closes_on`` date + the reference
``today`` + the configured ``due_soon_days`` into one of four
``ObligationStatus`` outcomes (OVERDUE, DUE_TODAY, DUE_SOON,
UPCOMING). Previously exercised indirectly through `test_engine.py`'s
integration tests that assert ``schedule.status`` for synthetic
obligations, but the boundary conditions around ``due_soon_days``
are not pinned at the inequality level — a regression flipping
``<= due_soon_days`` to ``< due_soon_days`` would silently move
every operator's "due-soon" notification by one day, exactly the
kind of off-by-one bug integration tests can miss.

Tests here pin the four ObligationStatus outcomes plus the three
documented boundary conditions of the due-soon window. Assertions
are predicate-contract assertions, not calculation tautologies.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..engine import classify_obligation_status
from ..models import ObligationStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# Branch outcomes — each ObligationStatus is reachable
# ---------------------------------------------------------------------------


def test_classify_returns_overdue_when_today_is_after_close() -> None:
    """A window whose close date is in the past is OVERDUE regardless
    of the due-soon configuration."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 1), today=date(2026, 1, 2), due_soon_days=14)
        is ObligationStatus.OVERDUE
    )


def test_classify_returns_due_today_when_today_equals_close() -> None:
    """today == closes_on yields DUE_TODAY (not DUE_SOON or OVERDUE)."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 31), today=date(2026, 1, 31), due_soon_days=14)
        is ObligationStatus.DUE_TODAY
    )


def test_classify_returns_due_soon_inside_window() -> None:
    """A window closing in 7 days with due_soon_days=14 is DUE_SOON."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 31), today=date(2026, 1, 24), due_soon_days=14)
        is ObligationStatus.DUE_SOON
    )


def test_classify_returns_upcoming_outside_window() -> None:
    """A window closing in 30 days with due_soon_days=14 is UPCOMING."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 31), today=date(2026, 1, 1), due_soon_days=14)
        is ObligationStatus.UPCOMING
    )


# ---------------------------------------------------------------------------
# Boundary conditions — pin the inequality semantics
# ---------------------------------------------------------------------------


def test_classify_due_soon_boundary_lower_bound_is_tomorrow() -> None:
    """delta == 1 (the smallest delta strictly greater than zero) is
    DUE_SOON. A regression that flipped the lower-bound predicate
    from ``1 <= delta`` to ``2 <= delta`` would silently move
    "tomorrow" from DUE_SOON to DUE_TODAY-or-similar."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 2), today=date(2026, 1, 1), due_soon_days=14)
        is ObligationStatus.DUE_SOON
    )


def test_classify_due_soon_boundary_upper_bound_is_inclusive() -> None:
    """delta == due_soon_days (the exact upper bound) is DUE_SOON.
    A regression that flipped ``<= due_soon_days`` to ``<
    due_soon_days`` would silently move "exactly 14 days from now"
    from DUE_SOON to UPCOMING."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 15), today=date(2026, 1, 1), due_soon_days=14)
        is ObligationStatus.DUE_SOON
    )


def test_classify_one_day_past_due_soon_upper_bound_is_upcoming() -> None:
    """delta == due_soon_days + 1 falls outside the due-soon window —
    UPCOMING. Pinning this boundary together with the inclusive-
    upper-bound test above locks the ``1 <= delta <= due_soon_days``
    predicate against off-by-one drift in either direction."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 16), today=date(2026, 1, 1), due_soon_days=14)
        is ObligationStatus.UPCOMING
    )


# ---------------------------------------------------------------------------
# Edge cases — non-default due_soon_days
# ---------------------------------------------------------------------------


def test_classify_due_soon_days_zero_disables_due_soon_window() -> None:
    """With due_soon_days=0 the ``1 <= delta <= 0`` predicate is
    always false, so any future delta classifies as UPCOMING and the
    DUE_SOON outcome becomes unreachable."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 2), today=date(2026, 1, 1), due_soon_days=0)
        is ObligationStatus.UPCOMING
    )


def test_classify_due_today_wins_before_delta_math_runs() -> None:
    """When today == closes_on the DUE_TODAY branch returns before
    the delta computation. This holds even when due_soon_days is
    zero or negative — the DUE_TODAY arm never falls through to the
    delta math."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 15), today=date(2026, 1, 15), due_soon_days=0)
        is ObligationStatus.DUE_TODAY
    )


def test_classify_overdue_wins_before_due_today_when_today_strictly_greater() -> None:
    """Strict ordering: ``today > closes_on`` runs first; the
    DUE_TODAY arm only fires on exact equality. A single day past
    close yields OVERDUE regardless of due_soon_days."""
    assert (
        classify_obligation_status(closes_on=date(2026, 1, 1), today=date(2026, 1, 2), due_soon_days=0)
        is ObligationStatus.OVERDUE
    )
