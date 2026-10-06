"""Later Modelo 131 drafts preserve printed groups and revision-specific data."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("revision_id", ["2024", "2025", "2026", "2026-3t-4t"])
def test_131_groups_keep_all_boxes_context_and_additional_records(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/131")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert [p.id for p in layout.pages] == ["pag-1", "dpa", "did"]
    sections = {s.id: s for s in layout.pages[0].sections}
    assert list(sections) == [
        "identificacion",
        "devengo",
        "liquidacion-i",
        "liquidacion-ii",
        "liquidacion-iii",
        "liquidacion-iv",
        "complementaria-7",
    ]
    for sid, boxes in (
        ("i", ("01", "02")),
        ("ii", ("03", "04")),
        ("iii", ("05", "06")),
        ("iv", tuple(f"{n:02}" for n in range(7, 16))),
    ):
        assert (
            tuple(
                str(b.casilla_id)
                for b in sections[f"liquidacion-{sid}"].blocks
                if isinstance(b, FormFieldBlock) and b.casilla_id
            )
            == boxes
        )
    context = [b for s in sections.values() for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    assert len(context) == 5
    fields = [resolve_form_context_field(revision, b) for b in context]
    assert {str(f.producer_key) for f in fields if f.producer_key} == {
        "taxpayer.tax_id",
        "taxpayer.surnames",
        "taxpayer.given_name",
    }
    assert {str(f.draft_attribute) for f in fields if f.draft_attribute} == {"filing_year", "period_code"}
    grids = [b for b in sections["liquidacion-i"].blocks if isinstance(b, FormGridBlock)]
    assert len(grids) == 1 and len(grids[0].rows) == 5
    bindings = {
        b.binding_id for s in sections.values() for b in s.blocks if isinstance(b, FormFieldBlock) and b.binding_id
    }
    assert "modelo-131.page1.discapacidad-33" in bindings
    assert "modelo-131.page1.sin-datos-base-vivienda-limite" in bindings
    assert "modelo-131.page1.agraria-vivienda-limite" in bindings
    assert "modelo-131.page1.deduccion-art-110-cuantia" in bindings
    if revision_id == "2025":
        assert "modelo-131.page1.agraria-ingresos-ordinarias-generales" in bindings
        assert "modelo-131.page1.agraria-ingresos-prioritarias-ceuta-melilla-la-palma" in bindings
    assert any(pin.source_ref == "boe-2015-1656-modelos-130-131-form" for pin in layout.design_sources)
