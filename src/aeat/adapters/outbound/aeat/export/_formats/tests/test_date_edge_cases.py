"""Lock DATE field encoding round-trip invariants.

AEAT DR specs use two date conventions:

* ``YYYYMMDD`` (8 bytes, ``%Y%m%d``) — ISO-leaning, used by most post-2020
  Órdenes.
* ``DDMMYYYY`` (8 bytes, ``%d%m%Y``) — Spanish-conventional, historical
  Órdenes.

The suite locks three properties:

* Both formats encode and decode any valid ``datetime.date`` losslessly.
* Calendar-boundary values (Jan 1, Dec 31, Feb 29 on leap years) round-trip
  without drift.
* Invalid bytes (non-numeric, wrong length) raise at decode time rather than
  producing a garbage date object.

Targets :func:`aeat.adapters.outbound.aeat.export._formats._record_spec.encode_date`
and :func:`aeat.adapters.outbound.aeat.export._formats._deserialise._decode_date`.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..._errors import AeatExportFormatError
from .._deserialise import _decode_date
from .._record_spec import DateFmt, encode_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_SAMPLE_DATES: list[date] = [
    date(2024, 1, 1),  # year boundary (start)
    date(2024, 12, 31),  # year boundary (end)
    date(2024, 2, 29),  # leap day
    date(2025, 2, 28),  # non-leap Feb end
    date(2024, 3, 15),  # mid-year typical
    date(1999, 12, 31),  # pre-2000
    date(2099, 12, 31),  # future
]


class TestYYYYMMDDRoundTrip:
    @pytest.mark.parametrize("value", _SAMPLE_DATES, ids=lambda v: v.isoformat())
    def test_round_trip(self, value: date) -> None:
        encoded = encode_date(value, DateFmt.YYYYMMDD, encoding="cp1252")
        assert len(encoded) == 8
        assert encoded == value.strftime("%Y%m%d").encode("ascii")
        assert _decode_date(encoded, DateFmt.YYYYMMDD) == value


class TestDDMMYYYYRoundTrip:
    @pytest.mark.parametrize("value", _SAMPLE_DATES, ids=lambda v: v.isoformat())
    def test_round_trip(self, value: date) -> None:
        encoded = encode_date(value, DateFmt.DDMMYYYY, encoding="cp1252")
        assert len(encoded) == 8
        assert encoded == value.strftime("%d%m%Y").encode("ascii")
        assert _decode_date(encoded, DateFmt.DDMMYYYY) == value


class TestDateDecodeRejection:
    @pytest.mark.parametrize(
        "bad",
        [b"ABCDEFGH", b"20241301", b"20241232", b"20240230", b"notadate", b"2024    "],
        ids=["alpha", "bad_month", "bad_day_dec", "bad_day_feb_leap_off", "non_numeric", "space_padded"],
    )
    def test_yyyymmdd_rejects_garbage(self, bad: bytes) -> None:
        with pytest.raises(AeatExportFormatError, match=r"DATE field"):
            _decode_date(bad, DateFmt.YYYYMMDD)

    def test_yyyymmdd_error_redacts_payload_and_has_no_chained_context(self) -> None:
        bad = b"12345678Z"
        with pytest.raises(AeatExportFormatError) as exc_info:
            _decode_date(bad, DateFmt.YYYYMMDD)

        message = str(exc_info.value)
        assert "DATE field" in message
        assert "digest=sha256:" in message
        assert "12345678Z" not in message
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None

    @pytest.mark.parametrize(
        "bad",
        [b"ABCDEFGH", b"32122024", b"00122024", b"31022024"],
        ids=["alpha", "day_32", "day_00", "feb_31"],
    )
    def test_ddmmyyyy_rejects_garbage(self, bad: bytes) -> None:
        with pytest.raises(AeatExportFormatError, match=r"DATE field"):
            _decode_date(bad, DateFmt.DDMMYYYY)


class TestDateFormatsAreNotInterchangeable:
    def test_yyyymmdd_decoded_as_ddmmyyyy_is_wrong_or_raises(self) -> None:
        """A YYYYMMDD-encoded date fed to DDMMYYYY must either raise or
        produce a clearly wrong date. The fail mode is defensive: callers
        must pass the correct format."""
        encoded = encode_date(date(2024, 3, 15), DateFmt.YYYYMMDD, encoding="cp1252")  # b"20240315"
        # Decoded as DDMMYYYY: day=20, month=24 → ValueError (out of range or unconverted).
        with pytest.raises(AeatExportFormatError, match=r"DATE field"):
            _decode_date(encoded, DateFmt.DDMMYYYY)
