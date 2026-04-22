"""Fichero-BOE serialiser reading `_RECORD_SPECS` (EPIC #201 C3b, wave 79b).

Per the :doc:`fichero-BOE export ADR` the serialiser is format-generic:
one function drives every modelo via its `_RECORD_SPECS` tuple. A
concrete modelo module supplies:

- ``_RECORD_SPECS``: the field layout (validated at import time).
- ``RECORD_LENGTH``: content bytes (excluding CRLF terminator).
- ``ENCODING``: per-modelo wire encoding.
- ``REQUIRED_HEADER_FIELDS``: field_ids the draft MUST provide.

The caller passes a :class:`FilingDraft` plus a ``headers`` mapping
for metadata fields (NIF, ejercicio, período, etc.). CRLF terminator
ownership stays with this function; encoders do not emit line endings.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from ._record_spec import (
    FicheroBoeEncoding,
    FieldKind,
    RecordFieldSpec,
    encode_currency,
    encode_date,
    encode_text,
)

_ZERO = Decimal("0")
_CRLF = b"\r\n"


HeaderValue = str | date
"""Header values: strings for text/numeric fields; dates for DATE fields."""


def serialise(
    *,
    casilla_values: Mapping[str, Decimal],
    headers: Mapping[str, HeaderValue],
    specs: tuple[RecordFieldSpec, ...],
    encoding: FicheroBoeEncoding,
    total_length: int,
    required_field_ids: frozenset[str] = frozenset(),
) -> bytes:
    """Emit a fichero-BOE payload for one filing draft.

    Args:
        casilla_values: per-casilla numeric values. Missing casillas
            default to :class:`Decimal` zero — AEAT expects every
            CURRENCY field filled, zero-padded when not declared.
        headers: metadata fields (NIF, ejercicio, período, apellidos,
            nombre, tipo_declaracion, etc.) keyed by ``field_id``.
            Dates must be :class:`datetime.date` instances; other
            scalar text / numeric fields are strings.
        specs: the ordered tuple of :class:`RecordFieldSpec` entries.
        encoding: wire encoding for the payload (typically ``"cp1252"``).
        total_length: expected content-byte count (excluding CRLF).
        required_field_ids: ``field_id`` values the caller guarantees
            must be present in ``headers``; missing required fields
            raise :class:`ValueError` before any bytes are emitted.

    Returns:
        The ``total_length + 2`` byte payload (content + CRLF).

    Raises:
        ValueError: on missing required headers, on serialised-length
            mismatch, or from the individual encoders on overflow /
            non-encoding-compatible characters.
    """
    # Fail-fast on missing required headers before emitting any bytes.
    for required in required_field_ids:
        value = headers.get(required)
        if value is None or (isinstance(value, str) and not value):
            raise ValueError(f"required header {required!r} missing from draft; cannot serialise fichero-BOE payload")

    parts: list[bytes] = []
    for spec in specs:
        match spec.kind:
            case FieldKind.RESERVED:
                assert spec.literal_value is not None  # invariant from model_validator
                lit = spec.literal_value.encode(encoding)
                if len(lit) != spec.length:
                    raise ValueError(
                        f"RESERVED field {spec.field_id!r} literal width {len(lit)} != declared length {spec.length}"
                    )
                parts.append(lit)

            case FieldKind.CURRENCY:
                # CURRENCY fields with a casilla_id draw from the
                # ruleset draft; headerless casilla_id == None draws
                # from the headers mapping (e.g., IMPORTE_INGRESO).
                if spec.casilla_id is not None:
                    value = casilla_values.get(spec.casilla_id, _ZERO)
                else:
                    header_val = headers.get(spec.field_id, _ZERO)
                    if isinstance(header_val, (str, date)):
                        raise ValueError(
                            f"CURRENCY field {spec.field_id!r} requires a "
                            f"Decimal in headers; got {type(header_val).__name__}"
                        )
                    value = header_val
                parts.append(encode_currency(value, length=spec.length, encoding=encoding))

            case FieldKind.DATE:
                assert spec.date_fmt is not None  # invariant from model_validator
                dval = headers.get(spec.field_id)
                if not isinstance(dval, date):
                    raise ValueError(
                        f"DATE field {spec.field_id!r} requires a date in headers; got {type(dval).__name__}"
                    )
                parts.append(encode_date(dval, spec.date_fmt, encoding=encoding))

            case FieldKind.ALPHANUMERIC | FieldKind.NUMERIC:
                tval = headers.get(spec.field_id, "")
                if isinstance(tval, date):
                    raise ValueError(f"text field {spec.field_id!r} received a date; expected a string")
                parts.append(
                    encode_text(
                        str(tval),
                        length=spec.length,
                        justification=spec.justification,
                        pad_char=spec.pad_char,
                        encoding=encoding,
                    )
                )

    body = b"".join(parts)
    if len(body) != total_length:
        raise ValueError(
            f"serialised body is {len(body)} bytes but total_length={total_length} "
            f"was declared; likely an encoder width mismatch."
        )
    return body + _CRLF


__all__ = ["HeaderValue", "serialise"]
