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

from .. import try_parse_canonical_decimal

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


@pytest.mark.parametrize("raw", ["2.345", "0.075", "1.00000"])
def test_uncapped_fraction_accepts_sub_cent_precision(raw: str) -> None:
    """Sub-cent precision conforms when no cap is set.

    The AEAT fixed-width encoder rounds a sub-cent value to cents with
    ``ROUND_HALF_UP``, so a calculation input channel must admit it.
    """
    assert try_parse_canonical_decimal(raw) == Decimal(raw)


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
