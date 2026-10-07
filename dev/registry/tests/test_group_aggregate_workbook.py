"""Group examples use the selected template, typed member data and live formulas."""

from decimal import Decimal

import pytest

from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.application.storage.calc_sheets.records import TabName
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.core.period import Period
from cadrumo.domain.period import calculation_filing_date

from ..workbook_demo_group_aggregate import build_group_aggregate_plan

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.mark.parametrize("period,pages", [("01", 1), ("02", 2)])
def test_group_example_keeps_member_values_and_settlement_formula_sources(period: str, pages: int) -> None:
    source, plan = build_group_aggregate_plan(year=2026, period=period)
    assert len(source.revision.form_layouts[0].pages) == pages
    assert plan.metadata.template_digest == source.template_digest
    assert plan.tabs[0] is TabName.FORM
    layout = plan_layout(
        source.revision, bracket_filter_date=calculation_filing_date(Period.from_year_and_code(2026, period))
    )
    values = {cell.address: cell.value for cell in plan.value_cells}
    prefix = "modelo-353.page_01.entidad-2-"
    assert values[layout.binding_cells[prefix + "entidades-dependientes-resultado"]] == Decimal("-100")
    assert values[layout.binding_cells[prefix + "ent-depndtes-de-participac-al-final-del"]] == Decimal("75.25")
    assert values[layout.binding_cells[prefix + "entidades-dependientes-numero-de-justifi"]] == "0000000000003"
    assert values[layout.entradas_cells["01"]] == Decimal("2100")
    inputs = {
        cell.casilla_id: cell for cell in plan.value_cells if cell.address.tab is TabName.ENTRADAS and cell.casilla_id
    }
    for identifier in ("06", "07", "papel.importe-ingreso"):
        assert inputs[identifier].value is None
    formulas = {cell.casilla_id: cell for cell in plan.formula_cells if cell.address.tab is TabName.CALCULOS}
    assert {"03", "05", "09"} <= formulas.keys()
    assert "05" not in inputs
    if period == "02":
        assert inputs["10"].address.qualified() in formulas["05"].formula
    else:
        assert "10" not in inputs
    text = "\n".join(str(cell.value) for cell in plan.value_cells)
    assert "Grupo ficticio Ejemplo" in text
    for key in ("avanzado", "redeme"):
        heading = lookup_translation(f"modelo.schema.353.form.authored.{key}.heading", locale="es")
        # Locate through the declared heading, never a fixed row coordinate.
        labels = [cell for cell in plan.value_cells if cell.address.tab is TabName.FORM and cell.value == heading]
        assert len(labels) == 1
        assert any(
            cell.address.tab is TabName.FORM and cell.address.row == labels[0].address.row and cell.value == "No"
            for cell in plan.value_cells
        )
    assert any(
        "Cambiar una fila de entidades no actualiza ese total" in paragraph for paragraph in plan.guide.paragraphs
    )
    assert source.template_digest not in text
