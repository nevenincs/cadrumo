"""Preserve recipient bindings and the withdrawal of the historical paper form."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormRepeatingGroupBlock
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("position", "field_count", "source"),
    [
        (0, 64, "aeat-dr-190-2020"),
        (1, 69, "aeat-dr-190-2023"),
        (2, 70, "aeat-dr-190-2024"),
        (3, 76, "aeat-dr-190-2025"),
    ],
)
def test_recipient_sections_preserve_revision_fields_and_official_numbering(
    position: int, field_count: int, source: str
) -> None:
    revision_id = str(authored_revisions("190")[position].id)
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/190")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert len(layout.placements) == field_count
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    assert all(p.kind.value == "on_form" for p in layout.placements)
    numbered = {
        str(p.casilla_id): p.box_number for p in layout.placements if (p.box_number is not None and p.box_number)
    }
    if position == 3:
        assert numbered == {}
        assert [s.source_ref for s in layout.design_sources] == [source]
    else:
        assert numbered == {
            "decl.total-percepciones": "01",
            "decl.percepciones-total": "02",
            "decl.retenciones-total": "03",
        }
        assert [s.source_ref for s in layout.design_sources] == ["boe-2009-18567-modelo-190-form-pdf", source]
    groups = [
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock)
    ]
    assert all(g.row_source.value == "export_record" for g in groups)
    assert all(g.export_record_id == "modelo-190-perceptor" for g in groups)
    columns = [column for group in groups for column in group.columns]
    recipient_ids = {c.id for c in revision.casillas if str(c.id).startswith("perc.")}
    assert {c.casilla_id for c in columns} == recipient_ids
    assert len(columns) == len(recipient_ids)
    assert max(len(g.columns) for g in groups) <= 10
    assert ("perc.prestacion-jubilacion" in recipient_ids) == (position == 3)
    assert ("perc.retenciones-forales-navarra" in recipient_ids) == (position != 0)
