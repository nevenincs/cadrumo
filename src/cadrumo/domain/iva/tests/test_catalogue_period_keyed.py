"""Period-keyed IVA catalogue registry tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import MappingProxyType

import pytest

from .. import IvaCatalogueError, load_iva_catalogues, resolve_catalogue
from .._catalogue import load_iva_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_catalogues_by_year_contains_committed_2025_catalogue() -> None:
    assert 2025 in load_iva_catalogues()
    assert load_iva_catalogues()[2025] is resolve_catalogue(on=date(2025, 1, 1))


def test_catalogues_by_year_is_immutable() -> None:
    assert isinstance(load_iva_catalogues(), MappingProxyType)


def test_resolve_catalogue_2025_returns_committed_entry() -> None:
    catalogue = resolve_catalogue(on=date(2025, 6, 15))
    assert catalogue is load_iva_catalogues()[2025]


def test_resolve_catalogue_requires_exact_year() -> None:
    # The witness year is deliberately OUTSIDE the registry's supported filing
    # window. A supported year used here would assert that a year the product
    # claims to file is permanently ungrounded, pinning today's coverage gap as
    # the contract and reddening the moment that year is correctly added.
    with pytest.raises(IvaCatalogueError, match="year=1990"):
        resolve_catalogue(on=date(1990, 6, 15))


def test_load_iva_catalogue_wraps_missing_path_as_domain_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing-iva-catalogue.toml"

    with pytest.raises(IvaCatalogueError, match=r"cannot stat IVA catalogue"):
        load_iva_catalogue(missing)
