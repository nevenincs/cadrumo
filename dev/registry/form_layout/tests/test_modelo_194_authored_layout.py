"""The partial Modelo 194 summary must not net positive and negative bases."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormGridBlock,
    FormRepeatingGroupBlock,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("revision_id", ["2019", "2023", "2024"])
def test_summary_keeps_separate_bases_without_inventing_calculations(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/194")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert revision.authority_grade is not None
    assert revision.authority_grade.value == "applicability"
    assert {str(formula.target_casilla_id) for formula in revision.formulas} == {"02", "03", "05"}
    assert {str(c.id) for c in revision.casillas if c.input_kind.value == "bound"} == {"01", "04"}
    assert len(revision.export_layouts) == 1
    placements = {str(p.casilla_id): p.box_number for p in layout.placements}
    assert {key: value for key, value in placements.items() if key.isdigit()} == {f"0{i}": f"0{i}" for i in range(1, 6)}
    # Electronic record offsets are not printed box numbers on the human form.
    declaration_fields = {str(c.id) for c in revision.casillas if str(c.id).startswith("decl.")}
    assert len(declaration_fields) == 6
    assert {key: placements[key] for key in declaration_fields} == dict.fromkeys(declaration_fields)
    section_ids = [s.id for s in layout.pages[0].sections]
    assert section_ids == [
        "identificacion",
        "contacto",
        "declaracion",
        "resumen",
    ]
    for casilla in revision.casillas:
        for locale in ("es", "en", "ca", "hu"):
            label = casilla.get_label(locale)
            assert label and not label.startswith("modelo.schema.")
    grid = layout.pages[0].sections[-1].blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [[cell.casilla_id for cell in row.cells] for row in grid.rows] == [["01", "02", "03"], ["04", "05", None]]
    assert grid.rows[1].cells[2].kind.value == "blank"
    assert layout.review.notes is not None
    assert "not a complete" in layout.review.notes


@pytest.mark.parametrize(("epoch", "count"), [("2019", 28), ("2023", 29), ("2024", 29)])
def test_published_editions_place_every_recipient_field_and_real_identity_context(epoch: str, count: int) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/194")).revisions[epoch]
    layout = revision.form_layouts[0]
    assert all(p.kind.value == "on_form" for p in layout.placements)
    assert len(layout.placements) == count
    assert len(layout.pages) == 3
    blocks = [block for page in layout.pages for section in page.sections for block in section.blocks]
    groups = [block for block in blocks if isinstance(block, FormRepeatingGroupBlock)]
    columns = [column.casilla_id for group in groups for column in group.columns]
    expected = {c.id for c in revision.casillas if str(c.id).startswith("perc.")}
    assert set(columns) == expected
    assert len(columns) == len(expected) == count - 11
    assert all(group.export_record_id == "modelo-194-perceptor" for group in groups)
    assert max(len(group.columns) for group in groups) == 4
    context = [block for block in blocks if isinstance(block, FormContextFieldBlock)]
    assert {block.export_field_id for block in context} == {
        "modelo-194-decl-nif",
        "modelo-194-decl-nombre",
        "modelo-194-decl-year",
    }
    assert all(block.export_layout_id == revision.export_layouts[0].id for block in context)
    assert "perc.reducciones" not in columns
