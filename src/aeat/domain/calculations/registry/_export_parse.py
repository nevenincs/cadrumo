"""Parse AEAT filed/exported declaration payloads through registry layouts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from ....core.external_constants import LATIN_1_ENCODING as _LATIN_1_ENCODING
from ....core.parsing._utils import _parse_bool as _core_parse_bool
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId, ExportFieldId, ExportLayoutId, RecordId
from ._schema import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    RegistryModel,
    SourceReference,
)

_MONEY_SCALE = Decimal("100")
_DICTIONARY_LINE_RE = re.compile(
    r"^(?P<field>[^=#]+)=\[(?P<path>[^\]]*)\]\[(?P<type>[^\]]*)\]\[(?P<casilla>[^\]]*)\]\[(?P<label>.*)\]$"
)


class ParsedExportFieldValue(RegistryModel):
    """One field value read from an AEAT payload using a registry export field."""

    record_id: RecordId
    field_id: ExportFieldId
    casilla_id: CasillaId | None = None
    binding_id: BindingId | None = None
    raw: str
    value: Decimal | str | bool | None
    source_locator: str


class ParsedExportPayload(RegistryModel):
    """Casilla and field values parsed from a complete registry export layout."""

    layout_id: ExportLayoutId
    fields: tuple[ParsedExportFieldValue, ...]
    casillas: tuple[ParsedExportFieldValue, ...]


@dataclass(frozen=True)
class _XmlDictionaryEntry:
    field_id: str
    path: str
    data_type: str
    casilla_id: str | None


def parse_export_payload(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    source_root: Path | None = None,
    sources: Mapping[str, SourceReference] | None = None,
) -> ParsedExportPayload:
    """Parse a complete AEAT payload and return a :class:`ParsedExportPayload`."""
    if layout.format == "xml_dictionary":
        return _parse_xml_dictionary_payload(layout, payload, source_root=source_root, sources=sources)

    cursor = 0
    parsed: list[ParsedExportFieldValue] = []
    records = tuple(sorted(layout.records, key=lambda item: item.order))
    for index, record in enumerate(records):
        next_record = records[index + 1] if index + 1 < len(records) else None
        cursor = _consume_record_block(
            layout_id=layout.id,
            record=record,
            next_record=next_record,
            payload=payload,
            cursor=cursor,
            parsed=parsed,
        )
    trailing = payload[cursor:]
    if trailing and trailing.strip(b"\r\n"):
        raise RegistryValidationError(f"payload has {len(payload) - cursor} trailing byte(s) after export layout")
    casillas = tuple(value for value in parsed if value.casilla_id is not None)
    return ParsedExportPayload(layout_id=layout.id, fields=tuple(parsed), casillas=casillas)


def _consume_record_block(
    *,
    layout_id: str,
    record: ExportRecordDefinition,
    next_record: ExportRecordDefinition | None,
    payload: bytes,
    cursor: int,
    parsed: list[ParsedExportFieldValue],
) -> int:
    """Consume zero or more instances of ``record`` from ``payload`` at ``cursor``.

    Three record shapes:

    * ``repeat == "binding_rows"`` — read records repeatedly until
      the payload exhausts or the next record's start marker is
      reached.
    * unmatched optional — skipped.
    * unmatched required, or matched once — read exactly once.

    Returns the updated cursor; appends ``ParsedExportFieldValue``s
    into ``parsed`` in place to preserve allocation shape.
    """
    if record.repeat == "binding_rows":
        while cursor < len(payload) and not _matches_record_start(next_record, payload, cursor):
            record_values, cursor = _read_record(layout_id, record, payload, cursor)
            parsed.extend(record_values)
        return cursor
    if not _matches_record_start(record, payload, cursor) and not record.required:
        return cursor
    record_values, cursor = _read_record(layout_id, record, payload, cursor)
    parsed.extend(record_values)
    return cursor


def _parse_xml_dictionary_payload(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    source_root: Path | None,
    sources: Mapping[str, SourceReference] | None,
) -> ParsedExportPayload:
    entries = _load_xml_dictionary_entries(layout, source_root=source_root, sources=sources)
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise RegistryValidationError(f"XML export layout {layout.id!r} could not parse payload") from exc

    parsed: list[ParsedExportFieldValue] = []
    for entry in entries:
        for index, element in enumerate(_find_xml_path(root, entry.path), start=1):
            raw = (element.text or "").strip()
            if not raw:
                continue
            parsed.append(
                ParsedExportFieldValue(
                    record_id="xml",
                    field_id=entry.field_id,
                    casilla_id=entry.casilla_id,
                    raw=raw,
                    value=_parse_xml_dictionary_value(entry.data_type, raw),
                    source_locator=f"{layout.id}:{entry.path}:{index}",
                )
            )
    casillas = tuple(value for value in parsed if value.casilla_id is not None)
    return ParsedExportPayload(layout_id=layout.id, fields=tuple(parsed), casillas=casillas)


def _load_xml_dictionary_entries(
    layout: ExportLayoutDefinition,
    *,
    source_root: Path | None,
    sources: Mapping[str, SourceReference] | None,
) -> tuple[_XmlDictionaryEntry, ...]:
    if layout.dictionary_source_ref is None:
        raise RegistryValidationError(f"XML export layout {layout.id!r} has no dictionary source")
    if source_root is None or sources is None:
        raise RegistryValidationError(f"XML export layout {layout.id!r} requires source_root and sources")
    source = sources.get(str(layout.dictionary_source_ref))
    if source is None:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} has unresolved dictionary source {layout.dictionary_source_ref!r}"
        )
    dictionary_path = source_root / Path(source.corpus_path)
    entries: list[_XmlDictionaryEntry] = []
    for line in _read_dictionary_text(dictionary_path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _DICTIONARY_LINE_RE.match(stripped)
        if match is None:
            continue
        casilla_id = _normalize_dictionary_casilla(match["casilla"])
        entries.append(
            _XmlDictionaryEntry(
                field_id=match["field"].strip(),
                path=match["path"].strip(),
                data_type=match["type"].strip(),
                casilla_id=casilla_id,
            )
        )
    if not entries:
        raise RegistryValidationError(f"XML export layout {layout.id!r} dictionary has no parseable entries")
    return tuple(entries)


def _read_dictionary_text(path: Path) -> str:
    stat = path.stat()
    return _read_dictionary_text_cached(str(path.expanduser().resolve()), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _read_dictionary_text_cached(path: str, byte_count: int, modified_ns: int) -> str:
    del byte_count, modified_ns
    body = Path(path).read_bytes()
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode(_LATIN_1_ENCODING)


def _normalize_dictionary_casilla(value: str) -> str | None:
    text = value.strip()
    if not text or text.startswith("*"):
        return None
    return text if text.isdigit() else None


def _find_xml_path(root: Element[str], absolute_path: str) -> tuple[Element[str], ...]:
    parts = tuple(part for part in absolute_path.strip("/").split("/") if part)
    if not parts:
        return ()
    current: tuple[Element[str], ...] = (root,)
    for index, part in enumerate(parts):
        if index == 0 and len(current) == 1 and _local_name(current[0].tag) == part:
            continue
        next_elements: list[Element[str]] = []
        for element in current:
            next_elements.extend(child for child in element if _local_name(child.tag) == part)
        current = tuple(next_elements)
        if not current:
            return ()
    return current


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml_dictionary_value(data_type: str, raw: str) -> Decimal | str | bool | None:
    normalized = data_type.upper()
    if normalized.startswith(("N", "P")):
        return _parse_xml_decimal(raw)
    if normalized.startswith("L"):
        return _parse_boolean(raw)
    return raw


def _parse_xml_decimal(raw: str) -> Decimal:
    text = raw.strip().replace(",", ".")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise RegistryValidationError("XML dictionary numeric value contains invalid decimal data") from exc


def _read_record(
    layout_id: str,
    record: ExportRecordDefinition,
    payload: bytes,
    cursor: int,
) -> tuple[tuple[ParsedExportFieldValue, ...], int]:
    record_length = _record_length(record.fields)
    record_bytes = payload[cursor : cursor + record_length]
    if len(record_bytes) != record_length:
        raise RegistryValidationError(
            f"payload ended before export record {record.id!r}; expected {record_length} bytes, got {len(record_bytes)}"
        )
    try:
        record_text = record_bytes.decode(record.encoding)
    except UnicodeDecodeError as exc:
        raise RegistryValidationError(f"export record {record.id!r} is not {record.encoding!r}") from exc
    parsed = _parse_record_fields(layout_id, record.id, record_text, record.fields)
    cursor += record_length
    line_ending = _line_ending_bytes(record.line_ending)
    if line_ending:
        ending = payload[cursor : cursor + len(line_ending)]
        if ending != line_ending:
            raise RegistryValidationError(f"export record {record.id!r} missing declared line ending")
        cursor += len(line_ending)
    return parsed, cursor


def _matches_record_start(record: ExportRecordDefinition | None, payload: bytes, cursor: int) -> bool:
    if record is None:
        return False
    record_length = _record_length(record.fields)
    record_bytes = payload[cursor : cursor + record_length]
    if len(record_bytes) != record_length:
        return False
    try:
        record_text = record_bytes.decode(record.encoding)
    except UnicodeDecodeError:
        return False
    matched_literal = False
    for field in record.fields:
        if field.kind != "literal" or field.offset is None or field.length is None:
            continue
        matched_literal = True
        raw = record_text[field.offset - 1 : field.offset - 1 + field.length]
        if _parse_field_value(field, raw) != field.literal:
            return False
    if record.discriminator is not None:
        slice_start = record.discriminator.offset - 1
        slice_end = slice_start + record.discriminator.length
        discriminator_bytes = record_text[slice_start:slice_end]
        if len(discriminator_bytes) != record.discriminator.length:
            return False
        is_blank = all(char == " " for char in discriminator_bytes)
        if record.discriminator.requires == "blank" and not is_blank:
            return False
        # A discriminator is itself a record-identifying signal even when no
        # literal prefix is present.
        return not (record.discriminator.requires == "non_blank" and is_blank)
    return matched_literal


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
                binding_id=field.binding,
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
        return _parse_decimal(raw, field)
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


def _parse_decimal(raw: str, field: ExportFieldDefinition) -> Decimal:
    text = raw.strip().replace(",", ".")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise RegistryValidationError(f"decimal export field {field.id!r} contains invalid decimal data") from exc


_REGISTRY_TRUTHY = frozenset({"x", "1", "s", "si", "true"})
_REGISTRY_FALSY = frozenset({"0", "n", "no", "false"})


def _parse_boolean(raw: str) -> bool | None:
    """Thin wrapper around :func:`aeat.core.parsing._utils._parse_bool`.

    The registry export format uses uppercase affirmative tokens ("X", "S",
    "SI") that extend the core truthy set.  This wrapper normalises the raw
    string to lowercase before delegating so the core helper can match them.
    The local registry-specific sets are passed implicitly through the
    module-level constants; the core helper's generic sets are bypassed in
    favour of these registry-aware ones so that unrecognised tokens raise a
    typed :class:`RegistryValidationError` rather than silently returning
    ``None``.
    """
    if not raw or not raw.strip():
        return None
    token = raw.strip().lower()
    if token in _REGISTRY_TRUTHY:
        return True
    if token in _REGISTRY_FALSY:
        return False
    # Delegate to core for any token the registry sets don't cover so the
    # core helper's debug logging fires before we raise.
    result = _core_parse_bool(raw)
    if result is not None:
        return result
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
