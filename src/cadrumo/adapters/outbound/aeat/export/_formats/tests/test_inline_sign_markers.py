"""Only the two markers the wire format defines may decode an inline sign.

The fichero-BOE INLINE_SIGN convention has exactly two sign bytes: ASCII
``N`` for a negative amount and ASCII space for a non-negative one. The
deserialiser read the sign as ``sign_byte == b"N"``, which is a test for the
NEGATIVE marker rather than a check of membership in the allowed set, so every
other byte — ``X``, ``0``, a NUL, an accented byte from a mis-decoded stream —
decoded the absolute magnitude as a POSITIVE amount.

That is the worst shape a parse failure can take on this wire: the result is a
plausible number, so nothing downstream has a reason to question it, and a
corrupted or foreign record silently changes meaning instead of being refused.
The round-trip below is what makes the assertions non-tautological — the
expected decodings are what the project's own encoder produces for those
amounts, not figures restated by hand.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._errors import AeatExportFormatError
from .._deserialise import _decode_currency
from .._record_spec import encode_currency

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_LENGTH = 12
_ENCODING = "cp1252"


def _encoded(value: Decimal) -> bytes:
    return encode_currency(value, length=_LENGTH, inline_sign=True, encoding=_ENCODING)


def _with_marker(marker: bytes, value: Decimal) -> bytes:
    """Return a real encoded field with only its sign byte replaced."""
    encoded = _encoded(value)
    return marker + encoded[1:]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(Decimal("-1.23"), Decimal("-1.23"), id="negative"),
        pytest.param(Decimal("1.23"), Decimal("1.23"), id="positive"),
        pytest.param(Decimal("0.00"), Decimal("0.00"), id="zero"),
    ],
)
def test_the_two_defined_markers_round_trip(value: Decimal, expected: Decimal) -> None:
    """Encoder output decodes back to the amount it encoded.

    The positive control: a membership check that refused everything would
    satisfy every refusal below and nothing here.
    """
    assert _decode_currency(_encoded(value), inline_sign=True) == expected


@pytest.mark.parametrize(
    "marker",
    [
        pytest.param(b"X", id="foreign-letter"),
        pytest.param(b"0", id="digit"),
        pytest.param(b"\x00", id="nul"),
        pytest.param(b"-", id="ascii-minus"),
        pytest.param(b"n", id="lowercase-n"),
        pytest.param(b"\xf1", id="high-byte"),
        pytest.param(b"+", id="ascii-plus"),
    ],
)
def test_a_foreign_marker_is_refused_rather_than_read_as_positive(marker: bytes) -> None:
    """Every byte outside the defined pair refuses instead of decoding.

    ``n`` is called out on its own: the format's marker is uppercase, and a
    case-insensitive reading would be a guess about a wire contract rather
    than a reading of it.
    """
    with pytest.raises(AeatExportFormatError):
        _decode_currency(_with_marker(marker, Decimal("-1.23")), inline_sign=True)


def test_a_foreign_marker_carrying_a_valid_magnitude_is_still_refused() -> None:
    """The defect's exact shape: the magnitude parses, only the sign does not.

    Pre-fix this returned ``Decimal("1.23")`` — a well-formed answer to a
    record that never said it was positive.
    """
    corrupted = _with_marker(b"X", Decimal("1.23"))

    # The magnitude half is intact, so a refusal cannot be blamed on it.
    assert corrupted[1:] == _encoded(Decimal("1.23"))[1:]
    with pytest.raises(AeatExportFormatError):
        _decode_currency(corrupted, inline_sign=True)


def test_the_refusal_does_not_echo_the_wire_bytes() -> None:
    """A malformed record is reported by digest, not by quoting its contents.

    The bytes on this wire are a taxpayer's filing figures; a parse error is
    the wrong place to reproduce them.
    """
    corrupted = _with_marker(b"X", Decimal("1234.56"))

    with pytest.raises(AeatExportFormatError) as raised:
        _decode_currency(corrupted, inline_sign=True)

    message = str(raised.value)
    assert "123456" not in message
    assert "sha256:" in message


def test_an_unsigned_field_is_unaffected_by_the_marker_check() -> None:
    """UNSIGNED fields have no sign byte, so their first byte is a digit."""
    encoded = encode_currency(Decimal("1.23"), length=_LENGTH, encoding=_ENCODING)

    assert _decode_currency(encoded, inline_sign=False) == Decimal("1.23")
