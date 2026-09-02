"""A separator dropped as thousands grouping must really be grouping.

Found by importing a plain dot-decimal CSV: read under a comma-decimal dialect,
every ``.`` was stripped as grouping, so ``7.77`` became ``777`` and ``1210.00``
became ``121000``. The import reported success and the hundredfold overstatement
surfaced only much later, when an unrelated reconciliation could not make
base + IVA meet the gross -- and would not have surfaced at all for an operator
who never classified with explicit amounts.

The module already refuses scientific notation on exactly this reasoning: a
silent normalisation that rewrites the magnitude is worse than a refusal. These
extend that stance to grouping.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import pytest

from ......core.decimal.grammar import DecimalSeparator
from ..base import FinancialValidationError, parse_amount_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_a_two_digit_final_group_refuses_instead_of_inflating() -> None:
    """The defect case: neither convention can produce a two-digit group.

    Refusing is the point. Dropping the separator here yields ``121000`` -- a
    well-formed, plausible, hundredfold-wrong number that no downstream check
    can distinguish from a real one.
    """
    with pytest.raises(FinancialValidationError, match="three-digit group"):
        parse_amount_value("1210.00", decimal_separator=DecimalSeparator.COMMA)


def test_a_two_digit_group_refuses_for_the_mirrored_convention_too() -> None:
    """The guard is about group width, not about which separator is which."""
    with pytest.raises(FinancialValidationError, match="three-digit group"):
        parse_amount_value("1210,00", decimal_separator=DecimalSeparator.PERIOD)


@pytest.mark.parametrize(
    ("text", "separator", "expected"),
    [
        ("1.234,56", ",", Decimal("1234.56")),
        ("1.234", ",", Decimal("1234")),
        ("1.234.567,89", ",", Decimal("1234567.89")),
        ("1,234.56", ".", Decimal("1234.56")),
        ("1,234,567.89", ".", Decimal("1234567.89")),
    ],
)
def test_real_thousands_grouping_still_parses(text: str, separator: Literal[",", "."], expected: Decimal) -> None:
    """The guard must not cost a legitimately grouped amount.

    Without these the refusal above could be satisfied by rejecting every
    grouped amount, which would break every European bank export the providers
    exist to read.
    """
    assert parse_amount_value(text, decimal_separator=separator) == expected


def test_an_unambiguous_two_decimal_amount_still_parses_when_inferred() -> None:
    """Inference reads the rightmost separator, so the common shape is unaffected."""
    assert parse_amount_value("1210.00") == Decimal("1210.00")
    assert parse_amount_value("7.77") == Decimal("7.77")
