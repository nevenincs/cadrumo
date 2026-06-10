"""Lock the currency-encoding edge-case matrix.

The CURRENCY encoders in
:mod:`aeat.adapters.outbound.aeat.export._formats._record_spec` must handle
registry-calculated values across common fixed-width currency field widths,
and under both the UNSIGNED and INLINE_SIGN conventions. This matrix
exercises:

* Zero (``Decimal("0.00")``).
* Smallest positive: 0.01 (1 cent).
* Typical: 1234.56.
* Large value within the 13-byte limit.
* Signed negative: -100.00 (INLINE_SIGN only).
* Signed zero: -0.00 canonicalises to +0.00.

A value that would overflow the field width must raise at encode time, not
truncate silently.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .......core.external_constants import ISO_8859_1_ENCODING
from .._record_spec import encode_currency

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class TestUnsignedCurrency13Byte:
    """13-byte zero-padded cents, unsigned."""

    @pytest.mark.parametrize(
        ("value", "expected_text"),
        [
            (Decimal("0.00"), "0000000000000"),
            (Decimal("0.01"), "0000000000001"),
            (Decimal("1.00"), "0000000000100"),
            (Decimal("1234.56"), "0000000123456"),
            (Decimal("99999999999.99"), "9999999999999"),
        ],
        ids=["zero", "one_cent", "one_euro", "typical", "max"],
    )
    def test_round_trip_text(self, value: Decimal, expected_text: str) -> None:
        encoded = encode_currency(value, length=13, encoding="cp1252")
        assert encoded == expected_text.encode("cp1252")

    def test_overflow_raises(self) -> None:
        """Any value that would require > 13 digits of cents must raise."""
        with pytest.raises((ValueError, OverflowError), match=r"currency|length|overflow|exceed"):
            encode_currency(Decimal("100000000000.00"), length=13, encoding="cp1252")


class TestUnsignedCurrency17Byte:
    """17-byte zero-padded cents, unsigned."""

    @pytest.mark.parametrize(
        ("value", "expected_text"),
        [
            (Decimal("0.00"), "00000000000000000"),
            (Decimal("0.01"), "00000000000000001"),
            (Decimal("1234.56"), "00000000000123456"),
            (Decimal("20000.00"), "00000000002000000"),
            (Decimal("999999999999999.99"), "99999999999999999"),
        ],
        ids=["zero", "one_cent", "typical", "large", "max"],
    )
    def test_round_trip_text(self, value: Decimal, expected_text: str) -> None:
        encoded = encode_currency(value, length=17, encoding=ISO_8859_1_ENCODING)
        assert encoded == expected_text.encode(ISO_8859_1_ENCODING)


class TestInlineSignedCurrency17Byte:
    """INLINE_SIGN: 1-byte sign plus 16-digit magnitude."""

    @pytest.mark.parametrize(
        ("value", "expected_text"),
        [
            (Decimal("0.00"), " 0000000000000000"),
            (Decimal("0.01"), " 0000000000000001"),
            (Decimal("2500.50"), " 0000000000250050"),
            (Decimal("-0.01"), "N0000000000000001"),
            (Decimal("-2500.50"), "N0000000000250050"),
            (Decimal("-3150.00"), "N0000000000315000"),
        ],
        ids=["zero", "one_cent", "positive_typical", "neg_cent", "neg_typical", "neg_large"],
    )
    def test_round_trip_text(self, value: Decimal, expected_text: str) -> None:
        encoded = encode_currency(value, length=17, signed=True, inline_sign=True, encoding=ISO_8859_1_ENCODING)
        assert encoded == expected_text.encode(ISO_8859_1_ENCODING)

    def test_signed_negative_zero_canonicalises_to_positive(self) -> None:
        """Decimal('-0.00') should encode as if it were +0.00 — the sign byte
        must be space, not 'N'."""
        encoded = encode_currency(
            Decimal("-0.00"),
            length=17,
            signed=True,
            inline_sign=True,
            encoding=ISO_8859_1_ENCODING,
        )
        assert encoded == b" 0000000000000000"

    def test_unsigned_negative_raises(self) -> None:
        """encode_currency without signed=True must refuse negative values
        (documented behaviour — the caller must opt into signing)."""
        with pytest.raises(ValueError, match="signed=True"):
            encode_currency(Decimal("-1.00"), length=13, encoding="cp1252")


class TestRoundingBehaviour:
    """Decimal values with sub-cent precision round ROUND_HALF_UP per the
    mandate (matches AEAT's rounding convention)."""

    @pytest.mark.parametrize(
        ("value", "expected_cents_int"),
        [
            (Decimal("0.005"), 1),  # half-up to 1 cent
            (Decimal("0.004"), 0),  # rounds down
            (Decimal("1.005"), 101),  # half-up to 101 cents
            (Decimal("1.004"), 100),  # rounds down
            (Decimal("2.345"), 235),  # half-up to 235 cents
        ],
        ids=["half_cent_up", "just_under_cent", "one_euro_half_up", "one_euro_half_down", "two_thirty_four_half_up"],
    )
    def test_rounding_half_up(self, value: Decimal, expected_cents_int: int) -> None:
        encoded = encode_currency(value, length=13, encoding="cp1252")
        # Decode as integer cents — the decimal is implicit, so parse-as-int is safe.
        cents = int(encoded.decode("ascii"))
        assert cents == expected_cents_int
