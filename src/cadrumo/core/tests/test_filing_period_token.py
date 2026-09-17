"""Only tokens that name one filable period are filing-period tokens."""

from __future__ import annotations

import pytest

from ..period import Period, is_filing_period_token

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("token", ["1T", "0A", "12", "2P", "EXT-3T", "AD-HOC", "EVENT-3", " 4t "])
def test_filable_tokens_build_a_period(token: str) -> None:
    assert is_filing_period_token(token)
    Period.from_year_and_code(2026, token)


@pytest.mark.parametrize("token", ["EVENT-N", "ALTA", "COMUNICACION", "5T", ""])
def test_selectors_and_unknown_tokens_are_not_filable(token: str) -> None:
    assert not is_filing_period_token(token)
