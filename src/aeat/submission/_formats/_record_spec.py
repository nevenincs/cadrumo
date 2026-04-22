"""Fixed-width record-spec primitives for fichero-BOE export.

EPIC #201 wave 75d. See ADR
``.vault/adr/2026-04-22-aeat-fichero-boe-export-adr.md`` §2-4 for
the design rationale.

Every concrete modelo module authors a tuple of
:class:`RecordFieldSpec` entries describing the BOE *Diseño de
registros* field layout. The encoders defined here produce the
byte-exact output the AEAT portal expects via "importar datos".
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# AEAT fichero-BOE canonical encoding — ISO-8859-15 since 2016 for
# every autónomo-core modelo (130/303/390). A future modelo using a
# different encoding would extend the ``encoding`` literal.
_FICHERO_BOE_ENCODING = "ISO-8859-15"


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
    )


def encode_currency(value: Decimal, *, length: int) -> bytes:
    """Right-justified, zero-padded currency with 2 implicit decimals.

    AEAT fichero-BOE currency fields emit the ``value * 100`` integer
    with no separators. A ``Decimal("1234.56")`` in a length-13
    currency field produces ``b"0000000123456"``.

    Negative values: two's-complement-style emission is NOT standard.
    Most modelos carry a sign-adjacent field (e.g. ``SIGNO``) that
    flips the magnitude. This encoder emits the ABSOLUTE magnitude
    and relies on the spec to carry the sign in a separate field.
    """
    # AEAT currency fields are always ``abs(value)`` with 2 implicit
    # decimals. Use quantize to avoid float drift.
    quantised = abs(value).quantize(Decimal("0.01"))
    cents = int(quantised * 100)
    s = str(cents).rjust(length, "0")
    if len(s) > length:
        raise ValueError(f"currency value {value} overflows length-{length} field (would need {len(s)} bytes)")
    return s.encode(_FICHERO_BOE_ENCODING)


def encode_text(
    value: str,
    *,
    length: int,
    justification: Justification = Justification.LEFT,
    pad_char: str = " ",
) -> bytes:
    """Alphanumeric encoder.

    Accents preserved within ISO-8859-15. If the value contains a
    character outside ISO-8859-15 (e.g. an emoji), this raises
    :class:`UnicodeEncodeError` at encode time — no silent
    substitution.
    """
    if len(pad_char) != 1:
        raise ValueError("pad_char must be a single character")
    s = value[:length] if len(value) > length else value
    s = s.ljust(length, pad_char) if justification is Justification.LEFT else s.rjust(length, pad_char)
    return s.encode(_FICHERO_BOE_ENCODING)


def encode_date(value: date, fmt: DateFmt) -> bytes:
    """Date encoder per BOE *Diseño de registros* shapes."""
    match fmt:
        case DateFmt.YYYYMMDD:
            return value.strftime("%Y%m%d").encode(_FICHERO_BOE_ENCODING)
        case DateFmt.DDMMYYYY:
            return value.strftime("%d%m%Y").encode(_FICHERO_BOE_ENCODING)
