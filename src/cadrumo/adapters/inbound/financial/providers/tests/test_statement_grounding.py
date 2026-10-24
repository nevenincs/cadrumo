"""Deterministic grounding of proposed statement movements, rule by rule.

Each case hands :func:`ground_statement` a page's printed text and a proposal,
exactly as a reader would, and asserts what the rules accept, drop or refuse.
No model and no PDF is involved: the rules are pure functions of the page text.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ......application.ledger.statement_reading import (
    ProposedDirection,
    ProposedStatementMovement,
    ProposedStatementPage,
)
from .._statement_grounding import ReconciliationOutcome, StatementPageText, ground_statement

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _movement(
    booked: str,
    amount: str,
    *,
    description: str = "Movement",
    direction: ProposedDirection | None = None,
    balance: str | None = None,
    counterparty: str | None = None,
) -> ProposedStatementMovement:
    return ProposedStatementMovement(
        booked_date=booked,
        value_date=None,
        description=description,
        counterparty=counterparty,
        amount=amount,
        direction=direction,
        balance=balance,
    )


def _page(
    text: str,
    *movements: ProposedStatementMovement,
    opening: str | None = None,
    closing: str | None = None,
    currency: str | None = None,
) -> StatementPageText:
    return StatementPageText(
        page_number=1,
        text=text,
        proposal=ProposedStatementPage(
            movements=movements,
            opening_balance=opening,
            closing_balance=closing,
            currency=currency,
        ),
        transcribed_by="pdfplumber",
    )


def test_a_line_backs_at_most_one_movement() -> None:
    """Two proposals for one printed line import once; the duplicate is reported."""
    page = _page(
        "Rent 03/02/2026 -800,00\nGroceries 04/02/2026 -42,10",
        _movement("03/02/2026", "-800,00", description="Rent"),
        _movement("03/02/2026", "-800,00", description="Rent"),
        _movement("04/02/2026", "-42,10", description="Groceries"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert [m.signed_amount for m in grounded.movements] == [Decimal("-800.00"), Decimal("-42.10")]
    assert any("movement 2" in warning and "dropped" in warning for warning in grounded.warnings)


def test_dates_printed_in_both_day_orders_refuse_the_statement() -> None:
    """A 13th in the first group and a 13th in the second cannot be one convention."""
    page = _page(
        "Coffee 13/02/2026 -3,00\nTaxi 02/14/2026 -12,00",
        _movement("13/02/2026", "-3,00"),
        _movement("02/14/2026", "-12,00"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert not grounded.importable
    assert grounded.refusals == ("the statement prints dates in both day-month and month-day order",)


def test_month_first_dates_are_read_month_first() -> None:
    """A statement whose second group exceeds 12 reads every date month-first."""
    page = _page(
        "Coffee 02/14/2026 -3.00 USD\nTaxi 03/01/2026 -12.00 USD",
        _movement("02/14/2026", "-3.00 USD"),
        _movement("03/01/2026", "-12.00 USD"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert [m.booked_date for m in grounded.movements] == [date(2026, 2, 14), date(2026, 3, 1)]
    assert {m.currency for m in grounded.movements} == {"USD"}


@pytest.mark.parametrize(
    ("first_balance", "second_balance"),
    [("1.000,00", "958,00"), ("958,00", "1.000,00")],
    ids=["oldest-first", "newest-first"],
)
def test_running_balances_reconcile_in_either_listing_order(first_balance: str, second_balance: str) -> None:
    """Oldest-first and newest-first statements both reconcile their running balances."""
    if first_balance == "1.000,00":
        text = f"Deposit 01/02/2026 +1.000,00 {first_balance}\nFee 02/02/2026 -42,00 {second_balance}"
        movements = (
            _movement("01/02/2026", "+1.000,00", balance=first_balance),
            _movement("02/02/2026", "-42,00", balance=second_balance),
        )
    else:
        text = f"Fee 02/02/2026 -42,00 {first_balance}\nDeposit 01/02/2026 +1.000,00 {second_balance}"
        movements = (
            _movement("02/02/2026", "-42,00", balance=first_balance),
            _movement("01/02/2026", "+1.000,00", balance=second_balance),
        )

    grounded = ground_statement((_page(text, *movements),), default_currency="EUR")

    assert grounded.reconciliation is ReconciliationOutcome.RECONCILED
    assert grounded.importable


def test_running_balances_that_do_not_follow_refuse_the_statement() -> None:
    """A running balance the movements cannot produce means a movement was misread."""
    page = _page(
        "Deposit 01/02/2026 +1.000,00 1.000,00\nFee 02/02/2026 -42,00 990,00",
        _movement("01/02/2026", "+1.000,00", balance="1.000,00"),
        _movement("02/02/2026", "-42,00", balance="990,00"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.reconciliation is ReconciliationOutcome.CONTRADICTED
    assert not grounded.importable


def test_an_amount_whose_separator_stays_ambiguous_is_dropped() -> None:
    """``1.234`` reads both ways, and with no other amount to decide by it is not guessed."""
    page = _page(
        "Transfer 01/02/2026 -1.234 EUR",
        _movement("01/02/2026", "-1.234 EUR"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.movements == ()
    assert any("not a readable amount" in warning for warning in grounded.warnings)


def test_the_statement_convention_decides_an_otherwise_ambiguous_amount() -> None:
    """A comma-decimal amount elsewhere on the statement settles ``1.234`` as one thousand."""
    page = _page(
        "Transfer 01/02/2026 -1.234 EUR\nFee 02/02/2026 -2,50 EUR",
        _movement("01/02/2026", "-1.234 EUR"),
        _movement("02/02/2026", "-2,50 EUR"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert [m.signed_amount for m in grounded.movements] == [Decimal("-1234"), Decimal("-2.50")]


def test_a_description_with_words_the_page_does_not_print_falls_back_to_the_line() -> None:
    """Invented narrative is replaced by the anchored line's own text."""
    page = _page(
        "Bizum Ana 01/02/2026 -20,00",
        _movement("01/02/2026", "-20,00", description="Monthly rent to landlord", counterparty="Landlord SL"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    movement = grounded.movements[0]
    assert movement.description == "Bizum Ana"
    assert movement.counterparty is None


def test_a_printed_currency_symbol_names_the_currency() -> None:
    """An unambiguous symbol printed with the amount is read as its ISO code."""
    page = _page(
        "Card payment 01/02/2026 -9,99 £",
        _movement("01/02/2026", "-9,99 £"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.movements[0].currency == "GBP"


def test_a_statement_printing_no_currency_uses_the_default_and_says_so() -> None:
    """The fallback currency is stated, never silent."""
    page = _page("Card payment 01/02/2026 -9,99", _movement("01/02/2026", "-9,99"))

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.movements[0].currency == "EUR"
    assert any("prints no currency" in warning for warning in grounded.warnings)


def test_a_typographic_minus_is_a_printed_sign() -> None:
    """The U+2212 minus PDF text layers print is read as a minus, not as no sign."""
    page = _page(
        "Card payment 01/02/2026 −9,99 EUR",
        _movement("01/02/2026", "−9,99 EUR", direction=ProposedDirection.IN),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.movements == ()
    assert any("contradicts the printed sign" in warning for warning in grounded.warnings)


def test_a_year_less_date_is_dropped_rather_than_completed() -> None:
    """A date printed without its year is not given one by guess."""
    page = _page("Coffee 01/02 -3,00 EUR", _movement("01/02", "-3,00 EUR"))

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.movements == ()
    assert any("not a complete date" in warning for warning in grounded.warnings)
