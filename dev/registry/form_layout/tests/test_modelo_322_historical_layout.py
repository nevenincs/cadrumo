"""Historical 322 pages preserve their own boxes and explicit paper declarations."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormFieldBlock, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("revision_id, expected_rows", [("2008-2022", 14), ("2023", 19), ("2024-2025", 22)])
def test_historical_322_has_the_official_grids_and_no_future_gasoline_fields(
    revision_id: str, expected_rows: int
) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source == "authored"
    assert len(layout.pages) == 4
    assert {item.casilla_id for item in layout.placements} == {item.id for item in revision.casillas}
    grids = {
        block.id: block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
    }
    assert len(grids["devengado"].rows) == expected_rows
    shown = {cell.casilla_id for row in grids["devengado"].rows for cell in row.cells}
    assert ({"167", "170", "173"} <= shown) == (revision_id == "2024-2025")
    assert {"112", "decl.deduccion-pago-cuenta-gasolinas"}.isdisjoint(layout.casilla_sections())
    activities = grids["actividades"]
    assert len(activities.rows) == 6
    assert all(str(row.cells[0].casilla_id).endswith(".descripcion") for row in activities.rows)
    assert layout.pages[2].condition_periods == ("12",)


@pytest.mark.parametrize("revision_id", ["2008-2022", "2023", "2024-2025", "2026-y-siguientes"])
def test_no_activity_is_an_explicit_form_input_and_not_a_settlement_formula(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322")).revisions[revision_id]
    owner = next(item for item in revision.casillas if item.id == "decl.sin-actividad")
    assert owner.input_kind == "manual"
    assert owner.formula is None
    assert owner.constraints is not None
    assert owner.constraints.enum == ("X", "")
    fields = [
        block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormFieldBlock) and block.casilla_id == owner.id
    ]
    assert len(fields) == 1


@pytest.mark.parametrize("revision_id", ["2008-2022", "2023", "2024-2025"])
def test_historical_identification_choices_do_not_offer_later_empty_code(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322")).revisions[revision_id]
    fields = {
        block.casilla_id: block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormFieldBlock)
    }
    for casilla_id in ("decl.exonerado-modelo-390", "decl.volumen-anual-no-cero"):
        assert {choice.value for choice in fields[casilla_id].choices} == {"1", "2"}
    assert {choice.value for choice in fields["decl.prorrata-especial"].choices} == {"0", "1", "2"}


def test_2022_keeps_the_legacy_record_slot_outside_the_official_form() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322")).revisions["2008-2022"]
    layout = revision.form_layouts[0]
    placements = {item.casilla_id: item for item in layout.placements}
    assert placements["73"].kind == "working_figure"
    assert placements["73"].workbook_exclusion is None
    assert "73" not in layout.casilla_sections()
    assert all(str(number) not in placements for number in range(150, 174))
    assert revision.period_selector.years == (2022,)
    contexts = {
        block.id: block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if block.kind == "context_field"
    }
    assert contexts["marca-complementaria"].export_field_id == "m322-2022.page-02.f018"
    assert contexts["justificante"].export_field_id == "m322-2022.page-02.f019"
