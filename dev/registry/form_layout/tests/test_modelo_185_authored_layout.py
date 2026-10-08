"""Modelo 185 uses a monthly comparison instead of electronic-file offsets."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_185_monthly_grid_preserves_each_declared_month_and_has_no_false_boxes() -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/185"))
    revision = modelo.revisions["2025-y-siguientes"]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored" and layout.review.state.value == "generated"
    assert len(layout.placements) == len(revision.casillas) == 21
    assert all(p.box_number is None for p in layout.placements)
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    grid = layout.pages[1].sections[1].blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [r.key for r in grid.rows] == ["mes", "mes-anterior", "dos-meses-antes"]
    assert [r.cells[2].casilla_id for r in grid.rows] == [
        "declarado.dias-alta-mes",
        "declarado.dias-alta-mes-1",
        "declarado.dias-alta-mes-2",
    ]
    context = [b for s in layout.pages[0].sections for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    assert len(context) == 5
    assert {str(resolve_form_context_field(revision, b).producer_key) for b in context} == {
        "taxpayer.tax_id",
        "taxpayer.surnames_or_legal_name",
        "contact_person.phone",
        "contact_person.full_name",
        "amendment_evidence.original_aeat_receipt",
    }
    assert revision.valid_from.year == 2026
