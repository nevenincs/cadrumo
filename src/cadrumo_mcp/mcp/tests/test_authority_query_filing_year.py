"""The bindings authority query bounds its filing year by the canonical window."""

from __future__ import annotations

import pytest

from cadrumo.core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN

from ..authority_query import authority_query

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("year", [FILING_YEAR_MIN - 1, 1900, FILING_YEAR_MAX + 1, 9999])
def test_bindings_query_refuses_a_year_outside_the_filing_window(year: int) -> None:
    with pytest.raises(ValueError, match="invalid filing year"):
        authority_query({"query": "bindings", "modelo": "100", "filing_year": year})


def test_bindings_query_admits_a_year_inside_the_filing_window() -> None:
    answer = authority_query({"query": "bindings", "modelo": "100", "filing_year": 2024})

    assert answer["outcome"] == "published"
