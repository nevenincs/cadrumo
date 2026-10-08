"""Historical and electronic forms retain live arithmetic and honest absences."""

from decimal import Decimal

import pytest

from cadrumo.application.storage.calc_sheets.records import TabName

from ..workbook_demo_agricultural_compensation import build_agricultural_compensation_plan

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.mark.parametrize("year", [2015, 2026])
def test_compiled_compensation_example_has_live_rows_and_refund_mirror(year: int) -> None:
    source, plan = build_agricultural_compensation_plan(year=year)
    inputs = {
        cell.casilla_id: cell for cell in plan.value_cells if cell.address.tab is TabName.ENTRADAS and cell.casilla_id
    }
    calculations = {cell.casilla_id: cell for cell in plan.formula_cells if cell.address.tab is TabName.CALCULOS}
    assert {"07", "08", "09", "10"} <= calculations.keys()
    assert not {"07", "08", "09", "10"}.intersection(inputs)
    for result, base, rate in (("07", "01", "04"), ("08", "02", "05"), ("09", "03", "06")):
        assert inputs[base].address.qualified() in calculations[result].formula
        assert inputs[rate].address.qualified() in calculations[result].formula
    assert inputs["01"].value == Decimal("1500")
    assert inputs["05"].value == Decimal("10.5")
    for result in ("07", "08", "09"):
        assert calculations[result].address.qualified() in calculations["10"].formula
    total_mirrors = [
        cell for cell in plan.formula_cells if cell.address.tab is TabName.FORM and cell.casilla_id == "10"
    ]
    assert len(total_mirrors) == 2
    assert all(calculations["10"].address.qualified() in cell.formula for cell in total_mirrors)
    text = "\n".join(str(cell.value) for cell in plan.value_cells)
    assert "12345678Z" in text and "00000000T" not in text
    assert source.template_digest not in text
    if year == 2015:
        assert inputs["papel-domicilio-codigo-postal"].value == "08001"
        assert inputs["papel-firma"].value is None
        assert inputs["wire.codigo-cuenta-cliente"].value is None
    else:
        assert not any(key.startswith("papel-") for key in inputs)
