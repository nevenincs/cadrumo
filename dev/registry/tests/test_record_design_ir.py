"""Real-binary tests for the record-design generator intermediate representation."""

from __future__ import annotations

import pytest

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    extract_record_design,
    load_catalogue_file,
    resolve_record_design_binary,
)

from .._record_design_ir import (
    RecordDesignWorkbookFormat,
    load_record_design_intermediate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_intermediate_retains_the_verified_binary_and_shipped_parser_coordinates() -> None:
    """The M200/2025 IR is a direct typed projection of the official workbook parser."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    parsed_sheets = extract_record_design(resolved.path)

    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )

    assert intermediate.source.source_ref == resolved.source.id
    assert intermediate.source.source_sha256 == resolved.source.sha256
    assert intermediate.source.design_epoch == resolved.source.record_design_epoch
    assert intermediate.source.workbook_format is RecordDesignWorkbookFormat.XLSX
    fixed_parser_sheets = tuple(sheet for sheet in parsed_sheets if sheet.variable_envelope is None)
    assert len(intermediate.sheets) == len(fixed_parser_sheets)
    assert {sheet.sheet for sheet in intermediate.sheets} == {sheet.name for sheet in fixed_parser_sheets}
    assert "DP200000" not in {sheet.sheet for sheet in intermediate.sheets}

    parser_sheet = fixed_parser_sheets[0]
    intermediate_sheet = intermediate.sheets[0]
    assert intermediate_sheet.sheet == parser_sheet.name
    assert intermediate_sheet.record_identity == parser_sheet.name
    assert intermediate_sheet.declared_total == parser_sheet.total_positions
    assert len(intermediate_sheet.fields) == len(parser_sheet.fields)

    parser_field = parser_sheet.fields[0]
    intermediate_field = intermediate_sheet.fields[0]
    assert intermediate_field.sheet == parser_field.sheet
    assert intermediate_field.record_identity == parser_sheet.name
    assert intermediate_field.source_row == parser_field.row
    assert intermediate_field.source_cell == f"A{parser_field.row}"
    assert intermediate_field.ordinal == parser_field.ordinal
    assert intermediate_field.offset == parser_field.offset
    assert intermediate_field.length == parser_field.length
    assert intermediate_field.aeat_type == parser_field.type_code
    assert intermediate_field.normalized_description == parser_field.description
    assert intermediate_field.validation == parser_field.validation
    assert intermediate_field.content == parser_field.content

    assert len(intermediate.variable_envelopes) == 1
    envelope = intermediate.variable_envelopes[0]
    assert envelope.sheet == "DP200000"
    assert envelope.record_identity == "DP200000"
    assert envelope.prefix_extent == 328
    assert max(field.offset + field.length - 1 for field in envelope.prefix_fields) == 328
    assert (envelope.body_source_cell, envelope.body_offset, envelope.body_length) == (
        "A14",
        329,
        "Variable",
    )
    assert (
        envelope.closing_source_cell,
        envelope.closing_offset,
        envelope.closing_length,
    ) == ("A15", "***", 18)
    assert (
        envelope.total_source_cell,
        envelope.total_label,
        envelope.total_length,
    ) == ("A16", "total", "Variable")
