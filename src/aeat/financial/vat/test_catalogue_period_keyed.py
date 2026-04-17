"""Unit tests for the period-keyed catalogue infrastructure (#183)."""

from __future__ import annotations

import logging
from datetime import date

import pytest

from . import VAT_CATALOGUE_2025, VAT_CATALOGUES_BY_YEAR, resolve_catalogue


@pytest.mark.unit
def test_catalogues_by_year_contains_2025() -> None:
    """The wave-2 mapping ships the 2025 entry."""
    assert 2025 in VAT_CATALOGUES_BY_YEAR
    assert VAT_CATALOGUES_BY_YEAR[2025] is VAT_CATALOGUE_2025


@pytest.mark.unit
def test_catalogues_by_year_is_immutable() -> None:
    """The mapping is a MappingProxyType; runtime mutation must fail."""
    from types import MappingProxyType

    assert isinstance(VAT_CATALOGUES_BY_YEAR, MappingProxyType)


@pytest.mark.unit
def test_resolve_catalogue_2025_returns_2025_entry() -> None:
    catalogue = resolve_catalogue(on=date(2025, 6, 15))
    assert catalogue is VAT_CATALOGUE_2025


@pytest.mark.unit
def test_resolve_catalogue_2024_falls_back_with_log(caplog: pytest.LogCaptureFixture) -> None:
    """Non-populated years fall back to 2025 with a debug log line."""
    caplog.set_level(logging.DEBUG, logger="aeat.financial.vat._catalogue")
    catalogue = resolve_catalogue(on=date(2024, 6, 15))
    assert catalogue is VAT_CATALOGUE_2025
    assert any("no catalogue for year 2024" in record.getMessage() for record in caplog.records)


@pytest.mark.unit
def test_resolve_catalogue_2026_also_falls_back() -> None:
    """Future years also fall back gracefully (no exception)."""
    catalogue = resolve_catalogue(on=date(2026, 1, 1))
    assert catalogue is VAT_CATALOGUE_2025
