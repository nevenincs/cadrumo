"""Fichero-BOE deserialiser for explicit fixed-width specs.

Round-trip inverse of
:func:`aeat.adapters.outbound.aeat.export._formats._serialise.serialise`.
Takes a fichero-BOE byte payload plus a :class:`RecordFieldSpec` tuple and
yields a :class:`ParsedRecord` carrying the per-field values (as
strings, :class:`datetime.date` for date fields, or
:class:`decimal.Decimal` for currency) plus metadata.

Use this module when the caller already has adapter-local
:class:`RecordFieldSpec` or :class:`SegmentSpec` declarations and needs a
byte-level round-trip check. The application export-verification flow
parses registry layouts through
:func:`aeat.domain.calculations.registry.parse_export_payload` so it can
compare a file against the canonical
:class:`aeat.domain.calculations.registry.ExportLayoutDefinition`.

See Also:
    :func:`aeat.adapters.outbound.aeat.export._formats._serialise.serialise`
        Explicit-spec serialiser that produces the bytes parsed here.
    :class:`aeat.domain.calculations.registry.ParsedExportPayload`
        Registry-level parsed payload used by the application verifier.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from ......core import STRICT_FROZEN_CONFIG
from ......core.hashing import sha256_hex as _sha256_hex
from ......core.money import round_to_cents as _round_to_cents
from ......domain.calculations.registry import CasillaId
from .._errors import AeatExportFormatError
from ._record_spec import (
    DateFmt,
    FicheroBoeEncoding,
    FieldKind,
    RecordFieldSpec,
    SegmentSpec,
    SignedMode,
)


class ParsedRecord(BaseModel):
    """Typed result of parsing a fichero-BOE record.

    Strict / frozen / ``extra="forbid"`` per the boundary-record mandate.
    Each field value is keyed by ``field_id``; currency fields also appear
    in :attr:`casilla_values` keyed by ``casilla_id`` for easy
    cross-reference against
    :class:`aeat.application.filing.ModeloDraft`.

    Attributes:
        field_values: Every ``field_id`` mapped to its parsed value
            (strings, :class:`datetime.date`, or :class:`decimal.Decimal`).
        casilla_values: Casilla-keyed currency values; a subset of
            :attr:`field_values` filtered to fields with a non-``None``
            ``casilla_id``.
        raw_length: Byte length of the parsed content, excluding the
            optional CRLF terminator.

    See Also:
        :class:`RecordFieldSpec`
            Field declarations that drive the parser.
        :class:`aeat.domain.calculations.registry.ParsedExportPayload`
            Registry-level parser result for application export
            verification.
    """

    model_config = STRICT_FROZEN_CONFIG

    field_values: Mapping[str, str | Decimal | date]
    """Every field_id mapped to its parsed value."""

    casilla_values: Mapping[CasillaId, Decimal]
    """Casilla-keyed currency values (subset of field_values)."""

    raw_length: Annotated[int, Field(ge=0)]
    """Byte length of the parsed content (excluding CRLF)."""


_CRLF = b"\r\n"


def _wire_digest(raw: bytes) -> str:
    """Return a short digest for malformed wire bytes without exposing them."""
    return f"sha256:{_sha256_hex(raw)[:8]}"


def _decode_currency(raw: bytes, *, inline_sign: bool = False) -> Decimal:
    """Decode a zero-padded cents string into a 2-decimal :class:`Decimal`.

    Inverse of
    :func:`aeat.adapters.outbound.aeat.export._formats._record_spec.encode_currency`.
    With ``inline_sign=True``, byte 0 is the sign marker (``"N"`` for
    negatives, ``" "`` for non-negatives) and the remaining bytes carry
    the zero-padded absolute magnitude.

    The fichero-BOE spec requires every CURRENCY field to be zero-
    padded with ASCII digits; blank bytes are a wire-format error.
    Reject blank input explicitly so a malformed payload surfaces as
    ``AeatExportFormatError`` at parse time, instead of silently decoding
    to ``Decimal("0.00")`` and leaving the operator unable to
    distinguish "filed as zero" from "field was blank on the wire".
    """
    if inline_sign:
        if not raw:
            raise AeatExportFormatError("INLINE_SIGN CURRENCY field cannot be empty")
        sign_byte = raw[:1]
        magnitude_bytes = raw[1:]
        is_negative = sign_byte == b"N"
        text = magnitude_bytes.decode("ascii").strip()
        if not text:
            raise AeatExportFormatError(
                "INLINE_SIGN CURRENCY magnitude is blank; expected zero-padded digits "
                "(use 0000000000 for an explicit zero, not whitespace)",
            )
        cents = int(text)
        result = _round_to_cents(Decimal(cents) / Decimal(100))
        return -result if is_negative else result

    text = raw.decode("ascii").strip()
    if not text:
        raise AeatExportFormatError(
            "CURRENCY field is blank; expected zero-padded digits "
            "(use 0000000000 for an explicit zero, not whitespace)",
        )
    cents = int(text)
    return _round_to_cents(Decimal(cents) / Decimal(100))


def _decode_date(raw: bytes, fmt: DateFmt) -> date:
    """Decode a fixed-width ASCII date payload per ``fmt``."""
    text: str = ""
    decode_failure: str | None = None
    try:
        text = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        decode_failure = type(exc).__name__
    if decode_failure is not None:
        raise AeatExportFormatError(
            f"DATE field contains non-ASCII wire bytes; length={len(raw)} "
            f"digest={_wire_digest(raw)} failure={decode_failure}",
        )
    parse_failure: str | None = None
    try:
        match fmt:
            case DateFmt.YYYYMMDD:
                return datetime.strptime(text, "%Y%m%d").date()
            case DateFmt.DDMMYYYY:
                return datetime.strptime(text, "%d%m%Y").date()
            case _:
                raise AeatExportFormatError(f"unsupported DATE format {fmt!s}")
    except ValueError as exc:
        parse_failure = type(exc).__name__
    raise AeatExportFormatError(
        f"DATE field does not match {fmt.value}; length={len(raw)} digest={_wire_digest(raw)} failure={parse_failure}",
    )


def deserialise(
    payload: bytes,
    *,
    specs: tuple[RecordFieldSpec, ...],
    encoding: FicheroBoeEncoding,
    total_length: int,
) -> ParsedRecord:
    """Parse a fichero-BOE byte payload into a :class:`ParsedRecord`.

    Args:
        payload: Full on-wire byte sequence (content + optional CRLF).
        specs: The ordered :class:`RecordFieldSpec` tuple describing the
            fixed-width layout.
        encoding: Wire encoding matching the serialiser's choice.
        total_length: Expected content-byte count (excludes CRLF).

    Returns:
        A :class:`ParsedRecord` carrying field and casilla values.

    Raises:
        AeatExportFormatError: On length mismatch, literal mismatch, or decode
            errors (unparseable date, non-ASCII currency, etc.).
    """
    # Strip any trailing CRLF so we can parse either an on-wire
    # stream (content + CRLF) or already-stripped content bytes.
    body = payload[: -len(_CRLF)] if payload.endswith(_CRLF) else payload
    if len(body) != total_length:
        raise AeatExportFormatError(
            f"payload content is {len(body)} bytes but total_length={total_length} "
            f"was declared; likely wrong record spec or corrupted stream.",
        )

    field_values: dict[str, str | Decimal | date] = {}
    casilla_values: dict[CasillaId, Decimal] = {}

    for spec in specs:
        raw = _slice_field_bytes(body, spec)
        _decode_field_into(
            spec,
            raw,
            encoding=encoding,
            field_values=field_values,
            casilla_values=casilla_values,
        )

    return ParsedRecord(
        field_values=field_values,
        casilla_values=casilla_values,
        raw_length=len(body),
    )


def _slice_field_bytes(body: bytes, spec: RecordFieldSpec) -> bytes:
    """Return the byte slice for one field, raising if the payload is too short."""
    start = spec.offset - 1  # 1-based -> 0-based slice
    end = start + spec.length
    raw = body[start:end]
    if len(raw) != spec.length:
        raise AeatExportFormatError(
            f"field {spec.field_id!r} expects {spec.length} bytes "
            f"at offset {spec.offset}; got {len(raw)} — payload too short?",
        )
    return raw


def _decode_field_into(
    spec: RecordFieldSpec,
    raw: bytes,
    *,
    encoding: FicheroBoeEncoding,
    field_values: dict[str, str | Decimal | date],
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    """Dispatch one field's raw bytes to its kind-specific decoder.

    Mutates ``field_values`` (always) and ``casilla_values`` (only for
    CURRENCY fields that declare a casilla_id) in place. Keeping the
    mutation sinks explicit at the call site preserves the serialiser/
    deserialiser symmetry the fichero-BOE layout contract relies on.
    """
    match spec.kind:
        case FieldKind.RESERVED:
            _decode_reserved_field(spec, raw, encoding, field_values)
        case FieldKind.CURRENCY:
            _decode_currency_field(spec, raw, field_values, casilla_values)
        case FieldKind.DATE:
            assert spec.date_fmt is not None
            field_values[spec.field_id] = _decode_date(raw, spec.date_fmt)
        case FieldKind.ALPHANUMERIC | FieldKind.NUMERIC:
            field_values[spec.field_id] = _decode_text_field(spec, raw, encoding)


def _decode_reserved_field(
    spec: RecordFieldSpec,
    raw: bytes,
    encoding: FicheroBoeEncoding,
    field_values: dict[str, str | Decimal | date],
) -> None:
    """Decode a RESERVED literal field, accepting either padded or exact-width bytes."""
    assert spec.literal_value is not None
    expected = spec.literal_value.encode(encoding).ljust(spec.length, b" ")
    if raw != expected and raw != spec.literal_value.encode(encoding):
        raise AeatExportFormatError(
            f"RESERVED field {spec.field_id!r} expected literal length {spec.length}; "
            f"got length={len(raw)} digest={_wire_digest(raw)}",
        )
    field_values[spec.field_id] = spec.literal_value


def _decode_currency_field(
    spec: RecordFieldSpec,
    raw: bytes,
    field_values: dict[str, str | Decimal | date],
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    """Decode a CURRENCY field and mirror the value into casilla_values when bound."""
    inline_sign = spec.signed_mode is SignedMode.INLINE_SIGN
    value: Decimal = Decimal(0)
    currency_failure: str | None = None
    try:
        value = _decode_currency(raw, inline_sign=inline_sign)
    except AeatExportFormatError:
        raise
    except (UnicodeDecodeError, ValueError) as exc:
        currency_failure = type(exc).__name__
    if currency_failure is not None:
        raise AeatExportFormatError(
            f"CURRENCY field {spec.field_id!r} has invalid wire bytes; "
            f"length={len(raw)} digest={_wire_digest(raw)} failure={currency_failure}",
        )
    field_values[spec.field_id] = value
    if spec.casilla_id is not None:
        casilla_values[spec.casilla_id] = value


def _decode_text_field(spec: RecordFieldSpec, raw: bytes, encoding: FicheroBoeEncoding) -> str:
    """Decode an ALPHANUMERIC or NUMERIC field, stripping pad chars per justification.

    All-zero NUMERIC fields normalise to ``"0"`` — the canonical
    semantic for the unsignaled-zero case. The original byte-level
    width is recoverable from ``spec.length`` if a downstream consumer
    needs the padded form. This mirrors :func:`_decode_currency` which
    also collapses all-zero CURRENCY fields to ``Decimal("0.00")``.
    """
    text: str = ""
    text_failure: str | None = None
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError as exc:
        text_failure = type(exc).__name__
    if text_failure is not None:
        raise AeatExportFormatError(
            f"{spec.kind.value} field {spec.field_id!r} cannot be decoded with {encoding}; "
            f"length={len(raw)} digest={_wire_digest(raw)} failure={text_failure}",
        )
    if spec.pad_char == " ":
        return text.rstrip(" ") if spec.justification.value == "left" else text.lstrip(" ")
    if spec.pad_char == "0":
        text = text.rstrip("0") if spec.justification.value == "left" else text.lstrip("0")
        return text or "0"
    return text


class ParsedEnvelope(BaseModel):
    """Result of parsing a multi-segment fichero-BOE envelope.

    The envelope-level analogue of :class:`ParsedRecord`. Each
    segment's :class:`ParsedRecord` is addressable by ``segment_id`` so
    callers can diff a specific page without walking every segment.

    Attributes:
        segments: Per-segment parsed records keyed by ``segment_id``.
        merged_casilla_values: Flat view of every casilla across every
            segment. Convenient for verification paths that compare a
            filing against AEAT's record per ``casilla_id`` without
            caring which envelope segment the value lived in.
        merged_field_values: Flat view of every ``field_id`` across
            every segment. Envelope-level headers surface here so CLI
            consumers can present them without walking
            :attr:`segments`. Field IDs that collide across segments
            (for example a repeated envelope marker
            repeated in header and trailer) must carry the same value;
            divergent collisions raise at deserialisation time,
            mirroring the casilla-level contract.

    See Also:
        :class:`SegmentSpec`
            Segment declarations consumed by :func:`deserialise_envelope`.
        :func:`aeat.domain.calculations.registry.parse_export_payload`
            Registry-level parser for application export verification.
    """

    model_config = STRICT_FROZEN_CONFIG

    segments: Mapping[str, ParsedRecord]
    """Per-segment parsed records keyed by ``segment_id``."""

    merged_casilla_values: Mapping[CasillaId, Decimal]
    """Flat view of every casilla across every segment."""

    merged_field_values: Mapping[str, str | Decimal | date]
    """Flat view of every field_id across every segment."""


def deserialise_envelope(
    payload: bytes,
    *,
    segments: tuple[SegmentSpec, ...],
    encoding: FicheroBoeEncoding,
) -> ParsedEnvelope:
    """Parse a multi-segment fichero-BOE envelope.

    Consumes the payload in segment order, slicing ``total_length``
    bytes per segment. The final CRLF is optional (the caller may have
    stripped it before hashing).

    Args:
        payload: Concatenated segment bytes with an optional trailing
            CRLF.
        segments: Ordered tuple of :class:`SegmentSpec` describing each
            segment's layout.
        encoding: Wire encoding shared across the envelope.

    Returns:
        A :class:`ParsedEnvelope` with per-segment records plus merged
        casilla and field views.

    Raises:
        AeatExportFormatError: If the payload length does not match the sum of
            segment lengths, any segment fails its shape check, or a
            casilla / field id collides with a divergent value across
            segments.
    """
    if not segments:
        raise AeatExportFormatError("segments must not be empty")

    body = payload[: -len(_CRLF)] if payload.endswith(_CRLF) else payload
    expected_total = sum(s.total_length for s in segments)
    if len(body) != expected_total:
        raise AeatExportFormatError(
            f"envelope payload is {len(body)} bytes but segments sum to "
            f"{expected_total}; wrong envelope composition or corrupted stream.",
        )

    parsed: dict[str, ParsedRecord] = {}
    merged: dict[CasillaId, Decimal] = {}
    merged_fields: dict[str, str | Decimal | date] = {}
    cursor = 0
    for segment in segments:
        slice_end = cursor + segment.total_length
        segment_bytes = body[cursor:slice_end]
        record = deserialise(
            segment_bytes,
            specs=segment.specs,
            encoding=encoding,
            total_length=segment.total_length,
        )
        parsed[segment.segment_id] = record
        for cid, value in record.casilla_values.items():
            if cid in merged and merged[cid] != value:
                raise AeatExportFormatError(
                    f"casilla {cid!r} appears with divergent values across "
                    f"segments; record spec must not duplicate casilla_id across pages.",
                )
            merged[cid] = value
        for fid, fvalue in record.field_values.items():
            if fid in merged_fields and merged_fields[fid] != fvalue:
                raise AeatExportFormatError(
                    f"field {fid!r} appears with divergent values across "
                    f"segments; record spec must not duplicate field_id across pages "
                    f"unless the fields carry identical values.",
                )
            merged_fields[fid] = fvalue
        cursor = slice_end

    return ParsedEnvelope(
        segments=parsed,
        merged_casilla_values=merged,
        merged_field_values=merged_fields,
    )


__all__ = ["ParsedEnvelope", "ParsedRecord", "deserialise", "deserialise_envelope"]
