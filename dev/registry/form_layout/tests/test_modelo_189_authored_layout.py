"""Summary boxes and complete detail placement across the 189 design epochs."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("position", range(4))
def test_summary_and_detail_preserve_every_field_and_only_real_box_numbers(position: int) -> None:
    revision_id = str(authored_revisions("189")[position].id)
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/189")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert len(layout.placements) == 25
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    assert all(p.kind.value == "on_form" for p in layout.placements)
    assert {
        str(p.casilla_id): p.box_number for p in layout.placements if (p.box_number is not None and p.box_number)
    } == {
        "numero-total-declarados": "01",
        "valoracion-total": "02",
    }
    assert [s.id for s in layout.pages[0].sections] == ["declarante", "ejercicio", "declaracion", "resumen"]
    assert [s.id for s in layout.pages[1].sections] == ["identificacion", "valor", "valoracion"]
    assert layout.design_sources[0].source_ref == "boe-2008-19523-modelo-189-form-pdf"
    assert layout.design_sources[1].source_ref == ("aeat-dr-189-2021-2022" if position == 0 else "aeat-dr-189-2023")
    assert not revision.formulas
