"""Field-level fichero-BOE serialise/deserialise round-trip tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .......core.external_constants import ISO_8859_1_ENCODING
from ..._errors import AeatExportFormatError
from .._deserialise import deserialise
from .._record_spec import DateFmt, FieldKind, Justification, SignedMode, record_field, validate_record_specs
from .._serialise import serialise
from ._fichero_boe_roundtrip_support import _AMOUNT_CASILLA, _currency_specs, _wire_body

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(
    ("amount", "expected_marker"),
    (
        (Decimal("-12345.67"), b"N"),
        (Decimal("42.00"), b" "),
    ),
    ids=("negative-marker", "positive-marker"),
)
def test_currency_inline_sign_round_trips_value(amount: Decimal, expected_marker: bytes) -> None:
    specs = _currency_specs(signed_mode=SignedMode.INLINE_SIGN)

    payload = serialise(
        casilla_values={_AMOUNT_CASILLA: amount},
        headers={},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=12,
    )

    assert _wire_body(payload)[0:1] == expected_marker

    parsed = deserialise(payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)
    assert parsed.casilla_values[_AMOUNT_CASILLA] == amount


@pytest.mark.parametrize(
    ("field_id", "date_fmt", "expected_body"),
    (
        ("DEVENGO", DateFmt.YYYYMMDD, b"20250420"),
        ("FECHA", DateFmt.DDMMYYYY, b"20042025"),
    ),
)
def test_date_field_round_trips(field_id: str, date_fmt: DateFmt, expected_body: bytes) -> None:
    specs = (
        record_field(
            offset=1,
            length=8,
            field_id=field_id,
            kind=FieldKind.DATE,
            date_fmt=date_fmt,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    target = date(2025, 4, 20)
    payload = serialise(
        casilla_values={},
        headers={field_id: target},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=8,
    )
    assert _wire_body(payload) == expected_body

    parsed = deserialise(payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=8)
    assert parsed.field_values[field_id] == target


def test_alphanumeric_zero_padded_field_round_trips() -> None:
    """A ``pad_char='0'`` field round-trips intact, including the strip rule."""
    specs = (
        record_field(
            offset=1,
            length=8,
            field_id="REF",
            kind=FieldKind.ALPHANUMERIC,
            pad_char="0",
            justification=Justification.LEFT,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    payload = serialise(
        casilla_values={},
        headers={"REF": "ABC123"},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=8,
    )
    parsed = deserialise(payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=8)
    assert parsed.field_values["REF"] == "ABC123"


def test_currency_blank_input_rejected_at_decode() -> None:
    """A blank CURRENCY field is rejected with AeatExportFormatError."""
    specs = _currency_specs()

    blank_payload = b" " * 12 + b"\r\n"
    with pytest.raises(AeatExportFormatError, match=r"CURRENCY field is blank"):
        deserialise(blank_payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)


def test_currency_inline_sign_blank_magnitude_rejected_at_decode() -> None:
    """A blank INLINE_SIGN CURRENCY magnitude is rejected."""
    specs = _currency_specs(signed_mode=SignedMode.INLINE_SIGN)

    blank_payload = b"N" + b" " * 11 + b"\r\n"
    with pytest.raises(AeatExportFormatError, match=r"magnitude is blank"):
        deserialise(blank_payload, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)


def test_currency_invalid_wire_bytes_raise_redacted_export_format_error() -> None:
    """Invalid CURRENCY wire bytes must not be echoed in parser errors."""
    specs = _currency_specs()

    canary = b"12345678Z999"
    with pytest.raises(AeatExportFormatError) as exc_info:
        deserialise(canary + b"\r\n", specs=specs, encoding=ISO_8859_1_ENCODING, total_length=12)

    message = str(exc_info.value)
    assert "CURRENCY field 'AMOUNT' has invalid wire bytes" in message
    assert "length=12" in message
    assert "digest=sha256:" in message
    assert "12345678Z" not in message
    assert canary.decode("ascii") not in message
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_cp1252_encoded_field_round_trips_non_ascii() -> None:
    """CP1252-encoded ALPHANUMERIC field carries a Spanish-language byte intact."""
    specs = (
        record_field(
            offset=1,
            length=8,
            field_id="NOMBRE",
            kind=FieldKind.ALPHANUMERIC,
            pad_char=" ",
            justification=Justification.LEFT,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    payload = serialise(
        casilla_values={},
        headers={"NOMBRE": "Pañito"},
        specs=specs,
        encoding="cp1252",
        total_length=8,
    )
    assert b"\xf1" in _wire_body(payload)

    parsed = deserialise(payload, specs=specs, encoding="cp1252", total_length=8)
    assert parsed.field_values["NOMBRE"] == "Pañito"


def test_reserved_field_corruption_rejected_at_decode() -> None:
    """A corrupted RESERVED literal field is rejected."""
    specs = (
        record_field(
            offset=1,
            length=4,
            field_id="ENVELOPE_TAG",
            kind=FieldKind.RESERVED,
            literal_value="AEAT",
        ),
    )
    validate_record_specs(specs, total_length=4)

    payload = serialise(
        casilla_values={},
        headers={},
        specs=specs,
        encoding=ISO_8859_1_ENCODING,
        total_length=4,
    )
    assert b"AEAT" in payload, payload

    corrupted = payload.replace(b"AEAT", b"XXXX")
    assert corrupted != payload

    with pytest.raises(AeatExportFormatError, match="RESERVED"):
        deserialise(corrupted, specs=specs, encoding=ISO_8859_1_ENCODING, total_length=4)


def test_reserved_field_corruption_error_redacts_wire_bytes() -> None:
    """RESERVED mismatch errors must describe corrupted bytes by digest only."""
    specs = (
        record_field(
            offset=1,
            length=9,
            field_id="ENVELOPE_TAG",
            kind=FieldKind.RESERVED,
            literal_value="SAFE-TAG!",
        ),
    )
    validate_record_specs(specs, total_length=9)

    canary = b"12345678Z"
    with pytest.raises(AeatExportFormatError) as exc_info:
        deserialise(canary + b"\r\n", specs=specs, encoding=ISO_8859_1_ENCODING, total_length=9)

    message = str(exc_info.value)
    assert "RESERVED field 'ENVELOPE_TAG'" in message
    assert "length=9" in message
    assert "digest=sha256:" in message
    assert "12345678Z" not in message
    assert canary.decode("ascii") not in message
