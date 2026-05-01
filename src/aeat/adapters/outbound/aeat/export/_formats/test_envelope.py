"""Tests for multi-segment envelope serialise/deserialise.

The envelope pattern is what EPIC #201 needs for Modelo 303+ which
uses XML-tagged pages rather than a single flat record. These tests
use synthetic segment specs modelled on the Modelo 303 envelope shape
(DP30300 header + DP30301 page 1) but with drastically reduced field
counts to exercise the architecture without tying the tests to
Modelo 303's BOE offsets.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._deserialise import deserialise_envelope
from ._record_spec import (
    FieldKind,
    SegmentSpec,
    record_field,
    validate_segment_specs,
)
from ._serialise import serialise_envelope

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _build_envelope_mini() -> tuple[SegmentSpec, ...]:
    """Two-segment envelope mimicking Modelo 303 DP30300 + DP30301 shape.

    Segment 1 (DP30300-MINI, 17 bytes): envelope opener "<T30300>" +
    4-byte ejercicio + 5-byte close tag.
    Segment 2 (DP30301-MINI, 43 bytes): page opener "<T30301000>" +
    9-byte NIF + 17-byte casilla 01 + page closer "</T30301000>".
    """
    seg_header = SegmentSpec(
        segment_id="DP30300_MINI",
        specs=(
            record_field(
                offset=1,
                length=8,
                field_id="OPEN_ENV",
                kind=FieldKind.RESERVED,
                literal_value="<T30300>",
            ),
            record_field(
                offset=9,
                length=4,
                field_id="EJERCICIO",
                kind=FieldKind.NUMERIC,
            ),
            record_field(
                offset=13,
                length=5,
                field_id="CLOSE_ENV",
                kind=FieldKind.RESERVED,
                literal_value="</T3>",
            ),
        ),
        total_length=17,
    )

    seg_page = SegmentSpec(
        segment_id="DP30301_MINI",
        specs=(
            record_field(
                offset=1,
                length=11,
                field_id="OPEN_PAGE",
                kind=FieldKind.RESERVED,
                literal_value="<T30301000>",
            ),
            record_field(
                offset=12,
                length=9,
                field_id="NIF_DECLARANTE",
                kind=FieldKind.ALPHANUMERIC,
            ),
            record_field(
                offset=21,
                length=11,
                field_id="CASILLA_01_BASE",
                casilla_id="01",
                kind=FieldKind.CURRENCY,
            ),
            record_field(
                offset=32,
                length=12,
                field_id="CLOSE_PAGE",
                kind=FieldKind.RESERVED,
                literal_value="</T30301000>",
            ),
        ),
        total_length=43,
    )
    return (seg_header, seg_page)


class TestEnvelopeValidation:
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
    def test_round_trip_preserves_casilla_value(self) -> None:
        segments = _build_envelope_mini()
        validate_segment_specs(segments)

        payload = serialise_envelope(
            casilla_values={"01": Decimal("12345.67")},
            headers={
                "EJERCICIO": "2024",
                "NIF_DECLARANTE": "X1234567L",
            },
            segments=segments,
            encoding="iso-8859-1",
        )

        # 17 (seg 1) + 43 (seg 2) + 2 (CRLF) = 62.
        assert len(payload) == 62
        assert payload.endswith(b"\r\n")

        # Envelope opener at positions 1-8.
        assert payload[0:8] == b"<T30300>"
        # EJERCICIO at 9-12.
        assert payload[8:12] == b"2024"
        # Page 2 opener right after envelope close tag "</T3E>".
        assert payload[17:28] == b"<T30301000>"
        # NIF in page 2.
        assert payload[28:37] == b"X1234567L"
        # Casilla 01 = 12345.67 → 1234567 cents zero-padded to 11 digits.
        assert payload[37:48] == b"00001234567"
        # Page closer.
        assert payload[48:60] == b"</T30301000>"

    def test_round_trip_preserves_casilla_via_deserialise(self) -> None:
        segments = _build_envelope_mini()
        payload = serialise_envelope(
            casilla_values={"01": Decimal("500.00")},
            headers={
                "EJERCICIO": "2024",
                "NIF_DECLARANTE": "X1234567L",
            },
            segments=segments,
            encoding="iso-8859-1",
        )
        parsed = deserialise_envelope(
            payload,
            segments=segments,
            encoding="iso-8859-1",
        )
        assert "DP30300_MINI" in parsed.segments
        assert "DP30301_MINI" in parsed.segments
        assert parsed.merged_casilla_values["01"] == Decimal("500.00")
        assert parsed.segments["DP30301_MINI"].field_values["NIF_DECLARANTE"] == "X1234567L"
        assert parsed.segments["DP30300_MINI"].field_values["EJERCICIO"] == "2024"

    def test_missing_required_header_raises(self) -> None:
        segments = _build_envelope_mini()
        with pytest.raises(ValueError, match="NIF_DECLARANTE"):
            serialise_envelope(
                casilla_values={"01": Decimal("0.00")},
                headers={"EJERCICIO": "2024"},  # NIF missing
                segments=segments,
                encoding="iso-8859-1",
                required_field_ids=frozenset({"NIF_DECLARANTE"}),
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
