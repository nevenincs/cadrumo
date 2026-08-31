"""Real-behavior tests for :func:`cadrumo.core.decimal.try_parse_canonical_decimal`.

Expected accept/refuse outcomes are derived from the canonical grammar the
governing input-localisation decision specifies — a dot decimal separator, no
thousands grouping, no comma decimal, no scientific notation, no leading ``+``,
no embedded whitespace, no ``NaN``/``Infinity`` — not from the implementation.
Each refused form below is one a bare :class:`~decimal.Decimal` call accepts, so
the test would fail if the guard were removed.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pytest

from .._grammar import european_thousands_reading_is_ambiguous, try_parse_canonical_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Forms the bare ``Decimal`` constructor ACCEPTS but the canonical grammar must
# refuse. Each is a silent-misinterpretation hazard, not merely invalid text:
# ``1e3``/``1E3``/``1e-3`` are scientific notation, ``+100`` carries a leading
# sign the grammar excludes, ``1_000`` hides digit separators, ``1.``/``.5`` omit
# a required digit run, and ``NaN``/``Infinity`` are non-finite.
_DECIMAL_ACCEPTS_BUT_GRAMMAR_REFUSES = (
    "1e3",
    "1E3",
    "1e-3",
    "+100",
    "+1.50",
    "NaN",
    "-NaN",
    "sNaN",
    "Infinity",
    "-Infinity",
    "inf",
    "1_000",
    "1.",
    ".5",
)

# Forms the constructor also rejects; the grammar must refuse them as ``None``
# rather than letting an exception escape to the caller.
_ALSO_REFUSED = ("1.234,56", "1,00", "not-decimal", "", "   ", "1 000", "--5", "1.2.3", "5%", "€5")


def test_refuses_forms_the_bare_constructor_would_accept() -> None:
    for raw in _DECIMAL_ACCEPTS_BUT_GRAMMAR_REFUSES:
        # Anchor the case as a genuine tightening rather than a restatement of
        # the constructor: the bare call this replaced really does accept it.
        assert isinstance(Decimal(raw), Decimal), raw
        assert try_parse_canonical_decimal(raw) is None, raw


def test_refuses_malformed_text_without_raising() -> None:
    for raw in _ALSO_REFUSED:
        with pytest.raises(InvalidOperation):
            Decimal(raw)
        assert try_parse_canonical_decimal(raw) is None, raw


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", Decimal("0")),
        ("1000", Decimal("1000")),
        ("1234.56", Decimal("1234.56")),
        ("-1000", Decimal("-1000")),
        ("-1234.56", Decimal("-1234.56")),
        ("0.5", Decimal("0.5")),
        ("21.00", Decimal("21.00")),
        # Surrounding whitespace is stripped; the number itself is canonical.
        ("  1234.56  ", Decimal("1234.56")),
    ],
)
def test_accepts_canonical_forms(raw: str, expected: Decimal) -> None:
    assert try_parse_canonical_decimal(raw) == expected


@pytest.mark.parametrize("raw", ["0.075", "1.00000", "1234.567"])
def test_uncapped_fraction_accepts_sub_cent_precision(raw: str) -> None:
    """Sub-cent precision conforms when no cap is set.

    The AEAT fixed-width encoder rounds a sub-cent value to cents with
    ``ROUND_HALF_UP``, so a calculation input channel must admit it.

    ``2.345`` used to be one of these cases and is now refused, because it is
    exactly the Spanish thousands shape -- two thousand three hundred and
    forty-five -- and the parser no longer picks a reading. The cases here are
    chosen to keep the sub-cent guarantee while carrying their own evidence: a
    leading zero and a four-digit lead group cannot open a thousands run, and
    five fraction digits are not a grouping.
    """
    assert try_parse_canonical_decimal(raw) == Decimal(raw)


@pytest.mark.parametrize("raw", ["2.345", "8.000", "12.500", "100.000"])
def test_sub_cent_precision_is_refused_when_the_token_is_ambiguous(raw: str) -> None:
    """The narrow window where sub-cent precision is unavailable, named.

    One to three integer digits with no leading zero and exactly three
    fraction digits is indistinguishable from a Spanish thousands group, so it
    refuses rather than resolving. This is a real cost of the ruling and it is
    pinned here so it reads as a decision rather than a gap: a caller needing
    2.345 supplies it as a Decimal, not as operator-typed text.
    """
    assert try_parse_canonical_decimal(raw) is None


@pytest.mark.parametrize("raw", ["1.000", "2.345", "0.075", "1.00000"])
def test_two_digit_cap_refuses_more_than_euro_cent_precision(raw: str) -> None:
    """With ``max_fraction_digits=2`` the Spanish thousands shape refuses.

    ``1.000`` is the shape that previously became ``Decimal("1.0")`` silently —
    a one-euro figure where the operator meant one thousand.
    """
    assert try_parse_canonical_decimal(raw, max_fraction_digits=2) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1000", Decimal("1000")), ("1234.56", Decimal("1234.56")), ("1234.5", Decimal("1234.5"))],
)
def test_two_digit_cap_accepts_euro_amounts(raw: str, expected: Decimal) -> None:
    assert try_parse_canonical_decimal(raw, max_fraction_digits=2) == expected


def test_unsigned_variant_refuses_negative() -> None:
    assert try_parse_canonical_decimal("-1000", signed=False) is None
    assert try_parse_canonical_decimal("1000", signed=False) == Decimal("1000")


def test_signed_variant_accepts_negative() -> None:
    assert try_parse_canonical_decimal("-1000", signed=True) == Decimal("-1000")


@pytest.mark.parametrize(
    "token",
    (
        pytest.param("1.234", id="one-thousand-two-hundred-and-thirty-four"),
        pytest.param("10.500", id="ten-thousand-five-hundred"),
        pytest.param("100.000", id="one-hundred-thousand"),
        pytest.param("1.000", id="one-thousand"),
        pytest.param("-1.234", id="signed"),
        pytest.param("  1.234  ", id="surrounded-by-whitespace"),
    ),
)
def test_a_lone_dot_before_three_digits_is_two_way_readable(token: str) -> None:
    """Spanish thousands and an English decimal are written identically here.

    Nothing in the token itself decides between them, so a parser that picks
    one is guessing at a thousandfold error.
    """
    assert european_thousands_reading_is_ambiguous(token) is True


@pytest.mark.parametrize(
    ("token", "why"),
    (
        pytest.param("1.234,56", "a comma settles it: Spanish marks decimals with it", id="grouped-with-comma"),
        pytest.param("1234,56", "same, without grouping", id="bare-comma"),
        pytest.param("1234.56", "two trailing digits cannot be a thousands group", id="two-decimals"),
        pytest.param("0.5", "one trailing digit cannot be either", id="one-decimal"),
        pytest.param("1.2345", "four cannot be: a grouped number would read 12.345", id="four-decimals"),
        pytest.param("0.333", "a thousands run never opens with a zero group", id="coefficient"),
        pytest.param("1000.000", "a lead of four digits would itself have been grouped", id="long-lead"),
        pytest.param("1.234.567", "two dots cannot be a decimal at all", id="fully-grouped"),
        pytest.param("1234", "no separator, nothing to read two ways", id="plain-integer"),
    ),
)
def test_a_token_carrying_its_own_evidence_is_not_ambiguous(token: str, why: str) -> None:
    """Only the genuinely two-way tokens refuse; everything else keeps working.

    The coefficient and long-lead cases are the ones that make this usable on
    values whose kind is not yet known — refusing ``0.333`` to catch ``1.234``
    would trade one wrong answer for another.
    """
    assert european_thousands_reading_is_ambiguous(token) is False, why
