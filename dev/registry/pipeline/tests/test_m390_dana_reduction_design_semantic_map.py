"""Exact-source Modelo 390 semantic map for the design that introduces the DANA reduction rows."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from ...compiler.authority import compiled_bundled_authority
from ...tests.authored_edition_support import source_first_exercise, source_with_sha256
from ..semantic_map import SemanticMapEntry, load_semantic_map
from ._m390_semantic_map_support import (
    assert_anchors_biject_to_layout,
    assert_page_07_close,
    entry_index,
    field_index,
    load_design,
    render_edition,
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


def test_m390_dana_reduction_design_bijects_every_parser_anchor_to_the_reviewed_revision_owner() -> None:
    authority = compiled_bundled_authority()
    revision = authority.modelo("390").revisions[str(_DESIGN_EXERCISE)]
    predecessor_design = load_design(
        _PREDECESSOR_SOURCE_REF, filing_year=_PREDECESSOR_EXERCISE, epoch=str(_PREDECESSOR_EXERCISE)
    )
    design = load_design(_SOURCE_REF, filing_year=_DESIGN_EXERCISE, epoch=str(_DESIGN_EXERCISE))
    predecessor_fields = field_index(predecessor_design)
    fields = field_index(design)
    delta = {key for key in predecessor_fields.keys() | fields.keys() if predecessor_fields.get(key) != fields.get(key)}

    assert len(predecessor_fields) == 541
    assert len(fields) == 621
    assert Counter(record for record, _cell in delta) == Counter(_DELTA_COUNTS)
    assert len(set(predecessor_fields) & set(fields) - delta) == 341
    assert sum(len(envelope.prefix_fields) for envelope in design.variable_envelopes) == 13

    predecessor_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_390/{_PREDECESSOR_EXERCISE}"))
    semantic_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_390/{_DESIGN_EXERCISE}"))
    predecessor_entries = entry_index(predecessor_map.entries)
    entries = entry_index(semantic_map.entries)
    stable = set(predecessor_fields) & set(fields) - delta
    assert {key: _stable_payload(predecessor_entries[key], str(_PREDECESSOR_EXERCISE)) for key in stable} == {
        key: _stable_payload(entries[key], str(_DESIGN_EXERCISE)) for key in stable
    }

    filler_anchors = assert_anchors_biject_to_layout(
        design=design,
        revision=revision,
        entries=entries,
        source_ref=_SOURCE_REF,
        complementaria_anchors=_COMPLEMENTARIA_INDICATOR_ANCHORS,
    )
    assert filler_anchors == _RESERVED_ANCHORS | _COMPLEMENTARIA_INDICATOR_ANCHORS
    assert {cell: str(entries[("Pág. 5", cell)].binding) for cell in _LORCA_BINDING_IDS} == _LORCA_BINDING_IDS
    assert {cell: str(entries[("Pág. 5", cell)].binding) for cell in _DANA_BINDING_IDS} == _DANA_BINDING_IDS


def test_m390_dana_reduction_design_profile_and_map_render_all_numbered_anchors_from_the_exact_source(
    tmp_path: Path,
) -> None:
    rendered = render_edition(
        tmp_path,
        exercise=_DESIGN_EXERCISE,
        source_ref=_SOURCE_REF,
        source_sha256=_SOURCE_SHA256,
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
    assert_page_07_close(rendered)
