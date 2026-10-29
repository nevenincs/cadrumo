"""Parse AEAT filed/exported declaration payloads through registry layouts."""

from __future__ import annotations

from collections.abc import Mapping

from ....core.casilla_id import CasillaId
from ....core.export_layout_format import ExportLayoutFormat
from ....core.filing_producer_key import FilingProducerKey
from ..export_field_kind import CasillaFieldKind
from .errors import RegistryValidationError
from .export_components import reconstruct_component_values
from .export_parse_models import ParsedExportFieldValue, ParsedExportPayload
from .export_value_policy import ParsedExportPolicyValue
from .export_xml_dictionary import parse_xml_dictionary_payload
from .fixed_width_codec import render_empty_block_slot
from .fixed_width_parser import parse_fixed_width_export_field
from .schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    FilingEnvelopeDefinition,
)
from .schema_references import SourceReference


def parse_export_payload(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    sources: Mapping[str, SourceReference] | None = None,
    source_payloads: Mapping[str, bytes] | None = None,
) -> ParsedExportPayload:
    """Validate exported bytes, including blank filler and declared record terminators."""
    return _parse_payload(layout, payload, sources=sources, source_payloads=source_payloads, filed=False)


def parse_filed_payload(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    sources: Mapping[str, SourceReference] | None = None,
    source_payloads: Mapping[str, bytes] | None = None,
) -> ParsedExportPayload:
    """Read downloaded filing evidence without treating AEAT annotations as export inputs.

    AEAT can return a compact envelope and populate its reserved filler slots.
    Preserve those slots' raw bytes but give them no semantic value. Compact
    framing is admitted only for a declared envelope without any CR or LF;
    mixed framing still has to satisfy every declared record terminator.
    Geometry, literal, numeric and envelope validation remain shared with export.
    """
    return _parse_payload(layout, payload, sources=sources, source_payloads=source_payloads, filed=True)


def _compact_filing_payload(layout: ExportLayoutDefinition, payload: bytes, filed: bool) -> bool:
    """Recognise a filed envelope with no declared record line endings in its bytes."""
    return filed and layout.filing_envelope is not None and b"\r" not in payload and b"\n" not in payload


def _payload_body(layout: ExportLayoutDefinition, payload: bytes) -> tuple[int, bytes]:
    """Locate the body after admitting the filing envelope or auxiliary header extent."""
    cursor = 0
    if layout.filing_envelope is not None:
        cursor, payload = _filing_envelope_body(layout.filing_envelope, payload)
    elif layout.auxiliary_envelope_header is not None:
        # The total-less page-zero header opens the payload ahead of the
        # records. Its bytes carry filing-instance facts (year, period,
        # product identity) this parser does not hold, so the skip is exact
        # extent rather than content re-derivation; a payload whose header is
        # absent or wrong-length misaligns every following record start and
        # still refuses on the records' own literals.
        cursor = layout.auxiliary_envelope_header.prefix_extent
    return cursor, payload


def _parse_payload(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
    filed: bool,
) -> ParsedExportPayload:
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        return parse_xml_dictionary_payload(layout, payload, sources=sources, source_payloads=source_payloads)

    compact = _compact_filing_payload(layout, payload, filed)
    cursor, payload = _payload_body(layout, payload)
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
            filed=filed,
            compact=compact,
        )
    trailing = payload[cursor:]
    if layout.filing_envelope is not None and trailing:
        raise RegistryValidationError(f"filing envelope has {len(trailing)} undeclared body byte(s) after its records")
    if trailing and trailing.strip(b"\r\n"):
        raise RegistryValidationError(f"payload has {len(payload) - cursor} trailing byte(s) after export layout")
    casillas = tuple(value for value in parsed if value.casilla_id is not None)
    return ParsedExportPayload(layout_id=layout.id, fields=tuple(parsed), casillas=casillas)


def _filing_envelope_body(envelope: FilingEnvelopeDefinition, payload: bytes) -> tuple[int, bytes]:
    """Return the body start and the payload without its closer, refusing a malformed envelope.

    The prefix carries filing-instance facts (year, period, product identity)
    this parser does not hold, so it is skipped by exact extent; the closer is
    derived from the payload's own opening tag and must end the payload, so a
    truncated or foreign envelope refuses instead of parsing as records.
    """
    if len(payload) < envelope.prefix_extent:
        raise RegistryValidationError(
            f"filing envelope {envelope.record_identity!r} payload is shorter than its "
            f"{envelope.prefix_extent}-byte prefix"
        )
    closer = envelope.closer_for(payload[: envelope.opening_tag_extent])
    if envelope.record_terminator == "crlf":
        if not payload.endswith(b"\r\n"):
            raise RegistryValidationError(
                f"filing envelope {envelope.record_identity!r} requires its source-declared CRLF terminator"
            )
        body_end = len(payload) - 2
    else:
        if payload.endswith((b"\r", b"\n")):
            raise RegistryValidationError(
                f"filing envelope {envelope.record_identity!r} has an undeclared trailing record terminator"
            )
        body_end = len(payload)
    if payload[body_end - len(closer) : body_end] != closer:
        raise RegistryValidationError(
            f"filing envelope {envelope.record_identity!r} payload does not end with its relative closer"
        )
    return envelope.prefix_extent, payload[: body_end - len(closer)]


def _consume_record_block(
    *,
    layout_id: str,
    record: ExportRecordDefinition,
    next_record: ExportRecordDefinition | None,
    payload: bytes,
    cursor: int,
    parsed: list[ParsedExportFieldValue],
    filed: bool,
    compact: bool,
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
            record_values, cursor = _read_record(layout_id, record, payload, cursor, filed=filed, compact=compact)
            parsed.extend(record_values)
        return cursor
    if not _matches_record_start(record, payload, cursor) and not record.required:
        return cursor
    record_values, cursor = _read_record(layout_id, record, payload, cursor, filed=filed, compact=compact)
    parsed.extend(record_values)
    return cursor


def _read_record(
    layout_id: str,
    record: ExportRecordDefinition,
    payload: bytes,
    cursor: int,
    *,
    filed: bool,
    compact: bool,
) -> tuple[tuple[ParsedExportFieldValue, ...], int]:
    record_length = _record_length(record.fields)
    record_bytes = payload[cursor : cursor + record_length]
    if len(record_bytes) != record_length:
        raise RegistryValidationError(
            f"payload ended before export record {record.id!r}; "
            f"expected {record_length} bytes, got {len(record_bytes)}",
        )
    try:
        record_text = record_bytes.decode(record.encoding)
    except UnicodeDecodeError as exc:
        raise RegistryValidationError(f"export record {record.id!r} is not {record.encoding!r}") from exc
    parsed = _parse_record_fields(layout_id, record.id, record_text, record.fields, filed=filed)
    cursor += record_length
    line_ending = b"" if compact else _line_ending_bytes(record.line_ending)
    if line_ending:
        ending = payload[cursor : cursor + len(line_ending)]
        if ending != line_ending:
            raise RegistryValidationError(f"export record {record.id!r} missing declared line ending")
        cursor += len(line_ending)
    return parsed, cursor


def _matches_record_start(record: ExportRecordDefinition | None, payload: bytes, cursor: int) -> bool:
    if record is None:
        return False
    record_text = _record_candidate_text(record, payload, cursor)
    if record_text is None:
        return False
    literals_match, matched_literal = _record_literals_match(record, record_text)
    if not literals_match:
        return False
    if record.discriminator is None:
        return matched_literal
    return _record_discriminator_matches(record, record_text)


def _record_candidate_text(
    record: ExportRecordDefinition,
    payload: bytes,
    cursor: int,
) -> str | None:
    """Decode the candidate record window, returning ``None`` for a non-match."""
    record_length = _record_length(record.fields)
    record_bytes = payload[cursor : cursor + record_length]
    if len(record_bytes) != record_length:
        return None
    try:
        record_text = record_bytes.decode(record.encoding)
    except UnicodeDecodeError:
        return None
    return record_text


def _record_literals_match(record: ExportRecordDefinition, record_text: str) -> tuple[bool, bool]:
    """Match every literal field and report success plus whether one was present."""
    matched_literal = False
    for field in record.fields:
        if field.kind != CasillaFieldKind.LITERAL or field.offset is None or field.length is None:
            continue
        matched_literal = True
        raw = record_text[field.offset - 1 : field.offset - 1 + field.length]
        try:
            parsed_literal = _parse_field_value(field, raw)
        except RegistryValidationError:
            return False, matched_literal
        if parsed_literal != field.literal:
            return False, matched_literal
    return True, matched_literal


def _record_discriminator_matches(record: ExportRecordDefinition, record_text: str) -> bool:
    """Match the optional record discriminator after literal fields pass."""
    discriminator = record.discriminator
    if discriminator is None:
        return False
    slice_start = discriminator.offset - 1
    slice_end = slice_start + discriminator.length
    discriminator_bytes = record_text[slice_start:slice_end]
    if len(discriminator_bytes) != discriminator.length:
        return False
    is_blank = all(char == " " for char in discriminator_bytes)
    if discriminator.requires == "blank" and not is_blank:
        return False
    # A discriminator is itself a record-identifying signal even when no
    # literal prefix is present.
    return not (discriminator.requires == "non_blank" and is_blank)


def _record_length(fields: tuple[ExportFieldDefinition, ...]) -> int:
    if not fields:
        return 0
    ranges: list[int] = []
    for field in fields:
        if field.offset is None or field.length is None:
            raise RegistryValidationError(f"export field {field.id!r} must declare offset and length")
        ranges.append(field.offset + field.length - 1)
    return max(ranges)


def _record_field_raw(field: ExportFieldDefinition, record_text: str) -> str:
    """Require a complete declared wire slot before interpreting its field policy."""
    if field.offset is None or field.length is None:
        raise RegistryValidationError(f"export field {field.id!r} must declare offset and length")
    start = field.offset - 1
    end = start + field.length
    raw = record_text[start:end]
    if len(raw) != field.length:
        raise RegistryValidationError(f"export field {field.id!r} ended before declared length")
    return raw


def _parse_record_fields(
    layout_id: str,
    record_id: str,
    record_text: str,
    fields: tuple[ExportFieldDefinition, ...],
    *,
    filed: bool,
) -> tuple[ParsedExportFieldValue, ...]:
    parsed: list[ParsedExportFieldValue] = []
    ordered_fields = tuple(sorted(fields, key=lambda item: item.offset or 0))
    empty_blocks = _empty_occurrence_blocks(record_text, ordered_fields)
    for field in ordered_fields:
        raw = _record_field_raw(field, record_text)
        value: ParsedExportPolicyValue
        if filed and field.kind == CasillaFieldKind.FILLER:
            value = None
        elif field.required_with is not None and field.required_with in empty_blocks:
            if raw != render_empty_block_slot(field):
                raise RegistryValidationError(
                    f"export field {field.id!r} carries data inside an occurrence block with no anchor",
                )
            value = None
        else:
            value = _parse_field_value(field, raw)
        if field.kind == CasillaFieldKind.LITERAL and value != field.literal:
            raise RegistryValidationError(f"export literal field {field.id!r} does not match the registry layout")
        parsed.append(
            ParsedExportFieldValue(
                record_id=record_id,
                field_id=field.id,
                casilla_id=field.casilla_id,
                binding_id=field.binding,
                raw=raw,
                value=value,
                source_locator=f"{layout_id}:{record_id}:{field.id}:{field.offset}:{field.length}",
            ),
        )
    reconstruct_component_values(ordered_fields, parsed)
    return tuple(parsed)


def _empty_occurrence_blocks(
    record_text: str,
    fields: tuple[ExportFieldDefinition, ...],
) -> frozenset[CasillaId]:
    """Return the anchors of the record's occurrence blocks whose anchor holds its blank fill.

    An empty block carries no occurrence, so its campos are read as absent rather
    than parsed against the requirement the design states for an occurrence.
    """
    anchors = {field.required_with for field in fields if field.required_with is not None}
    empty: set[CasillaId] = set()
    for field in fields:
        if field.casilla_id not in anchors or field.offset is None or field.length is None:
            continue
        raw = record_text[field.offset - 1 : field.offset - 1 + field.length]
        if raw == render_empty_block_slot(field):
            empty.add(field.casilla_id)
    return frozenset(empty)


def _parse_field_value(
    field: ExportFieldDefinition,
    raw: str,
) -> ParsedExportPolicyValue:
    if field.producer_key is FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA and "aeat-dr-369-2021" in field.source_refs:
        # DR369 v1.1 declares this mandatory byte as [blank | constant "C"].
        # Preserve the ordinary-return blank as its actual text token rather
        # than converting it to None, which would fail required-slot replay.
        if field.data_type != "text" or field.length != 1 or raw not in {" ", "C"}:
            raise RegistryValidationError("Modelo 369 complementaria must contain exactly C or one ASCII space")
        return raw
    return parse_fixed_width_export_field(field, raw)


def _line_ending_bytes(line_ending: str) -> bytes:
    if line_ending == "crlf":
        return b"\r\n"
    if line_ending == "lf":
        return b"\n"
    return b""


__all__ = ["parse_export_payload", "parse_filed_payload"]
