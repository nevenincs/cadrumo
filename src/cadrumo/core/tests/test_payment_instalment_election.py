"""The split of an amount to pay in two instalments at the share the registry declares.

RD 439/2007 art. 62.2 sets the 60 per cent; no official rule states the cent
rounding, which is Cadrumo's own and worked here by hand.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..payment_instalment_election import PaymentInstalmentElection, instalment_amounts, second_instalment_is_payable

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SIXTY: Decimal = Decimal("0.60")


@pytest.mark.parametrize(
    ("amount", "first", "second"),
    [
        (Decimal("1000.00"), Decimal("600.00"), Decimal("400.00")),
        # 60 per cent of 1.000,01 is 600,006, rounded to 600,01; the second is what remains.
        (Decimal("1000.01"), Decimal("600.01"), Decimal("400.00")),
        # 60 per cent of 0,02 is 0,012, rounded to 0,01, which leaves the least second instalment of 0,01.
        (Decimal("0.02"), Decimal("0.01"), Decimal("0.01")),
        (Decimal("333.33"), Decimal("200.00"), Decimal("133.33")),
    ],
)
def test_the_first_instalment_is_sixty_per_cent_to_the_cent_and_the_second_the_rest(
    amount: Decimal, first: Decimal, second: Decimal
) -> None:
    assert instalment_amounts(amount, first_share=_SIXTY) == (first, second)
    assert sum(instalment_amounts(amount, first_share=_SIXTY)) == amount


def test_an_amount_whose_second_instalment_would_be_nothing_is_not_split() -> None:
    """60 per cent of 0,01 is 0,006, rounded to 0,01, which leaves nothing for the second."""
    amount = Decimal("0.01")

    assert not second_instalment_is_payable(amount, first_share=_SIXTY)
    with pytest.raises(ValueError, match="second instalment"):
        instalment_amounts(amount, first_share=_SIXTY)


@pytest.mark.parametrize(
    ("amount", "payable"),
    [
        (Decimal("0.00"), False),
        (Decimal("-10.00"), False),
        (Decimal("0.01"), False),
        (Decimal("0.02"), True),
        (Decimal("0.03"), True),
        (Decimal("1000.00"), True),
    ],
)
def test_the_second_instalment_is_payable_from_two_cents(amount: Decimal, payable: bool) -> None:
    assert second_instalment_is_payable(amount, first_share=_SIXTY) is payable


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-10.00")])
def test_only_an_amount_to_pay_is_split(amount: Decimal) -> None:
    with pytest.raises(ValueError, match="positive"):
        instalment_amounts(amount, first_share=_SIXTY)


def test_each_election_says_whether_it_splits_and_debits_the_second() -> None:
    assert [(member.splits, member.debits_second) for member in PaymentInstalmentElection] == [
        (False, False),
        (True, True),
        (True, False),
    ]
