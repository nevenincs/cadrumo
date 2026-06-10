"""Tests for multi-segment envelope serialise / deserialise.

These tests exercise a reduced two-segment record layout so the generic
envelope serialiser and deserialiser are validated without coupling the
tests to any real registry offsets.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._deserialise import deserialise_envelope
from .._record_spec import (
    FieldKind,
    SegmentSpec,
    record_field,
    validate_segment_specs,
)
from .._serialise import serialise_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _build_envelope_mini() -> tuple[SegmentSpec, ...]:
    """Build a two-segment envelope with neutral literals."""
    seg_header = SegmentSpec(
        segment_id="SEG0_MINI",
        specs=(
            record_field(
                offset=1,
                length=8,
                field_id="OPEN_ENV",
                kind=FieldKind.RESERVED,
                literal_value="<ENV000>",
            ),
            record_field(
                offset=9,
                length=4,
                field_id="FIELD_YEAR",
                kind=FieldKind.NUMERIC,
            ),
            record_field(
                offset=13,
                length=5,
                field_id="CLOSE_ENV",
                kind=FieldKind.RESERVED,
                literal_value="</E0>",
            ),
        ),
        total_length=17,
    )

    seg_page = SegmentSpec(
        segment_id="SEG1_MINI",
        specs=(
            record_field(
                offset=1,
                length=11,
                field_id="OPEN_PAGE",
                kind=FieldKind.RESERVED,
                literal_value="<PAGE00001>",
            ),
            record_field(
                offset=12,
                length=9,
                field_id="FIELD_IDENTITY",
                kind=FieldKind.ALPHANUMERIC,
            ),
            record_field(
                offset=21,
                length=11,
                field_id="FIELD_AMOUNT",
                casilla_id="01",
                kind=FieldKind.CURRENCY,
            ),
            record_field(
                offset=32,
                length=12,
                field_id="CLOSE_PAGE",
                kind=FieldKind.RESERVED,
                literal_value="</PAGE00001>",
            ),
        ),
        total_length=43,
    )
    return (seg_header, seg_page)


class TestEnvelopeValidation:
    """Invariant checks performed by :func:`validate_segment_specs`."""

    def test_empty_envelope_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_segment_specs(())

    def test_duplicate_segment_id_rejected(self) -> None:
        seg_a = SegmentSpec(
            segment_id="DUP",
            specs=(record_field(offset=1, length=3, field_id="A", kind=FieldKind.RESERVED, literal_value="ABC"),),
            total_length=3,
        )
        seg_b = SegmentSpec(
            segment_id="DUP",
            specs=(record_field(offset=1, length=3, field_id="B", kind=FieldKind.RESERVED, literal_value="XYZ"),),
            total_length=3,
        )
        with pytest.raises(ValueError, match="duplicate segment_id"):
            validate_segment_specs((seg_a, seg_b))

    def test_segment_internal_invariant_bubbles_up(self) -> None:
        """A segment whose field-offset is wrong fails validation with
        the segment_id in the error message."""
        try:
            bad = SegmentSpec(
                segment_id="BADSEG",
                specs=(
                    record_field(
                        offset=5,
                        length=3,
                        field_id="A",  # offset != 1
                        kind=FieldKind.RESERVED,
                        literal_value="ABC",
                    ),
                ),
                total_length=7,
            )
            validate_segment_specs((bad,))
        except ValueError as exc:
            assert "BADSEG" in str(exc)
            assert "must start at offset=1" in str(exc)
        else:
            pytest.fail("expected ValueError")


class TestEnvelopeSerialise:
    """Round-trip and pre-flight behaviour of the envelope serialiser pair."""

    def test_round_trip_preserves_casilla_value(self) -> None:
        segments = _build_envelope_mini()
        validate_segment_specs(segments)

        payload = serialise_envelope(
            casilla_values={"01": Decimal("12345.67")},
            headers={
                "FIELD_YEAR": "2024",
                "FIELD_IDENTITY": "X1234567L",
            },
            segments=segments,
            encoding="iso-8859-1",
        )

        # 17 (seg 1) + 43 (seg 2) + 2 (CRLF) = 62.
        assert len(payload) == 62
        assert payload.endswith(b"\r\n")

        # Envelope opener at positions 1-8.
        assert payload[0:8] == b"<ENV000>"
        # Year field at 9-12.
        assert payload[8:12] == b"2024"
        # Page opener right after the first segment.
        assert payload[17:28] == b"<PAGE00001>"
        # Identity field in page 2.
        assert payload[28:37] == b"X1234567L"
        # Casilla 01 = 12345.67 → 1234567 cents zero-padded to 11 digits.
        assert payload[37:48] == b"00001234567"
        # Page closer.
        assert payload[48:60] == b"</PAGE00001>"

    def test_round_trip_preserves_casilla_via_deserialise(self) -> None:
        segments = _build_envelope_mini()
        payload = serialise_envelope(
            casilla_values={"01": Decimal("500.00")},
            headers={
                "FIELD_YEAR": "2024",
                "FIELD_IDENTITY": "X1234567L",
            },
            segments=segments,
            encoding="iso-8859-1",
        )
        parsed = deserialise_envelope(
            payload,
            segments=segments,
            encoding="iso-8859-1",
        )
        assert "SEG0_MINI" in parsed.segments
        assert "SEG1_MINI" in parsed.segments
        assert parsed.merged_casilla_values["01"] == Decimal("500.00")
        assert parsed.segments["SEG1_MINI"].field_values["FIELD_IDENTITY"] == "X1234567L"
        assert parsed.segments["SEG0_MINI"].field_values["FIELD_YEAR"] == "2024"

    def test_missing_required_header_raises(self) -> None:
        segments = _build_envelope_mini()
        with pytest.raises(ValueError, match="FIELD_IDENTITY"):
            serialise_envelope(
                casilla_values={"01": Decimal("0.00")},
                headers={"FIELD_YEAR": "2024"},
                segments=segments,
                encoding="iso-8859-1",
                required_field_ids=frozenset({"FIELD_IDENTITY"}),
            )

    def test_envelope_length_mismatch_raises(self) -> None:
        """deserialise_envelope validates total payload length against
        the sum of segment lengths."""
        segments = _build_envelope_mini()
        with pytest.raises(ValueError, match="envelope payload is"):
            deserialise_envelope(
                b"SHORT",
                segments=segments,
                encoding="iso-8859-1",
            )
