"""Fichero-BOE deserialiser (EPIC #201 C3d, wave 80a).

Round-trip inverse of :func:`aeat.submission._formats._serialise.serialise`.
Takes a fichero-BOE byte payload + a `_RECORD_SPECS` tuple and yields
a ``ParsedRecord`` carrying the per-field values (as strings or
:class:`Decimal` for currency) plus metadata.

This is the primary verification hook for issue #239 (Kent can
prove his exported numbers match AEAT's record): the serialiser
produces bytes, the deserialiser parses bytes back, and a diff
over casilla values is a one-line operation. Round-trip fidelity
is the wave-80b / C3d acceptance test.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ._record_spec import (
    DateFmt,
    FicheroBoeEncoding,
    FieldKind,
    RecordFieldSpec,
)


class ParsedRecord(BaseModel):
    """Typed result of parsing a fichero-BOE record.

    Each field value is keyed by ``field_id``; currency fields also
    appear in :attr:`casilla_values` keyed by ``casilla_id`` for
    easy cross-reference against :class:`aeat.filing.FilingDraft`.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    field_values: Mapping[str, str | Decimal | date]
    """Every field_id mapped to its parsed value."""

    casilla_values: Mapping[str, Decimal]
    """Casilla-keyed currency values (subset of field_values)."""

    raw_length: Annotated[int, Field(ge=0)]
    """Byte length of the parsed content (excluding CRLF)."""


_CRLF = b"\r\n"


def _decode_currency(raw: bytes) -> Decimal:
    """Decode a zero-padded cents string into a 2-decimal Decimal.

    Inverse of :func:`encode_currency` for unsigned magnitudes. Sign
    must be reconstructed by the caller from an adjacent SIGNO/TIPO
    field (see the Modelo 130 ``TIPO_DECLARACION`` pattern).
    """
    text = raw.decode("ascii").strip()
    if not text:
        return Decimal("0.00")
    cents = int(text)
    # ``cents / 100`` would introduce float drift; build the Decimal
    # directly to preserve arbitrary precision.
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def _decode_date(raw: bytes, fmt: DateFmt) -> date:
    text = raw.decode("ascii").strip()
    match fmt:
        case DateFmt.YYYYMMDD:
            return datetime.strptime(text, "%Y%m%d").date()
        case DateFmt.DDMMYYYY:
            return datetime.strptime(text, "%d%m%Y").date()


def deserialise(
    payload: bytes,
    *,
    specs: tuple[RecordFieldSpec, ...],
    encoding: FicheroBoeEncoding,
    total_length: int,
) -> ParsedRecord:
    """Parse a fichero-BOE byte payload into a :class:`ParsedRecord`.

    Args:
        payload: full on-wire byte sequence (content + optional CRLF).
        specs: the ordered :class:`RecordFieldSpec` tuple.
        encoding: wire encoding matching the serialiser's choice.
        total_length: expected content-byte count (excludes CRLF).

    Returns:
        :class:`ParsedRecord` with field and casilla values.

    Raises:
        ValueError: on length mismatch, literal mismatch, or decode
            errors (unparseable date, non-ASCII currency, etc.).
    """
    # Strip any trailing CRLF so we can parse either an on-wire
    # stream (content + CRLF) or already-stripped content bytes.
    body = payload[: -len(_CRLF)] if payload.endswith(_CRLF) else payload
    if len(body) != total_length:
        raise ValueError(
            f"payload content is {len(body)} bytes but total_length={total_length} "
            f"was declared; likely wrong modelo spec or corrupted stream."
        )

    field_values: dict[str, str | Decimal | date] = {}
    casilla_values: dict[str, Decimal] = {}

    for spec in specs:
        start = spec.offset - 1  # 1-based → 0-based slice
        end = start + spec.length
        raw = body[start:end]
        if len(raw) != spec.length:
            raise ValueError(
                f"field {spec.field_id!r} expects {spec.length} bytes "
                f"at offset {spec.offset}; got {len(raw)} — payload too short?"
            )

        match spec.kind:
            case FieldKind.RESERVED:
                assert spec.literal_value is not None
                expected = spec.literal_value.encode(encoding).ljust(spec.length, b" ")
                if raw != expected and raw != spec.literal_value.encode(encoding):
                    raise ValueError(f"RESERVED field {spec.field_id!r} expected {spec.literal_value!r}; got {raw!r}")
                field_values[spec.field_id] = spec.literal_value

            case FieldKind.CURRENCY:
                value = _decode_currency(raw)
                field_values[spec.field_id] = value
                if spec.casilla_id is not None:
                    casilla_values[spec.casilla_id] = value

            case FieldKind.DATE:
                assert spec.date_fmt is not None
                field_values[spec.field_id] = _decode_date(raw, spec.date_fmt)

            case FieldKind.ALPHANUMERIC | FieldKind.NUMERIC:
                # Preserve right-side padding stripped per justification.
                text = raw.decode(encoding)
                # Strip the pad char only on the padded side to preserve
                # intentional inner whitespace.
                if spec.pad_char == " ":
                    text = text.rstrip(" ") if spec.justification.value == "left" else text.lstrip(" ")
                elif spec.pad_char == "0":
                    text = text.rstrip("0") if spec.justification.value == "left" else text.lstrip("0")
                    # Edge case: a field whose canonical value IS all zeros
                    # (e.g., "0000") would be stripped to empty string.
                    # Normalize to "0" for downstream consistency.
                    if text == "":
                        text = "0"
                field_values[spec.field_id] = text

    return ParsedRecord(
        field_values=field_values,
        casilla_values=casilla_values,
        raw_length=len(body),
    )


__all__ = ["ParsedRecord", "deserialise"]
