"""The export text check holds a written fichero to its design's record geometry, encoding and character rules."""

from __future__ import annotations

from functools import cache

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportEncoding,
    render_absent_slot,
    render_fixed_width_export_field,
)
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope

from ..export_text import check_export_text, declared_case_rule, violation_reason

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NIF = "modelo-347-contraparte-row-nif"


@cache
def _layout() -> ExportLayoutDefinition:
    with bundled_indexed_authority().operation() as operation:
        year = year_envelope(operation).horizon - 1
        revision = operation.revision_for_context("347", filing_year=year, period="0A")
        return operation.revision_with_export_layouts("347", revision.id).export_layouts[0]


def _span(field: ExportFieldDefinition) -> tuple[int, int]:
    assert field.offset is not None
    assert field.length is not None
    return field.offset - 1, field.length


def _piece(field: ExportFieldDefinition, nif: str) -> str:
    if field.literal is not None:
        return field.literal
    if field.binding == _NIF:
        return nif.ljust(field.length or 0)
    if field.binding is not None and field.binding.endswith("-clave"):
        return render_fixed_width_export_field(field, "A")
    return render_absent_slot(field)


def _record(record: ExportRecordDefinition, nif: str = "B00000026") -> str:
    text = [" "] * max(start + length for start, length in map(_span, record.fields))
    for field in record.fields:
        start, length = _span(field)
        text[start : start + length] = list(_piece(field, nif))
    return "".join(text)


def _payload(nif: str = "B00000026", trim: int = 0) -> bytes:
    records = sorted(_layout().records, key=lambda item: item.order)
    lines: list[str] = [_record(records[0]), _record(records[1], nif)]
    lines[1] = lines[1][: len(lines[1]) - trim]
    return "".join(line + "\r\n" for line in lines).encode("iso-8859-1")


def _upper_case_declared(_record: ExportRecordDefinition) -> bool:
    return True


def test_a_clean_fichero_passes() -> None:
    assert check_export_text(_layout(), _payload(), _upper_case_declared) == []


def test_a_lowercase_letter_fails_where_the_design_declares_the_case_rule() -> None:
    found = check_export_text(_layout(), _payload("b0000002a"), _upper_case_declared)
    assert [violation.rule for violation in found] == ["lowercase letter"]
    assert "b0000002a" not in violation_reason(found)
    record = sorted(_layout().records, key=lambda item: item.order)[1]
    assert violation_reason(found).startswith(f"export text: record {record.record_type} field ")


def test_an_accented_vowel_fails_but_enye_and_cedilla_pass() -> None:
    assert [v.rule for v in check_export_text(_layout(), _payload("B0000002\u00c1"), _upper_case_declared)] == [
        "accented letter"
    ]
    assert check_export_text(_layout(), _payload("B0000002\u00d1"), _upper_case_declared) == []
    assert check_export_text(_layout(), _payload("B0000002\u00c7"), _upper_case_declared) == []


def test_the_case_rule_the_registry_declares_refuses_a_lower_case_letter() -> None:
    layout = _layout()
    assert any(declared_case_rule(record) for record in layout.records)
    assert check_export_text(layout, _payload("B00000026")) == []
    assert check_export_text(layout, _payload("b0000002a")) != []


def test_a_wrong_record_length_fails() -> None:
    found = check_export_text(_layout(), _payload(trim=1), _upper_case_declared)
    assert violation_reason(found).startswith("export text: line 2 has ")


def test_an_undecodable_byte_fails_under_the_encoding_the_layout_declares() -> None:
    layout = _layout()
    ascii_layout = layout.model_copy(
        update={"records": tuple(r.model_copy(update={"encoding": ExportEncoding.ASCII}) for r in layout.records)}
    )
    assert check_export_text(ascii_layout, _payload(), _upper_case_declared) == []
    found = check_export_text(ascii_layout, _payload("B0000002Ñ"), _upper_case_declared)
    assert violation_reason(found) == "export text: file does not decode as ascii"
