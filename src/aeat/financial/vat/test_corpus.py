"""Unit tests for the VAT corpus loader."""

from __future__ import annotations

import logging

import pytest

from aeat.financial.vat import (
    VAT_CATALOGUE_2025,
    VatCatalogueError,
    load_vat_rules_from_manual,
)


@pytest.mark.unit
def test_load_2025_returns_fallback_catalogue(caplog: pytest.LogCaptureFixture) -> None:
    """The 2025 loader returns the in-memory catalogue and logs INFO."""
    caplog.set_level(logging.INFO, logger="aeat.financial.vat._corpus")
    catalogue = load_vat_rules_from_manual(2025)
    assert catalogue is VAT_CATALOGUE_2025
    assert any("falling back to in-memory VAT_CATALOGUE_2025" in record.getMessage() for record in caplog.records)


@pytest.mark.unit
def test_load_unsupported_year_raises() -> None:
    """Any year other than 2025 must raise VatCatalogueError."""
    with pytest.raises(VatCatalogueError):
        load_vat_rules_from_manual(2024)
