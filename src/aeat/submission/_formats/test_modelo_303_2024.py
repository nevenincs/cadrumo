"""Smoke tests for the auto-generated Modelo 303 2024 schema (wave 88+89+90)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._deserialise import deserialise_envelope
from ._serialise import serialise_envelope
from .modelo_303_2024 import ENCODING, ENVELOPE, REQUIRED_HEADER_FIELDS

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo3032024Envelope:
    def test_envelope_total_bytes(self) -> None:
        """DP30300 (328) + 6 page segments (7648) + TRAILER (18) = 7994."""
        total = sum(s.total_length for s in ENVELOPE)
        assert total == 7994

    def test_eight_segments(self) -> None:
        assert len(ENVELOPE) == 8

    def test_encoding_is_iso_8859_1(self) -> None:
        assert ENCODING == "iso-8859-1"

    def test_serialise_empty_filing_well_formed(self) -> None:
        """A zero-casilla filing must still produce a valid 7996-byte envelope
        (7994 content + CRLF)."""
        headers: dict[str, str] = {hdr: "" for hdr in REQUIRED_HEADER_FIELDS}
        # Supply required headers with dummy single-character values.
        # The serialiser will zero/space-pad to field length.
        for hdr in REQUIRED_HEADER_FIELDS:
            headers[hdr] = "A"

        # Additionally provide the ejercicio-of-devengo (shared between header
        # and trailer) — it's outside the REQUIRED_HEADER_FIELDS heuristic set
        # because the first-segment scan runs on DP30300 which has it as
        # ALPHANUMERIC without casilla_id.
        headers["DP30300_F004_EJERCICIO_DE_DEVENGO"] = "2024"

        payload = serialise_envelope(
            casilla_values={},
            headers=headers,
            segments=ENVELOPE,
            encoding=ENCODING,
        )
        assert len(payload) == 7994 + 2
        assert payload.endswith(b"\r\n")
        # Envelope opener at position 1-2.
        assert payload[0:2] == b"<T"
        assert payload[2:5] == b"303"
        # Ejercicio in the header at positions 7-10.
        assert payload[6:10] == b"2024"
        # Cumulative: DP30300(328) + pages(7648) = 7976; TRAILER is next 18.
        # So trailer occupies 0-indexed bytes 7976-7993 (positions 7977-7994).
        assert payload[7976:7982] == b"</T303"

    def test_round_trip_signed_currency(self) -> None:
        """Casilla 86 is a CURRENCY + INLINE_SIGN field in DP30304."""
        headers: dict[str, str] = {hdr: "A" for hdr in REQUIRED_HEADER_FIELDS}
        headers["DP30300_F004_EJERCICIO_DE_DEVENGO"] = "2024"

        payload = serialise_envelope(
            casilla_values={"86": Decimal("2500.50")},
            headers=headers,
            segments=ENVELOPE,
            encoding=ENCODING,
        )
        parsed = deserialise_envelope(payload, segments=ENVELOPE, encoding=ENCODING)
        assert parsed.merged_casilla_values["86"] == Decimal("2500.50")

    def test_round_trip_unsigned_currency(self) -> None:
        """Casilla 01 (base imponible al 4 %) is an unsigned CURRENCY field.

        Wave 90 reclassified every 17-byte casilla-bearing NUMERIC field
        as CURRENCY so ordinary base-imponible values round-trip.
        """
        headers: dict[str, str] = {hdr: "A" for hdr in REQUIRED_HEADER_FIELDS}
        headers["DP30300_F004_EJERCICIO_DE_DEVENGO"] = "2024"

        payload = serialise_envelope(
            casilla_values={"01": Decimal("1234.56")},
            headers=headers,
            segments=ENVELOPE,
            encoding=ENCODING,
        )
        parsed = deserialise_envelope(payload, segments=ENVELOPE, encoding=ENCODING)
        assert parsed.merged_casilla_values["01"] == Decimal("1234.56")
