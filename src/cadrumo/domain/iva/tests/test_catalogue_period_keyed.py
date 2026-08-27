"""Year-resolved IVA catalogue registry tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from .. import IvaCatalogueError, iva_catalogue_years, resolve_catalogue
from .._catalogue import bundled_iva_catalogue, load_iva_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_grounded_years_are_derived_from_the_citation_windows() -> None:
    """Coverage comes from the evidence, not from a filename.

    Property, not tally: the assertion is that every grounded year resolves and
    that the set is non-empty, so adding a year's citations widens it without
    editing this test.
    """
    grounded = iva_catalogue_years()

    assert grounded, "the catalogue grounds no year at all; every assertion below would be vacuous"
    for year in sorted(grounded):
        assert resolve_catalogue(on=date(year, 6, 15)) is not None


def test_a_resolved_catalogue_carries_only_citations_asserted_over_that_year() -> None:
    """Projection is the point: a year gets the evidence that speaks to it."""
    year = min(iva_catalogue_years())

    catalogue = resolve_catalogue(on=date(year, 6, 15))

    citations = [citation for regulation in catalogue for citation in regulation.citations]
    assert citations, "the resolved catalogue carries no citations; the projection dropped everything"
    assert all(citation.window.covers_year(year) for citation in citations)


def test_resolving_the_same_year_twice_returns_the_same_projection() -> None:
    assert resolve_catalogue(on=date(2025, 6, 15)) is resolve_catalogue(on=date(2025, 1, 1))


def test_the_undated_corpus_carries_every_citation_regardless_of_span() -> None:
    """The loaded corpus is the whole record; only resolution narrows it."""
    whole = sum(len(regulation.citations) for regulation in bundled_iva_catalogue())
    resolved = sum(
        len(regulation.citations) for regulation in resolve_catalogue(on=date(max(iva_catalogue_years()), 1, 1))
    )

    assert whole >= resolved > 0


def test_resolve_catalogue_requires_a_grounded_year() -> None:
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
