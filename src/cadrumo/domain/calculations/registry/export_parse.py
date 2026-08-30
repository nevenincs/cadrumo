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

from ....core import ExportLayoutFormat
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.decimal import normalize_decimal_separators
from ....core.external_constants import LATIN_1_ENCODING as _LATIN_1_ENCODING
from ....core.paths import path_stat_fingerprint
from ..export_field_kind import CasillaFieldKind
from .errors import RegistryValidationError
from .export_value_policy import ParsedExportPolicyValue
from .fixed_width_codec import parse_fixed_width_export_field
from .ids import BindingId, ExportFieldId, ExportLayoutId, RecordId
from .schema_base import RegistryModel
from .schema_exports import ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition
from .schema_references import SourceReference

# The dictionary's two boolean row types. ``LGC`` resolves to the XSD's
# ``tipo_logico`` (``0``/``1``) and ``S_N`` to ``tipo_SINO_Exclusivo``
# (``NO``/``SI``); the tokens differ but both rows carry a boolean. Public: this
# is the one canonical declaration of the vocabulary. The application-layer XML
# dictionary renderer (``_export_xml_dictionary.py``) shares the exact same two
# type codes for the write direction and imports them through this package's
# facade rather than re-declaring its own copy.
LOGICAL_DICTIONARY_TYPE = "LGC"
SINO_DICTIONARY_TYPE = "S_N"
# Named as a set rather than matched by prefix so a future type code beginning
# with the same letter is not silently read as a boolean.
XML_DICTIONARY_BOOLEAN_TYPES = frozenset({LOGICAL_DICTIONARY_TYPE, SINO_DICTIONARY_TYPE})
_DICTIONARY_LINE_RE = re.compile(
    r"^(?P<field>[^=#]+)=\[(?P<path>[^\]]*)\]\[(?P<type>[^\]]*)\]\[(?P<casilla>[^\]]*)\]\[(?P<label>.*)\]$",
)
_DICTIONARY_NUMERIC_CASILLA_ID_RE = re.compile(r"^\d+$")
_DICTIONARY_LETTER_CASILLA_ID_RE = re.compile(r"^[A-Z]$")


class ParsedExportFieldValue(RegistryModel):
    """One field value read from an AEAT payload using a registry export field."""

    record_id: RecordId
    field_id: ExportFieldId
    casilla_id: CasillaId | None = None
    binding_id: BindingId | None = None
    raw: str
    value: ParsedExportPolicyValue
    source_locator: str


class ParsedExportPayload(RegistryModel):
    """Casilla and field values parsed from a complete registry export layout."""

    layout_id: ExportLayoutId
    fields: tuple[ParsedExportFieldValue, ...]
    casillas: tuple[ParsedExportFieldValue, ...]


@dataclass(frozen=True, slots=True)
class XmlDictionaryEntry:
    """One field mapping from an official AEAT XML dictionary source."""

    field_id: str
    path: str
    data_type: str
    casilla_id: CasillaId | None


def parse_export_payload(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    source_root: Path | None = None,
    sources: Mapping[str, SourceReference] | None = None,
) -> ParsedExportPayload:
    """Parse a complete AEAT payload and return a :class:`ParsedExportPayload`."""
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        return _parse_xml_dictionary_payload(layout, payload, source_root=source_root, sources=sources)

    cursor = 0
    if layout.auxiliary_envelope_header is not None:
        # The total-less page-zero header opens the payload ahead of the
        # records. Its bytes carry filing-instance facts (year, period,
        # product identity) this parser does not hold, so the skip is exact
        # extent rather than content re-derivation; a payload whose header is
        # absent or wrong-length misaligns every following record start and
        # still refuses on the records' own literals.
        cursor = layout.auxiliary_envelope_header.prefix_extent
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
    entries = xml_dictionary_entries(layout, source_root=source_root, sources=sources)
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
                ),
            )
    casillas = tuple(value for value in parsed if value.casilla_id is not None)
    return ParsedExportPayload(layout_id=layout.id, fields=tuple(parsed), casillas=casillas)


def _xml_dictionary_source(
    layout: ExportLayoutDefinition,
    *,
    source_root: Path | None,
    sources: Mapping[str, SourceReference] | None,
) -> tuple[SourceReference, Path]:
    if layout.dictionary_source_ref is None:
        raise RegistryValidationError(f"XML export layout {layout.id!r} has no dictionary source")
    if source_root is None or sources is None:
        raise RegistryValidationError(f"XML export layout {layout.id!r} requires source_root and sources")
    source = sources.get(str(layout.dictionary_source_ref))
    if source is None:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} has unresolved dictionary source {layout.dictionary_source_ref!r}",
        )
    return source, source_root / Path(source.corpus_path)


def _parse_xml_dictionary_line(
    line: str,
    *,
    source: SourceReference,
    overrides: Mapping[str, str],
) -> XmlDictionaryEntry | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = _DICTIONARY_LINE_RE.match(stripped)
    if match is None:
        return None
    casilla_id = _parse_dictionary_casilla_id(
        match["casilla"],
        allow_letter_id=source.supports_single_uppercase_letter_casilla_ids,
    )
    field_id = match["field"].strip()
    return XmlDictionaryEntry(
        field_id=field_id,
        path=overrides.get(field_id, match["path"].strip()),
        data_type=match["type"].strip(),
        casilla_id=casilla_id,
    )


def xml_dictionary_entries(
    layout: ExportLayoutDefinition,
    *,
    source_root: Path | None,
    sources: Mapping[str, SourceReference] | None,
) -> tuple[XmlDictionaryEntry, ...]:
    """Resolve official AEAT XML dictionary :class:`XmlDictionaryEntry` rows for ``layout``."""
    source, dictionary_path = _xml_dictionary_source(layout, source_root=source_root, sources=sources)
    # Applied here rather than at either consumer: the renderer and
    # :func:`parse_export_payload` both resolve their rows from this call, so a
    # correction reaching only one of them would make an exported artefact
    # verify as drift against itself.
    overrides = {override.field_id: override.path for override in layout.dictionary_path_overrides}
    entries: list[XmlDictionaryEntry] = []
    for line in _read_dictionary_text(dictionary_path).splitlines():
        entry = _parse_xml_dictionary_line(line, source=source, overrides=overrides)
        if entry is not None:
            entries.append(entry)
    if not entries:
        raise RegistryValidationError(f"XML export layout {layout.id!r} dictionary has no parseable entries")
    _assert_every_override_was_applied(layout, entries)
    return tuple(entries)


def _assert_every_override_was_applied(
    layout: ExportLayoutDefinition,
    entries: list[XmlDictionaryEntry],
) -> None:
    """Refuse an override naming a field this dictionary does not carry.

    An override is a claim that a specific published row is wrong. If the row is
    absent -- a typo, or a revision where AEAT never declared the field -- the
    correction silently applies to nothing and the defect it was written for goes
    on shipping, with a declaration in the registry that reads as if it were
    fixed. Refusing at read time makes that impossible to leave in place.
    """
    declared = {entry.field_id for entry in entries}
    unmatched = sorted(
        override.field_id for override in layout.dictionary_path_overrides if override.field_id not in declared
    )
    if unmatched:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} declares dictionary path overrides for {unmatched!r}, "
            "which the official dictionary does not declare, so the correction would apply to nothing",
        )


def _read_dictionary_text(path: Path) -> str:
    resolved = path.expanduser().resolve()
    return _read_dictionary_text_cached(*path_stat_fingerprint(resolved))


@lru_cache(maxsize=256)
def _read_dictionary_text_cached(path: str, byte_count: int, modified_ns: int) -> str:
    del byte_count, modified_ns
    body = Path(path).read_bytes()
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode(_LATIN_1_ENCODING)


def _parse_dictionary_casilla_id(value: str, *, allow_letter_id: bool = False) -> CasillaId | None:
    """Return the exact official casilla identifier a dictionary row declares.

    Official dictionaries print decimal box numbers, and some reviewed sources
    additionally publish one-uppercase-letter annex boxes. ``###`` and ``*``
    rows are explicit non-casilla placeholders. The source's typed grammar
    capability, declared alongside its digest-pinned corpus identity and
    temporal applicability, is the one authority that admits the extension; a
    numeric-only source cannot smuggle an unevidenced identifier in.

    The parser preserves the published spelling: it does not fold case,
    normalize arbitrary alphanumeric labels, or manufacture an identifier from a
    source-row placeholder.
    """
    text = value.strip()
    if not text or text.startswith("*"):
        return None
    is_numeric = _DICTIONARY_NUMERIC_CASILLA_ID_RE.fullmatch(text) is not None
    is_grounded_letter = allow_letter_id and _DICTIONARY_LETTER_CASILLA_ID_RE.fullmatch(text) is not None
    if not is_numeric and not is_grounded_letter:
        return None
    return validated_casilla_id(text, surface="XML dictionary casilla id")


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
    """Read one dictionary value back as the type its row declares.

    Both boolean row types are read as booleans. They differ only in the tokens
    AEAT spells them with -- ``LGC`` rows carry ``0``/``1`` and ``S_N`` rows carry
    ``NO``/``SI`` -- which is a spelling difference, not a difference in what the
    row means. Reading one as a boolean and the other as text made the two halves
    of this boundary disagree about an ``S_N`` row: the writer emitted a marker
    for a boolean casilla and the reader handed back a string, so a comparison
    against the draft saw ``True`` on one side and ``"SI"`` on the other and
    reported drift on a file that matched.
    """
    normalized = data_type.upper()
    if normalized.startswith(("N", "P")):
        return _parse_xml_decimal(raw)
    if normalized in XML_DICTIONARY_BOOLEAN_TYPES:
        return _parse_xml_boolean(normalized, raw)
    return raw


def _parse_xml_decimal(raw: str) -> Decimal:
    text = normalize_decimal_separators(raw.strip(), strip_thousands=False)
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
            f"payload ended before export record {record.id!r}; "
            f"expected {record_length} bytes, got {len(record_bytes)}",
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
        if field.kind != CasillaFieldKind.LITERAL or field.offset is None or field.length is None:
            continue
        matched_literal = True
        raw = record_text[field.offset - 1 : field.offset - 1 + field.length]
        try:
            parsed_literal = _parse_field_value(field, raw)
        except RegistryValidationError:
            return False
        if parsed_literal != field.literal:
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
    return tuple(parsed)


def _parse_field_value(
    field: ExportFieldDefinition,
    raw: str,
) -> ParsedExportPolicyValue:
    return parse_fixed_width_export_field(field, raw)


_XML_BOOLEAN_TOKENS = {
    LOGICAL_DICTIONARY_TYPE: {"1": True, "0": False},
    SINO_DICTIONARY_TYPE: {"si": True, "no": False},
}


def _parse_xml_boolean(data_type: str, raw: str) -> bool | None:
    """Parse the official XML-dictionary boolean vocabulary only."""
    if not raw or not raw.strip():
        return None
    normalized = data_type.upper()
    tokens = _XML_BOOLEAN_TOKENS.get(normalized)
    if tokens is None:
        raise RegistryValidationError(f"unsupported XML dictionary boolean data type {data_type!r}")
    token = raw.strip().lower()
    try:
        return tokens[token]
    except KeyError as exc:
        raise RegistryValidationError(
            f"XML dictionary boolean field {normalized!r} contains invalid data",
        ) from exc


def _line_ending_bytes(line_ending: str) -> bytes:
    if line_ending == "crlf":
        return b"\r\n"
    if line_ending == "lf":
        return b"\n"
    return b""


__all__ = [
    "LOGICAL_DICTIONARY_TYPE",
    "SINO_DICTIONARY_TYPE",
    "XML_DICTIONARY_BOOLEAN_TYPES",
    "ParsedExportFieldValue",
    "ParsedExportPayload",
    "XmlDictionaryEntry",
    "parse_export_payload",
    "xml_dictionary_entries",
]
