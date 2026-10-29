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
from .._statement_grounding import ReconciliationOutcome, StatementPageText
from ..statement_grounding import ground_statement

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

    assert [m.signed_amount for m in grounded.movements] == [Decimal("-9.99")]
    assert any("disagrees with the printed sign" in warning for warning in grounded.warnings)


def test_a_year_less_date_is_dropped_rather_than_completed() -> None:
    """A date printed without its year is not given one by guess."""
    page = _page("Coffee 01/02 -3,00 EUR", _movement("01/02", "-3,00 EUR"))

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.movements == ()
    assert any("not a complete date" in warning for warning in grounded.warnings)


def test_a_reformatted_amount_is_matched_by_its_digits_and_parsed_as_printed() -> None:
    """A reader that dropped a thousands separator still anchors to the amount the line prints."""
    page = _page(
        "Max Mustermann 19.06.2024 +5.000,00EUR\nFee 20.06.2024 -2,50EUR",
        _movement("19.06.2024", "+5000,00EUR", direction=ProposedDirection.IN),
        _movement("20.06.2024", "-2,50EUR", direction=ProposedDirection.OUT),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert [m.signed_amount for m in grounded.movements] == [Decimal("5000.00"), Decimal("-2.50")]
    assert grounded.movements[0].printed["amount_printed"] == "+5.000,00"


def _paid_out_paid_in_page(*movements: ProposedStatementMovement) -> StatementPageText:
    return _page(
        "Date Description Paid out Paid in Balance\n"
        "01/03/2026 Balance brought forward 3,400.00\n"
        "02/03/2026 Rent 1,200.00 2,200.00\n"
        "04/03/2026 Invoice 2,450.00 4,650.00\n"
        "16/03/2026 Card payment 6.40 4,643.60\n"
        "31/03/2026 Balance carried forward 4,643.60",
        *movements,
        opening="4,643.60",
        closing="4,643.60",
    )


def test_running_balances_decide_unsigned_debit_and_credit_columns() -> None:
    """Separate paid-out and paid-in columns print no sign; the balances prove each direction.

    The reader here misreads every direction and both balances, as the local
    model was measured doing, and lists the brought- and carried-forward lines
    as movements. None of it reaches the result.
    """
    out = ProposedDirection.OUT
    page = _paid_out_paid_in_page(
        _movement("01/03/2026", "3,400.00", description="Balance brought forward", direction=out),
        _movement("02/03/2026", "1,200.00", description="Rent", direction=out, balance="4,643.60"),
        _movement("04/03/2026", "2,450.00", description="Invoice", direction=out, balance="4,643.60"),
        _movement("16/03/2026", "6.40", description="Card payment", direction=out, balance="4,643.60"),
        _movement("31/03/2026", "4,643.60", description="Balance carried forward", direction=out),
    )

    grounded = ground_statement((page,), default_currency="GBP")

    assert [m.signed_amount for m in grounded.movements] == [
        Decimal("-1200.00"),
        Decimal("2450.00"),
        Decimal("-6.40"),
    ]
    assert {m.direction_source for m in grounded.movements} == {"running_balance"}
    assert grounded.reconciliation is ReconciliationOutcome.RECONCILED
    assert sum("prints a balance, not a movement" in warning for warning in grounded.warnings) == 2


def test_a_reader_direction_no_printed_balance_confirms_refuses_the_statement() -> None:
    """An unsigned amount with no balance to prove its direction rests on the reader alone."""
    page = _page(
        "05/03/2026 Supplier invoice 40,00\n06/03/2026 Customer payment 15,00",
        _movement("05/03/2026", "40,00", direction=ProposedDirection.OUT),
        _movement("06/03/2026", "15,00", direction=ProposedDirection.IN),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert {m.direction_source for m in grounded.movements} == {"reader"}
    assert not grounded.importable
    assert any("no printed balance confirms the reader's direction" in refusal for refusal in grounded.refusals)


def test_a_reader_direction_the_opening_and_closing_balances_confirm_is_accepted() -> None:
    """The balances chain from opening to closing only under the reader's directions."""
    page = _page(
        "Saldo anterior 100,00\n05/03/2026 Supplier invoice 40,00\n06/03/2026 Customer payment 15,00\n"
        "Saldo final 75,00",
        _movement("05/03/2026", "40,00", direction=ProposedDirection.OUT),
        _movement("06/03/2026", "15,00", direction=ProposedDirection.IN),
        opening="100,00",
        closing="75,00",
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.importable
    assert grounded.reconciliation is ReconciliationOutcome.RECONCILED
    assert [m.signed_amount for m in grounded.movements] == [Decimal("-40.00"), Decimal("15.00")]
    assert all(m.confirmed for m in grounded.movements)


def test_a_movement_the_reader_missed_on_a_statement_without_balances_refuses_it() -> None:
    """A dated line with an amount that nothing accounts for may be a missed movement."""
    page = _page(
        "Rent 03/02/2026 -800,00\nGroceries 04/02/2026 -42,10\nRefund 05/02/2026 +12,00",
        _movement("03/02/2026", "-800,00"),
        _movement("05/02/2026", "+12,00"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert not grounded.importable
    assert grounded.refusals == ("page 1 line 2 prints a date and an amount that no accepted movement accounts for",)


def test_a_first_movement_missed_beside_running_balances_refuses_the_statement() -> None:
    """Running balances alone cannot see a movement missed before the first of them."""
    page = _page(
        "Deposit 01/02/2026 +1.000,00 1.000,00\nFee 02/02/2026 -42,00 958,00\nCard 03/02/2026 -8,00 950,00",
        _movement("02/02/2026", "-42,00", balance="958,00"),
        _movement("03/02/2026", "-8,00", balance="950,00"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.reconciliation is ReconciliationOutcome.RECONCILED
    assert not grounded.importable
    assert grounded.refusals == ("page 1 line 1 prints a date and an amount that no accepted movement accounts for",)


def test_a_misread_line_without_a_balance_between_two_balances_is_contradicted() -> None:
    """A line printing no balance is checked inside the span of the balances around it."""
    page = _page(
        "Deposit 01/02/2026 +1.000,00 1.000,00\nTransfer 02/02/2026 -40,00 fee -2,00\nCard 03/02/2026 -8,00 950,00",
        _movement("01/02/2026", "+1.000,00", balance="1.000,00"),
        _movement("02/02/2026", "-2,00"),
        _movement("03/02/2026", "-8,00", balance="950,00"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.reconciliation is ReconciliationOutcome.CONTRADICTED
    assert not grounded.importable


def test_a_balance_named_by_its_label_is_read_from_its_line() -> None:
    """A reader copying only a balance's label still names the one amount printed with it."""
    page = _page(
        "Old balance +100,00EUR\nCard 02/02/2026 -8,00EUR\nNew balance +92,00EUR",
        _movement("02/02/2026", "-8,00EUR"),
        opening="Old balance",
        closing="New balance",
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.reconciliation is ReconciliationOutcome.RECONCILED
    assert grounded.importable


def test_a_dated_line_printing_a_balance_or_a_rate_is_not_a_missed_movement() -> None:
    """A ``balance on`` line and an interest rate are accounted for without a movement."""
    page = _page(
        "Rent 03/02/2026 -800,00 1.200,00\nBalance on 28/02/2026 1.200,00\nRate 0,50 % until 31/12/2026",
        _movement("03/02/2026", "-800,00", balance="1.200,00"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.importable


def test_an_unaccounted_line_is_only_reported_when_the_balances_prove_nothing_is_missing() -> None:
    """A chain from the opening to the closing balance leaves no room for a missed movement."""
    page = _page(
        "Opening 100,00\nCard 02/02/2026 -8,00\nStatement total 28/02/2026 8,00\nClosing 92,00",
        _movement("02/02/2026", "-8,00"),
        opening="100,00",
        closing="92,00",
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.importable
    assert any("page 1 line 3 prints a date and an amount" in warning for warning in grounded.warnings)


def test_a_month_name_date_is_read() -> None:
    """``03 Mar 2026`` is a complete date in any of the supported languages."""
    page = _page(
        "03 Mar 2026 Coffee Roasters -12.50 GBP\n14 de marzo de 2026 Reembolso +30.00 GBP",
        _movement("03 Mar 2026", "-12.50"),
        _movement("14 de marzo de 2026", "+30.00"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert [m.booked_date for m in grounded.movements] == [date(2026, 3, 3), date(2026, 3, 14)]
    assert {m.currency for m in grounded.movements} == {"GBP"}


def test_a_code_elsewhere_on_the_line_is_not_the_amount_currency() -> None:
    """A ``BIC`` label on the line names no currency for the movement's amount."""
    page = _page(
        "Transfer 01/02/2026 BIC ABCDESMM -20,00",
        _movement("01/02/2026", "-20,00"),
    )

    grounded = ground_statement((page,), default_currency="EUR")

    assert grounded.movements[0].currency == "EUR"
