"""Unit tests for fichero-BOE record-spec primitives (EPIC #201 wave 75d)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ._record_spec import (
    DateFmt,
    FieldKind,
    Justification,
    RecordFieldSpec,
    encode_currency,
    encode_date,
    encode_text,
    record_field,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestRecordFieldSpec:
    """Spec is strict/frozen/extra=forbid and rejects invalid inputs."""

    def test_constructs_with_required_fields(self) -> None:
        spec = record_field(
            offset=1,
            length=9,
            field_id="NIF",
            kind=FieldKind.ALPHANUMERIC,
        )
        assert spec.offset == 1
        assert spec.length == 9
        assert spec.field_id == "NIF"
        assert spec.justification is Justification.LEFT  # ALPHANUMERIC default
        assert spec.pad_char == " "

    def test_numeric_defaults_to_right_zero(self) -> None:
        spec = record_field(offset=1, length=8, field_id="EJERCICIO", kind=FieldKind.NUMERIC)
        assert spec.justification is Justification.RIGHT
        assert spec.pad_char == "0"

    def test_currency_defaults_to_right_zero(self) -> None:
        spec = record_field(offset=1, length=13, field_id="CASILLA_04", kind=FieldKind.CURRENCY)
        assert spec.justification is Justification.RIGHT
        assert spec.pad_char == "0"

    def test_frozen_rejects_mutation(self) -> None:
        spec = record_field(offset=1, length=9, field_id="NIF", kind=FieldKind.ALPHANUMERIC)
        with pytest.raises(ValidationError):
            spec.length = 10  # type: ignore[misc]

    def test_offset_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            record_field(
                offset=0,
                length=9,
                field_id="NIF",
                kind=FieldKind.ALPHANUMERIC,
            )

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            RecordFieldSpec.model_validate(
                {
                    "offset": 1,
                    "length": 9,
                    "field_id": "NIF",
                    "kind": FieldKind.ALPHANUMERIC,
                    "justification": Justification.LEFT,
                    "pad_char": " ",
                    "unexpected_kwarg": "boom",
                }
            )


class TestEncodeCurrency:
    """Currency → right-justified zero-padded cents."""

    def test_typical_value(self) -> None:
        assert encode_currency(Decimal("1234.56"), length=13) == b"0000000123456"

    def test_zero(self) -> None:
        assert encode_currency(Decimal("0.00"), length=13) == b"0000000000000"

    def test_negative_emits_absolute_magnitude(self) -> None:
        """The AEAT convention is a separate SIGNO field; encoder emits |value|."""
        assert encode_currency(Decimal("-100.00"), length=10) == b"0000010000"

    def test_overflow_raises(self) -> None:
        with pytest.raises(ValueError, match="overflows"):
            encode_currency(Decimal("99999999999.99"), length=5)

    def test_quantises_to_two_decimals(self) -> None:
        # Decimal("1.999") → cents 200 (ROUND_HALF_EVEN → 2.00).
        assert encode_currency(Decimal("1.995"), length=6) == b"000200"


class TestEncodeText:
    """Text → ISO-8859-15 ljust/rjust with custom pad."""

    def test_left_justified_space(self) -> None:
        assert encode_text("ACME", length=10) == b"ACME      "

    def test_right_justified_zero(self) -> None:
        assert encode_text("42", length=6, justification=Justification.RIGHT, pad_char="0") == b"000042"

    def test_truncates_over_length(self) -> None:
        assert encode_text("LONGVALUE", length=4) == b"LONG"

    def test_preserves_iso_8859_15_accents(self) -> None:
        """NIF with Ñ + label text with accents must round-trip."""
        # ñ = 0xF1 in ISO-8859-15.
        assert encode_text("ÑOÑO", length=4) == b"\xd1O\xd1O"

    def test_non_iso_8859_15_char_raises(self) -> None:
        # Emoji has no ISO-8859-15 mapping.
        with pytest.raises(UnicodeEncodeError):
            encode_text("Kent 🎉", length=10)


class TestEncodeDate:
    """Per-modelo BOE date shapes."""

    def test_yyyymmdd(self) -> None:
        assert encode_date(date(2025, 4, 22), DateFmt.YYYYMMDD) == b"20250422"

    def test_ddmmyyyy(self) -> None:
        assert encode_date(date(2025, 4, 22), DateFmt.DDMMYYYY) == b"22042025"
