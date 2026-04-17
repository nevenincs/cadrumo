"""Invariant tests for the in-code canonical calendar."""

from __future__ import annotations

import pytest

from aeat.deadlines import CALENDAR, KNOWN_AUTONOMO_MODELOS, SUPPORTED_YEARS

pytestmark = pytest.mark.unit


def test_calendar_is_non_empty() -> None:
    assert CALENDAR


def test_supported_years_present() -> None:
    years_in_calendar = {window.year for window in CALENDAR}
    assert set(SUPPORTED_YEARS).issubset(years_in_calendar)


def test_every_window_modelo_is_known() -> None:
    for window in CALENDAR:
        assert window.modelo in KNOWN_AUTONOMO_MODELOS


def test_every_window_has_citation() -> None:
    for window in CALENDAR:
        assert window.boe_references, f"{window.modelo} {window.period} missing citation"
        assert all(ref for ref in window.boe_references)


def test_window_order() -> None:
    for window in CALENDAR:
        assert window.opens_on <= window.closes_on
        if window.payment_cutoff_on is not None:
            assert window.payment_cutoff_on <= window.closes_on


def test_quarterly_modelo_303_2026_count() -> None:
    """The 2026 calendar must contain four quarterly entries for 303."""
    entries = [w for w in CALENDAR if w.modelo == "303" and w.year == 2026]
    assert len(entries) == 4
    assert {w.period for w in entries} == {"2026Q1", "2026Q2", "2026Q3", "2026Q4"}


def test_annual_modelo_347_2026_window() -> None:
    """The 2026 calendar must contain one annual 347 entry."""
    entries = [w for w in CALENDAR if w.modelo == "347" and w.year == 2026]
    assert len(entries) == 1
    assert entries[0].opens_on.isoformat() == "2027-02-01"
    assert entries[0].closes_on.isoformat() == "2027-03-01"
