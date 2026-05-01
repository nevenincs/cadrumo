"""Golden-fixture byte-exactness tests for Modelo 303 2024.

Pins the full 7996-byte multi-segment envelope for a known-good
autónomo Kent filing scenario. Any schema/encoder/serialiser change
that shifts a single byte fails this test immediately.

The SHA256 digest is the audit-trail anchor. A future wave that
genuinely needs to change the byte layout (e.g., DR303 update for
ejercicio 2025+ or a classifier correction) MUST update this file
AND document the reason in the commit message. Stray byte shifts
must never pass silently.
"""

from __future__ import annotations

import hashlib

import pytest

from ._serialise import serialise_envelope
from ._test_fixtures import KENT_303_CASILLAS_HAND, kent_303_headers
from .modelo_303_2024 import ENCODING, ENVELOPE, REQUIRED_HEADER_FIELDS

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo3032024GoldenKentQ1:
    """Kent's Q1 2024 Modelo 303: régimen general, cuota IVA 21 %."""

    @staticmethod
    def _serialise_kent_q1() -> bytes:
        return serialise_envelope(
            casilla_values=KENT_303_CASILLAS_HAND,
            headers=kent_303_headers("2024"),
            segments=ENVELOPE,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )

    def test_total_length_is_7996(self) -> None:
        """ENVELOPE content (7994) + CRLF (2) = 7996 on the wire."""
        payload = self._serialise_kent_q1()
        assert len(payload) == 7996

    def test_sha256_digest_is_stable(self) -> None:
        """Golden digest — DO NOT change without documented intent.

        A byte-layout change that alters this digest is a decision,
        not an accident. The commit message must name which offset /
        encoder / field changed and why.
        """
        payload = self._serialise_kent_q1()
        expected = "32ca797eee318d0565c0970ea26e1d0651f5b63355feecb8ea7654f4366500fd"
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, (
            f"byte-layout drift detected!\n"
            f"  expected SHA256: {expected}\n"
            f"  actual   SHA256: {actual}\n"
            f"If the change is intentional (wave-Nx offset correction),\n"
            f"update the `expected` literal above AND document the\n"
            f"reason in the commit message."
        )

    def test_payload_ends_with_crlf(self) -> None:
        payload = self._serialise_kent_q1()
        assert payload.endswith(b"\r\n")

    def test_envelope_opener_and_trailer(self) -> None:
        """Envelope is bracketed by ``<T303...>`` and ``</T303...>``."""
        payload = self._serialise_kent_q1()
        # Opener: `<T` + `303` + `0` + `2024` + `01` + `0000>`.
        assert payload[0:2] == b"<T"
        assert payload[2:5] == b"303"
        assert payload[6:10] == b"2024"
        # Trailer lives at cumulative offset 7976 (DP30300 328 + pages 7648).
        assert payload[7976:7982] == b"</T303"

    def test_dp30301_page_identification(self) -> None:
        """Per-page identification fields land at the DR303-documented offsets."""
        payload = self._serialise_kent_q1()
        dp30301_start = 328
        # DR303 1-based offsets within DP30301: F006 TIPO=13, F007 NIF=14,
        # F010 PERIODO=107.
        assert payload[dp30301_start + 12 : dp30301_start + 13] == b"I"
        assert payload[dp30301_start + 13 : dp30301_start + 22] == b"X1234567L"
        assert payload[dp30301_start + 106 : dp30301_start + 108] == b"1T"

    def test_casilla_01_base_imponible_bytes(self) -> None:
        """Casilla 01 (base imponible al 4 %) is an UNSIGNED 17-byte CURRENCY
        field in DP30301 — 20 000.00 encodes as 2 000 000 cents zero-padded."""
        payload = self._serialise_kent_q1()
        # DP30301 starts at 328; locate casilla 01 by its sentinel bytes.
        expected = b"00000000002000000"
        assert expected in payload[328:1909], (
            "casilla 01 (20 000.00 → 2 000 000 cents) not found in DP30301; CURRENCY reclassification or offset drift?"
        )
