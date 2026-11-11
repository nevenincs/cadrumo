"""The bindings authority query bounds its filing year by the canonical window."""

from __future__ import annotations

import pytest

from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ..authority_query import authority_query

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _supported_prior_year() -> int:
    """The supported year before the horizon, read from the published authority."""
    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years().horizon - 1


_PRIOR_YEAR = _supported_prior_year()


@pytest.mark.parametrize("year", [FOUR_DIGIT_YEAR_FIRST - 1, 0, FOUR_DIGIT_YEAR_LAST + 1])
def test_bindings_query_refuses_a_value_not_written_as_a_year(year: int) -> None:
    with pytest.raises(ValueError, match="invalid filing year"):
        authority_query({"query": "bindings", "modelo": "100", "filing_year": year})


def test_bindings_query_admits_a_year_inside_the_filing_window() -> None:
    answer = authority_query({"query": "bindings", "modelo": "100", "filing_year": _PRIOR_YEAR})

    assert answer["outcome"] == "published"
