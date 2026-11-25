"""Tests for the registry-grounded EU member state validators.

Country code validation anchors to :class:`cadrumo.domain.iva.EUMemberState`
rather than a hand-maintained list.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.eu_member_state_catalogue import resolve_eu_member_state_catalogue
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..validators import is_eu_member_state_code, validate_country_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ENVELOPE_YEAR = filing_year_envelope().horizon
_ON = date(_ENVELOPE_YEAR, 6, 15)


@pytest.fixture(autouse=True)
def _authority_scope(operation: PinnedAuthorityOperation) -> Iterator[None]:
    with validating_governed_facts(operation):
        yield


def test_eu_member_state_codes_match_substrate_catalogue_27_states(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = resolve_eu_member_state_catalogue(effective_date=_ON, authority=operation)
    northern_ireland = catalogue.require("xi")
    members = tuple(member for member in catalogue.choices if member != northern_ireland)
    assert len(members) == 27
    assert all(is_eu_member_state_code(member.value.upper(), effective_date=_ON) for member in members)
    assert not is_eu_member_state_code("XI", effective_date=_ON)


def test_is_eu_member_state_code_accepts_each_substrate_member(operation: PinnedAuthorityOperation) -> None:
    catalogue = resolve_eu_member_state_catalogue(effective_date=_ON, authority=operation)
    northern_ireland = catalogue.require("xi")
    for member in (member for member in catalogue.choices if member != northern_ireland):
        assert is_eu_member_state_code(member.value.upper(), effective_date=_ON) is True
        assert is_eu_member_state_code(member.value.lower(), effective_date=_ON) is True
        assert is_eu_member_state_code(f"  {member.value}  ", effective_date=_ON) is True


def test_is_eu_member_state_code_rejects_non_eu_codes() -> None:
    for non_eu in ("GB", "XI", "CH", "NO", "IS", "US", "CA", "TR", "MX", "JP", "BR"):
        assert is_eu_member_state_code(non_eu, effective_date=_ON) is False, non_eu


def test_is_eu_member_state_code_rejects_malformed_inputs() -> None:
    for bad in ("", "X", "ESP", "1F", "&&", "  "):
        assert is_eu_member_state_code(bad, effective_date=_ON) is False, bad


def test_membership_resolves_at_the_envelope_floor_and_horizon(operation: PinnedAuthorityOperation) -> None:
    envelope = operation.supported_filing_years().date_envelope()
    for day in (envelope.floor, envelope.horizon):
        assert is_eu_member_state_code("DE", effective_date=day) is True
        assert is_eu_member_state_code("US", effective_date=day) is False


def test_membership_takes_the_supplied_date_and_never_the_run_date(operation: PinnedAuthorityOperation) -> None:
    """A date below the support floor is refused by the dated read, proving the date is the one resolved."""
    envelope = operation.supported_filing_years().date_envelope()
    with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
        is_eu_member_state_code("DE", effective_date=date(envelope.floor.year - 1, 6, 1))


def test_validate_country_code_remains_permissive_for_general_invoice_use() -> None:
    """The base validator is unchanged; only the EU-narrowing helpers are
    new. Existing invoice records with non-EU counterparties keep
    working through ``validate_country_code``."""
    assert validate_country_code("us") == "US"
    assert validate_country_code("MX") == "MX"
    assert validate_country_code("AU") == "AU"
