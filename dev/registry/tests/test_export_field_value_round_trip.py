"""Every resolved fixed-width field can carry populated values through the real codec."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.filing.record_field_renderer import COMPUTED_VALUE_PRODUCERS, DRAFT_VALUE_PRODUCERS
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.fixed_width_parser import parse_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition

from ..conformance.registry_schema_support import committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _values(field: ExportFieldDefinition) -> tuple[object, ...]:
    policy = field.value_policy
    if field.producer_key is FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA and "aeat-dr-369-2021" in field.source_refs:
        return ("C", " ")
    if field.kind in {CasillaFieldKind.LITERAL, CasillaFieldKind.FILLER}:
        return (field.literal,)
    if policy in {ExportValuePolicy.FOUR_DIGIT_YEAR, ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS}:
        return (max(2025, field.minimum_year or 0),)
    if policy in {ExportValuePolicy.YYYYMMDD, ExportValuePolicy.DDMMYYYY}:
        return (date(2025, 3, 14),)
    if policy in {
        ExportValuePolicy.YYYYMMDD_TEXT_YEAR,
        ExportValuePolicy.YYYYMMDD_TEXT_MONTH,
        ExportValuePolicy.YYYYMMDD_TEXT_DAY,
    }:
        return ("20250314",)
    if policy in {ExportValuePolicy.TWO_DIGIT_MONTH, ExportValuePolicy.TWO_DIGIT_DAY}:
        return (3,)
    if field.allowed_values:
        return field.allowed_values
    if policy is ExportValuePolicy.SELECTED_1_UNSELECTED_0:
        return (False, True)
    if policy is ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN:
        return (Decimal("-1.2"),)
    if policy in {
        ExportValuePolicy.INTEGER_PART,
        ExportValuePolicy.FRACTIONAL_DIGITS,
        ExportValuePolicy.SIGNED_COMPONENT_SIGN,
        ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE,
        ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
        ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
    }:
        if policy in {
            ExportValuePolicy.SIGNED_COMPONENT_SIGN,
            ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE,
            ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
            ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
        }:
            return (Decimal("1.2"), Decimal("-1.2"), Decimal(0))
        return (Decimal("1.2"),)
    if policy in {ExportValuePolicy.DIGIT_STRING, ExportValuePolicy.IDENTIFIER_DIGITS}:
        assert field.length is not None
        return ("1" * field.length,)
    if field.minimum_year is not None:
        return (field.minimum_year,)
    if field.data_type == "money":
        return (Decimal("0.12"), Decimal("-0.12")) if field.signed else (Decimal("0.12"),)
    if field.data_type == "decimal":
        assert field.decimals is not None
        return (Decimal(1).scaleb(-field.decimals),)
    if field.data_type == "integer":
        return (1,)
    if field.data_type == "boolean":
        return (True, False)
    if field.data_type == "date":
        return ("20250314",)
    return ("A",)


def test_every_resolved_export_field_round_trips_populated_values() -> None:
    modelos, _ = committed_registry_tree()
    failures: list[str] = []
    checked: set[tuple[str, str, str, str]] = set()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for layout in derive_export_layouts_from_bindings(revision):
                for record in layout.records:
                    for field in record.fields:
                        coordinate = (str(modelo.id), str(revision.id), str(record.id), str(field.id))
                        checked.add(coordinate)
                        values = _values(field)
                        if not field.required and field.kind not in {CasillaFieldKind.LITERAL, CasillaFieldKind.FILLER}:
                            values += (None,)
                        for value in values:
                            try:
                                raw = render_fixed_width_export_field(field, value)
                                restored = parse_fixed_width_export_field(field, raw)
                                repeated = render_fixed_width_export_field(field, restored)
                                assert repeated == raw
                                assert len(raw.encode(record.encoding)) == field.length
                            except (RegistryValidationError, AssertionError) as error:
                                failures.append(f"{'/'.join(coordinate)} value={value!r}: {error}")
    assert checked, "no fixed-width field was exercised"
    assert not failures, "\n".join(failures)


def test_patrimonio_checkbox_values_use_the_official_numeric_flags() -> None:
    modelos, _ = committed_registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "714")
    casillas = {
        "identificacion-1",
        "identificacion-2",
        "identificacion-4",
        "identificacion-10",
        "identificacion-12",
        "declaracion-negativa",
    }
    for revision in modelo.revisions.values():
        flags = {
            field.casilla_id: field
            for layout in derive_export_layouts_from_bindings(revision)
            for record in layout.records
            for field in record.fields
            if field.casilla_id in casillas
        }
        assert flags.keys() == casillas
        for field in flags.values():
            assert render_fixed_width_export_field(field, True) == "1"
            assert render_fixed_width_export_field(field, False) == "0"
            assert render_fixed_width_export_field(field, None) == "0"


@pytest.mark.parametrize("sample_index", (0, 1))
def test_every_fixed_width_record_preserves_populated_fields_at_its_declared_offsets(sample_index: int) -> None:
    modelos, _ = committed_registry_tree()
    checked: set[tuple[str, str, str]] = set()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for layout in derive_export_layouts_from_bindings(revision):
                for record in layout.records:
                    expected = {
                        field.id: render_fixed_width_export_field(
                            field, _values(field)[min(sample_index, len(_values(field)) - 1)]
                        )
                        for field in record.fields
                    }
                    extent = max(
                        field.offset + len(expected[field.id]) - 1
                        for field in record.fields
                        if field.offset is not None
                    )
                    body = bytearray(b" " * extent)
                    for field in record.fields:
                        assert field.offset is not None
                        encoded = expected[field.id].encode(record.encoding)
                        body[field.offset - 1 : field.offset - 1 + len(encoded)] = encoded
                    ending = {"crlf": b"\r\n", "lf": b"\n", "none": b""}[record.line_ending]
                    # Read the unchanged record declaration on its own, so every
                    # optional/repeated page is exercised without inventing filing facts.
                    record_layout = ExportLayoutDefinition(
                        id=layout.id,
                        format="fixed_width",
                        records=(record,),
                        source_refs=layout.source_refs,
                        legal_refs=layout.legal_refs,
                    )
                    parsed = parse_export_payload(record_layout, bytes(body) + ending)
                    assert {field.field_id: field.raw for field in parsed.fields} == expected
                    fields_by_id = {field.id: field for field in record.fields}
                    for field in parsed.fields:
                        assert render_fixed_width_export_field(fields_by_id[field.field_id], field.value) == field.raw
                    checked.add((str(modelo.id), str(revision.id), str(record.id)))
    assert checked, "no fixed-width record was exercised"


def test_every_declared_export_producer_has_a_runtime_renderer() -> None:
    modelos, _ = committed_registry_tree()
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for layout in derive_export_layouts_from_bindings(revision):
                for record in layout.records:
                    for field in record.fields:
                        if (
                            field.kind is CasillaFieldKind.COMPUTED
                            and field.computed_key not in COMPUTED_VALUE_PRODUCERS
                        ):
                            failures.append(f"{modelo.id}/{revision.id}/{field.id}: {field.computed_key}")
                        if field.kind is CasillaFieldKind.DRAFT and field.draft_attribute not in DRAFT_VALUE_PRODUCERS:
                            failures.append(f"{modelo.id}/{revision.id}/{field.id}: {field.draft_attribute}")
    assert not failures, "\n".join(failures)
