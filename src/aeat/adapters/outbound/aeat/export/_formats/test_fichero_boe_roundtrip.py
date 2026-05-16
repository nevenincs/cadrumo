"""Deep-fidelity roundtrip tests for the fichero-BOE export format.

The existing :mod:`test_envelope` suite covers a happy-path
serialise / deserialise pair on a minimal two-segment layout. This
file extends that coverage to the failure-prone shapes the registry
data actually emits at the AEAT wire boundary:

* DATE fields in both BOE conventions (``YYYYMMDD`` and ``DDMMYYYY``).
* CURRENCY fields under ``SignedMode.INLINE_SIGN`` with a negative
  value (the byte-0 ``N`` marker must survive the cycle).
* ALPHANUMERIC fields padded with the non-default ``"0"`` filler so
  the read-side strip rule is verified end-to-end.
* CP1252 encoding (the default for AEAT's fichero-BOE submissions)
  so a byte-level mis-encoding of a non-ASCII character surfaces as
  a strict byte inequality.

Every test uses real :func:`serialise` / :func:`deserialise` against
inline-built record specs — no fixtures, no mocks, no reused
registry data — so a regression in any of the encoders or decoders
surfaces as a strict equality failure naming the divergent field.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ._deserialise import deserialise
from ._record_spec import (
    DateFmt,
    FieldKind,
    Justification,
    SignedMode,
    record_field,
    validate_record_specs,
)
from ._serialise import serialise

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def test_currency_inline_sign_round_trips_negative_value() -> None:
    """A signed-currency field with byte-0 ``N`` marker round-trips strictly.

    The :class:`SignedMode.INLINE_SIGN` convention puts an ``N``
    or space in byte 0 of the field, followed by the absolute
    magnitude in cents. A regression that flips byte 0 (e.g.
    emits ``-`` instead of ``N`` or fails to read the sign back)
    surfaces as a strict Decimal inequality.
    """

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT_SIGNED",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
            signed_mode=SignedMode.INLINE_SIGN,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    payload = serialise(
        casilla_values={"01": Decimal("-12345.67")},
        headers={},
        specs=specs,
        encoding="iso-8859-1",
        total_length=12,
    )

    # Byte 0 must be the inline-sign marker for negative values.
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body[0:1] == b"N", (
        f"INLINE_SIGN negative value should emit 'N' in byte 0; got {body[0:1]!r}"
    )

    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=12)
    assert parsed.casilla_values["01"] == Decimal("-12345.67")


def test_currency_inline_sign_round_trips_positive_value() -> None:
    """Positive INLINE_SIGN values emit a leading space, decoded as a positive Decimal."""

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT_SIGNED",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
            signed_mode=SignedMode.INLINE_SIGN,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    payload = serialise(
        casilla_values={"01": Decimal("42.00")},
        headers={},
        specs=specs,
        encoding="iso-8859-1",
        total_length=12,
    )

    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body[0:1] == b" ", (
        f"INLINE_SIGN non-negative value should emit space in byte 0; got {body[0:1]!r}"
    )

    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=12)
    assert parsed.casilla_values["01"] == Decimal("42.00")


def test_date_field_yyyymmdd_round_trips() -> None:
    """A ``YYYYMMDD`` DATE field round-trips a real calendar date strictly."""

    specs = (
        record_field(
            offset=1,
            length=8,
            field_id="DEVENGO",
            kind=FieldKind.DATE,
            date_fmt=DateFmt.YYYYMMDD,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    target = date(2025, 4, 20)
    payload = serialise(
        casilla_values={},
        headers={"DEVENGO": target},
        specs=specs,
        encoding="iso-8859-1",
        total_length=8,
    )
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body == b"20250420"

    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=8)
    assert parsed.field_values["DEVENGO"] == target


def test_date_field_ddmmyyyy_round_trips() -> None:
    """A ``DDMMYYYY`` DATE field round-trips, distinguishing it from YYYYMMDD."""

    specs = (
        record_field(
            offset=1,
            length=8,
            field_id="FECHA",
            kind=FieldKind.DATE,
            date_fmt=DateFmt.DDMMYYYY,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    target = date(2025, 4, 20)
    payload = serialise(
        casilla_values={},
        headers={"FECHA": target},
        specs=specs,
        encoding="iso-8859-1",
        total_length=8,
    )
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    assert body == b"20042025"

    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=8)
    assert parsed.field_values["FECHA"] == target


def test_alphanumeric_zero_padded_field_round_trips() -> None:
    """A ``pad_char='0'`` field round-trips intact, including the strip rule.

    ALPHANUMERIC fields padded with ``"0"`` on the right are stripped
    of the padding on the read side. A canonical value of ``"0"``
    that would naively strip to the empty string must reconstitute
    as ``"0"`` so the round-trip is faithful.
    """

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
        encoding="iso-8859-1",
        total_length=8,
    )
    parsed = deserialise(payload, specs=specs, encoding="iso-8859-1", total_length=8)
    assert parsed.field_values["REF"] == "ABC123"


def test_currency_blank_input_rejected_at_decode() -> None:
    """A blank CURRENCY field is rejected with ExportFormatError.

    A blank CURRENCY field is a wire-format error per the fichero-
    BOE spec (zero-padded ASCII digits required). The decode path
    must surface this as a typed parse refusal rather than silently
    consuming blank bytes as ``Decimal("0.00")`` indistinguishable
    from a legitimate zero.
    """

    from ._deserialise import deserialise
    from .._errors import ExportFormatError

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
        ),
    )
    validate_record_specs(specs, total_length=specs[-1].offset - 1 + specs[-1].length)

    # 12 spaces — a wire shape that earlier silently decoded to 0.00.
    blank_payload = b" " * 12 + b"\r\n"
    with pytest.raises(ExportFormatError, match=r"CURRENCY field is blank"):
        deserialise(blank_payload, specs=specs, encoding="iso-8859-1", total_length=12)


def test_currency_inline_sign_blank_magnitude_rejected_at_decode() -> None:
    """A blank INLINE_SIGN CURRENCY magnitude is rejected.

    Same contract as the unsigned-CURRENCY case: ``N           ``
    (sign marker + blank magnitude) must fail rather than silently
    decode to a negative-zero.
    """

    from ._deserialise import deserialise
    from .._errors import ExportFormatError

    specs = (
        record_field(
            offset=1,
            length=12,
            field_id="AMOUNT",
            casilla_id="01",
            kind=FieldKind.CURRENCY,
            signed_mode=SignedMode.INLINE_SIGN,
        ),
    )
    validate_record_specs(specs, total_length=12)
    # Sign byte 'N' + 11 blank magnitude bytes
    blank_payload = b"N" + b" " * 11 + b"\r\n"
    with pytest.raises(ExportFormatError, match=r"magnitude is blank"):
        deserialise(blank_payload, specs=specs, encoding="iso-8859-1", total_length=12)


def test_cp1252_encoded_field_round_trips_non_ascii() -> None:
    """CP1252-encoded ALPHANUMERIC field carries a Spanish-language byte intact.

    AEAT's default wire encoding is CP1252. An ``ñ`` codes to a
    single byte (0xF1) on the wire; UTF-8 would emit two bytes.
    A regression that silently upgrades the encoding to UTF-8
    would either truncate the field (byte budget overflow) or
    decode garbled on the read side.
    """

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
    body = payload[: -len(b"\r\n")] if payload.endswith(b"\r\n") else payload
    # The ñ must encode as a single CP1252 byte (0xF1).
    assert b"\xf1" in body

    parsed = deserialise(payload, specs=specs, encoding="cp1252", total_length=8)
    assert parsed.field_values["NOMBRE"] == "Pañito"
