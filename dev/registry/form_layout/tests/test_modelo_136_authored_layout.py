"""BOE-A-2018-10064 annex III places both numbered and unnumbered 136 fields."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormFieldBlock,
    FormLayoutSeedSource,
    FormPlacementKind,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("revision_id", ["2022-2025", "2026"])
def test_annex_iii_places_all_twenty_four_declared_fields(revision_id):
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/136")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    assert form_layout_failures(revision) == ()
    assert len(layout.pages) == 1
    sections = layout.pages[0].sections
    assert [str(s.id) for s in sections] == [
        "declarante",
        "devengo",
        "loteria",
        "liquidacion",
        "complementaria",
        "ingreso",
    ]
    assert [len(s.blocks) for s in sections] == [3, 3, 6, 7, 2, 3]
    placed = [str(b.casilla_id) for s in sections for b in s.blocks if isinstance(b, FormFieldBlock)]
    assert len(placed) == len(set(placed)) == len(revision.casillas) == 24
    assert set(placed) == {str(c.id) for c in revision.casillas}
    assert all(p.kind is FormPlacementKind.ON_FORM for p in layout.placements)
    boxes = {str(p.casilla_id): p.box_number for p in layout.placements}
    assert {k: v for k, v in boxes.items() if v is not None} == {f"{n:02}": f"{n:02}" for n in range(1, 8)}
    # The payment field is labelled I on paper; 09 occurs in its caption only.
    # Do not manufacture a numeric box 08 or mislabel I as a printed box 09.
    assert boxes["09"] is None
    assert "08" not in boxes
    assert [str(b.casilla_id) for b in sections[-1].blocks if isinstance(b, FormFieldBlock)] == [
        "09",
        "forma-pago",
        "iban",
    ]
    assert {str(s.source_ref) for s in layout.design_sources} == {"boe-modelo-136-current-form"}
