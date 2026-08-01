"""Unit tests for the shared synthetic-PDF generator primitives."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._generator_shared import format_amount

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_format_amount_matches_aeat_style() -> None:
    """Spanish-style thousands (`.`) + comma decimal (`,`) — matches AEAT's receipts."""
    cases = (
        ("zero-int", Decimal("0"), "0,00"),
        ("zero-decimal", Decimal("0.00"), "0,00"),
        ("thousands", Decimal("1234.56"), "1.234,56"),
        ("millions", Decimal("1000000"), "1.000.000,00"),
        ("negative", Decimal("-42.50"), "-42,50"),
        ("cents", Decimal("0.01"), "0,01"),
    )
    for case_id, value, expected in cases:
        assert format_amount(value) == expected, case_id


def test_format_amount_quantises_to_two_decimals() -> None:
    """Two-decimal rendering.

    SUPPORTING. ``100.555`` is the case where half-up and half-even
    happen to agree, so it passes under both rules and cannot tell them
    apart. It is kept as a shape check only; the discriminating ties are
    pinned separately below.
    """
    assert format_amount(Decimal("100.5")) == "100,50"
    assert format_amount(Decimal("100.555")) == "100,56"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.005"), "1,01"),
        (Decimal("-1.005"), "-1,01"),
        (Decimal("0.125"), "0,13"),
        (Decimal("-0.125"), "-0,13"),
        (Decimal("2.345"), "2,35"),
        (Decimal("-2.345"), "-2,35"),
    ],
)
def test_format_amount_rounds_cent_ties_half_up_like_aeat(value: Decimal, expected: str) -> None:
    """Cent ties round away from zero, as AEAT money-2 requires.

    DISCRIMINATING. Every value here sits exactly on a half-cent with an
    EVEN cent digit below it, so ``Decimal.quantize``'s default half-even
    rounds it DOWN while half-up rounds it UP. Restoring the default
    rounding fails all six of these; ``100.555`` would not, which is why
    it is kept separate as a supporting case.

    Negatives are covered because the formatter rounds the magnitude and
    re-applies the sign, so a sign-handling regression would surface as a
    tie resolving toward zero.
    """
    assert format_amount(value) == expected


def test_format_amount_agrees_with_the_canonical_money_rule() -> None:
    """The generator's rounding is the production rule, not a copy of it.

    DISCRIMINATING. Asserted against :func:`round_to_cents` itself rather
    than against literal expected strings, so the fixture corpus cannot
    encode arithmetic the engine forbids even if someone later re-derives
    the expectations. Fails on the first tie under half-even.
    """
    from ......core.money import round_to_cents

    for raw in ("1.005", "-1.005", "0.125", "-0.125", "2.345", "99999.995"):
        value = Decimal(raw)
        assert format_amount(value) == format_amount(round_to_cents(value)), raw


def test_format_amount_nbsp_thousands() -> None:
    """Generator must be able to render NBSP / narrow-NBSP thousands."""
    cases = (
        ("nbsp", Decimal("1234.56"), "\xa0", "1\xa0234,56"),
        ("plain-space", Decimal("1234.56"), " ", "1 234,56"),
        ("multi-group-nbsp", Decimal("1000000"), "\xa0", "1\xa0000\xa0000,00"),
    )
    for case_id, value, sep, expected in cases:
        assert format_amount(value, thousands_sep=sep) == expected, case_id
