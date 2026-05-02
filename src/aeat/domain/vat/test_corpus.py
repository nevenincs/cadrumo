"""Unit tests for :func:`aeat.domain.vat.load_vat_rules_from_manual`.

Verifies the in-memory fallback for the supported 2025 year and the
:exc:`aeat.domain.vat.VatCatalogueError` for every other year.
"""

from __future__ import annotations

import logging

import pytest

from . import (
    VAT_CATALOGUE_2025,
    VatCatalogueError,
    load_vat_rules_from_manual,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_load_2025_returns_fallback_catalogue(caplog: pytest.LogCaptureFixture) -> None:
    """The 2025 loader returns :data:`VAT_CATALOGUE_2025` and logs INFO."""
    caplog.set_level(logging.INFO, logger="aeat.domain.vat._corpus")
    catalogue = load_vat_rules_from_manual(2025)
    assert catalogue is VAT_CATALOGUE_2025
    assert any("falling back to in-memory VAT_CATALOGUE_2025" in record.getMessage() for record in caplog.records)


def test_load_unsupported_year_raises() -> None:
    """Any year other than 2025 must raise :exc:`VatCatalogueError`."""
    with pytest.raises(VatCatalogueError):
        load_vat_rules_from_manual(2024)
