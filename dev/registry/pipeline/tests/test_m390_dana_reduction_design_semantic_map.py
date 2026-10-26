"""Exact-source Modelo 390 semantic map for the design that introduces the DANA reduction rows."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_registry_tree
from ...tests.authored_edition_support import source_first_exercise, source_with_sha256
from .._export_tree import render_complete_export_tree
from ..record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..render_check import GeneratedExportBootstrapTransport, revision_render_inputs
from ..semantic_map import (
    SemanticMapEntry,
    load_semantic_map,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# The official record design this map is reviewed against, found by its pinned bytes;
# its catalogued applicability names the exercise. The predecessor design it is
# diffed against is the preceding exercise's.
_SOURCE_SHA256 = "8be79bacc86034c3c7951d2ea671c030800ed9a4cc3f52b9e5d407bc19bc03f0"
_SOURCE = source_with_sha256(_SOURCE_SHA256)
_SOURCE_REF = _SOURCE.id
_DESIGN_EXERCISE = source_first_exercise(_SOURCE)
_PREDECESSOR_EXERCISE = _DESIGN_EXERCISE - 1
_PREDECESSOR_SOURCE_REF = f"aeat-dr-390-{_PREDECESSOR_EXERCISE}"
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
_COMPLEMENTARIA_INDICATOR_ANCHORS = {
    (record, "A10") for record in ("Pág. 1", "Pág. 2", "Pág. 2 bis", "Pág. 3", "Pág. 4", "Pág. 6", "Pág. 8")
}
_LORCA_BINDING_IDS = {
    "A27": (
        "modelo-390.page_5.operaciones-reg-simplificado-actividad-1-"
        "reduccion-aplicable-por-actividad-realizada-en-el-termin"
    ),
    "A51": (
        "modelo-390.page_5.operaciones-reg-simplificado-actividad-2-"
        "reduccion-aplicable-por-actividad-realizada-en-el-termin"
    ),
}
_DANA_BINDING_IDS = {
    "A101": (
        "modelo-390.page_5.operaciones-reg-simplificado-actividad-1-"
        "reduccion-aplicable-por-actividad-realizada-en-municip"
    ),
    "A102": "modelo-390.page_5.operaciones-reg-simplificado-actividad-1-reducciones-total",
    "A103": (
        "modelo-390.page_5.operaciones-reg-simplificado-actividad-2-"
        "reduccion-aplicable-por-actividad-realizada-en-municip"
    ),
    "A104": "modelo-390.page_5.operaciones-reg-simplificado-actividad-2-reducciones-total",
    "A105": (
        "modelo-390.page_5.operaciones-reg-simplificado-act-agricolas-y-ganaderas-actividad-1-reduccion-aplicable-por"
    ),
    "A106": (
        "modelo-390.page_5.operaciones-reg-simplificado-act-agricolas-y-ganaderas-actividad-2-reduccion-aplicable-por"
    ),
    "A107": (
        "modelo-390.page_5.operaciones-reg-simplificado-act-agricolas-y-ganaderas-actividad-3-reduccion-aplicable-por"
    ),
    "A108": (
        "modelo-390.page_5.operaciones-reg-simplificado-act-agricolas-y-ganaderas-actividad-4-reduccion-aplicable-por"
    ),
    "A109": (
        "modelo-390.page_5.operaciones-reg-simplificado-act-agricolas-y-ganaderas-actividad-5-reduccion-aplicable-por"
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


def _field_index(design: RecordDesignIntermediate) -> dict[tuple[str, str], RecordDesignIntermediateField]:
    return {
        (sheet.record_identity, field.source_cell or ""): field for sheet in design.sheets for field in sheet.fields
    }


def _entry_index(entries: tuple[SemanticMapEntry, ...]) -> dict[tuple[str, str], SemanticMapEntry]:
    return {(entry.anchor.record_identity, entry.anchor.source_cell or ""): entry for entry in entries}


_StablePayload = tuple[str, str | None, str | None, str | None, str | None, str | None, str | None, str | None]

# These printed page-5 quantities moved from unrouted manual bindings to their
# source-backed casillas. Their wire concepts remain unchanged; the target
# edition's anchor-to-layout proof below independently checks each new owner.
_PROMOTED_SIMPLIFICADO_OWNERS = {
    "iva-devengado-suma-cuotas-actividades-no-agric-ganad-y-forest": "cuota-resultante-no-agricola",
    "iva-devengado-suma-cuotas-actividades-agric-ganad-y-forest": "cuota-resultante-agricola",
    "iva-devengado-en-adquisiciones-intracomunitarias": "aic-bienes-cuota-devengada",
    "iva-devengado-iva-devengado-por-inversion-del-sujeto-pasivo": "inversion-sujeto-pasivo",
    "iva-devengado-iva-devengado-en-entregas-de-activos-fijos": "entrega-activos-fijos",
    "deducciones-iva-soportado-en-adquisicion-de-activos-fijos": "iva-soportado-activos-fijos",
    "deducciones-regularizacion-de-bienes-de-inversion": "regularizacion-bienes-inversion",
    "deducciones-suma-de-deducciones": "suma-deducciones",
    "resultado-regimen-simplificado": "resultado",
}


def _stable_payload(entry: SemanticMapEntry, revision: str) -> _StablePayload:
    binding = None if entry.binding is None else str(entry.binding).replace(f"modelo-390-{revision}.", "modelo-390-X.")
    kind = entry.kind.value
    casilla_id = None if entry.casilla_id is None else str(entry.casilla_id)
    if binding is not None:
        prefix = "modelo-390.page_5.operaciones-reg-simplificado-"
        if binding.startswith(prefix) and binding.removeprefix(prefix) in _PROMOTED_SIMPLIFICADO_OWNERS:
            kind = "casilla"
            casilla_id = f"iva.anual.regimen-simplificado.{_PROMOTED_SIMPLIFICADO_OWNERS[binding.removeprefix(prefix)]}"
            binding = None
        elif binding in {f"{prefix}actividad-{row}-lorca" for row in (1, 2)}:
            row = binding.removeprefix(prefix).split("-")[1]
            binding = _LORCA_BINDING_IDS["A27" if row == "1" else "A51"]
    return (
        kind,
        casilla_id,
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


def test_m390_dana_reduction_design_bijects_every_parser_anchor_to_the_reviewed_revision_owner() -> None:
    authority = compiled_bundled_authority()
    revision = authority.modelo("390").revisions[str(_DESIGN_EXERCISE)]
    predecessor_design = _design(
        _PREDECESSOR_SOURCE_REF, filing_year=_PREDECESSOR_EXERCISE, epoch=str(_PREDECESSOR_EXERCISE)
    )
    design = _design(_SOURCE_REF, filing_year=_DESIGN_EXERCISE, epoch=str(_DESIGN_EXERCISE))
    predecessor_fields = _field_index(predecessor_design)
    fields = _field_index(design)
    delta = {key for key in predecessor_fields.keys() | fields.keys() if predecessor_fields.get(key) != fields.get(key)}

    assert len(predecessor_fields) == 541
    assert len(fields) == 621
    assert Counter(record for record, _cell in delta) == Counter(_DELTA_COUNTS)
    assert len(set(predecessor_fields) & set(fields) - delta) == 341
    assert sum(len(envelope.prefix_fields) for envelope in design.variable_envelopes) == 13

    predecessor_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_390/{_PREDECESSOR_EXERCISE}"))
    semantic_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_390/{_DESIGN_EXERCISE}"))
    predecessor_entries = _entry_index(predecessor_map.entries)
    entries = _entry_index(semantic_map.entries)
    stable = set(predecessor_fields) & set(fields) - delta
    assert {key: _stable_payload(predecessor_entries[key], str(_PREDECESSOR_EXERCISE)) for key in stable} == {
        key: _stable_payload(entries[key], str(_DESIGN_EXERCISE)) for key in stable
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
                # An inherited binding keeps the source that grounded it at its origin;
                # the generated field cites this edition's design.
                assert binding.source_refs
                assert tuple(layout_field.source_refs) == (_SOURCE_REF,)

    assert covered_record_types == set(layout_records)
    published_fields = [field for record in revision.export_layouts[0].records for field in record.fields]
    assert owned_field_ids == {str(field.id) for field in published_fields}
    assert owned_kinds == Counter(field.kind.value for field in published_fields)
    assert sum(owned_kinds.values()) == len(fields)
    assert filler_anchors == _RESERVED_ANCHORS | _COMPLEMENTARIA_INDICATOR_ANCHORS
    assert {cell: str(entries[("Pág. 5", cell)].binding) for cell in _LORCA_BINDING_IDS} == _LORCA_BINDING_IDS
    assert {cell: str(entries[("Pág. 5", cell)].binding) for cell in _DANA_BINDING_IDS} == _DANA_BINDING_IDS


def test_m390_dana_reduction_design_profile_and_map_render_all_numbered_anchors_from_the_exact_source(
    tmp_path: Path,
) -> None:
    inputs = revision_render_inputs(
        compiled_bundled_authority(),
        modelo="390",
        revision=str(_DESIGN_EXERCISE),
        source_ref=_SOURCE_REF,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id=f"generated-modelo-390-{_DESIGN_EXERCISE}-fichero",
            line_ending="crlf",
            source_ref=_SOURCE_REF,
            source_sha256=_SOURCE_SHA256,
        ),
    )

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=str(_DESIGN_EXERCISE),
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
