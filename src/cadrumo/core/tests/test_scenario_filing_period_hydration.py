"""Tests for the shared scenario ``filing_period`` hydration validator."""

from __future__ import annotations

from datetime import date

import pytest

from ..period import Period, hydrate_scenario_filing_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_hydrates_from_filing_year_and_period() -> None:
    hydrated = hydrate_scenario_filing_period({"filing_year": 2026, "period": "1T"})
    assert hydrated == {"filing_year": 2026, "period": "1T", "filing_period": Period.from_year_and_code(2026, "1T")}


def test_preserves_an_existing_filing_period() -> None:
    payload = {"filing_year": 2026, "period": "1T", "filing_period": Period.from_year_and_code(2025, "4T")}
    assert hydrate_scenario_filing_period(payload) is payload


def test_preserves_non_mapping_values() -> None:
    value = date(2026, 1, 1)
    assert hydrate_scenario_filing_period(value) is value


def test_preserves_ill_typed_pairs() -> None:
    payload = {"filing_year": "2026", "period": "1T"}
    assert hydrate_scenario_filing_period(payload) is payload


def test_preserves_invalid_period_codes() -> None:
    payload = {"filing_year": 2026, "period": "Q1"}
    assert hydrate_scenario_filing_period(payload) is payload


def test_hydration_carries_extra_keys_forward() -> None:
    hydrated = hydrate_scenario_filing_period({"filing_year": 2026, "period": "1T", "surprise": True})
    assert hydrated == {
        "filing_year": 2026,
        "period": "1T",
        "surprise": True,
        "filing_period": Period.from_year_and_code(2026, "1T"),
    }
