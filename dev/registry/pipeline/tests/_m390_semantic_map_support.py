"""Shared checks for the exact-source Modelo 390 semantic-map edition tests."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_registry_tree
from .._export_tree import render_complete_export_tree
from ..export_tree_models import RenderedExportTree
from ..record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..render_check import GeneratedExportBootstrapTransport, revision_render_inputs
from ..semantic_map import SemanticMapEntry
from ..source_defects import SourceDefectDeclaration


def load_design(source_ref: str, *, filing_year: int, epoch: str) -> RecordDesignIntermediate:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=epoch,
    )


def field_index(design: RecordDesignIntermediate) -> dict[tuple[str, str], RecordDesignIntermediateField]:
    return {
        (sheet.record_identity, field.source_cell or ""): field for sheet in design.sheets for field in sheet.fields
    }


def entry_index(entries: tuple[SemanticMapEntry, ...]) -> dict[tuple[str, str], SemanticMapEntry]:
    return {(entry.anchor.record_identity, entry.anchor.source_cell or ""): entry for entry in entries}


def assert_layout_owner(entry: SemanticMapEntry, field: ExportFieldDefinition) -> None:
    assert entry.export_field_id == field.id
    assert entry.kind == field.kind
    assert entry.casilla_id == field.casilla_id
    assert entry.binding == field.binding
    assert entry.literal == field.literal
    assert entry.producer_key == field.producer_key
    assert entry.projection_ref == field.projection_ref
    assert entry.draft_attribute == field.draft_attribute
    assert entry.computed_key == field.computed_key
    assert entry.legal_refs == field.legal_refs
    assert entry.source_refs == field.source_refs


def assert_anchors_biject_to_layout(
    *,
    design: RecordDesignIntermediate,
    revision: Any,
    entries: dict[tuple[str, str], SemanticMapEntry],
    source_ref: str,
    complementaria_anchors: set[tuple[str, str]],
) -> set[tuple[str, str]]:
    """Check each parser anchor owns exactly one published layout field; return the filler anchors."""
    layout_records: dict[str, ExportRecordDefinition] = {
        str(record.record_type): record for record in revision.export_layouts[0].records
    }
    bindings_by_id = {str(binding.id): binding for binding in revision.bindings}

    owned_field_ids: set[str] = set()
    owned_kinds: Counter[str] = Counter()
    covered_record_types: set[str] = set()
    filler_anchors: set[tuple[str, str]] = set()
    for sheet in design.sheets:
        suffix = "02b" if sheet.record_identity == "Pág. 2 bis" else sheet.record_identity.split()[-1].zfill(2)
        record_type = f"page_{suffix}"
        covered_record_types.add(record_type)
        layout = layout_records[record_type]
        layout_fields = {
            (field.offset, field.length): field
            for field in layout.fields
            if field.offset is not None and field.length is not None
        }
        for field in sheet.fields:
            anchor = (sheet.record_identity, field.source_cell or "")
            entry = entries[anchor]
            layout_field = layout_fields[(field.offset, field.length)]
            assert_layout_owner(entry, layout_field)
            assert str(layout_field.id) not in owned_field_ids
            owned_field_ids.add(str(layout_field.id))
            owned_kinds[layout_field.kind.value] += 1
            if layout_field.kind.value == "filler":
                filler_anchors.add(anchor)
                if anchor in complementaria_anchors:
                    assert str(layout_field.id).endswith("-complementaria-indicator")
            if layout_field.kind.value == "binding":
                binding = bindings_by_id[str(layout_field.binding)]
                assert tuple(binding.legal_refs) == tuple(layout_field.legal_refs)
                # An inherited binding keeps the source that grounded it at its origin;
                # the generated field cites this edition's design.
                assert binding.source_refs
                assert tuple(layout_field.source_refs) == (source_ref,)

    assert covered_record_types == set(layout_records)
    published_fields = [field for record in revision.export_layouts[0].records for field in record.fields]
    assert owned_field_ids == {str(field.id) for field in published_fields}
    assert owned_kinds == Counter(field.kind.value for field in published_fields)
    assert sum(owned_kinds.values()) == sum(len(sheet.fields) for sheet in design.sheets)
    return filler_anchors


def render_edition(
    tmp_path: Path,
    *,
    exercise: int,
    source_ref: str,
    source_sha256: str,
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
) -> RenderedExportTree:
    inputs = revision_render_inputs(
        compiled_bundled_authority(),
        modelo="390",
        revision=str(exercise),
        source_ref=source_ref,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id=f"generated-modelo-390-{exercise}-fichero",
            line_ending="crlf",
            source_ref=source_ref,
            source_sha256=source_sha256,
        ),
    )
    return render_complete_export_tree(
        tmp_path / "export",
        revision_id=str(exercise),
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
        source_defects=source_defects,
    )


def assert_page_07_close(rendered: RenderedExportTree) -> None:
    close = next(
        field
        for record in rendered.layout.records
        for field in record.fields
        if str(field.id) == "modelo-390-page-07-close"
    )
    assert close.literal == "</T39007000>"
