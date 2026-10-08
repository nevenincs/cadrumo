"""Modelo 181 summary uses printed boxes, with separate financial-operation detail."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_181_summary_preserves_official_boxes_and_all_registry_fields() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/181")).revisions["2022-y-siguientes"]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert len(layout.placements) == len(revision.casillas) == 62
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    assert {p.casilla_id: p.box_number for p in layout.placements if p.box_number} == {
        "numero-total-declarados": "01",
        "importe-total-capital-amortizado": "02",
        "importe-total-intereses": "03",
        "importe-total-gastos-financiacion": "04",
        "importe-total-saldos-pendientes": "05",
    }
    assert [p.id for p in layout.pages] == ["resumen", "operacion", "inmueble"]
    context = [b for s in layout.pages[0].sections for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    assert {str(resolve_form_context_field(revision, b).producer_key) for b in context} == {
        "taxpayer.tax_id",
        "contact_person.phone",
        "contact_person.full_name",
    }
    assert {s.source_ref for s in layout.design_sources} == {"boe-2009-21165-modelo-181-form", "aeat-dr-181-2022"}
    assert "2026" in (layout.review.notes or "")
