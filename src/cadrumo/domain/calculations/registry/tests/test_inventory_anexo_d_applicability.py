"""The Anexo D inventory rows apply from the year the registry authors them, across every year after it."""

from __future__ import annotations

import pytest

from ..authority import PinnedAuthorityOperation
from ..inventory_anexo_d_applicability import inventory_anexo_d_applies, resolve_inventory_anexo_d_first_filing_year
from .authored_editions import newest_authored_edition, projected_exercise

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_rows_apply_in_the_year_the_registry_first_authors_them(operation: PinnedAuthorityOperation) -> None:
    first = resolve_inventory_anexo_d_first_filing_year(filing_year=newest_authored_edition("100"), authority=operation)

    assert inventory_anexo_d_applies(filing_year=first, authority=operation)


def test_the_rows_apply_in_a_year_no_edition_authors(operation: PinnedAuthorityOperation) -> None:
    projected = projected_exercise("100")

    assert inventory_anexo_d_applies(filing_year=projected, authority=operation)


def test_the_rows_do_not_apply_before_the_year_the_registry_first_authors_them(
    operation: PinnedAuthorityOperation,
) -> None:
    floor = operation.supported_filing_years().floor
    first = resolve_inventory_anexo_d_first_filing_year(filing_year=floor, authority=operation)

    assert first > floor, "the registry holds editions before the one that first authors the rows"
    for year in range(floor, first):
        assert not inventory_anexo_d_applies(filing_year=year, authority=operation)
