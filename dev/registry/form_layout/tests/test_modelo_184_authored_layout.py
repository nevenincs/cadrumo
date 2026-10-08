"""Current Modelo 184 presents semantic sections without electronic-file offsets."""

from pathlib import Path

import pytest

from cadrumo.application.storage.calc_sheets.workbook_exclusions import workbook_transport_controls
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormRepeatingGroupBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("revision_id,count", [("2023-2024", 86), ("2025-y-siguientes", 87)])
def test_184_keeps_each_revision_and_hides_only_declared_transport_controls(revision_id: str, count: int) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/184")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored" and layout.review.state.value == "generated"
    assert len(layout.placements) == count
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    assert all(p.box_number is None for p in layout.placements)
    assert workbook_transport_controls(revision) == {"decl.tipo-soporte", "tipo2.tipo-hoja", "tipo3.tipo-hoja"}
    assert [p.id for p in layout.pages] == ["m184-declarante", "m184-entidad", "m184-socio"]
    assert [s.id for s in layout.pages[1].sections] == [
        "identificacion-renta",
        "actividad",
        "cesionario",
        "inversion",
        "renta",
        "inmueble",
        "gastos-actividad",
        "gastos-inmueble",
    ]
    context = [b for s in layout.pages[0].sections for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    assert len(context) == 4
    assert {str(resolve_form_context_field(revision, b).producer_key) for b in context} == {
        "taxpayer.tax_id",
        "taxpayer.surnames_or_legal_name",
        "contact_person.phone",
        "contact_person.full_name",
    }
    summary = layout.pages[0].sections[-1]
    assert any(getattr(b, "casilla_id", None) == "decl.total-registros-entidad" for b in summary.blocks) == (
        revision_id == "2025-y-siguientes"
    )
    members = layout.pages[2].sections[0].blocks[0]
    assert isinstance(members, FormRepeatingGroupBlock)
    assert len(members.columns) == 23
    assert [str(c.casilla_id) for c in members.columns[:3]] == [
        "tipo3.miembro-nif",
        "tipo3.representante-fiscal-nif",
        "tipo3.miembro-nombre",
    ]
