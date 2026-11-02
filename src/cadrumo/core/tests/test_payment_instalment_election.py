"""The 60/40 split of a Modelo 100 result to pay, by RD 439/2007 art. 62.2."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..payment_instalment_election import PaymentInstalmentElection, instalment_amounts, two_instalments_declared

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("amount", "first", "second"),
    [
        (Decimal("1000.00"), Decimal("600.00"), Decimal("400.00")),
        # 60 per cent of 1.000,01 is 600,006, rounded to 600,01; the second is what remains.
        (Decimal("1000.01"), Decimal("600.01"), Decimal("400.00")),
        # 60 per cent of 0,01 is 0,006, rounded to 0,01, which leaves nothing for the second.
        (Decimal("0.01"), Decimal("0.01"), Decimal("0.00")),
        (Decimal("333.33"), Decimal("200.00"), Decimal("133.33")),
    ],
)
def test_the_first_instalment_is_sixty_per_cent_to_the_cent_and_the_second_the_rest(
    amount: Decimal, first: Decimal, second: Decimal
) -> None:
    assert instalment_amounts(amount) == (first, second)
    assert sum(instalment_amounts(amount)) == amount


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-10.00")])
def test_only_an_amount_to_pay_is_split(amount: Decimal) -> None:
    with pytest.raises(ValueError, match="positive"):
        instalment_amounts(amount)


def test_only_modelo_100_declares_the_split() -> None:
    assert two_instalments_declared("100")
    assert not two_instalments_declared("303") and not two_instalments_declared("130")


def test_each_election_says_whether_it_splits_and_debits_the_second() -> None:
    assert [(member.splits, member.debits_second) for member in PaymentInstalmentElection] == [
        (False, False),
        (True, True),
        (True, False),
    ]
