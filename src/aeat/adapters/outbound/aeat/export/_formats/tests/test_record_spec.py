"""Unit tests for fichero-BOE record-spec primitives.

Covers :class:`RecordFieldSpec` validation, the per-kind encoders
(:func:`encode_currency`, :func:`encode_text`, :func:`encode_date`),
and the cross-spec invariant guard :func:`validate_record_specs`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Required, TypedDict

import pytest
from pydantic import ValidationError

from .......core.external_constants import ISO_8859_1_ENCODING
from .......domain.calculations.registry import CasillaId, validated_casilla_id
from .._record_spec import (
    DateFmt,
    FicheroBoeEncoding,
    FieldKind,
    Justification,
    RecordFieldSpec,
    encode_currency,
    encode_date,
    encode_text,
    record_field,
    validate_record_specs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_SEGMENT_QUALIFIED_BASE_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00552",
    surface="_SEGMENT_QUALIFIED_BASE_CASILLA",
)
_DUPLICATE_FIELD_CASILLA: CasillaId = validated_casilla_id("01", surface="_DUPLICATE_FIELD_CASILLA")

_FIELD_KIND_DEFAULT_CASES = (
    (FieldKind.NUMERIC, Justification.RIGHT, "0"),
    (FieldKind.CURRENCY, Justification.RIGHT, "0"),
)

_CURRENCY_ENCODING_CASES = (
    (Decimal("1234.56"), 13, False, False, b"0000000123456"),
    (Decimal("0.00"), 13, False, False, b"0000000000000"),
    (Decimal("-100.00"), 10, True, False, b"0000010000"),
)

_CURRENCY_ROUNDING_CASES = (
    ("rounds-half-up-positive", Decimal("2.005"), b"000201"),
    ("rounds-half-up-carry", Decimal("1.995"), b"000200"),
    ("rounds-away-from-zero-half-cent", Decimal("1.885"), b"000189"),
)

_CURRENCY_LENGTH_CASES = (
    ("typical-length", Decimal("1234.56"), 13),
    ("short-zero-length", Decimal("0.00"), 5),
)

_INLINE_SIGN_CASES = (
    (Decimal("1234.56"), False, b" 0000000000123456"),
    (Decimal("-1234.56"), False, b"N0000000000123456"),
    (Decimal("0.00"), False, b" 0000000000000000"),
    (Decimal("-5.00"), True, b"N000000500"),
)


class _TextEncodingOptions(TypedDict, total=False):
    """Keyword arguments for :func:`encode_text`, matching its real signature."""

    length: Required[int]
    encoding: Required[FicheroBoeEncoding]
    justification: Justification
    pad_char: str
    truncate: bool


_TEXT_ENCODING_CASES: tuple[tuple[str, _TextEncodingOptions, bytes], ...] = (
    ("ACME", {"length": 10, "encoding": "cp1252"}, b"ACME      "),
    (
        "42",
        {"length": 6, "justification": Justification.RIGHT, "pad_char": "0", "encoding": "cp1252"},
        b"000042",
    ),
    ("LONGVALUE", {"length": 4, "truncate": True, "encoding": "cp1252"}, b"LONG"),
    ("ÑOÑO", {"length": 4, "encoding": "cp1252"}, b"\xd1O\xd1O"),
)

_TEXT_LENGTH_CASES = (
    ("ascii-space-padded", "ACME", 10),
    ("cp1252-accents", "ÑOÑO", 4),
)

_DATE_ENCODING_CASES = (
    (DateFmt.YYYYMMDD, b"20250422"),
    (DateFmt.DDMMYYYY, b"22042025"),
)
_DATE_ENCODING_IDS = ("yyyymmdd", "ddmmyyyy")


class TestRecordFieldSpec:
    """Spec is strict/frozen/extra=forbid and rejects invalid inputs."""

    def test_constructs_with_required_fields(self) -> None:
        spec = record_field(
            offset=1,
            length=9,
            field_id="FIELD_TEXT",
            kind=FieldKind.ALPHANUMERIC,
        )
        assert spec.offset == 1
        assert spec.length == 9
        assert spec.field_id == "FIELD_TEXT"
        assert spec.justification is Justification.LEFT  # ALPHANUMERIC default
        assert spec.pad_char == " "

    def test_kind_defaults(self) -> None:
        for kind, justification, pad_char in _FIELD_KIND_DEFAULT_CASES:
            spec = record_field(offset=1, length=13, field_id=f"FIELD_{kind.name}", kind=kind)
            assert spec.justification is justification, kind.name
            assert spec.pad_char == pad_char, kind.name

    def test_frozen_rejects_mutation(self) -> None:
        spec = record_field(offset=1, length=9, field_id="FIELD_TEXT", kind=FieldKind.ALPHANUMERIC)
        with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
            spec.length = 10

    def test_offset_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match=r"offset|greater than"):
            record_field(
                offset=0,
                length=9,
                field_id="FIELD_TEXT",
                kind=FieldKind.ALPHANUMERIC,
            )

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            RecordFieldSpec.model_validate(
                {
                    "offset": 1,
                    "length": 9,
                    "field_id": "FIELD_TEXT",
                    "kind": FieldKind.ALPHANUMERIC,
                    "justification": Justification.LEFT,
                    "pad_char": " ",
                    "unexpected_kwarg": "boom",
                },
            )

    def test_casilla_id_accepts_segment_qualified_canonical_id(self) -> None:
        spec = record_field(
            offset=1,
            length=13,
            field_id="LIQUIDACION_BASE",
            casilla_id=_SEGMENT_QUALIFIED_BASE_CASILLA,
            kind=FieldKind.CURRENCY,
        )

        assert spec.casilla_id == _SEGMENT_QUALIFIED_BASE_CASILLA


class TestEncodeCurrency:
    """Currency → right-justified zero-padded cents."""

    def test_encoding_cases(self) -> None:
        for value, length, signed, inline_sign, expected in _CURRENCY_ENCODING_CASES:
            assert (
                encode_currency(value, length=length, signed=signed, inline_sign=inline_sign, encoding="cp1252")
                == expected
            ), repr(value)

    def test_negative_without_signed_raises(self) -> None:
        """negative must be explicit via signed=True."""
        with pytest.raises(ValueError, match="without signed=True"):
            encode_currency(Decimal("-100.00"), length=10, encoding="cp1252")

    def test_overflow_raises(self) -> None:
        with pytest.raises(ValueError, match="overflows"):
            encode_currency(Decimal("99999999999.99"), length=5, encoding="cp1252")

    def test_half_up_rounding(self) -> None:
        """AEAT Instrucciones use ROUND_HALF_UP, not HALF_EVEN.

        Decimal("2.005") → cents 201 under HALF_UP; 200 under HALF_EVEN.
        Pinning the correct behaviour catches future rounding drift.
        """
        for case_id, value, expected in _CURRENCY_ROUNDING_CASES:
            assert encode_currency(value, length=6, encoding="cp1252") == expected, case_id

    def test_length_invariant(self) -> None:
        """C F6: output byte-length must equal declared length."""
        for case_id, value, length in _CURRENCY_LENGTH_CASES:
            assert len(encode_currency(value, length=length, encoding="cp1252")) == length, case_id


class TestEncodeCurrencyInlineSign:
    """Inline-sign convention: 'N' prefix for negatives."""

    def test_encoding_cases(self) -> None:
        """Inline-sign output emits one sign byte plus zero-padded magnitude."""
        for value, signed, expected in _INLINE_SIGN_CASES:
            result = encode_currency(
                value,
                length=len(expected),
                inline_sign=True,
                signed=signed,
                encoding="cp1252",
            )
            assert len(result) == len(expected), repr(value)
            assert result == expected, repr(value)

    def test_negative_without_inline_sign_or_signed_raises(self) -> None:
        with pytest.raises(ValueError, match="inline_sign=True"):
            encode_currency(Decimal("-100.00"), length=17, encoding="cp1252")

    def test_inline_sign_requires_length_2(self) -> None:
        with pytest.raises(ValueError, match="inline_sign=True requires length"):
            encode_currency(Decimal("0.00"), length=1, inline_sign=True, encoding="cp1252")

    def test_inline_sign_magnitude_overflow_raises(self) -> None:
        """Inline-sign carve-out means overflow floor is length-1."""
        with pytest.raises(ValueError, match="overflows inline-sign"):
            # 9 999 999 999.99 * 100 = 999 999 999 999 (12 digits).
            # length=5 means magnitude_width=4; can't fit 12 digits.
            encode_currency(Decimal("99999.99"), length=5, inline_sign=True, encoding="cp1252")


class TestEncodeText:
    """Text → ISO-8859-15 ljust/rjust with custom pad."""

    def test_encoding_cases(self) -> None:
        for value, options, expected in _TEXT_ENCODING_CASES:
            assert encode_text(value, **options) == expected, value

    def test_overflow_without_truncate_raises(self) -> None:
        """silent truncation would corrupt official field content."""
        with pytest.raises(ValueError, match="overflows"):
            encode_text("LONGVALUE", length=4, encoding="cp1252")

    def test_euro_symbol_requires_iso_8859_15(self) -> None:
        """Euro symbol: 0x80 in CP1252; 0xA4 in ISO-8859-15; absent from ISO-8859-1."""
        # CP1252 emits 0x80 (its Euro).
        assert encode_text("€", length=1, encoding="cp1252") == b"\x80"
        # ISO-8859-15 emits 0xA4.
        assert encode_text("€", length=1, encoding="iso-8859-15") == b"\xa4"
        # ISO-8859-1 has no Euro.
        with pytest.raises(UnicodeEncodeError, match=r"iso-8859-1|latin"):
            encode_text("€", length=1, encoding=ISO_8859_1_ENCODING)

    def test_non_cp1252_char_raises(self) -> None:
        # Emoji has no CP1252 mapping.
        with pytest.raises(UnicodeEncodeError, match=r"cp1252|charmap"):
            encode_text("TEXT 🎉", length=10, encoding="cp1252")

    def test_length_invariant(self) -> None:
        for case_id, value, length in _TEXT_LENGTH_CASES:
            assert len(encode_text(value, length=length, encoding="cp1252")) == length, case_id


class TestEncodeDate:
    """BOE date shapes."""

    def test_encoding_cases(self) -> None:
        for case_id, (date_fmt, expected) in zip(_DATE_ENCODING_IDS, _DATE_ENCODING_CASES, strict=True):
            assert encode_date(date(2025, 4, 22), date_fmt, encoding="cp1252") == expected, case_id

    def test_length_invariants(self) -> None:
        for case_id, (date_fmt, expected) in zip(_DATE_ENCODING_IDS, _DATE_ENCODING_CASES, strict=True):
            assert len(encode_date(date(2025, 4, 22), date_fmt, encoding="cp1252")) == len(expected), case_id


class TestReservedInvariant:
    """RESERVED ⇔ literal_value model-level invariant."""

    def test_reserved_without_literal_raises(self) -> None:
        with pytest.raises(ValidationError, match="RESERVED fields must carry"):
            record_field(
                offset=1,
                length=3,
                field_id="FORM",
                kind=FieldKind.RESERVED,
            )

    def test_reserved_with_literal_ok(self) -> None:
        spec = record_field(
            offset=1,
            length=3,
            field_id="FORM",
            kind=FieldKind.RESERVED,
            literal_value="ABC",
        )
        assert spec.literal_value == "ABC"

    def test_non_reserved_with_literal_raises(self) -> None:
        with pytest.raises(ValidationError, match="literal_value is only valid"):
            record_field(
                offset=1,
                length=9,
                field_id="FIELD_TEXT",
                kind=FieldKind.ALPHANUMERIC,
                literal_value="SHOULDFAIL",
            )

    def test_date_without_fmt_raises(self) -> None:
        with pytest.raises(ValidationError, match="DATE fields must carry"):
            record_field(
                offset=1,
                length=8,
                field_id="FECHA",
                kind=FieldKind.DATE,
            )

    def test_inline_sign_on_non_currency_raises(self) -> None:
        """signed_mode=INLINE_SIGN only valid on CURRENCY."""
        from .._record_spec import SignedMode

        with pytest.raises(ValidationError, match="INLINE_SIGN is only valid"):
            record_field(
                offset=1,
                length=10,
                field_id="NAME",
                kind=FieldKind.ALPHANUMERIC,
                signed_mode=SignedMode.INLINE_SIGN,
            )


class TestValidateRecordSpecs:
    """monotonic offset/length invariant across a spec tuple."""

    def _three_field_spec(self) -> tuple[RecordFieldSpec, ...]:
        return (
            record_field(offset=1, length=3, field_id="FORM", kind=FieldKind.RESERVED, literal_value="ABC"),
            record_field(offset=4, length=9, field_id="FIELD_TEXT", kind=FieldKind.ALPHANUMERIC),
            record_field(offset=13, length=4, field_id="FIELD_NUMBER", kind=FieldKind.NUMERIC),
        )

    def test_happy_path(self) -> None:
        specs = self._three_field_spec()
        assert len(specs) == 3
        assert sum(s.length for s in specs) == 16
        result = validate_record_specs(specs, total_length=16)
        assert result is None

    def test_empty_specs_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_record_specs((), total_length=0)

    def test_wrong_first_offset_raises(self) -> None:
        bad = (record_field(offset=5, length=3, field_id="FORM", kind=FieldKind.RESERVED, literal_value="ABC"),)
        with pytest.raises(ValueError, match="must start at offset=1"):
            validate_record_specs(bad, total_length=7)

    def test_gap_between_fields_raises(self) -> None:
        bad = (
            record_field(offset=1, length=3, field_id="FORM", kind=FieldKind.RESERVED, literal_value="ABC"),
            record_field(
                offset=5,
                length=9,
                field_id="FIELD_TEXT",  # gap at 4
                kind=FieldKind.ALPHANUMERIC,
            ),
        )
        with pytest.raises(ValueError, match="breaks monotonic contiguity"):
            validate_record_specs(bad, total_length=13)

    def test_overlap_raises(self) -> None:
        bad = (
            record_field(offset=1, length=3, field_id="FORM", kind=FieldKind.RESERVED, literal_value="ABC"),
            record_field(
                offset=3,
                length=9,
                field_id="FIELD_TEXT",  # overlap at 3
                kind=FieldKind.ALPHANUMERIC,
            ),
        )
        with pytest.raises(ValueError, match="breaks monotonic contiguity"):
            validate_record_specs(bad, total_length=11)

    def test_total_length_mismatch_raises(self) -> None:
        specs = self._three_field_spec()
        with pytest.raises(ValueError, match="total_length=99"):
            validate_record_specs(specs, total_length=99)

    def test_duplicate_field_id_raises(self) -> None:
        bad = (
            record_field(offset=1, length=3, field_id="DUP", kind=FieldKind.RESERVED, literal_value="ABC"),
            record_field(offset=4, length=9, field_id="DUP", kind=FieldKind.ALPHANUMERIC),
        )
        with pytest.raises(ValueError, match="duplicate field_id"):
            validate_record_specs(bad, total_length=12)

    def test_duplicate_casilla_id_raises(self) -> None:
        bad = (
            record_field(
                offset=1,
                length=13,
                field_id="A",
                casilla_id=_DUPLICATE_FIELD_CASILLA,
                kind=FieldKind.CURRENCY,
            ),
            record_field(
                offset=14,
                length=13,
                field_id="B",
                casilla_id=_DUPLICATE_FIELD_CASILLA,
                kind=FieldKind.CURRENCY,
            ),
        )
        with pytest.raises(ValueError, match="duplicate casilla_id"):
            validate_record_specs(bad, total_length=26)
