"""Historical group-VAT fixtures preserve real template fields and unknowns."""

from decimal import Decimal

import pytest

from cadrumo.application.storage.calc_sheets.records import TabName

from ..workbook_demo_group_vat_historical import build_historical_group_vat_plan

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.mark.parametrize("year", [2022, 2023, 2025])
def test_historical_322_example_compiles_every_printed_total_without_future_boxes(year: int) -> None:
    source, plan = build_historical_group_vat_plan(year=year)
    assert plan.metadata.template_digest == source.template_digest
    assert plan.tabs[0] is TabName.FORM
    mirrors = {cell.casilla_id: cell for cell in plan.formula_cells if cell.address.tab is TabName.FORM}
    assert {"38", "62", "63", "65", "68", "70", "88", "717", "735"} <= mirrors.keys()
    assert "112" not in mirrors
    inputs = {
        cell.casilla_id: cell for cell in plan.value_cells if cell.address.tab is TabName.ENTRADAS and cell.casilla_id
    }
    assert inputs["20"].value == Decimal("2100")
    assert inputs["decl.prorrata-especial"].value == "1"
    assert inputs["actividad.principal.codigo"].value is None
    assert "70" not in inputs
    assert inputs["20"].address.qualified() in mirrors["20"].formula
    text = "\n".join(str(cell.value) for cell in plan.value_cells)
    assert "Entidad ficticia del grupo Ejemplo" in text
    assert "B12345674" in text
    assert source.template_digest not in text
    if year == 2022:
        assert inputs["73"].value is None
        assert "73" in mirrors
        assert "150" not in inputs
        assert "Clave" in text
