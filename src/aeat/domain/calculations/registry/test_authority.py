"""Tests for the centralized validated registry authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.resources import bundled_path, resources

from . import RegistrySnapshotError, calculate_registry_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def test_authority_returns_cached_validated_snapshot_for_repeated_filing_context() -> None:
    authority = resources().modelos.authority

    first = authority.snapshot("130", filing_year=2026, period="1T")
    second = authority.snapshot("130", filing_year=2026, period="1T")

    assert first is second
    assert first.revision.period_selector.includes_year(2026)
    assert "1T" in first.revision.period_selector.periods


def test_authority_snapshot_runs_real_modelo_calculation() -> None:
    authority = resources().modelos.authority
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("10000.00"),
            "02": Decimal("4000.00"),
            "05": Decimal("100.00"),
            "06": Decimal("50.00"),
            "08": Decimal("5000.00"),
            "10": Decimal("20.00"),
            "15": Decimal("20.00"),
            "16": Decimal("5.00"),
            "18": Decimal("100.00"),
        },
        binding_values={"irpf.previous_year_economic_activity_net_income": Decimal("9500.00")},
        date_context={"filing_period": date(2026, 4, 20)},
    )

    assert "19" in result.values
    assert {entry.target for entry in result.entries} >= {"19"}


def test_authority_rejects_unknown_modelo() -> None:
    authority = resources().modelos.authority

    with pytest.raises(RegistrySnapshotError, match="999"):
        authority.snapshot("999", filing_year=2026, period="1T")


def test_authority_deadline_windows_are_validated_and_sorted() -> None:
    authority = resources().modelos.authority

    windows = authority.deadline_windows(2026, modelos=("130",))

    assert [window.period for _, _, window in windows] == ["2026Q1", "2026Q2", "2026Q3", "2026Q4"]
    assert [window.closes_on for _, _, window in windows] == sorted(window.closes_on for _, _, window in windows)
