"""DR145 family slots retain their identity when rendered as readable tables."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormGridBlock, FormLayoutSeedSource

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_145_family_tables_preserve_each_record_slot_and_disclose_historical_scope() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/145")).revisions[
        "2012-01-31-y-siguientes"
    ]
    layout = revision.form_layouts[0]
    assert layout.seed_source is FormLayoutSeedSource.AUTHORED
    assert form_layout_failures(revision) == ()
    sections = layout.pages[0].sections
    assert [s.id for s in sections] == [
        "perceptor",
        "descendientes",
        "ascendientes",
        "pensiones",
        "vivienda",
        "firma",
        "acuse",
    ]
    expected = (
        (
            sections[1],
            "descendiente",
            4,
            ("anio-nacimiento", "anio-adopcion", "discapacidad-grado", "ayuda-movilidad", "computo-entero"),
        ),
        (
            sections[2],
            "ascendiente",
            2,
            ("anio-nacimiento", "discapacidad-grado", "ayuda-movilidad", "convivencia-otros"),
        ),
    )
    for section, family, count, columns in expected:
        grid = section.blocks[0]
        assert isinstance(grid, FormGridBlock)
        assert tuple(c.key for c in grid.columns) == columns
        assert len(grid.rows) == count
        for number, row in enumerate(grid.rows, 1):
            assert [str(cell.casilla_id) for cell in row.cells] == [f"{family}-{number}.{column}" for column in columns]
    assert len(layout.placements) == len(revision.casillas) == 56
    control = next(p for p in layout.placements if p.casilla_id == "comunicacion.pagina-complementaria")
    assert control.workbook_exclusion == "transport_control"
    assert control.workbook_exclusion_reason and "byte 10" in control.workbook_exclusion_reason
    assert all(p.box_number is None for p in layout.placements)
    assert layout.review.state.value == "generated"
    assert layout.review.notes and "not a verified current payer communication" in layout.review.notes
    assert {str(s.source_ref) for s in layout.design_sources} == {"aeat-dr-145-v20"}
