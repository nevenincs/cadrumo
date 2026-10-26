"""BOE Annex I structure keeps fiscal fields and excludes protocol controls."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_refund_form_preserves_all_fields_without_wire_offset_box_numbers() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/360")).revisions["2010-y-siguientes"]
    (layout,) = revision.form_layouts
    assert form_layout_failures(revision) == ()
    assert layout.seed_source == "authored"
    assert len(layout.pages) == 3
    assert len(layout.placements) == len(revision.casillas) == 226
    assert not any(p.box_number for p in layout.placements)
    excluded = {p.casilla_id for p in layout.placements if p.workbook_exclusion}
    assert excluded == {"decl.presentacion-pruebas", "decl.calidad-datos"}
    assert all(p.kind == "on_form" for p in layout.placements if p.casilla_id not in excluded)


def test_activities_annexes_and_both_operation_tables_keep_numeric_row_order() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/360")).revisions["2010-y-siguientes"]
    grids = {
        block.id: block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
    }
    assert set(grids) == {"actividades", "anexos", "bienes-1", "bienes-2"}
    for grid in grids.values():
        assert [row.key for row in grid.rows] == [f"fila-{i}" for i in range(1, 11)]
    for n in (1, 2):
        for i, row in enumerate(grids[f"bienes-{n}"].rows, 1):
            assert [cell.casilla_id for cell in row.cells] == [
                f"decl.op{n}-{key}-{i}" for key in ("codigo", "idioma", "descripcion")
            ]


def test_applicant_identity_uses_exact_filing_producer_owners() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/360")).revisions["2010-y-siguientes"]
    contexts = [
        block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock)
    ]
    assert {block.export_field_id for block in contexts} == {"m360-2010.pagina01.f012", "m360-2010.pagina01.f013"}
    assert all(block.export_record_id == "m360-solicitud" for block in contexts)
