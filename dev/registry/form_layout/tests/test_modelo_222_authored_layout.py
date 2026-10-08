"""Consolidated instalments retain their own adjustments and pre-group losses."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("revision_id,count", [("2022", 67), ("2023", 69), ("2024", 69)])
def test_222_historical_layout_preserves_revision_specific_adjustments(revision_id: str, count: int) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/222")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.placements) == count
    grids = {b.id: b for p in layout.pages for s in p.sections for b in s.blocks if isinstance(b, FormGridBlock)}
    assert ("ajustes-grupo" in grids) is (revision_id != "2022")
    assert [[c.casilla_id for c in row.cells] for row in grids["tipos"].rows] == [
        ["20", "21", "22"],
        ["23", "24", "25"],
    ]
    assert len(grids["correcciones"].rows) == 4
    assert not {"61", "62", "63", "64", "65", "66", "67"} & {str(p.casilla_id) for p in layout.placements}
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                if isinstance(block, FormContextFieldBlock):
                    assert "2025" not in block.export_field_id
                    resolve_form_context_field(revision, block)
    assert next(p for p in layout.placements if p.casilla_id == "decl.tipo-declaracion").workbook_exclusion == (
        "transport_control"
    )


def test_222_consolidated_form_preserves_group_adjustments_and_four_rates() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/222")).revisions["2025-y-siguientes"]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.placements) == len(revision.casillas) == 76
    grids = {b.id: b for p in layout.pages for s in p.sections for b in s.blocks if isinstance(b, FormGridBlock)}
    assert [c.casilla_id for c in grids["ajustes-grupo"].rows[0].cells] == ["59", "60"]
    assert [c.casilla_id for c in grids["consolidacion"].rows[0].cells] == ["11", "12"]
    assert [[c.casilla_id for c in row.cells] for row in grids["tipos"].rows] == [
        ["20", "21", "22"],
        ["23", "24", "25"],
        ["61", "62", "63"],
        ["64", "65", "66"],
    ]
    sections = {s.id: s for p in layout.pages for s in p.sections}
    for section, expected in (("b1", {"49", "50", "51", "58"}), ("b2", {"54", "57", "42", "43"})):
        assert expected <= {getattr(b, "casilla_id", None) for b in sections[section].blocks}
    keys = {
        str(resolve_form_context_field(revision, b).producer_key)
        for p in layout.pages
        for s in p.sections
        for b in s.blocks
        if isinstance(b, FormContextFieldBlock)
    }
    assert {
        "m222.numero_grupo",
        "m222.entidad_dominante_identificacion",
        "m222.fecha_inicio_periodo_impositivo",
    } <= keys
    assert not any(key.startswith("m202.") for key in keys)
    assert layout.review.state.value == "generated"
    assert layout.review.notes and "Part 2" in layout.review.notes
