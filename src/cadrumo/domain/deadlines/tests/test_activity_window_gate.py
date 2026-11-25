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
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...contribuyente.entity_type import EntityType
from ..engine import window_outside_activity_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon - 2
"""A base year for pure date-order cases; each probe is placed relative to it."""


def test_pre_start_window_is_filtered_out() -> None:
    """A window that closes before the operator's alta is dropped."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR - 1, "1T"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR - 1, 1, 1),
            closes_on=date(_YEAR - 1, 4, 20),
            activity_start_date=date(_YEAR - 1, 6, 1),
            activity_end_date=None,
        )
        is True
    )


def test_post_baja_window_is_filtered_out() -> None:
    """A window that opens after the operator's baja is dropped."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR + 1, "3T"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR + 1, 7, 1),
            closes_on=date(_YEAR + 1, 7, 20),
            activity_start_date=None,
            activity_end_date=date(_YEAR + 1, 5, 31),
        )
        is True
    )


def test_window_straddling_alta_is_retained() -> None:
    """A window whose close date is on or after the alta is kept —
    the operator may still owe a return covering the active fraction."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR, "2T"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR, 4, 1),
            closes_on=date(_YEAR, 4, 20),
            activity_start_date=date(_YEAR, 4, 15),
            activity_end_date=None,
        )
        is False
    )


def test_window_straddling_baja_is_retained() -> None:
    """A window whose open date is on or before the baja is kept —
    activity occurred during the window even if it ended mid-period."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR, "2T"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR, 4, 1),
            closes_on=date(_YEAR, 4, 20),
            activity_start_date=None,
            activity_end_date=date(_YEAR, 4, 10),
        )
        is False
    )


def test_no_censo_dates_means_no_filtering() -> None:
    """When the operator has not yet captured a censo, both dates
    are None and the gate never fires. The profile lacks the legal
    activity-period evidence needed to suppress any window."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR, "2T"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR, 4, 1),
            closes_on=date(_YEAR, 4, 20),
            activity_start_date=None,
            activity_end_date=None,
        )
        is False
    )


def test_window_inside_active_period_is_retained() -> None:
    """Standard case: window opens after alta and closes before baja."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR, "3T"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR, 7, 1),
            closes_on=date(_YEAR, 7, 20),
            activity_start_date=date(_YEAR - 4, 1, 1),
            activity_end_date=date(_YEAR + 1, 12, 31),
            legal_entity_token=EntityType.from_registry("legal_entity"),
        )
        is False
    )


def test_period_ending_on_alta_date_is_retained() -> None:
    """A period ending on the alta date still overlaps activity."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR, "03"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR, 4, 1),
            closes_on=date(_YEAR, 4, 22),
            activity_start_date=date(_YEAR, 3, 31),
            activity_end_date=None,
        )
        is False
    )


def test_period_opening_on_baja_date_is_retained() -> None:
    """A period opening on the baja date still overlaps activity."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR, "2T"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR, 7, 1),
            closes_on=date(_YEAR, 7, 22),
            activity_start_date=None,
            activity_end_date=date(_YEAR, 4, 1),
        )
        is False
    )


@pytest.mark.parametrize("period_code", ["4T", "0A"])
def test_residual_obligation_after_cessation_is_retained(period_code: str) -> None:
    """A later filing window does not erase an overlapping final tax period."""

    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR + 1, period_code),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR + 2, 1, 1),
            closes_on=date(_YEAR + 2, 1, 30),
            activity_start_date=date(_YEAR - 4, 1, 1),
            activity_end_date=date(_YEAR + 1, 12, 15),
        )
        is False
    )


def test_period_entirely_after_cessation_is_filtered() -> None:
    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR + 2, "1T"),
            entity_type=EntityType.from_registry("natural_person"),
            opens_on=date(_YEAR + 2, 4, 1),
            closes_on=date(_YEAR + 2, 4, 20),
            activity_start_date=None,
            activity_end_date=date(_YEAR + 1, 12, 31),
        )
        is True
    )


def test_legal_entity_activity_end_does_not_impersonate_extinction() -> None:
    assert (
        window_outside_activity_period(
            period=Period.from_year_and_code(_YEAR + 2, "0A"),
            entity_type=EntityType.from_registry("legal_entity"),
            opens_on=date(_YEAR + 3, 7, 1),
            closes_on=date(_YEAR + 3, 7, 25),
            activity_start_date=date(_YEAR - 4, 1, 1),
            activity_end_date=date(_YEAR + 1, 12, 31),
            legal_entity_token=EntityType.from_registry("legal_entity"),
        )
        is False
    )
