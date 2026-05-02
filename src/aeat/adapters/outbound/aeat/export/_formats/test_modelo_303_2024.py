"""Smoke tests for the auto-generated Modelo 303 2024 envelope schema."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._deserialise import deserialise_envelope
from ._serialise import serialise_envelope
from .modelo_303_2024 import ENCODING, ENVELOPE, REQUIRED_HEADER_FIELDS

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


class TestModelo3032024Envelope:
    """Coarse-grained shape checks on the Modelo 303 2024 envelope."""

    def test_envelope_total_bytes(self) -> None:
        """Assert the envelope sums to 7994 bytes (DP30300 328 + 6 page segments 7648 + TRAILER 18)."""
        total = sum(s.total_length for s in ENVELOPE)
        assert total == 7994

    def test_eight_segments(self) -> None:
        """Assert the envelope contains exactly 8 segments."""
        assert len(ENVELOPE) == 8

    def test_required_fields_include_dp30301_page_identification(self) -> None:
        """Assert the DP30301 page-identification fields are required at serialisation.

        Filings without ``TIPO_DECLARACION`` / ``NIF`` /
        ``APELLIDOS+NOMBRE`` / ``DEVENGO_EJERCICIO`` /
        ``DEVENGO_PERIODO`` must be rejected by the serialiser.
        """
        expected = {
            "DP30301_F006_TIPO_DECLARACI_N",
            "DP30301_F007_IDENTIFICACI_N_NIF",
            "DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N",
            "DP30301_F009_DEVENGO_EJERCICIO",
            "DP30301_F010_DEVENGO_PER_ODO",
        }
        assert expected.issubset(REQUIRED_HEADER_FIELDS)

    def test_serialise_empty_filing_well_formed(self) -> None:
        """Assert a zero-casilla filing still produces a valid 7996-byte envelope (7994 content + CRLF)."""
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
        """Assert casilla 86 (CURRENCY + INLINE_SIGN in DP30304) round-trips through serialise/deserialise."""
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
        """Assert casilla 01 (unsigned CURRENCY base imponible al 4 %) round-trips.

        Every 17-byte casilla-bearing NUMERIC field is treated as
        CURRENCY so ordinary base-imponible values round-trip cleanly.
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
