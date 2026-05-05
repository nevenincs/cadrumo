"""Parse AEAT filed/exported declaration payloads through registry layouts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ._errors import RegistryValidationError
from ._schema import ExportFieldDefinition, ExportLayoutDefinition, RegistryModel

_MONEY_SCALE = Decimal("100")


class ParsedExportFieldValue(RegistryModel):
    """One field value read from an AEAT payload using a registry export field."""

    record_id: str
    field_id: str
    casilla_id: str | None = None
    raw: str
    value: Decimal | str | bool | None
    source_locator: str


class ParsedExportPayload(RegistryModel):
    """Casilla and field values parsed from a complete registry export layout."""

    layout_id: str
    fields: tuple[ParsedExportFieldValue, ...]
    casillas: tuple[ParsedExportFieldValue, ...]


def parse_export_payload(layout: ExportLayoutDefinition, payload: bytes) -> ParsedExportPayload:
    """Parse a complete AEAT payload according to a registry export layout."""

    cursor = 0
    parsed: list[ParsedExportFieldValue] = []
    for record in sorted(layout.records, key=lambda item: item.order):
        record_length = _record_length(record.fields)
        record_bytes = payload[cursor : cursor + record_length]
        if len(record_bytes) != record_length:
            raise RegistryValidationError(
                f"payload ended before export record {record.id!r}; "
                f"expected {record_length} bytes, got {len(record_bytes)}"
            )
        try:
            record_text = record_bytes.decode(record.encoding)
        except UnicodeDecodeError as exc:
            raise RegistryValidationError(f"export record {record.id!r} is not {record.encoding!r}") from exc
        parsed.extend(_parse_record_fields(layout.id, record.id, record_text, record.fields))
        cursor += record_length
        line_ending = _line_ending_bytes(record.line_ending)
        if line_ending:
            ending = payload[cursor : cursor + len(line_ending)]
            if ending != line_ending:
                raise RegistryValidationError(f"export record {record.id!r} missing declared line ending")
            cursor += len(line_ending)
    if cursor != len(payload):
        raise RegistryValidationError(f"payload has {len(payload) - cursor} trailing byte(s) after export layout")
    casillas = tuple(value for value in parsed if value.casilla_id is not None)
    return ParsedExportPayload(layout_id=layout.id, fields=tuple(parsed), casillas=casillas)


def _record_length(fields: tuple[ExportFieldDefinition, ...]) -> int:
    if not fields:
        return 0
    ranges: list[int] = []
    for field in fields:
        if field.offset is None or field.length is None:
            raise RegistryValidationError(f"export field {field.id!r} must declare offset and length")
        ranges.append(field.offset + field.length - 1)
    return max(ranges)


def _parse_record_fields(
    layout_id: str,
    record_id: str,
    record_text: str,
    fields: tuple[ExportFieldDefinition, ...],
) -> tuple[ParsedExportFieldValue, ...]:
    parsed: list[ParsedExportFieldValue] = []
    for field in sorted(fields, key=lambda item: item.offset or 0):
        if field.offset is None or field.length is None:
            raise RegistryValidationError(f"export field {field.id!r} must declare offset and length")
        start = field.offset - 1
        end = start + field.length
        raw = record_text[start:end]
        if len(raw) != field.length:
            raise RegistryValidationError(f"export field {field.id!r} ended before declared length")
        value = _parse_field_value(field, raw)
        if field.kind == "literal" and value != field.literal:
            raise RegistryValidationError(f"export literal field {field.id!r} does not match the registry layout")
        parsed.append(
            ParsedExportFieldValue(
                record_id=record_id,
                field_id=field.id,
                casilla_id=field.casilla,
                raw=raw,
                value=value,
                source_locator=f"{layout_id}:{record_id}:{field.id}:{field.offset}:{field.length}",
            )
        )
    return tuple(parsed)


def _parse_field_value(field: ExportFieldDefinition, raw: str) -> Decimal | str | bool | None:
    if field.kind == "filler":
        return None
    if field.data_type == "money":
        return _parse_money(field, raw)
    if field.data_type == "integer":
        return _parse_integer(field, raw)
    if field.data_type == "decimal":
        return _parse_decimal(field, raw)
    if field.data_type == "boolean":
        return _parse_boolean(raw)
    value = raw.strip()
    return value if value else None


def _parse_money(field: ExportFieldDefinition, raw: str) -> Decimal:
    negative = raw.startswith("N")
    if negative and not field.signed:
        raise RegistryValidationError(f"unsigned export field {field.id!r} contains a negative amount")
    digits = raw[1:] if negative else raw
    digits = digits.strip()
    if not digits:
        return Decimal("0")
    if not digits.isdigit():
        raise RegistryValidationError(f"money export field {field.id!r} contains non-digit data")
    amount = Decimal(int(digits)) / _MONEY_SCALE
    return -amount if negative else amount


def _parse_integer(field: ExportFieldDefinition, raw: str) -> Decimal:
    text = raw.strip()
    if not text:
        return Decimal("0")
    if not text.isdigit():
        raise RegistryValidationError(f"integer export field {field.id!r} contains non-digit data")
    return Decimal(int(text))


def _parse_decimal(field: ExportFieldDefinition, raw: str) -> Decimal:
    text = raw.strip().replace(",", ".")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise RegistryValidationError(f"decimal export field {field.id!r} contains invalid decimal data") from exc


def _parse_boolean(raw: str) -> bool | None:
    text = raw.strip().upper()
    if not text:
        return None
    if text in {"X", "1", "S", "SI", "TRUE"}:
        return True
    if text in {"0", "N", "NO", "FALSE"}:
        return False
    raise RegistryValidationError("boolean export field contains invalid data")


def _line_ending_bytes(line_ending: str) -> bytes:
    if line_ending == "crlf":
        return b"\r\n"
    if line_ending == "lf":
        return b"\n"
    return b""


__all__ = [
    "ParsedExportFieldValue",
    "ParsedExportPayload",
    "parse_export_payload",
]
