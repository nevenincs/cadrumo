"""The 349 form summary and correction detail share backend invoice facts."""

import re
from decimal import Decimal

import pytest

from cadrumo.application.storage.calc_sheets.records import TabName

from ..workbook_demo import DemoCase, build_demonstration_plan
from ..workbook_demo_intracommunity import intracommunity_records, intracommunity_summary

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("governed_fact_scope")]


def test_compiled_intracommunity_summary_and_correction_share_invoice_projection() -> None:
    snapshot, plan = build_demonstration_plan(DemoCase("349", "2020-y-siguientes", None, None))
    summary = intracommunity_summary(snapshot)
    expected = {
        "numero-operadores": Decimal("2"),
        "importe-operaciones": Decimal("16500"),
        "numero-rectificaciones": Decimal("1"),
        "importe-rectificaciones": Decimal("900"),
    }
    inputs = {
        str(cell.casilla_id): cell.value
        for cell in plan.value_cells
        if cell.address.tab is TabName.ENTRADAS and cell.casilla_id
    }
    for suffix, amount in expected.items():
        assert summary[f"iva-349-declarante-{suffix}"] == amount
        assert inputs[f"decl.{suffix}"] == amount
    rows = intracommunity_records(snapshot).row_binding_values
    assert rows["iva-349-operador-row-nif"] == {"1": "123456789", "2": "12345678901"}
    assert Decimal(rows["iva-349-operador-row-base"]["1"]) == Decimal("12000")
    assert rows["iva-349-rectificacion-row-codigo-pais"] == {"1": "IT"}
    assert rows["iva-349-rectificacion-row-periodo"] == {"1": "3T"}
    assert Decimal(rows["iva-349-rectificacion-row-base-rectificada"]["1"]) == Decimal("900")
    assert Decimal(rows["iva-349-rectificacion-row-base-anterior"]["1"]) == Decimal("1000")
    form_values = [cell.value for cell in plan.value_cells if cell.address.tab is TabName.FORM]
    assert "Empresa ficticia C" in form_values
    assert "3T" in form_values
    assert Decimal("900") in form_values and Decimal("1000") in form_values
    year_cells = [
        cell.address for cell in plan.value_cells if cell.address.tab is TabName.FORM and cell.value == Decimal("2025")
    ]
    assert year_cells
    formats = {directive.address: directive.pattern for directive in plan.number_formats}
    assert len(year_cells) == 2
    assert all(formats[address] == "0" for address in year_cells)
    assert not re.search(r"\b[0-9a-f]{64}\b", "\n".join(str(value) for value in form_values))
    assert plan.guide is not None
    assert "no la diferencia" in " ".join(plan.guide.paragraphs)
