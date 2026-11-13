"""The ledger can classify interest, dividends and gains without entering any existing income route.

The two savings families are admitted by the published taxonomy. Their purposes
match none of the activity, rent or employment predicates, so a row tagged with
one is classifiable but is picked up by no withholding or income aggregation.
The one predicate that does hold is the non-employment one, which is intended:
interest is settled net of its withholding.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..enums import TransactionDirection
from ..errors import TransactionValidationError
from ..irpf_categories import (
    has_activity_irpf_category,
    has_employment_irpf_category,
    has_non_work_irpf_category,
    has_rent_irpf_category,
    ledger_irpf_category,
    require_ledger_irpf_category,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CAPITAL = "capital_mobiliario"
_GAINS = "ganancias_patrimoniales"


@pytest.fixture
def authority() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


@pytest.mark.parametrize("token", [_CAPITAL, _GAINS])
def test_the_taxonomy_accepts_the_savings_family_tokens(authority: PinnedAuthorityOperation, token: str) -> None:
    assert require_ledger_irpf_category(token, authority=authority) == token
    assert require_ledger_irpf_category(f"  {token.upper()} ", authority=authority) == token


def test_an_undeclared_token_is_still_refused_and_the_refusal_names_the_new_ids(
    authority: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(TransactionValidationError) as refused:
        require_ledger_irpf_category("dividendos_inventados", authority=authority)

    assert _CAPITAL in str(refused.value)
    assert _GAINS in str(refused.value)


def test_capital_yield_is_incoming_only_and_gains_run_both_ways(authority: PinnedAuthorityOperation) -> None:
    capital = ledger_irpf_category(_CAPITAL, authority=authority)
    gains = ledger_irpf_category(_GAINS, authority=authority)

    assert capital is not None
    assert gains is not None
    assert capital.directions == (TransactionDirection.INCOMING,)
    assert set(gains.directions) == {TransactionDirection.INCOMING, TransactionDirection.OUTGOING}
    assert not capital.net_paid
    assert not gains.net_paid
    assert capital.related_ids == ()
    assert gains.related_ids == ()
    assert ledger_irpf_category(_CAPITAL, direction=TransactionDirection.OUTGOING, authority=authority) is None


@pytest.mark.parametrize("token", [_CAPITAL, _GAINS])
def test_no_existing_income_route_matches_a_savings_family(authority: PinnedAuthorityOperation, token: str) -> None:
    for direction in TransactionDirection:
        assert not has_activity_irpf_category(token, direction=direction, authority=authority)
        assert not has_rent_irpf_category(token, direction=direction, authority=authority)
        assert not has_employment_irpf_category(token, direction=direction, authority=authority)


def test_the_non_employment_predicate_holds_for_a_savings_row_in_a_declared_direction(
    authority: PinnedAuthorityOperation,
) -> None:
    assert has_non_work_irpf_category(_CAPITAL, direction=TransactionDirection.INCOMING, authority=authority)
    assert has_non_work_irpf_category(_GAINS, direction=TransactionDirection.OUTGOING, authority=authority)
