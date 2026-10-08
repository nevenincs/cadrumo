"""Modelo 180 keeps printed summary boxes and exact repeating-record fields."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormRepeatingGroupBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "revision_id,source", [("2019-2022", "aeat-dr-180-2014"), ("2023-y-siguientes", "aeat-dr-180-2023")]
)
def test_180_printed_boxes_do_not_confuse_record_offsets(revision_id: str, source: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/180")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert {str(p.casilla_id) for p in layout.placements} == {str(c.id) for c in revision.casillas}
    boxes = {str(p.casilla_id): p.box_number for p in layout.placements if p.box_number}
    assert boxes == {"decl.total-perceptores": "01", "decl.base-total": "02", "decl.retenciones-total": "03"}
    assert {str(p.source_ref) for p in layout.design_sources} == {"boe-2000-21430-modelo-115-form", source}
    assert [s.id for s in layout.pages[0].sections] == ["declarante", "ejercicio", "declaracion", "resumen"]
    context = [b for s in layout.pages[0].sections for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    fields = [resolve_form_context_field(revision, block) for block in context]
    assert len(fields) == 5
    assert {str(f.producer_key) for f in fields if f.producer_key} == {
        "taxpayer.tax_id",
        "taxpayer.full_name",
        "contact_person.phone",
        "contact_person.full_name",
    }
    assert {str(f.draft_attribute) for f in fields if f.draft_attribute} == {"filing_year"}
    repeated = layout.pages[1].sections[0].blocks[0]
    assert isinstance(repeated, FormRepeatingGroupBlock)
    assert repeated.export_record_id == "modelo-180-perceptor"
    ids = [str(column.casilla_id) for column in repeated.columns]
    assert ids[:9] == [
        "perc.nif",
        "perc.nif-representante-legal",
        "perc.nombre",
        "perc.provincia",
        "perc.modalidad",
        "perc.base",
        "perc.porcentaje-retencion",
        "perc.retenciones",
        "perc.ejercicio-devengo",
    ]
    assert len(ids) == len(set(ids)) == 27
    assert set(ids) == {str(c.id) for c in revision.casillas if str(c.id).startswith("perc.")}
