"""Modelo 347 retains per-person quarterly amounts and exact filing identity."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormRepeatingGroupBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("revision_id", ["2011-2024", "2025-y-siguientes"])
def test_quarters_remain_inside_each_declared_person(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/347")).revisions[revision_id]
    (layout,) = revision.form_layouts
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    summary, persons, properties = layout.pages
    assert [s.id for s in summary.sections] == ["identificacion", "contacto", "declaracion", "resumen", "firma"]
    signature_fields = [c for c in revision.casillas if c.id.startswith("firma-")]
    assert {c.id for c in signature_fields} == {"firma-fecha", "firma-nombre", "firma-cargo"}
    assert all(c.input_kind.value == "informational" and c.binding is None for c in signature_fields)
    assert all(p.box_number is None for p in layout.placements if p.casilla_id.startswith("firma-"))
    contexts = [b for s in summary.sections for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    assert {b.id for b in contexts} == {
        "nif",
        "nombre",
        "anterior",
        "resumen-personas",
        "resumen-operaciones",
        "resumen-inmuebles",
        "resumen-arrendamientos",
    }
    assert {b.box_number for b in contexts if b.box_number} == {"01", "02", "03", "04"}
    assert all(b.export_record_id == "m347-declarante" for b in contexts)
    (group,) = persons.sections[0].blocks
    assert isinstance(group, FormRepeatingGroupBlock)
    assert group.export_record_id == "m347-declarado"
    (grid,) = group.grids
    assert len(grid.rows) == 4
    for quarter, row in enumerate(grid.rows, start=1):
        assert [cell.casilla_id for cell in row.cells] == [
            f"contraparte.importe-Q{quarter}",
            f"contraparte.importe-transmisiones-Q{quarter}",
        ]
    assert [c.casilla_id for c in group.columns[:2]] == ["contraparte.nif", "contraparte.nombre"]
    (property_group,) = properties.sections[0].blocks
    assert isinstance(property_group, FormRepeatingGroupBlock)
    assert property_group.export_record_id == "m347-inmueble"
    assert {c.casilla_id for c in property_group.columns} == {
        c.id for c in revision.casillas if c.id.startswith("inmueble.")
    }
    if revision_id == "2025-y-siguientes":
        assert "contraparte.numero-convocatoria-bdns" in {c.casilla_id for c in group.columns}
