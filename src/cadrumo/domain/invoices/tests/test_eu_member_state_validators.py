"""Tests for the registry-grounded EU member state validators.

Country code validation anchors to :class:`cadrumo.domain.iva.EUMemberState`
rather than a hand-maintained list.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.eu_member_state_catalogue import resolve_eu_member_state_catalogue
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ..validators import is_eu_member_state_code, validate_country_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_scope(operation: PinnedAuthorityOperation) -> Iterator[None]:
    with validating_governed_facts(operation):
        yield


def test_eu_member_state_codes_match_substrate_catalogue_27_states(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = resolve_eu_member_state_catalogue(effective_date=date(2025, 1, 1), authority=operation)
    northern_ireland = catalogue.require("xi")
    members = tuple(member for member in catalogue.choices if member != northern_ireland)
    assert len(members) == 27
    assert all(is_eu_member_state_code(member.value.upper()) for member in members)
    assert not is_eu_member_state_code("XI")


def test_is_eu_member_state_code_accepts_each_substrate_member(operation: PinnedAuthorityOperation) -> None:
    catalogue = resolve_eu_member_state_catalogue(effective_date=date(2025, 1, 1), authority=operation)
    northern_ireland = catalogue.require("xi")
    for member in (member for member in catalogue.choices if member != northern_ireland):
        assert is_eu_member_state_code(member.value.upper()) is True
        assert is_eu_member_state_code(member.value.lower()) is True
        assert is_eu_member_state_code(f"  {member.value}  ") is True


def test_is_eu_member_state_code_rejects_non_eu_codes() -> None:
    for non_eu in ("GB", "XI", "CH", "NO", "IS", "US", "CA", "TR", "MX", "JP", "BR"):
        assert is_eu_member_state_code(non_eu) is False, non_eu


def test_is_eu_member_state_code_rejects_malformed_inputs() -> None:
    for bad in ("", "X", "ESP", "1F", "&&", "  "):
        assert is_eu_member_state_code(bad) is False, bad


def test_validate_country_code_remains_permissive_for_general_invoice_use() -> None:
    """The base validator is unchanged; only the EU-narrowing helpers are
    new. Existing invoice records with non-EU counterparties keep
    working through ``validate_country_code``."""
    assert validate_country_code("us") == "US"
    assert validate_country_code("MX") == "MX"
    assert validate_country_code("AU") == "AU"
