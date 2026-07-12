"""IVA catalogue access tests."""

from __future__ import annotations

from datetime import date

import pytest

from .. import IvaCatalogueError, load_iva_rules_from_manual, resolve_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_load_2025_returns_committed_catalogue() -> None:
    catalogue = load_iva_rules_from_manual(2025)
    assert catalogue is resolve_catalogue(on=date(2025, 1, 1))


def test_load_missing_year_raises() -> None:
    with pytest.raises(IvaCatalogueError, match="year=2024"):
        load_iva_rules_from_manual(2024)
