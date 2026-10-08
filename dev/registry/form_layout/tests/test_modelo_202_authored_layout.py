"""The 2025 form keeps four rate columns and asymmetric correction boxes."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormCellKind, FormContextFieldBlock, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_202_additional_details_resolve_declared_regime_facts() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/202")).revisions["2025-y-siguientes"]
    sections = revision.form_layouts[0].pages[0].sections
    details = next(section for section in sections if section.id == "datos-adicionales")
    assert [section.id for section in sections][:3] == ["identificacion", "devengo", "datos-adicionales"]
    assert all(isinstance(block, FormContextFieldBlock) for block in details.blocks)
    assert [
        str(resolve_form_context_field(revision, block).producer_key)
        for block in details.blocks
        if isinstance(block, FormContextFieldBlock)
    ] == [
        "m202.regimen.ley_49_2002_sin_fines_lucrativos",
        "m202.regimen.ley_11_2009_socimi",
        "m202.regimen.entidad_capital_riesgo",
        "m202.regimen.entidades_navieras_tonelaje",
        "m202.regimen.articulo_101_lis_reducida_dimension",
        "m202.cifra_negocios_doce_meses_umbral",
        "m202.cooperativa_fiscalmente_protegida",
        "m202.cifra_negocios_periodo_anterior_bajo_umbral",
        "m202.multiples_tipos_impositivos",
        "m202.tipo_gravamen_impuesto_sociedades",
    ]


@pytest.mark.parametrize("revision_id", ["2019-2022", "2023-2024"])
def test_202_historical_pages_keep_two_rates_and_b1_on_first_page(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/202")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.placements) == 54
    assert "b1" in {s.id for s in layout.pages[0].sections}
    assert "b1" not in {s.id for s in layout.pages[1].sections}
    grids = {b.id: b for p in layout.pages for s in p.sections for b in s.blocks if isinstance(b, FormGridBlock)}
    assert [[str(c.casilla_id) for c in row.cells] for row in grids["tipos"].rows] == [
        ["20", "21", "22"],
        ["23", "24", "25"],
    ]
    assert len(grids["correcciones"].rows) == 4
    assert not {"61", "62", "63", "64", "65", "66", "67"} & {str(p.casilla_id) for p in layout.placements}
    details = next(s for s in layout.pages[0].sections if s.id == "datos-adicionales")
    keys = {
        str(resolve_form_context_field(revision, block).producer_key)
        for block in details.blocks
        if isinstance(block, FormContextFieldBlock)
    }
    assert len(details.blocks) == (7 if revision_id == "2019-2022" else 8)
    assert "m202.regimen.entidad_capital_riesgo" in keys
    assert "m202.cooperativa_o_multiples_tipos" not in keys
    assert "m202.cooperativa_fiscalmente_protegida" not in keys
    assert "m202.multiples_tipos_impositivos" not in keys
    assert ("m202.cifra_negocios_periodo_anterior_bajo_umbral" in keys) is (revision_id == "2023-2024")
    small_enterprise = next(b for b in details.blocks if b.id == "reducida-dimension")
    assert isinstance(small_enterprise, FormContextFieldBlock)
    assert (
        small_enterprise.heading_key == "modelo.schema.202.form.authored-historical.context.reducida-dimension.heading"
    )


def test_202_current_grid_matches_the_printed_rate_and_correction_boxes() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/202")).revisions["2025-y-siguientes"]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.placements) == len(revision.casillas) == 61
    grids = {b.id: b for p in layout.pages for s in p.sections for b in s.blocks if isinstance(b, FormGridBlock)}
    assert [[str(c.casilla_id) for c in row.cells] for row in grids["tipos"].rows] == [
        ["20", "21", "22"],
        ["23", "24", "25"],
        ["61", "62", "63"],
        ["64", "65", "66"],
    ]
    correction_rows = grids["correcciones"].rows
    assert correction_rows[1].cells[0].casilla_id == "67"
    assert correction_rows[1].cells[1].kind is FormCellKind.BLANK
    assert correction_rows[2].cells[0].kind is FormCellKind.BLANK
    assert correction_rows[2].cells[1].casilla_id == "37"
    assert layout.review.state.value == "generated"
    assert layout.review.notes and "Part 2" in layout.review.notes
    assert "boe-2025-5407-modelo-202-form-pdf" in {str(s.source_ref) for s in layout.design_sources}
