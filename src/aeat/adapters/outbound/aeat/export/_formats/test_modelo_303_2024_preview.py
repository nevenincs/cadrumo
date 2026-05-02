"""Proof-of-concept tests for the Modelo 303 envelope preview module.

The preview module is intentionally NOT wired into the CLI schema
registry; it exists to exercise the envelope + ``inline_sign``
architecture against the only three Modelo 303 offsets that could
be verified with high confidence:

* DP30300 envelope opener/closer + ejercicio + período.
* DP30301 ``NIF_DECLARANTE`` at offset 14.
* DP30303 casilla 69 at offset 323 (signed inline, type N).

A complete Modelo 303 schema requires xlsx-ingestion tooling and is
covered separately by the auto-generated full schema tests.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._deserialise import deserialise_envelope
from ._serialise import serialise_envelope
from .modelo_303_2024_preview import (
    ENCODING,
    ENVELOPE_PREVIEW,
    REQUIRED_HEADER_FIELDS,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def _headers() -> dict[str, str]:
    """Return the minimal header dict for the preview envelope."""
    return {
        "EJERCICIO": "2024",
        "PERIODO": "1T",
        "NIF_DECLARANTE": "X1234567L",
        "TIPO_DECLARACION": "I",
        # Prefix fillers (DP30303 pre-casilla padding) — 322 bytes of spaces.
        "DP30303_PREFIX_FILLER": " " * 322,
    }


class TestModelo3032024Preview:
    """Smoke coverage for the preview envelope's segment + offset arithmetic."""

    def test_envelope_length(self) -> None:
        """Assert the preview envelope sums to 375 bytes (DP30300 12 + DP30301 22 + DP30303 339 + CRLF 2)."""
        payload = serialise_envelope(
            casilla_values={"69": Decimal("1234.56")},
            headers=_headers(),
            segments=ENVELOPE_PREVIEW,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        assert len(payload) == 375
        assert payload.endswith(b"\r\n")

    def test_envelope_opener_bytes(self) -> None:
        """Assert the DP30300 12-byte envelope opener bytes."""
        payload = serialise_envelope(
            casilla_values={"69": Decimal("0.00")},
            headers=_headers(),
            segments=ENVELOPE_PREVIEW,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        # DP30300 envelope header: "<T" + "303" + "0" + "2024" + "1T" = 12 bytes.
        assert payload[0:2] == b"<T"
        assert payload[2:5] == b"303"
        assert payload[5:6] == b"0"
        assert payload[6:10] == b"2024"
        assert payload[10:12] == b"1T"

    def test_dp30301_nif_at_verified_offset_14(self) -> None:
        """Assert ``NIF_DECLARANTE`` lands at DP30301 segment-local offset 14."""
        payload = serialise_envelope(
            casilla_values={"69": Decimal("0.00")},
            headers=_headers(),
            segments=ENVELOPE_PREVIEW,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        # DP30300 ends at byte 11 (0-indexed); DP30301 starts at 12.
        # Segment-local offset 14 (1-based) → global byte 12 + 13 = 25.
        assert payload[25:34] == b"X1234567L"

    def test_casilla_69_inline_sign_positive(self) -> None:
        """Assert a positive casilla 69 encodes as leading space + zero-padded magnitude."""
        payload = serialise_envelope(
            casilla_values={"69": Decimal("1000.00")},
            headers=_headers(),
            segments=ENVELOPE_PREVIEW,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        # DP30300 (12) + DP30301 (22) = 34; DP30303 starts at byte 34.
        # Casilla 69 at segment-local offset 323 → global byte 34 + 322 = 356.
        # 17 bytes wide: 1 sign byte + 16 magnitude.
        assert payload[356:373] == b" 0000000000100000"

    def test_casilla_69_inline_sign_negative(self) -> None:
        """Assert a negative casilla 69 encodes as leading ``'N'`` + zero-padded magnitude.

        :attr:`aeat.adapters.outbound.aeat.export._formats._record_spec.RecordFieldSpec.signed_mode`
        equal to ``INLINE_SIGN`` routes negative casilla values through
        ``encode_currency(inline_sign=True)`` automatically; callers
        do not need to flip a sign flag themselves.
        """
        payload = serialise_envelope(
            casilla_values={"69": Decimal("-750.00")},
            headers=_headers(),
            segments=ENVELOPE_PREVIEW,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        # Casilla 69 at global byte 356: 1 'N' byte + 16 magnitude bytes.
        # -750.00 -> 75 000 cents -> 0000000000075000 (16 digits).
        assert payload[356:373] == b"N0000000000075000"

    def test_round_trip_preserves_casilla_69(self) -> None:
        """Assert serialise/deserialise round-trips casilla 69 and its preview headers."""
        payload = serialise_envelope(
            casilla_values={"69": Decimal("500.00")},
            headers=_headers(),
            segments=ENVELOPE_PREVIEW,
            encoding=ENCODING,
            required_field_ids=REQUIRED_HEADER_FIELDS,
        )
        parsed = deserialise_envelope(payload, segments=ENVELOPE_PREVIEW, encoding=ENCODING)
        assert parsed.merged_casilla_values["69"] == Decimal("500.00")
        assert parsed.segments["DP30300_PREVIEW"].field_values["EJERCICIO"] == "2024"
        assert parsed.segments["DP30301_PREVIEW"].field_values["NIF_DECLARANTE"] == "X1234567L"
