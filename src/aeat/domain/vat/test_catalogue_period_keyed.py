"""Period-keyed VAT catalogue registry tests."""

from __future__ import annotations

from datetime import date
from types import MappingProxyType

import pytest

from . import VAT_CATALOGUES_BY_YEAR, VatCatalogueError, resolve_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_catalogues_by_year_contains_committed_2025_catalogue() -> None:
    assert 2025 in VAT_CATALOGUES_BY_YEAR
    assert VAT_CATALOGUES_BY_YEAR[2025] is resolve_catalogue(on=date(2025, 1, 1))


def test_catalogues_by_year_is_immutable() -> None:
    assert isinstance(VAT_CATALOGUES_BY_YEAR, MappingProxyType)


def test_resolve_catalogue_2025_returns_committed_entry() -> None:
    catalogue = resolve_catalogue(on=date(2025, 6, 15))
    assert catalogue is VAT_CATALOGUES_BY_YEAR[2025]


def test_resolve_catalogue_requires_exact_year() -> None:
    with pytest.raises(VatCatalogueError, match="year=2024"):
        resolve_catalogue(on=date(2024, 6, 15))
