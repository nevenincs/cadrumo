"""Exact-source Modelo 390 2024 semantic-map and render-profile coverage."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition

from ..pipeline._export_tree import render_complete_export_tree
from ..pipeline._record_design_ir import RecordDesignIntermediate, load_record_design_intermediate
from ..pipeline._semantic_map import SemanticMapEntry
from ..pipeline._semantic_map_loader import load_semantic_map
from ..pipeline.render_check import GeneratedExportBootstrapTransport, revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE_REF = "aeat-dr-390-2024"
_SOURCE_SHA256 = "8be79bacc86034c3c7951d2ea671c030800ed9a4cc3f52b9e5d407bc19bc03f0"
_DELTA_COUNTS = {
    "Pág. 2": 96,
    "Pág. 2 bis": 28,
    "Pág. 3": 100,
    "Pág. 4": 42,
    "Pág. 5": 13,
    "Pág. 7": 1,
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
    ("Pág. 5", "A110"),
    ("Pág. 6", "A53"),
    ("Pág. 7", "A52"),
    ("Pág. 8", "A65"),
}
_LORCA_BINDING_IDS = {
    "A27": (
        "modelo-390-2024.page_5.223-239.operaciones-reg-simplificado-actividad-1-"
        "reduccion-aplicable-por-actividad-realizada-en-el-termin"
    ),
    "A51": (
        "modelo-390-2024.page_5.543-559.operaciones-reg-simplificado-actividad-2-"
        "reduccion-aplicable-por-actividad-realizada-en-el-termin"
    ),
}
_DANA_BINDING_IDS = {
    "A101": (
        "modelo-390-2024.page_5.1205-1221.operaciones-reg-simplificado-actividad-1-"
        "reduccion-aplicable-por-actividad-realizada-en-municip"
    ),
    "A102": "modelo-390-2024.page_5.1222-1238.operaciones-reg-simplificado-actividad-1-reducciones-total",
    "A103": (
        "modelo-390-2024.page_5.1239-1255.operaciones-reg-simplificado-actividad-2-"
        "reduccion-aplicable-por-actividad-realizada-en-municip"
    ),
    "A104": "modelo-390-2024.page_5.1256-1272.operaciones-reg-simplificado-actividad-2-reducciones-total",
    "A105": (
        "modelo-390-2024.page_5.1273-1289.operaciones-reg-simplificado-act-agricolas-y-ganaderas-"
        "actividad-1-reduccion-aplicable-por-1273"
    ),
    "A106": (
        "modelo-390-2024.page_5.1290-1306.operaciones-reg-simplificado-act-agricolas-y-ganaderas-"
        "actividad-2-reduccion-aplicable-por-1290"
    ),
    "A107": (
        "modelo-390-2024.page_5.1307-1323.operaciones-reg-simplificado-act-agricolas-y-ganaderas-"
        "actividad-3-reduccion-aplicable-por-1307"
    ),
    "A108": (
        "modelo-390-2024.page_5.1324-1340.operaciones-reg-simplificado-act-agricolas-y-ganaderas-"
        "actividad-4-reduccion-aplicable-por-1324"
    ),
    "A109": (
        "modelo-390-2024.page_5.1341-1357.operaciones-reg-simplificado-act-agricolas-y-ganaderas-"
        "actividad-5-reduccion-aplicable-por-1341"
    ),
}


def _design(source_ref: str, *, filing_year: int, epoch: str) -> RecordDesignIntermediate:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=epoch,
    )


def _field_index(design: RecordDesignIntermediate) -> dict[tuple[str, str], object]:
    return {(sheet.record_identity, field.source_cell): field for sheet in design.sheets for field in sheet.fields}


def _entry_index(entries: tuple[SemanticMapEntry, ...]) -> dict[tuple[str, str], SemanticMapEntry]:
    return {(entry.anchor.record_identity, entry.anchor.source_cell or ""): entry for entry in entries}


def _stable_payload(entry: SemanticMapEntry, revision: str) -> tuple[str, str | None, ...]:
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


def _selector_parts(binding: DataBindingDefinition) -> tuple[str, int, int, str] | None:
    selector = binding.selector
    if isinstance(selector, BaseModel):
        raw: Mapping[str, object] = selector.model_dump()
    else:
        raw = selector
    record = raw.get("record")
    offset = raw.get("offset")
    length = raw.get("length")
    field = raw.get("field")
    if not isinstance(record, str) or not isinstance(offset, int) or not isinstance(length, int):
        return None
    if not isinstance(field, str):
        return None
    return record, offset, length, field


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


def test_m390_2024_bijects_every_parser_anchor_to_the_reviewed_revision_owner() -> None:
    authority = bundled_authority()
    revision = authority.modelo("390").revisions["2024"]
    design_2023 = _design("aeat-dr-390-2023", filing_year=2023, epoch="2023")
    design = _design(_SOURCE_REF, filing_year=2024, epoch="2024")
    fields_2023 = _field_index(design_2023)
    fields = _field_index(design)
    delta = {key for key in fields_2023.keys() | fields.keys() if fields_2023.get(key) != fields.get(key)}

    assert len(fields_2023) == 541
    assert len(fields) == 621
    assert Counter(record for record, _cell in delta) == Counter(_DELTA_COUNTS)
    assert len(set(fields_2023) & set(fields) - delta) == 341
    assert sum(len(header.fields) for header in design.auxiliary_envelope_headers) == 13

    semantic_map_2023 = load_semantic_map(Path("dev/registry/mappings/modelo_390/2023"))
    semantic_map = load_semantic_map(Path("dev/registry/mappings/modelo_390/2024"))
    entries_2023 = _entry_index(semantic_map_2023.entries)
    entries = _entry_index(semantic_map.entries)
    stable = set(fields_2023) & set(fields) - delta
    assert {key: _stable_payload(entries_2023[key], "2023") for key in stable} == {
        key: _stable_payload(entries[key], "2024") for key in stable
    }

    layout_records: dict[str, ExportRecordDefinition] = {
        str(record.record_type): record for record in revision.export_layouts[0].records
    }
    bindings: dict[tuple[str, int, int], DataBindingDefinition] = {}
    for binding in revision.bindings:
        parts = _selector_parts(binding)
        if parts is not None:
            record, offset, length, _field = parts
            key = record, offset, length
            assert key not in bindings
            bindings[key] = binding

    ownership_counts: Counter[str] = Counter()
    for sheet in design.sheets:
        suffix = "02b" if sheet.record_identity == "Pág. 2 bis" else sheet.record_identity.split()[-1].zfill(2)
        record_type = f"page_{suffix}"
        binding_record = f"page_{suffix if suffix == '02b' else int(suffix)}"
        layout = layout_records[record_type]
        layout_fields = {
            (field.offset, field.length): field
            for field in layout.fields
            if field.offset is not None and field.length is not None
        }
        for field in sheet.fields:
            entry = entries[(sheet.record_identity, field.source_cell)]
            layout_field = layout_fields.get((field.offset, field.length))
            if layout_field is not None:
                _assert_layout_owner(entry, layout_field)
                ownership_counts["layout"] += 1
                continue
            binding = bindings.get((binding_record, field.offset, field.length))
            if binding is not None:
                assert entry.kind.value == "binding"
                assert entry.binding == binding.id
                assert entry.legal_refs == binding.legal_refs
                assert entry.source_refs == binding.source_refs
                ownership_counts["binding"] += 1
                continue
            assert (sheet.record_identity, field.source_cell) in _RESERVED_ANCHORS
            assert entry.kind.value == "filler"
            ownership_counts["filler"] += 1

    assert ownership_counts == Counter({"layout": 477, "binding": 130, "filler": 14})
    assert {cell: str(entries[("Pág. 5", cell)].binding) for cell in _LORCA_BINDING_IDS} == _LORCA_BINDING_IDS
    assert {cell: str(entries[("Pág. 5", cell)].binding) for cell in _DANA_BINDING_IDS} == _DANA_BINDING_IDS


def test_m390_2024_profile_and_map_render_all_numbered_anchors_from_the_exact_source(tmp_path: Path) -> None:
    inputs = revision_render_inputs(
        bundled_authority(),
        modelo="390",
        revision="2024",
        source_ref=_SOURCE_REF,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="generated-modelo-390-2024-fichero",
            line_ending="crlf",
            source_ref=_SOURCE_REF,
            source_sha256=_SOURCE_SHA256,
        ),
    )

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id="2024",
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )

    assert len(rendered.layout.records) == 9
    assert sum(len(record.fields) for record in rendered.layout.records) == 621
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
