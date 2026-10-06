"""Modelo 193 keeps recipients and expense owners in distinct repeating records."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormRepeatingGroupBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("revision_id", "field_count", "source"),
    [
        ("2022", 42, "aeat-dr-193-2019"),
        ("2023", 48, "aeat-dr-193-2023"),
        ("2024", 52, "aeat-dr-193-2024"),
        ("2025-y-siguientes", 53, "aeat-dr-193-2025"),
    ],
)
def test_official_sections_preserve_both_repeating_record_owners(
    revision_id: str, field_count: int, source: str
) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/193")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert len(layout.placements) == field_count
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    assert all(p.kind.value == "on_form" for p in layout.placements)
    assert {str(p.casilla_id): p.box_number for p in layout.placements if p.box_number} == {
        "decl.total-perceptores": "01",
        "decl.base-total": "02",
        "decl.retenciones-total": "03",
        "decl.retenciones-ingresadas": "04",
        "decl.gastos-total": "05",
    }
    assert [s.source_ref for s in layout.design_sources] == ["boe-2011-19396-modelo-193-form-pdf", source]
    groups = [
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock)
    ]
    for prefix, record in (("perc.", "modelo-193-perceptor"), ("gasto.", "modelo-193-gastos")):
        columns = [column for group in groups if group.export_record_id == record for column in group.columns]
        expected = {c.id for c in revision.casillas if str(c.id).startswith(prefix)}
        assert {column.casilla_id for column in columns} == expected
        assert len(columns) == len(expected)
    assert all(group.row_source.value == "export_record" for group in groups)
    assert max(len(group.columns) for group in groups) <= 8
    assert all(len(page.sections) <= 4 for page in layout.pages)
