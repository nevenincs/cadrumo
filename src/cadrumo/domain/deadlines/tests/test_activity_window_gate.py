"""Tests for the censo-driven activity-window gate on the deadline engine.

Closes #502 (2/2): TaxpayerProfile censo fields (activity_start_date /
activity_end_date) are evaluated against the tax period represented by each
obligation. Filing windows may open after cessation while still covering a
partially active final period, so they are not the lifecycle boundary.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.period import Period
from ..engine import _window_outside_activity_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_pre_start_window_is_filtered_out() -> None:
    """A window that closes before the operator's alta is dropped."""

    assert (
        _window_outside_activity_period(
            period=Period.from_year_and_code(2023, "1T"),
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
            period=Period.from_year_and_code(2025, "3T"),
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
            period=Period.from_year_and_code(2024, "2T"),
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
            period=Period.from_year_and_code(2024, "2T"),
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
            period=Period.from_year_and_code(2024, "2T"),
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
            period=Period.from_year_and_code(2024, "3T"),
            opens_on=date(2024, 7, 1),
            closes_on=date(2024, 7, 20),
            activity_start_date=date(2020, 1, 1),
            activity_end_date=date(2025, 12, 31),
        )
        is False
    )


def test_period_ending_on_alta_date_is_retained() -> None:
    """A period ending on the alta date still overlaps activity."""

    assert (
        _window_outside_activity_period(
            period=Period.from_year_and_code(2024, "03"),
            opens_on=date(2024, 4, 1),
            closes_on=date(2024, 4, 22),
            activity_start_date=date(2024, 3, 31),
            activity_end_date=None,
        )
        is False
    )


def test_period_opening_on_baja_date_is_retained() -> None:
    """A period opening on the baja date still overlaps activity."""

    assert (
        _window_outside_activity_period(
            period=Period.from_year_and_code(2024, "2T"),
            opens_on=date(2024, 7, 1),
            closes_on=date(2024, 7, 22),
            activity_start_date=None,
            activity_end_date=date(2024, 4, 1),
        )
        is False
    )


@pytest.mark.parametrize("period_code", ["4T", "0A"])
def test_residual_obligation_after_cessation_is_retained(period_code: str) -> None:
    """A later filing window does not erase an overlapping final tax period."""

    assert (
        _window_outside_activity_period(
            period=Period.from_year_and_code(2025, period_code),
            opens_on=date(2026, 1, 1),
            closes_on=date(2026, 1, 30),
            activity_start_date=date(2020, 1, 1),
            activity_end_date=date(2025, 12, 15),
        )
        is False
    )


def test_period_entirely_after_cessation_is_filtered() -> None:
    assert (
        _window_outside_activity_period(
            period=Period.from_year_and_code(2026, "1T"),
            opens_on=date(2026, 4, 1),
            closes_on=date(2026, 4, 20),
            activity_start_date=None,
            activity_end_date=date(2025, 12, 31),
        )
        is True
    )
