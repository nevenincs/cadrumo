"""Modelo 303 carry mapping resolves for the revision selected at each filing scope."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ..m303_carry_ingress import m303_declaration_type_header_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPORT = PublishedGovernedFactSource().supported_filing_years()


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


# Every supported year, at its first quarter, its terminal quarter and its terminal month,
# so each revision the selector can pick for a filing scope is exercised.
@pytest.mark.parametrize("period", ("1T", "4T", "12"), ids=("first-quarter", "terminal-quarter", "monthly"))
@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_carry_mapping_matches_the_selected_modelo_303_revision(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
    period: str,
) -> None:
    header_key = m303_declaration_type_header_key(
        filing_year=filing_year,
        period=period,
        operation=authority_operation,
    )

    assert header_key == "declaration_type"
