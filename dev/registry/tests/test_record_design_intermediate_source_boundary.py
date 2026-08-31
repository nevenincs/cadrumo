"""Real-binary proof that the generator IR has no derivative input boundary."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.corpus_catalogue import resolve_record_design_binary
from cadrumo.domain.calculations.registry.loader import load_catalogue_file
from cadrumo.domain.calculations.registry.record_design import extract_record_design
from cadrumo.domain.calculations.registry.record_design_schema import (
    RecordDesignRelativeSuffixMarker,
    RecordDesignSheet,
)

from ..pipeline._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateRelativeSuffixMarker,
    load_record_design_intermediate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_REF = "aeat-dr-200-2025"
_FILING_YEAR = 2025
_DESIGN_EPOCH = "2025"


def test_intermediate_consumes_the_hash_pinned_binary_not_adjacent_derivatives(tmp_path: Path) -> None:
    """Contradictory review sidecars cannot alter a complete parser-derived IR."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    bundled = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref=_SOURCE_REF,
        filing_year=_FILING_YEAR,
        design_epoch=_DESIGN_EPOCH,
    )

    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _copy_verified_binary_with_derivatives(first_root, bundled.path, bundled.source.corpus_path, marker="FIRST")
    _copy_verified_binary_with_derivatives(second_root, bundled.path, bundled.source.corpus_path, marker="SECOND")

    first_resolved = resolve_record_design_binary(
        first_root,
        catalogues.sources,
        source_ref=_SOURCE_REF,
        filing_year=_FILING_YEAR,
        design_epoch=_DESIGN_EPOCH,
    )
    second_resolved = resolve_record_design_binary(
        second_root,
        catalogues.sources,
        source_ref=_SOURCE_REF,
        filing_year=_FILING_YEAR,
        design_epoch=_DESIGN_EPOCH,
    )
    first_intermediate = load_record_design_intermediate(
        first_root,
        catalogues.sources,
        source_ref=_SOURCE_REF,
        filing_year=_FILING_YEAR,
        design_epoch=_DESIGN_EPOCH,
    )
    second_intermediate = load_record_design_intermediate(
        second_root,
        catalogues.sources,
        source_ref=_SOURCE_REF,
        filing_year=_FILING_YEAR,
        design_epoch=_DESIGN_EPOCH,
    )

    assert first_resolved.source.sha256 == bundled.source.sha256
    assert second_resolved.source.sha256 == bundled.source.sha256
    assert first_intermediate == second_intermediate
    assert "S03-IR-DERIVATIVE-FIRST" not in first_intermediate.model_dump_json()
    assert "S03-IR-DERIVATIVE-SECOND" not in second_intermediate.model_dump_json()
    _assert_complete_parser_projection(first_intermediate, extract_record_design(first_resolved.path).accept_partial())


def _copy_verified_binary_with_derivatives(
    root: Path,
    source_binary: Path,
    corpus_path: str,
    *,
    marker: str,
) -> None:
    destination = root / corpus_path
    destination.parent.mkdir(parents=True)
    copyfile(source_binary, destination)
    destination.with_name(f"{destination.name}.extracted.md").write_text(
        f"S03-IR-DERIVATIVE-{marker}: position 999999 must never be read.\n",
        encoding="utf-8",
    )
    destination.with_name(f"{destination.name}.extracted.json").write_text(
        f'{{"units": [{{"anchor": "S03-IR-DERIVATIVE-{marker}", "text": "position 999999"}}]}}\n',
        encoding="utf-8",
    )


def _assert_complete_parser_projection(
    intermediate: RecordDesignIntermediate,
    parsed_sheets: tuple[RecordDesignSheet, ...],
) -> None:
    """Compare every parser coordinate to the IR without re-parsing any source."""
    fixed_sheets = tuple(sheet for sheet in parsed_sheets if sheet.variable_envelope is None)
    parsed_envelopes = tuple(sheet.variable_envelope for sheet in parsed_sheets if sheet.variable_envelope is not None)
    assert len(intermediate.sheets) == len(fixed_sheets)
    for intermediate_sheet, parsed_sheet in zip(intermediate.sheets, fixed_sheets, strict=True):
        assert intermediate_sheet.sheet == parsed_sheet.name
        assert intermediate_sheet.record_identity == parsed_sheet.name
        assert intermediate_sheet.declared_total == parsed_sheet.total_positions
        assert len(intermediate_sheet.fields) == len(parsed_sheet.fields)
        for intermediate_field, parsed_field in zip(intermediate_sheet.fields, parsed_sheet.fields, strict=True):
            assert intermediate_field.sheet == parsed_field.sheet
            assert intermediate_field.record_identity == parsed_sheet.name
            assert intermediate_field.source_row == parsed_field.row
            assert intermediate_field.source_cell == f"A{parsed_field.row}"
            assert intermediate_field.ordinal == parsed_field.ordinal
            assert intermediate_field.offset == parsed_field.offset
            assert intermediate_field.length == parsed_field.length
            assert intermediate_field.aeat_type == parsed_field.type_code
            assert intermediate_field.normalized_description == parsed_field.description
            assert intermediate_field.validation == parsed_field.validation
            assert intermediate_field.content == parsed_field.content

    assert len(intermediate.variable_envelopes) == len(parsed_envelopes)
    for intermediate_envelope, parsed_envelope in zip(
        intermediate.variable_envelopes,
        parsed_envelopes,
        strict=True,
    ):
        assert parsed_envelope is not None
        assert intermediate_envelope.sheet == parsed_envelope.name
        assert intermediate_envelope.record_identity == parsed_envelope.name
        assert intermediate_envelope.prefix_extent == parsed_envelope.prefix_extent
        assert len(intermediate_envelope.prefix_fields) == len(parsed_envelope.prefix_fields)
        for intermediate_field, parsed_field in zip(
            intermediate_envelope.prefix_fields,
            parsed_envelope.prefix_fields,
            strict=True,
        ):
            assert intermediate_field.source_row == parsed_field.row
            assert intermediate_field.ordinal == parsed_field.ordinal
            assert intermediate_field.offset == parsed_field.offset
            assert intermediate_field.length == parsed_field.length
            assert intermediate_field.aeat_type == parsed_field.type_code
            assert intermediate_field.normalized_description == parsed_field.description
            assert intermediate_field.validation == parsed_field.validation
            assert intermediate_field.content == parsed_field.content
        assert intermediate_envelope.body_source_row == parsed_envelope.body.row
        assert intermediate_envelope.body_offset == parsed_envelope.body.offset
        assert intermediate_envelope.body_length == parsed_envelope.body.length
        assert intermediate_envelope.body_aeat_type == parsed_envelope.body.type_code
        assert intermediate_envelope.body_normalized_description == parsed_envelope.body.description
        assert intermediate_envelope.body_validation == parsed_envelope.body.validation
        assert intermediate_envelope.body_content == parsed_envelope.body.content
        assert isinstance(intermediate_envelope.closing, RecordDesignIntermediateRelativeSuffixMarker)
        assert isinstance(parsed_envelope.closing, RecordDesignRelativeSuffixMarker)
        assert intermediate_envelope.closing.source_row == parsed_envelope.closing.row
        assert intermediate_envelope.closing.offset == parsed_envelope.closing.offset
        assert intermediate_envelope.closing.length == parsed_envelope.closing.length
        assert intermediate_envelope.closing.aeat_type == parsed_envelope.closing.type_code
        assert intermediate_envelope.closing.normalized_description == parsed_envelope.closing.description
        assert intermediate_envelope.closing.validation == parsed_envelope.closing.validation
        assert intermediate_envelope.closing.content == parsed_envelope.closing.content
        assert intermediate_envelope.total_source_row == parsed_envelope.variable_total.row
        assert intermediate_envelope.total_label == parsed_envelope.variable_total.label
        assert intermediate_envelope.total_length == parsed_envelope.variable_total.length
