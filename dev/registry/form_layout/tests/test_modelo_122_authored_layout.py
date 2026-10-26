"""Current 122 grouping follows BOE annex II; record offsets are not boxes."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormFieldBlock,
    FormLayoutSeedSource,
    FormPlacementKind,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_122_groups_dependants_and_keeps_transport_markers_off_the_form() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/122")).revisions["2017-y-siguientes"]
    layout = revision.form_layouts[0]
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    assert form_layout_failures(revision) == ()
    sections = layout.pages[0].sections
    assert [str(s.id) for s in sections] == [
        "ejercicio",
        "contribuyente",
        "descendientes",
        "ascendientes",
        "conyuge",
        "familia-numerosa",
        "ascendiente-dos-hijos",
        "liquidacion",
        "ingreso",
        "complementaria",
        "representante",
    ]
    for family in ("descendientes", "ascendientes"):
        section = next(s for s in sections if s.id == family)
        assert [str(b.casilla_id) for b in section.blocks if isinstance(b, FormFieldBlock)] == [
            f"{family}.{suffix}" for suffix in ("nif", "nombre", "deduccion", "abono-anticipado")
        ]
    placements = {str(p.casilla_id): p for p in layout.placements}
    assert len(placements) == len(revision.casillas) == 22
    for identifier in ("decl.pagina-complementaria", "decl.tipo-declaracion"):
        assert placements[identifier].kind is FormPlacementKind.WORKING_FIGURE
        assert placements[identifier].box_number is None
    assert placements["decl.ejercicio"].kind is FormPlacementKind.ON_FORM
    contexts = [b for s in sections for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    assert len(contexts) == 6
    assert all(b.export_record_id == "modelo-122-pagina-01" for b in contexts)
    assert "boe-modelo-122-form-2018" in {str(s.source_ref) for s in layout.design_sources}
    # This authoring increment must not claim the 2017 form has been reconciled.
    assert layout.review.state.value == "generated"
    assert layout.review.notes is not None and "original 2017 form" in layout.review.notes
