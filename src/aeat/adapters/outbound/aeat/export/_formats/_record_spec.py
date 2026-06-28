"""Fixed-width record-spec primitives for explicit fichero-BOE layouts.

The :class:`RecordFieldSpec` and :class:`SegmentSpec` records describe a
small adapter-local fixed-width layout that can be passed to
:func:`aeat.adapters.outbound.aeat.export._formats._serialise.serialise`
or :func:`aeat.adapters.outbound.aeat.export._formats._deserialise.deserialise`.
The canonical product export path is registry-backed:
:class:`aeat.domain.calculations.registry.ExportLayoutDefinition` and
:class:`aeat.domain.calculations.registry.ExportRecordDefinition` drive
:func:`aeat.application.filing.export_draft` and
:func:`aeat.domain.calculations.registry.parse_export_payload`.

Primitive-safety contract:

- :func:`encode_currency` uses explicit
  :data:`decimal.ROUND_HALF_UP` matching the AEAT
  *Instrucciones de cumplimentación* (not banker's rounding).
- :func:`encode_text` raises on overflow (no silent truncation) to
  prevent identity or name-field corruption from mis-measured specs.
- :class:`RecordFieldSpec` enforces the RESERVED ↔ ``literal_value``
  invariant at construction time.
- :func:`validate_record_specs` enforces monotonic
  ``offset + length == next.offset`` across a spec tuple.

Explicit-spec callers pin the concrete wire encoding via the
:data:`FicheroBoeEncoding` literal.

See Also:
    :class:`aeat.domain.calculations.registry.ExportFieldDefinition`
        Canonical registry field declaration for modelo export layouts.
    :class:`aeat.adapters.outbound.aeat.export.AeatExportFormatError`
        Error raised when an explicit fixed-width spec or encoded value
        violates the adapter contract.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from ......core import STRICT_FROZEN_CONFIG
from ......core.money import round_to_cents as _round_to_cents
from ......domain.calculations.registry import CasillaId
from .._errors import AeatExportFormatError

# FicheroBoeEncoding must stay as a Literal for static type-checking, but the
# canonical runtime set is sourced from BOE_ENCODING_CHOICES in external_constants.
FicheroBoeEncoding = Literal["cp1252", "iso-8859-1", "iso-8859-15"]
"""Allowed wire encodings for fichero-BOE payloads.

Windows-1252 is a superset of ISO-8859-1 that adds characters in the
0x80-0x9F range; AEAT treats them as equivalent for fichero-BOE
purposes. ISO-8859-15 adds the Euro symbol at 0xA4 plus other minor
deltas needed by some annual informativas.
"""


class FieldKind(StrEnum):
    """Semantic kind of a fixed-width field.

    Determines the pad-character and justification defaults plus the
    encoder routing performed in
    :func:`aeat.adapters.outbound.aeat.export._formats._serialise.serialise`.

    Attributes:
        ALPHANUMERIC: Free-form text fields; left-justified, space-padded
            by default.
        NUMERIC: Integer-shaped numeric fields; right-justified,
            zero-padded by default.
        CURRENCY: Two-decimal monetary amounts encoded as zero-padded
            cents via :func:`encode_currency`.
        DATE: Calendar date encoded per the field's :class:`DateFmt`.
        RESERVED: Literal constant slots, separators,
            envelope opener / closer) emitted verbatim from
            :attr:`RecordFieldSpec.literal_value`.
    """

    ALPHANUMERIC = "alphanumeric"
    NUMERIC = "numeric"
    CURRENCY = "currency"
    DATE = "date"
    RESERVED = "reserved"


class Justification(StrEnum):
    """Fixed-width field alignment.

    Attributes:
        LEFT: Pad on the right.
        RIGHT: Pad on the left.
    """

    LEFT = "left"
    RIGHT = "right"


class DateFmt(StrEnum):
    """BOE date shapes encountered across fixed-width record designs.

    The concrete registry spec pins the shape per field.

    Attributes:
        YYYYMMDD: Year-first calendar date, eight ASCII digits.
        DDMMYYYY: Day-first calendar date, eight ASCII digits.
    """

    YYYYMMDD = "yyyymmdd"
    DDMMYYYY = "ddmmyyyy"


class SignedMode(StrEnum):
    """Sign-convention for a CURRENCY field.

    AEAT record designs can use different conventions for negative
    amounts in the fichero-BOE wire format. Registry-backed definitions
    declare the correct mode per field; the serialiser routes to
    :func:`encode_currency` accordingly.

    Attributes:
        UNSIGNED: Field is always non-negative. Callers must either
            pass ``abs(value)`` or rely on an adjacent SIGNO / TIPO
            flag elsewhere in the record.
        INLINE_SIGN: Byte 0 is ``"N"`` for negatives or ``" "`` for
            non-negatives; remaining bytes carry the absolute
            magnitude.
    """

    UNSIGNED = "unsigned"
    INLINE_SIGN = "inline_sign"


class RecordFieldSpec(BaseModel):
    """One fixed-width field in a fichero-BOE record.

    Strict / frozen / ``extra="forbid"`` per the project's
    boundary-record mandate. Validated when the concrete spec tuple is
    constructed via
    :func:`record_field` and :func:`validate_record_specs`.

    Attributes:
        offset: 1-based byte offset per BOE convention.
        length: Field byte length.
        field_id: AEAT field identifier. The 96-char cap accommodates
            descriptive names from official record designs.
        casilla_id: Optional mapping to a registry casilla. ``None`` for
            header, reserved, or literal fields that do not correspond
            to a casilla.
        kind: Semantic :class:`FieldKind` selecting the encoder route.
        justification: Where to align the value within the ``length``
            window.
        pad_char: Single-byte pad character (typically ``" "`` for
            text, ``"0"`` for numeric).
        literal_value: For RESERVED literal fields, the exact byte
            string to emit. Required when ``kind == RESERVED`` and
            forbidden otherwise.
        date_fmt: Required when ``kind == DATE``; ignored otherwise.
        signed_mode: How CURRENCY fields encode negative amounts.
            Defaults to ``UNSIGNED``. Set to ``INLINE_SIGN`` for
            fields that carry the sign in the leading byte. Ignored for
            non-CURRENCY kinds.

    See Also:
        :class:`aeat.domain.calculations.registry.ExportFieldDefinition`
            Registry-backed declaration used by the application export
            renderer.
        :func:`record_field`
            Compact constructor that applies kind-aware defaults before
            producing this record.
    """

    model_config = STRICT_FROZEN_CONFIG

    offset: Annotated[int, Field(ge=1)]
    """1-based byte offset per BOE convention."""

    length: Annotated[int, Field(ge=1)]
    """Field byte length."""

    field_id: Annotated[str, Field(min_length=1, max_length=96)]
    """AEAT field identifier."""

    casilla_id: CasillaId | None = None
    """Optional mapping to a canonical registry ``casilla.id``."""

    kind: FieldKind

    justification: Justification
    """Where to align the value within the ``length`` window."""

    pad_char: Annotated[str, Field(min_length=1, max_length=1)] = " "
    """Single-byte pad character."""

    literal_value: str | None = None
    """For RESERVED / literal fields: the exact byte string to emit."""

    date_fmt: DateFmt | None = None
    """Required when ``kind == DATE``; ignored otherwise."""

    signed_mode: SignedMode = SignedMode.UNSIGNED
    """How CURRENCY fields encode negative amounts."""

    @model_validator(mode="after")
    def _reserved_requires_literal(self) -> RecordFieldSpec:
        """Enforce the RESERVED ↔ ``literal_value`` invariant.

        A RESERVED field is a literal constant (record
        separator, filler ``"0000"``, etc.). Constructing a RESERVED
        spec without a ``literal_value`` makes the serialiser
        undefined; declaring a ``literal_value`` on a non-RESERVED
        field is a modelling error. Also asserts ``DATE`` carries a
        :class:`DateFmt` and ``INLINE_SIGN`` only appears on CURRENCY
        fields.
        """
        if self.kind is FieldKind.RESERVED and self.literal_value is None:
            raise AeatExportFormatError(f"RESERVED fields must carry a literal_value; got None for {self.field_id!r}")
        if self.kind is not FieldKind.RESERVED and self.literal_value is not None:
            raise AeatExportFormatError(
                f"literal_value is only valid when kind=RESERVED; got {self.kind!r} for {self.field_id!r}",
            )
        if self.kind is FieldKind.DATE and self.date_fmt is None:
            raise AeatExportFormatError(f"DATE fields must carry a date_fmt; got None for {self.field_id!r}")
        if self.signed_mode is SignedMode.INLINE_SIGN and self.kind is not FieldKind.CURRENCY:
            raise AeatExportFormatError(
                f"signed_mode=INLINE_SIGN is only valid on CURRENCY fields; got {self.kind!r} for {self.field_id!r}",
            )
        return self


def record_field(
    *,
    offset: int,
    length: int,
    field_id: str,
    casilla_id: CasillaId | None = None,
    kind: FieldKind,
    justification: Justification | None = None,
    pad_char: str | None = None,
    literal_value: str | None = None,
    date_fmt: DateFmt | None = None,
    signed_mode: SignedMode = SignedMode.UNSIGNED,
) -> RecordFieldSpec:
    """Concise constructor for :class:`RecordFieldSpec`.

    Mirrors the compact registry declaration style. Applies kind-appropriate
    defaults for ``justification`` and ``pad_char`` so most field
    declarations only need ``offset`` / ``length`` / ``field_id`` /
    ``kind``:

    - ``NUMERIC`` and ``CURRENCY`` are right-justified and zero-padded.
    - ``ALPHANUMERIC``, ``RESERVED``, and ``DATE`` are left-justified
      and space-padded.

    Args:
        offset: 1-based byte offset within the record.
        length: Field byte length.
        field_id: AEAT field identifier.
        casilla_id: Optional canonical registry casilla mapping.
        kind: Semantic :class:`FieldKind`.
        justification: Override the kind-aware default justification.
        pad_char: Override the kind-aware default pad character.
        literal_value: Required for ``kind == RESERVED``.
        date_fmt: Required for ``kind == DATE``.
        signed_mode: Sign convention for ``kind == CURRENCY``.

    Returns:
        A validated :class:`RecordFieldSpec`.
    """
    if justification is None:
        justification = Justification.RIGHT if kind in {FieldKind.NUMERIC, FieldKind.CURRENCY} else Justification.LEFT
    if pad_char is None:
        pad_char = "0" if kind in {FieldKind.NUMERIC, FieldKind.CURRENCY} else " "
    return RecordFieldSpec(
        offset=offset,
        length=length,
        field_id=field_id,
        casilla_id=casilla_id,
        kind=kind,
        justification=justification,
        pad_char=pad_char,
        literal_value=literal_value,
        date_fmt=date_fmt,
        signed_mode=signed_mode,
    )


def encode_currency(
    value: Decimal,
    *,
    length: int,
    signed: bool = False,
    inline_sign: bool = False,
    encoding: FicheroBoeEncoding,
) -> bytes:
    """Encode currency as right-justified, zero-padded cents with two implicit decimals.

    AEAT fichero-BOE currency fields emit the ``value * 100`` integer
    with no separators. ``Decimal("1234.56")`` in a length-13 field
    produces ``b"0000000123456"``.

    Rounding uses an explicit :data:`decimal.ROUND_HALF_UP` to match
    AEAT *Instrucciones de cumplimentación* — not banker's rounding —
    so ``Decimal("2.005")`` rounds to ``b"000201"``.

    Args:
        value: Monetary amount to encode. Must be non-negative unless
            ``signed`` or ``inline_sign`` is ``True``.
        length: Total field width in bytes (including the sign byte
            when ``inline_sign=True``).
        signed: When ``True``, allow negative inputs whose sign has
            been wired through a separate SIGNO / TIPO field elsewhere
            in the record.
        inline_sign: When ``True``, switch to the leading ``"N"`` /
            ``" "`` sign-byte convention. The remaining ``length - 1``
            bytes carry the zero-padded absolute magnitude.
        encoding: Output byte encoding.

    Returns:
        The fixed-width byte sequence for the currency field.

    Raises:
        AeatExportFormatError: If ``value`` is negative without ``signed`` or
            ``inline_sign``, the magnitude overflows ``length``, or
            ``inline_sign=True`` is used with ``length < 2``.
    """
    negative = value < 0
    if negative and not (signed or inline_sign):
        raise AeatExportFormatError(
            f"encode_currency received negative {value!r} without "
            f"signed=True or inline_sign=True. Pass signed=True after "
            f"wiring a separate sign field, or inline_sign=True for an "
            f"'N'-prefix field.",
        )
    quantised = _round_to_cents(abs(value))
    cents = int(quantised * 100)

    if inline_sign:
        if length < 2:
            raise AeatExportFormatError(
                f"inline_sign=True requires length >= 2 (1 sign byte + ≥1 magnitude byte); got length={length}",
            )
        magnitude_width = length - 1
        s_magnitude = str(cents).rjust(magnitude_width, "0")
        if len(s_magnitude) > magnitude_width:
            raise AeatExportFormatError(
                f"currency value {value} overflows inline-sign length-"
                f"{length} field (magnitude needs {len(s_magnitude)} "
                f"bytes, {magnitude_width} available)",
            )
        prefix = "N" if negative else " "
        return (prefix + s_magnitude).encode(encoding)

    s = str(cents).rjust(length, "0")
    if len(s) > length:
        raise AeatExportFormatError(
            f"currency value {value} overflows length-{length} field (would need {len(s)} bytes)",
        )
    return s.encode(encoding)


def encode_text(
    value: str,
    *,
    length: int,
    justification: Justification = Justification.LEFT,
    pad_char: str = " ",
    truncate: bool = False,
    encoding: FicheroBoeEncoding,
) -> bytes:
    """Encode an alphanumeric value into a fixed-width byte field.

    Args:
        value: Text value to encode.
        length: Target field width in bytes.
        justification: Where to align ``value`` within ``length``.
        pad_char: Single-character pad applied to fill the remainder.
        truncate: When ``False`` (default), raise on overflow rather
            than silently clipping. A mis-measured spec that would
            clip an identity or name field is a legally-binding corruption
            — fail loud. Set ``truncate=True`` only when the caller
            has a concrete reason to allow clipping.
        encoding: Wire encoding supplied by the registry export layout.

    Returns:
        The fixed-width byte sequence.

    Raises:
        AeatExportFormatError: If ``pad_char`` is not exactly one character or
            ``len(value) > length`` and ``truncate`` is ``False``.
    """
    if len(pad_char) != 1:
        raise AeatExportFormatError("pad_char must be a single character")
    if len(value) > length and not truncate:
        raise AeatExportFormatError(
            f"text value {value!r} overflows length-{length} field "
            f"(would need {len(value)} bytes); set truncate=True to "
            f"allow silent clipping.",
        )
    s = value[:length] if len(value) > length else value
    s = s.ljust(length, pad_char) if justification is Justification.LEFT else s.rjust(length, pad_char)
    return s.encode(encoding)


def encode_date(
    value: date,
    fmt: DateFmt,
    *,
    encoding: FicheroBoeEncoding,
) -> bytes:
    """Encode a :class:`datetime.date` per the BOE *Diseño de registros* ``fmt``.

    Args:
        value: Calendar date to encode.
        fmt: Wire-format selector.
        encoding: Output byte encoding.

    Returns:
        Eight-byte ASCII representation of the date.
    """
    match fmt:
        case DateFmt.YYYYMMDD:
            return value.strftime("%Y%m%d").encode(encoding)
        case DateFmt.DDMMYYYY:
            return value.strftime("%d%m%Y").encode(encoding)


class SegmentSpec(BaseModel):
    """A named, variable-length segment in a multi-segment fichero-BOE envelope.

    Some AEAT record designs are not a single flat record. The on-wire
    format can be an envelope like::

        <SEG0> ... </SEG0> ... <SEG1>page1</SEG1> ...

    Each segment is itself a fixed-width record with its own field
    layout, opener + closer literal, and byte length. Segment IDs reset
    their internal offsets to 1.

    A :class:`SegmentSpec` carries one segment's layout. The envelope
    itself is a tuple of :class:`SegmentSpec` plus a selector that
    decides which optional segments are emitted.

    Attributes:
        segment_id: AEAT segment identifier.
        specs: The field layout for this segment. Offsets are
            segment-local (1-based within this segment, not global).
        total_length: Byte content length of this segment, excluding
            any CRLF terminator.

    See Also:
        :class:`aeat.domain.calculations.registry.ExportRecordDefinition`
            Registry-backed record declaration for the active modelo export
            renderer.
        :func:`aeat.adapters.outbound.aeat.export._formats._serialise.serialise_envelope`
            Explicit-spec envelope serialiser that consumes segments.
    """

    model_config = STRICT_FROZEN_CONFIG

    segment_id: Annotated[str, Field(min_length=1, max_length=32)]
    specs: tuple[RecordFieldSpec, ...]
    total_length: Annotated[int, Field(ge=1)]


def validate_segment_specs(segments: tuple[SegmentSpec, ...]) -> None:
    """Enforce per-segment invariants at import time.

    Runs :func:`validate_record_specs` on each segment and checks that
    segment IDs are unique across the envelope. Does NOT enforce a
    global offset — each segment resets to 1.

    Args:
        segments: Ordered tuple of :class:`SegmentSpec` to validate.

    Raises:
        AeatExportFormatError: If ``segments`` is empty, a ``segment_id`` repeats,
            or any segment fails its internal :func:`validate_record_specs` check.
    """
    if not segments:
        raise AeatExportFormatError("segments must not be empty")
    seen: set[str] = set()
    for i, seg in enumerate(segments):
        if seg.segment_id in seen:
            raise AeatExportFormatError(f"duplicate segment_id={seg.segment_id!r} at index {i}")
        seen.add(seg.segment_id)
        try:
            validate_record_specs(seg.specs, total_length=seg.total_length)
        except AeatExportFormatError as exc:
            raise AeatExportFormatError(f"segment {seg.segment_id!r} at index {i}: {exc}") from exc


def validate_record_specs(
    specs: tuple[RecordFieldSpec, ...],
    *,
    total_length: int,
) -> None:
    """Enforce the monotonic offset / length invariant for one segment.

    Registry-backed loaders call this before a filing layout can be used
    to guard against off-by-one errors that would cascade through every
    subsequent field. The checks are:

    - First field starts at offset 1 (BOE 1-based convention).
    - Fields are monotonically contiguous: no gaps, no overlaps.
    - Terminal field fills exactly to ``total_length``.
    - ``field_id`` values are unique.
    - ``casilla_id`` values are unique where non-``None``.

    Args:
        specs: Ordered tuple of field specs covering the segment.
        total_length: Expected segment byte content length.

    Raises:
        AeatExportFormatError: Carries a precise pointer (field id, offset,
            expected vs actual) for any violation.
    """
    if not specs:
        raise AeatExportFormatError("record specs must not be empty")
    if specs[0].offset != 1:
        raise AeatExportFormatError(
            f"first spec must start at offset=1 (BOE 1-based); "
            f"got offset={specs[0].offset} for field_id={specs[0].field_id!r}",
        )
    seen_field_ids: set[str] = set()
    seen_casilla_ids: set[CasillaId] = set()
    expected = 1
    for i, spec in enumerate(specs):
        if spec.offset != expected:
            prev = specs[i - 1] if i > 0 else None
            prev_hint = f"(prev {prev.field_id!r} ends at {prev.offset + prev.length - 1})" if prev is not None else ""
            raise AeatExportFormatError(
                f"spec #{i} {spec.field_id!r} offset={spec.offset} "
                f"breaks monotonic contiguity; expected offset={expected} {prev_hint}",
            )
        if spec.field_id in seen_field_ids:
            raise AeatExportFormatError(f"duplicate field_id={spec.field_id!r} at spec #{i}")
        seen_field_ids.add(spec.field_id)
        if spec.casilla_id is not None:
            if spec.casilla_id in seen_casilla_ids:
                raise AeatExportFormatError(
                    f"duplicate casilla_id={spec.casilla_id!r} at spec #{i} (field_id={spec.field_id!r})",
                )
            seen_casilla_ids.add(spec.casilla_id)
        expected = spec.offset + spec.length
    terminal_end = expected - 1
    if terminal_end != total_length:
        raise AeatExportFormatError(
            f"record specs fill {terminal_end} bytes but total_length={total_length} "
            f"was declared; adjust the final field or the declared length.",
        )
