"""Tests for the registry-grounded EU member state validators.

Country code validation anchors to :class:`aeat.domain.iva.EUMemberState`
rather than a hand-maintained list, and the
:func:`assert_eu_member_state_code` helper rejects non-EU codes for
callers (e.g. Modelo 369 binding selectors) that need an EU-only
boundary.
"""

from __future__ import annotations

import pytest

from ...iva import EUMemberState
from .._validators import (
    EU_MEMBER_STATE_CODES,
    assert_eu_member_state_code,
    is_eu_member_state_code,
    validate_country_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_eu_member_state_codes_match_substrate_enum_27_states() -> None:
    expected = {member.value.upper() for member in EUMemberState}
    assert expected == EU_MEMBER_STATE_CODES
    assert len(EU_MEMBER_STATE_CODES) == 27


def test_is_eu_member_state_code_accepts_each_substrate_member() -> None:
    for member in EUMemberState:
        assert is_eu_member_state_code(member.value.upper()) is True
        assert is_eu_member_state_code(member.value.lower()) is True
        assert is_eu_member_state_code(f"  {member.value}  ") is True


def test_is_eu_member_state_code_rejects_non_eu_codes() -> None:
    for non_eu in ("GB", "CH", "NO", "IS", "US", "CA", "TR", "MX", "JP", "BR"):
        assert is_eu_member_state_code(non_eu) is False


def test_is_eu_member_state_code_rejects_malformed_inputs() -> None:
    for bad in ("", "X", "ESP", "1F", "&&", "  "):
        assert is_eu_member_state_code(bad) is False


def test_assert_eu_member_state_code_returns_uppercase_for_eu_member() -> None:
    assert assert_eu_member_state_code("es") == "ES"
    assert assert_eu_member_state_code("DE") == "DE"
    assert assert_eu_member_state_code("  fr  ") == "FR"


def test_assert_eu_member_state_code_raises_for_non_eu_country() -> None:
    with pytest.raises(ValueError, match="not one of the 27 EU Member States"):
        assert_eu_member_state_code("GB")
    with pytest.raises(ValueError, match="not one of the 27 EU Member States"):
        assert_eu_member_state_code("US")


def test_assert_eu_member_state_code_raises_for_malformed_code() -> None:
    with pytest.raises(ValueError, match="ISO-3166 alpha-2"):
        assert_eu_member_state_code("ESP")
    with pytest.raises(ValueError, match="ISO-3166 alpha-2"):
        assert_eu_member_state_code("E1")


def test_validate_country_code_remains_permissive_for_general_invoice_use() -> None:
    """The base validator is unchanged; only the EU-narrowing helpers are
    new. Existing invoice records with non-EU counterparties keep
    working through ``validate_country_code``."""
    assert validate_country_code("us") == "US"
    assert validate_country_code("MX") == "MX"
    assert validate_country_code("AU") == "AU"
