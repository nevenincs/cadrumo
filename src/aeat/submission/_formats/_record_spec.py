"""Fixed-width record-spec primitives for fichero-BOE export.

EPIC #201 wave 75d + wave 77 primitive-safety hardening. See ADR
``.vault/adr/2026-04-22-aeat-fichero-boe-export-adr.md`` §2-4 for
the design rationale.

Every concrete modelo module authors a tuple of
:class:`RecordFieldSpec` entries describing the BOE *Diseño de
registros* field layout. The encoders defined here produce the
byte-exact output the AEAT portal expects via "importar datos".

Wave 77 primitive-safety contract:

- ``encode_currency`` uses explicit ``ROUND_HALF_UP`` matching AEAT
  *Instrucciones de cumplimentación* (NOT banker's rounding).
- ``encode_text`` raises on overflow (no silent truncation) to
  prevent NIF / razón-social corruption from mis-measured specs.
- ``RecordFieldSpec`` enforces the RESERVED ⇔ literal_value
  invariant at construction time.
- :func:`validate_record_specs` enforces monotonic ``offset + length
  == next.offset`` across a module's spec tuple. Wave 77c entry-
  gate for modelo schemas.

Per-modelo encoding: most modelos use **Windows-1252 / ISO-8859-1**
(Modelo 130 per Orden EHA/672/2007; Modelo 303 post-HAC/819/2024;
etc.). A handful of annual informativas (190 / 347) historically
used ISO-8859-15 for Euro-symbol compatibility. Concrete modelo
modules pin the encoding explicitly.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Per-BOE encoding choices. Windows-1252 is a superset of ISO-8859-1
# that adds characters in the 0x80-0x9F range; AEAT treats them as
# equivalent for fichero-BOE purposes. ISO-8859-15 adds the Euro
# symbol at 0xA4 and other minor deltas.
FicheroBoeEncoding = Literal["cp1252", "iso-8859-1", "iso-8859-15"]
DEFAULT_ENCODING: FicheroBoeEncoding = "cp1252"


class FieldKind(StrEnum):
    """Semantic kind of a fixed-width field.

    Determines the pad-character and justification defaults plus
    the encoder routing in :func:`RecordFieldSpec.encode`.
    """

    ALPHANUMERIC = "alphanumeric"
    NUMERIC = "numeric"
    CURRENCY = "currency"
    DATE = "date"
    RESERVED = "reserved"


class Justification(StrEnum):
    """Fixed-width field alignment."""

    LEFT = "left"
    RIGHT = "right"


class DateFmt(StrEnum):
    """BOE date shapes encountered across modelos.

    Most 2020+ modelos use ``YYYYMMDD``; some legacy and informativas
    still emit ``DDMMYYYY``. The concrete spec pins the shape per field.
    """

    YYYYMMDD = "yyyymmdd"
    DDMMYYYY = "ddmmyyyy"


class SignedMode(StrEnum):
    """Sign-convention for a CURRENCY field (wave 85b).

    Different AEAT modelos use different conventions for negative
    amounts in the fichero-BOE wire format:

    - ``UNSIGNED``: field is always non-negative. Callers must
      either pass abs(value) or rely on an adjacent SIGNO/TIPO
      flag elsewhere in the record. Modelo 130 default.
    - ``INLINE_SIGN``: byte 0 is ``"N"`` for negatives or ``" "``
      for non-negatives; remaining bytes carry |value|. Modelo 303
      type-N fields (casillas 69, 71, and many others).

    Concrete modelo modules declare the correct mode per field;
    the serialiser routes to ``encode_currency(inline_sign=...)``
    accordingly. Modelo 130 keeps ``UNSIGNED`` via default; Modelo
    303+ explicit ``INLINE_SIGN`` on signed casillas.
    """

    UNSIGNED = "unsigned"
    INLINE_SIGN = "inline_sign"


class RecordFieldSpec(BaseModel):
    """One fixed-width field in a fichero-BOE record.

    Strict/frozen/extra=forbid per the project's boundary-record
    mandate. Validated at module-import time when the concrete
    ``_RECORD_SPECS`` tuple is constructed.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    offset: Annotated[int, Field(ge=1)]
    """1-based byte offset per BOE convention."""

    length: Annotated[int, Field(ge=1)]
    """Field byte length."""

    field_id: Annotated[str, Field(min_length=1, max_length=32)]
    """AEAT field identifier (e.g. ``F01001``, ``NIF``, ``EJERCICIO``)."""

    casilla_id: Annotated[str, Field(max_length=5)] | None = None
    """Optional mapping to a ruleset casilla. ``None`` for header /
    reserved / literal fields that don't correspond to a casilla."""

    kind: FieldKind

    justification: Justification
    """Where to align the value within the ``length`` window."""

    pad_char: Annotated[str, Field(min_length=1, max_length=1)] = " "
    """Single-byte pad character (e.g. ``" "`` for text, ``"0"`` for
    numeric)."""

    literal_value: str | None = None
    """For RESERVED / literal fields: the exact byte string to emit.
    Ignored for data fields (kind != RESERVED)."""

    date_fmt: DateFmt | None = None
    """Required when ``kind == DATE``; ignored otherwise."""

    signed_mode: SignedMode = SignedMode.UNSIGNED
    """Wave 85b: how CURRENCY fields encode negative amounts.

    Defaults to ``UNSIGNED`` (Modelo 130 convention: magnitude +
    separate SIGNO flag). Set to ``INLINE_SIGN`` for Modelo 303
    type-N fields that carry the sign in the leading byte.
    Ignored for non-CURRENCY kinds.
    """

    @model_validator(mode="after")
    def _reserved_requires_literal(self) -> RecordFieldSpec:
        """Wave 77a: enforce RESERVED ⇔ literal_value invariant.

        A RESERVED field is a literal constant (modelo code, record
        separator, filler "0000", etc.). Constructing a RESERVED spec
        without a ``literal_value`` makes the serialiser undefined;
        declaring a ``literal_value`` on a non-RESERVED field is a
        modelling error.
        """
        if self.kind is FieldKind.RESERVED and self.literal_value is None:
            raise ValueError(f"RESERVED fields must carry a literal_value; got None for {self.field_id!r}")
        if self.kind is not FieldKind.RESERVED and self.literal_value is not None:
            raise ValueError(f"literal_value is only valid when kind=RESERVED; got {self.kind!r} for {self.field_id!r}")
        if self.kind is FieldKind.DATE and self.date_fmt is None:
            raise ValueError(f"DATE fields must carry a date_fmt; got None for {self.field_id!r}")
        if self.signed_mode is SignedMode.INLINE_SIGN and self.kind is not FieldKind.CURRENCY:
            raise ValueError(
                f"signed_mode=INLINE_SIGN is only valid on CURRENCY fields; "
                f"got {self.kind!r} for {self.field_id!r} (wave 86 audit hardening)"
            )
        return self


def record_field(
    *,
    offset: int,
    length: int,
    field_id: str,
    casilla_id: str | None = None,
    kind: FieldKind,
    justification: Justification | None = None,
    pad_char: str | None = None,
    literal_value: str | None = None,
    date_fmt: DateFmt | None = None,
    signed_mode: SignedMode = SignedMode.UNSIGNED,
) -> RecordFieldSpec:
    """Concise constructor for :class:`RecordFieldSpec`.

    Mirrors the :func:`aeat.formulas._rulesets._common.formula`
    helper pattern used in the formulas package. Applies
    kind-appropriate defaults for ``justification`` and ``pad_char``
    so most field declarations only need offset/length/field_id/kind.

    Defaults:
    - NUMERIC / CURRENCY → right-justified, zero-padded.
    - ALPHANUMERIC / RESERVED / DATE → left-justified, space-padded.
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
    encoding: FicheroBoeEncoding = DEFAULT_ENCODING,
) -> bytes:
    """Right-justified, zero-padded currency with 2 implicit decimals.

    AEAT fichero-BOE currency fields emit the ``value * 100`` integer
    with no separators. ``Decimal("1234.56")`` in a length-13 field
    produces ``b"0000000123456"``.

    Wave 77a hardening:
    - Explicit ``ROUND_HALF_UP`` matching AEAT *Instrucciones* (not
      banker's rounding). ``Decimal("2.005")`` → ``b"000201"``.
    - ``signed=False`` (default) rejects negative inputs so a caller
      who forgot to wire the adjacent SIGNO field gets a clear error
      instead of a byte-legal but semantically-wrong positive
      magnitude. Set ``signed=True`` when you have explicitly
      arranged the SIGNO flip elsewhere.

    Wave 83a (Modelo 303+ inline-sign convention):
    - ``inline_sign=True`` switches from AEAT's "separate SIGNO/TIPO
      field" convention (Modelo 130 ``TIPO_DECLARACION="N"``) to the
      inline "N"-prefix convention used by Modelo 303 and other IVA
      modelos. With ``inline_sign=True`` and a negative value, the
      LEADING byte becomes ``"N"`` and the remaining ``length - 1``
      bytes carry the zero-padded absolute magnitude. Positive
      values emit a leading space instead of ``"N"``. ``signed=True``
      is not required when ``inline_sign=True``.
    """
    negative = value < 0
    if negative and not (signed or inline_sign):
        raise ValueError(
            f"encode_currency received negative {value!r} without "
            f"signed=True or inline_sign=True; most AEAT modelos carry "
            f"a separate SIGNO/TIPO field. Pass signed=True after "
            f"wiring that field, or inline_sign=True for Modelo 303+ "
            f"'N'-prefix convention."
        )
    quantised = abs(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cents = int(quantised * 100)

    if inline_sign:
        if length < 2:
            raise ValueError(
                f"inline_sign=True requires length >= 2 (1 sign byte + ≥1 magnitude byte); got length={length}"
            )
        magnitude_width = length - 1
        s_magnitude = str(cents).rjust(magnitude_width, "0")
        if len(s_magnitude) > magnitude_width:
            raise ValueError(
                f"currency value {value} overflows inline-sign length-"
                f"{length} field (magnitude needs {len(s_magnitude)} "
                f"bytes, {magnitude_width} available)"
            )
        prefix = "N" if negative else " "
        return (prefix + s_magnitude).encode(encoding)

    s = str(cents).rjust(length, "0")
    if len(s) > length:
        raise ValueError(f"currency value {value} overflows length-{length} field (would need {len(s)} bytes)")
    return s.encode(encoding)


def encode_text(
    value: str,
    *,
    length: int,
    justification: Justification = Justification.LEFT,
    pad_char: str = " ",
    truncate: bool = False,
    encoding: FicheroBoeEncoding = DEFAULT_ENCODING,
) -> bytes:
    """Alphanumeric encoder.

    Wave 77a hardening:
    - Raises ``ValueError`` when ``len(value) > length`` (no silent
      truncation). A mis-measured spec that would clip a NIF or
      razón-social is a legally-binding corruption; fail loud.
    - Set ``truncate=True`` only when the caller has a concrete
      reason to allow clipping (rare; prefer fixing the spec).
    - Per-modelo ``encoding`` override. Default is Windows-1252
      (CP1252) which is a superset of ISO-8859-1; ISO-8859-15 for
      Euro-symbol modelos.
    """
    if len(pad_char) != 1:
        raise ValueError("pad_char must be a single character")
    if len(value) > length and not truncate:
        raise ValueError(
            f"text value {value!r} overflows length-{length} field "
            f"(would need {len(value)} bytes); set truncate=True to "
            f"allow silent clipping."
        )
    s = value[:length] if len(value) > length else value
    s = s.ljust(length, pad_char) if justification is Justification.LEFT else s.rjust(length, pad_char)
    return s.encode(encoding)


def encode_date(
    value: date,
    fmt: DateFmt,
    *,
    encoding: FicheroBoeEncoding = DEFAULT_ENCODING,
) -> bytes:
    """Date encoder per BOE *Diseño de registros* shapes."""
    match fmt:
        case DateFmt.YYYYMMDD:
            return value.strftime("%Y%m%d").encode(encoding)
        case DateFmt.DDMMYYYY:
            return value.strftime("%d%m%Y").encode(encoding)


class SegmentSpec(BaseModel):
    """A named, variable-length segment in a multi-segment fichero-BOE envelope.

    Wave 82a (EPIC #201, Modelo 303+ support). Modelo 303 — and every
    IVA modelo post-HAC/819/2024 — is not a single flat record. The
    on-wire format is an envelope like::

        <T3030AAAAPP0000> ... <AUX> ... </AUX> ... <T30301...>page1</T30301...> ...

    Each ``<T303PPPPP...>`` segment is itself a fixed-width record with
    its own field layout, opener + closer literal, and byte length.
    Segment IDs also reset their internal offsets to 1 (per-segment
    numbering — unlike Modelo 130's single flat 1..878 range).

    A :class:`SegmentSpec` carries one segment's layout. The envelope
    itself is a tuple of :class:`SegmentSpec` plus a per-draft selector
    that decides which optional segments are emitted (e.g., Modelo 303
    page 4 is emitted only on the last-period exonerado-390 filing).

    Attributes:
        segment_id: AEAT segment identifier (``"DP30300"``, ``"DP30301"``).
        specs: the field layout for this segment. Offsets are
            segment-local (1-based within this segment, NOT global).
        total_length: byte content length of this segment (excluding
            any CRLF terminator if present).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    segment_id: Annotated[str, Field(min_length=1, max_length=32)]
    specs: tuple[RecordFieldSpec, ...]
    total_length: Annotated[int, Field(ge=1)]


def validate_segment_specs(segments: tuple[SegmentSpec, ...]) -> None:
    """Enforce per-segment invariants at import time.

    Runs :func:`validate_record_specs` on each segment and checks that
    segment IDs are unique across the envelope. Does NOT enforce a
    global offset (each segment resets to 1). Wave 82a companion to
    :func:`validate_record_specs`.
    """
    if not segments:
        raise ValueError("segments must not be empty")
    seen: set[str] = set()
    for i, seg in enumerate(segments):
        if seg.segment_id in seen:
            raise ValueError(f"duplicate segment_id={seg.segment_id!r} at index {i}")
        seen.add(seg.segment_id)
        try:
            validate_record_specs(seg.specs, total_length=seg.total_length)
        except ValueError as exc:
            raise ValueError(f"segment {seg.segment_id!r} at index {i}: {exc}") from exc


def validate_record_specs(
    specs: tuple[RecordFieldSpec, ...],
    *,
    total_length: int,
) -> None:
    """Wave 77a: enforce the monotonic offset/length invariant.

    Each concrete modelo module calls this at import time to guard
    against hand-authoring off-by-one errors that would cascade
    through every subsequent field. Checks:

    - First field starts at offset 1 (BOE 1-based convention).
    - Fields are monotonically contiguous: no gaps, no overlaps.
    - Terminal field fills exactly to ``total_length``.
    - ``field_id`` values are unique.
    - ``casilla_id`` values are unique where non-None.

    Raises ``ValueError`` with a precise pointer on any violation.
    """
    if not specs:
        raise ValueError("record specs must not be empty")
    if specs[0].offset != 1:
        raise ValueError(
            f"first spec must start at offset=1 (BOE 1-based); "
            f"got offset={specs[0].offset} for field_id={specs[0].field_id!r}"
        )
    seen_field_ids: set[str] = set()
    seen_casilla_ids: set[str] = set()
    expected = 1
    for i, spec in enumerate(specs):
        if spec.offset != expected:
            prev = specs[i - 1] if i > 0 else None
            prev_hint = f"(prev {prev.field_id!r} ends at {prev.offset + prev.length - 1})" if prev is not None else ""
            raise ValueError(
                f"spec #{i} {spec.field_id!r} offset={spec.offset} "
                f"breaks monotonic contiguity; expected offset={expected} {prev_hint}"
            )
        if spec.field_id in seen_field_ids:
            raise ValueError(f"duplicate field_id={spec.field_id!r} at spec #{i}")
        seen_field_ids.add(spec.field_id)
        if spec.casilla_id is not None:
            if spec.casilla_id in seen_casilla_ids:
                raise ValueError(f"duplicate casilla_id={spec.casilla_id!r} at spec #{i} (field_id={spec.field_id!r})")
            seen_casilla_ids.add(spec.casilla_id)
        expected = spec.offset + spec.length
    terminal_end = expected - 1
    if terminal_end != total_length:
        raise ValueError(
            f"record specs fill {terminal_end} bytes but total_length={total_length} "
            f"was declared; adjust the final field or the declared length."
        )
