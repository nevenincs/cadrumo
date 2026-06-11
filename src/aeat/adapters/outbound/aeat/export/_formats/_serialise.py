"""Fichero-BOE serialiser for registry-backed fixed-width specs.

The serialiser is format-generic: one :func:`serialise` drives every
registry export layout via a validated tuple of :class:`RecordFieldSpec` entries. A
registry-backed filing layout supplies:

- field layout, validated before use.
- content byte length excluding the CRLF terminator.
- wire encoding declared by the registry layout.
- required header ``field_id`` values the draft MUST
  provide.

The caller passes a :class:`aeat.application.filing.ModeloDraft` plus
a ``headers`` mapping for metadata fields (identity, year, period,
and so on). CRLF terminator ownership stays with this function; the
per-field encoders in
:mod:`aeat.adapters.outbound.aeat.export._formats._record_spec` do
not emit line endings.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from .._errors import AeatExportFormatError
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
        headers: Metadata fields keyed by ``field_id``.
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
            raise :exc:`AeatExportFormatError` before any bytes are emitted.

    Returns:
        The ``total_length + 2`` byte payload (content + CRLF).

    Raises:
        AeatExportFormatError: On missing required headers, on serialised-length
            mismatch, or from the individual encoders on overflow or
            non-encoding-compatible characters.
    """
    _require_headers_present(headers, required_field_ids)
    parts = [_encode_field(spec, casilla_values=casilla_values, headers=headers, encoding=encoding) for spec in specs]
    body = b"".join(parts)
    if len(body) != total_length:
        raise AeatExportFormatError(
            f"serialised body is {len(body)} bytes but total_length={total_length} "
            f"was declared; likely an encoder width mismatch.",
        )
    return body + _CRLF


def _require_headers_present(headers: Mapping[str, HeaderValue], required_field_ids: frozenset[str]) -> None:
    """Fail fast on missing-or-empty required headers before any bytes are emitted."""
    for required in required_field_ids:
        value = headers.get(required)
        if value is None or (isinstance(value, str) and not value):
            raise AeatExportFormatError(
                f"required header {required!r} missing from draft; cannot serialise fichero-BOE payload",
            )


def _encode_field(
    spec: RecordFieldSpec,
    *,
    casilla_values: Mapping[str, Decimal],
    headers: Mapping[str, HeaderValue],
    encoding: FicheroBoeEncoding,
) -> bytes:
    """Dispatch one field spec to its kind-specific encoder."""
    match spec.kind:
        case FieldKind.RESERVED:
            return _encode_reserved_field(spec, encoding=encoding)
        case FieldKind.CURRENCY:
            return _encode_currency_field(spec, casilla_values=casilla_values, headers=headers, encoding=encoding)
        case FieldKind.DATE:
            return _encode_date_field(spec, headers=headers, encoding=encoding)
        case FieldKind.ALPHANUMERIC | FieldKind.NUMERIC:
            return _encode_text_field(spec, headers=headers, encoding=encoding)


def _encode_reserved_field(spec: RecordFieldSpec, *, encoding: FicheroBoeEncoding) -> bytes:
    """RESERVED literal field: encode declared literal verbatim, asserting width."""
    assert spec.literal_value is not None  # invariant from model_validator
    lit = spec.literal_value.encode(encoding)
    if len(lit) != spec.length:
        raise AeatExportFormatError(
            f"RESERVED field {spec.field_id!r} literal width {len(lit)} != declared length {spec.length}",
        )
    return lit


def _encode_currency_field(
    spec: RecordFieldSpec,
    *,
    casilla_values: Mapping[str, Decimal],
    headers: Mapping[str, HeaderValue],
    encoding: FicheroBoeEncoding,
) -> bytes:
    """CURRENCY field: bound casilla_id draws from the draft; otherwise from headers."""
    if spec.casilla_id is not None:
        value = casilla_values.get(spec.casilla_id, _ZERO)
    else:
        header_val = headers.get(spec.field_id, _ZERO)
        if isinstance(header_val, (str, date)):
            raise AeatExportFormatError(
                f"CURRENCY field {spec.field_id!r} requires a Decimal in headers; got {type(header_val).__name__}",
            )
        value = header_val
    return encode_currency(
        value,
        length=spec.length,
        inline_sign=spec.signed_mode is SignedMode.INLINE_SIGN,
        encoding=encoding,
    )


def _encode_date_field(
    spec: RecordFieldSpec,
    *,
    headers: Mapping[str, HeaderValue],
    encoding: FicheroBoeEncoding,
) -> bytes:
    """DATE field: read from headers as a :class:`datetime.date`, encode per ``spec.date_fmt``."""
    assert spec.date_fmt is not None  # invariant from model_validator
    dval = headers.get(spec.field_id)
    if not isinstance(dval, date):
        raise AeatExportFormatError(
            f"DATE field {spec.field_id!r} requires a date in headers; got {type(dval).__name__}",
        )
    return encode_date(dval, spec.date_fmt, encoding=encoding)


def _encode_text_field(
    spec: RecordFieldSpec,
    *,
    headers: Mapping[str, HeaderValue],
    encoding: FicheroBoeEncoding,
) -> bytes:
    """ALPHANUMERIC / NUMERIC field: stringify the header value, encode with justification / padding."""
    tval = headers.get(spec.field_id, "")
    if isinstance(tval, date):
        raise AeatExportFormatError(f"text field {spec.field_id!r} received a date; expected a string")
    return encode_text(
        str(tval),
        length=spec.length,
        justification=spec.justification,
        pad_char=spec.pad_char,
        encoding=encoding,
    )


def serialise_envelope(
    *,
    casilla_values: Mapping[str, Decimal],
    headers: Mapping[str, HeaderValue],
    segments: tuple[SegmentSpec, ...],
    encoding: FicheroBoeEncoding,
    required_field_ids: frozenset[str] = frozenset(),
) -> bytes:
    """Emit a multi-segment fichero-BOE envelope.

    Some AEAT record layouts use an XML-tagged envelope of ordered
    segments rather than a flat record. This helper serialises each
    segment via :func:`serialise` and concatenates the results. The
    CRLF terminator is appended ONCE at the end.

    Args:
        casilla_values: Per-casilla values shared across every segment.
        headers: Metadata header fields shared across every segment.
            Individual segments reference whichever headers they
            declare; unused headers are ignored per-segment.
        segments: Ordered tuple of
            :class:`aeat.adapters.outbound.aeat.export._formats._record_spec.SegmentSpec`
            to emit. Callers supplying the envelope decide which
            optional segments are present.
        encoding: Wire encoding shared across segments.
        required_field_ids: Fail-fast check applied ONCE at envelope
            start; individual segments do not re-check.

    Returns:
        The full envelope byte payload with a single trailing CRLF.

    Raises:
        AeatExportFormatError: Same conditions as :func:`serialise`, plus any
            per-segment width mismatch.
    """
    # Pre-flight required headers once (not per-segment).
    for required in required_field_ids:
        value = headers.get(required)
        if value is None or (isinstance(value, str) and not value):
            raise AeatExportFormatError(
                f"required header {required!r} missing from draft; cannot serialise fichero-BOE envelope",
            )

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
