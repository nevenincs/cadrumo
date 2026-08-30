"""Tests for the censo-driven activity-window gate on the deadline engine.

Closes #502 (2/2): TaxpayerProfile censo fields (activity_start_date /
activity_end_date) now have a real deadline-rule consumer in
:func:`cadrumo.domain.deadlines.engine._window_outside_activity_period`.
The engine skips obligation windows that fall entirely before alta
(``closes_on < activity_start_date``) or entirely after baja
(``opens_on > activity_end_date``); straddling windows stay on the
schedule.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..engine import _window_outside_activity_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_pre_start_window_is_filtered_out() -> None:
    """A window that closes before the operator's alta is dropped."""

    assert (
        _window_outside_activity_period(
            opens_on=date(2023, 1, 1),
            closes_on=date(2023, 4, 20),
            activity_start_date=date(2023, 6, 1),
            activity_end_date=None,
        )
        is True
    )


def test_post_baja_window_is_filtered_out() -> None:
    """A window that opens after the operator's baja is dropped."""

    assert (
        _window_outside_activity_period(
            opens_on=date(2025, 7, 1),
            closes_on=date(2025, 7, 20),
            activity_start_date=None,
            activity_end_date=date(2025, 5, 31),
        )
        is True
    )


def test_window_straddling_alta_is_retained() -> None:
    """A window whose close date is on or after the alta is kept —
    the operator may still owe a return covering the active fraction."""

    assert (
        _window_outside_activity_period(
            opens_on=date(2024, 4, 1),
            closes_on=date(2024, 4, 20),
            activity_start_date=date(2024, 4, 15),
            activity_end_date=None,
        )
        is False
    )


def test_window_straddling_baja_is_retained() -> None:
    """A window whose open date is on or before the baja is kept —
    activity occurred during the window even if it ended mid-period."""

    assert (
        _window_outside_activity_period(
            opens_on=date(2024, 4, 1),
            closes_on=date(2024, 4, 20),
            activity_start_date=None,
            activity_end_date=date(2024, 4, 10),
        )
        is False
    )


def test_no_censo_dates_means_no_filtering() -> None:
    """When the operator has not yet captured a censo, both dates
    are None and the gate never fires. The profile lacks the legal
    activity-period evidence needed to suppress any window."""

    assert (
        _window_outside_activity_period(
            opens_on=date(2024, 4, 1),
            closes_on=date(2024, 4, 20),
            activity_start_date=None,
            activity_end_date=None,
        )
        is False
    )


def test_window_inside_active_period_is_retained() -> None:
    """Standard case: window opens after alta and closes before baja."""

    assert (
        _window_outside_activity_period(
            opens_on=date(2024, 7, 1),
            closes_on=date(2024, 7, 20),
            activity_start_date=date(2020, 1, 1),
            activity_end_date=date(2025, 12, 31),
        )
        is False
    )


def test_window_closing_on_alta_date_is_retained() -> None:
    """Edge: closes_on == activity_start_date keeps the window
    (operator filed/declared activity on the close day, owes the
    return for that day's activity)."""

    assert (
        _window_outside_activity_period(
            opens_on=date(2024, 6, 1),
            closes_on=date(2024, 6, 15),
            activity_start_date=date(2024, 6, 15),
            activity_end_date=None,
        )
        is False
    )


def test_window_opening_on_baja_date_is_retained() -> None:
    """Edge: opens_on == activity_end_date keeps the window — the
    baja day is still within the active period."""

    assert (
        _window_outside_activity_period(
            opens_on=date(2024, 6, 15),
            closes_on=date(2024, 7, 5),
            activity_start_date=None,
            activity_end_date=date(2024, 6, 15),
        )
        is False
    )
