"""Fichero-BOE serialiser for registry-backed fixed-width specs.

The serialiser is format-generic: one :func:`serialise` drives every
modelo via a validated tuple of :class:`RecordFieldSpec` entries. A
registry-backed filing layout supplies:

- field layout, validated before use.
- content byte length excluding the CRLF terminator.
- per-modelo wire encoding.
- required header ``field_id`` values the draft MUST
  provide.

The caller passes a :class:`aeat.application.filing.FilingDraft` plus
a ``headers`` mapping for metadata fields (NIF, ejercicio, período,
and so on). CRLF terminator ownership stays with this function; the
per-field encoders in
:mod:`aeat.adapters.outbound.aeat.export._formats._record_spec` do
not emit line endings.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from ._record_spec import (
    FicheroBoeEncoding,
    FieldKind,
    RecordFieldSpec,
    SegmentSpec,
    SignedMode,
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
        casilla_values: Per-casilla numeric values. Missing casillas
            default to :class:`decimal.Decimal` zero — AEAT expects
            every CURRENCY field filled, zero-padded when not declared.
        headers: Metadata fields (NIF, ejercicio, período, apellidos,
            nombre, tipo_declaracion, ...) keyed by ``field_id``.
            Dates must be :class:`datetime.date` instances; other
            scalar text and numeric fields are strings.
        specs: Ordered tuple of
            :class:`aeat.adapters.outbound.aeat.export._formats._record_spec.RecordFieldSpec`
            entries.
        encoding: Wire encoding for the payload (typically
            ``"cp1252"``).
        total_length: Expected content-byte count, excluding CRLF.
        required_field_ids: ``field_id`` values the caller guarantees
            must be present in ``headers``; missing required fields
            raise :exc:`ValueError` before any bytes are emitted.

    Returns:
        The ``total_length + 2`` byte payload (content + CRLF).

    Raises:
        ValueError: On missing required headers, on serialised-length
            mismatch, or from the individual encoders on overflow or
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
                # calculated draft; headerless casilla_id == None draws
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
                # route inline-sign per-field via spec metadata.
                inline_sign = spec.signed_mode is SignedMode.INLINE_SIGN
                parts.append(
                    encode_currency(
                        value,
                        length=spec.length,
                        inline_sign=inline_sign,
                        encoding=encoding,
                    )
                )

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


def serialise_envelope(
    *,
    casilla_values: Mapping[str, Decimal],
    headers: Mapping[str, HeaderValue],
    segments: tuple[SegmentSpec, ...],
    encoding: FicheroBoeEncoding,
    required_field_ids: frozenset[str] = frozenset(),
) -> bytes:
    """Emit a multi-segment fichero-BOE envelope.

    Modelo 303 (and later IVA modelos) use an XML-tagged envelope of
    ordered segments rather than a flat record. This helper serialises
    each segment via :func:`serialise` and concatenates the results.
    The CRLF terminator is appended ONCE at the end — AEAT expects a
    single terminator per file, not per segment.

    Args:
        casilla_values: Per-casilla values shared across every segment.
        headers: Metadata header fields shared across every segment.
            Individual segments reference whichever headers they
            declare; unused headers are ignored per-segment.
        segments: Ordered tuple of
            :class:`aeat.adapters.outbound.aeat.export._formats._record_spec.SegmentSpec`
            to emit. Callers supplying the envelope decide which
            optional segments are present (Modelo 303 page 4, for
            example, appears only in exonerado-390 annual filings).
        encoding: Wire encoding shared across segments.
        required_field_ids: Fail-fast check applied ONCE at envelope
            start; individual segments do not re-check.

    Returns:
        The full envelope byte payload with a single trailing CRLF.

    Raises:
        ValueError: Same conditions as :func:`serialise`, plus any
            per-segment width mismatch.
    """
    # Pre-flight required headers once (not per-segment).
    for required in required_field_ids:
        value = headers.get(required)
        if value is None or (isinstance(value, str) and not value):
            raise ValueError(f"required header {required!r} missing from draft; cannot serialise fichero-BOE envelope")

    chunks: list[bytes] = []
    for segment in segments:
        # serialise() appends its own CRLF; strip it before concat
        # and re-append exactly one terminator at the end.
        part = serialise(
            casilla_values=casilla_values,
            headers=headers,
            specs=segment.specs,
            encoding=encoding,
            total_length=segment.total_length,
            required_field_ids=frozenset(),  # pre-checked above
        )
        if part.endswith(_CRLF):
            part = part[: -len(_CRLF)]
        chunks.append(part)
    return b"".join(chunks) + _CRLF


__all__ = ["serialise", "serialise_envelope"]
