"""Exact-source Modelo 390 2025 semantic-map and render-profile coverage."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_registry_tree
from ..pipeline._export_tree import render_complete_export_tree
from ..pipeline.record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..pipeline.render_check import GeneratedExportBootstrapTransport, revision_render_inputs
from ..pipeline.semantic_map import (
    SemanticMapEntry,
    load_semantic_map,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE_REF = "aeat-dr-390-2025"
_SOURCE_SHA256 = "6d33d8a4245976e55dc31ff85065b420f76d1588110dc1eb541a8039c5e3f252"
_DELTA_COUNTS = {
    "Pág. 2": 42,
    "Pág. 2 bis": 8,
    "Pág. 3": 18,
    "Pág. 4": 12,
    "Pág. 5": 13,
    "Pág. 7": 5,
}
_RESERVED_ANCHORS = {
    ("Pág. 1", "A11"),
    ("Pág. 1", "A16"),
    ("Pág. 1", "A75"),
    ("Pág. 1", "A76"),
    ("Pág. 1", "A77"),
    ("Pág. 1", "A78"),
    ("Pág. 2", "A107"),
    ("Pág. 2 bis", "A32"),
    ("Pág. 3", "A109"),
    ("Pág. 4", "A51"),
    ("Pág. 5", "A27"),
    ("Pág. 5", "A51"),
    ("Pág. 5", "A101"),
    ("Pág. 6", "A53"),
    ("Pág. 7", "A52"),
    ("Pág. 8", "A65"),
}
_COMPLEMENTARIA_INDICATOR_ANCHORS = {
    (record, "A10") for record in ("Pág. 1", "Pág. 2", "Pág. 2 bis", "Pág. 3", "Pág. 4", "Pág. 6", "Pág. 8")
}
_REMOVED_PAGE_5_ANCHORS = {("Pág. 5", f"A{row}") for row in range(103, 112)}
_RETIRED_PAGE_5_SLOTS = {("Pág. 5", cell) for cell in ("A27", "A51", "A101")}


def _design(source_ref: str, *, filing_year: int, epoch: str) -> RecordDesignIntermediate:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=epoch,
    )


def _field_index(design: RecordDesignIntermediate) -> dict[tuple[str, str], RecordDesignIntermediateField]:
    return {
        (sheet.record_identity, field.source_cell or ""): field for sheet in design.sheets for field in sheet.fields
    }


def _entry_index(entries: tuple[SemanticMapEntry, ...]) -> dict[tuple[str, str], SemanticMapEntry]:
    return {(entry.anchor.record_identity, entry.anchor.source_cell or ""): entry for entry in entries}


_StablePayload = tuple[str, str | None, str | None, str | None, str | None, str | None, str | None, str | None]


def _stable_payload(entry: SemanticMapEntry, revision: str) -> _StablePayload:
    binding = None if entry.binding is None else str(entry.binding).replace(f"modelo-390-{revision}.", "modelo-390-X.")
    return (
        entry.kind.value,
        None if entry.casilla_id is None else str(entry.casilla_id),
        binding,
        entry.literal,
        None if entry.producer_key is None else str(entry.producer_key),
        None if entry.projection_ref is None else str(entry.projection_ref),
        None if entry.draft_attribute is None else str(entry.draft_attribute),
        None if entry.computed_key is None else str(entry.computed_key),
    )


def _assert_layout_owner(entry: SemanticMapEntry, field: ExportFieldDefinition) -> None:
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


def test_m390_2025_bijects_every_parser_anchor_to_the_reviewed_revision_owner() -> None:
    authority = compiled_bundled_authority()
    revision = authority.modelo("390").revisions["2025"]
    design_2024 = _design("aeat-dr-390-2024", filing_year=2024, epoch="2024")
    design = _design(_SOURCE_REF, filing_year=2025, epoch="2025")
    fields_2024 = _field_index(design_2024)
    fields = _field_index(design)
    delta = {key for key in fields_2024.keys() | fields.keys() if fields_2024.get(key) != fields.get(key)}

    assert len(fields_2024) == 621
    assert len(fields) == 612
    assert Counter(record for record, _cell in delta) == Counter(_DELTA_COUNTS)
    assert fields_2024.keys() - fields.keys() == _REMOVED_PAGE_5_ANCHORS
    assert not fields.keys() - fields_2024.keys()
    assert len(set(fields_2024) & set(fields) - delta) == 523
    assert sum(len(header.fields) for header in design.auxiliary_envelope_headers) == 13

    semantic_map_2024 = load_semantic_map(Path("dev/registry/mappings/modelo_390/2024"))
    semantic_map = load_semantic_map(Path("dev/registry/mappings/modelo_390/2025"))
    entries_2024 = _entry_index(semantic_map_2024.entries)
    entries = _entry_index(semantic_map.entries)
    stable = set(fields_2024) & set(fields) - delta
    assert {key: _stable_payload(entries_2024[key], "2024") for key in stable} == {
        key: _stable_payload(entries[key], "2025") for key in stable
    }

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
            _assert_layout_owner(entry, layout_field)
            assert str(layout_field.id) not in owned_field_ids
            owned_field_ids.add(str(layout_field.id))
            owned_kinds[layout_field.kind.value] += 1
            if layout_field.kind.value == "filler":
                filler_anchors.add(anchor)
                if anchor in _COMPLEMENTARIA_INDICATOR_ANCHORS:
                    assert str(layout_field.id).endswith("-complementaria-indicator")
            if layout_field.kind.value == "binding":
                binding = bindings_by_id[str(layout_field.binding)]
                assert tuple(binding.legal_refs) == tuple(layout_field.legal_refs)
                assert tuple(binding.source_refs) == tuple(layout_field.source_refs)

    assert covered_record_types == set(layout_records)
    published_fields = [field for record in revision.export_layouts[0].records for field in record.fields]
    assert owned_field_ids == {str(field.id) for field in published_fields}
    assert owned_kinds == Counter(field.kind.value for field in published_fields)
    assert sum(owned_kinds.values()) == len(fields)
    assert filler_anchors == _RESERVED_ANCHORS | _COMPLEMENTARIA_INDICATOR_ANCHORS
    assert {anchor for anchor in filler_anchors if anchor[0] == "Pág. 5"} == _RETIRED_PAGE_5_SLOTS


def test_m390_2025_profile_and_map_render_all_numbered_anchors_from_the_exact_source(tmp_path: Path) -> None:
    inputs = revision_render_inputs(
        compiled_bundled_authority(),
        modelo="390",
        revision="2025",
        source_ref=_SOURCE_REF,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="generated-modelo-390-2025-fichero",
            line_ending="crlf",
            source_ref=_SOURCE_REF,
            source_sha256=_SOURCE_SHA256,
        ),
    )

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id="2025",
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )

    assert len(rendered.layout.records) == 9
    assert sum(len(record.fields) for record in rendered.layout.records) == 612
    assert [record.record_type for record in rendered.layout.records] == [
        "page_01",
        "page_02",
        "page_02b",
        "page_03",
        "page_04",
        "page_05",
        "page_06",
        "page_07",
        "page_08",
    ]
    close = next(
        field
        for record in rendered.layout.records
        for field in record.fields
        if str(field.id) == "modelo-390-page-07-close"
    )
    assert close.literal == "</T39007000>"
