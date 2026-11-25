"""Hold a written fichero BOE to the official design's character rules.

The registry export layout states each record's wire encoding, each field's
position and length, a numeric-versus-text type and its sign convention. Those
are always checked. The case and accent rule is not universal: a design states
it in its own text (the Modelo 347 design asks for upper case and no accented
vowel, with Ñ and Ç allowed) and another may state none. The check therefore
applies it only to a record whose layout declares it, read by
:func:`declared_case_rule`. The registry holds no such declaration yet, so the
case rule is inactive until one lands. Numeric fields ("N" with sign, "Num"
without) carry digits, with the sign marker where the design gives one.

The check reads the file through the registry's own parser for its field
positions only and applies the character rules itself, so it does not depend on
the text normalisation the product's writer applies. A violation names the
record type, field id, position and rule; it never carries a field's value.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.schema_base import ZERO_PADDED_EXPORT_DATA_TYPES, CasillaDataType
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)

_PERMITTED_MARKED_LETTERS = frozenset("ÑÇ")
"""The design allows these two marked letters in alphanumeric fields."""

_UPPER_UNACCENTED = "upper_unaccented"
"""The record declaration value meaning upper case, unaccented vowels, Ñ and Ç kept."""

_LINE_ENDINGS = {"crlf": b"\r\n", "lf": b"\n"}
_NUMERIC_TYPES = ZERO_PADDED_EXPORT_DATA_TYPES | {CasillaDataType.YEAR}
_SIGN_MARKERS = frozenset("N- ")
"""The sign bytes the registry's sign conventions use: ``N``, the hyphen and the blank."""


@dataclass(frozen=True, slots=True)
class TextViolation:
    """One broken character rule, located by record type, field id and 1-based positions."""

    record_type: str
    field_id: str
    first: int
    last: int
    rule: str

    def reason(self) -> str:
        """The violation as the table's reason text, free of any field value."""
        return f"export text: record {self.record_type} field {self.field_id} pos {self.first}-{self.last}: {self.rule}"


def _structural(rule: str) -> TextViolation:
    return TextViolation("-", "-", 0, 0, rule)


def _structural_reason(violation: TextViolation) -> str:
    if violation.first == 0:
        return f"export text: {violation.rule}"
    return violation.reason()


def violation_reason(violations: list[TextViolation]) -> str:
    """The first violation's reason, with the count when more than one."""
    if not violations:
        return ""
    head = _structural_reason(violations[0])
    return head if len(violations) == 1 else f"{head} (+{len(violations) - 1} more)"


def _is_numeric(field: ExportFieldDefinition) -> bool:
    return field.design_type is not None or field.data_type in _NUMERIC_TYPES


def declared_case_rule(record: ExportRecordDefinition) -> bool:
    """Whether the record's design declares the upper-case, no-accented-vowel rule.

    The one place that reads the declaration; the record's ``alphanumeric_text`` attribute is absent from the
    registry model until the layout schema adds it, so this is False for every record.
    """
    declared: object = getattr(record, "alphanumeric_text", None)
    return declared == _UPPER_UNACCENTED


def _text_rule(char: str, case_rule: bool) -> str | None:
    """The alphanumeric rule ``char`` breaks, or None; control characters are never allowed."""
    if unicodedata.category(char).startswith("C"):
        return "control character"
    if not case_rule:
        return None
    if unicodedata.category(char) == "Ll":
        return "lowercase letter"
    if char in _PERMITTED_MARKED_LETTERS:
        return None
    if any(unicodedata.category(part) == "Mn" for part in unicodedata.normalize("NFD", char)):
        return "accented letter"
    return None


def _numeric_rule(char: str, field: ExportFieldDefinition) -> str | None:
    """The numeric rule ``char`` breaks, or None."""
    if char in "0123456789":
        return None
    blank_allowed = field.absent_fill is not None or field.presence_marker is not None
    if field.signed or field.sign_position is not None:
        return None if char in _SIGN_MARKERS else "non-digit in signed numeric field"
    if char == " " and blank_allowed:
        return None
    return "non-digit in numeric field"


def _field_rule(raw: str, field: ExportFieldDefinition, case_rule: bool) -> str | None:
    """The first rule the field's raw wire text breaks, or None."""
    for char in raw:
        rule = _numeric_rule(char, field) if _is_numeric(field) else _text_rule(char, case_rule)
        if rule is not None:
            return rule
    return None


def _wire_encoding(layout: ExportLayoutDefinition) -> str:
    return str(layout.records[0].encoding.value)


def _decode_violation(layout: ExportLayoutDefinition, payload: bytes) -> TextViolation | None:
    encoding = _wire_encoding(layout)
    try:
        payload.decode(encoding)
    except UnicodeDecodeError:
        return _structural(f"file does not decode as {encoding}")
    return None


def _record_length(record: ExportRecordDefinition) -> int:
    return max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)


def _framing(layout: ExportLayoutDefinition) -> bytes | None:
    """The one line ending every record declares, or None when the layout is not plain line framed."""
    if layout.filing_envelope is not None or layout.auxiliary_envelope_header is not None:
        return None
    endings = {_LINE_ENDINGS.get(str(record.line_ending), b"") for record in layout.records}
    ending = next(iter(endings)) if len(endings) == 1 else b""
    return ending or None


def _length_violation(layout: ExportLayoutDefinition, payload: bytes) -> TextViolation | None:
    """A line whose length is none of the design's record lengths, found without the layout reader."""
    ending = _framing(layout)
    if ending is None:
        return None
    lengths = {_record_length(record) for record in layout.records if record.fields}
    lines = payload.split(ending)
    if lines and not lines[-1]:
        lines.pop()
    for number, line in enumerate(lines, start=1):
        if len(line) not in lengths:
            return _structural(f"line {number} has {len(line)} bytes, not a design record length")
    return None


def _field_index(
    layout: ExportLayoutDefinition,
) -> dict[tuple[str, str], tuple[ExportRecordDefinition, ExportFieldDefinition]]:
    return {(record.id, field.id): (record, field) for record in layout.records for field in record.fields}


def _character_violations(
    layout: ExportLayoutDefinition, payload: bytes, case_rule: Callable[[ExportRecordDefinition], bool]
) -> list[TextViolation]:
    index = _field_index(layout)
    found: list[TextViolation] = []
    for parsed in parse_export_payload(layout, payload).fields:
        record, field = index[(parsed.record_id, parsed.field_id)]
        rule = _field_rule(parsed.raw, field, case_rule(record))
        if rule is not None and field.offset is not None and field.length is not None:
            found.append(
                TextViolation(record.record_type, field.id, field.offset, field.offset + field.length - 1, rule)
            )
    return found


def check_export_text(
    layout: ExportLayoutDefinition,
    payload: bytes,
    case_rule: Callable[[ExportRecordDefinition], bool] = declared_case_rule,
) -> list[TextViolation]:
    """Every character rule the written fichero breaks, empty when it is clean.

    Fixed-width layouts only: an XML-dictionary layout has no character
    positions, so it is not held to these rules.
    """
    if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
        return []
    structural = _decode_violation(layout, payload) or _length_violation(layout, payload)
    if structural is not None:
        return [structural]
    try:
        return _character_violations(layout, payload, case_rule)
    except RegistryValidationError:
        return [_structural("file is refused by the registry layout reader")]
