"""The Union's four operation categories remain distinct through settlement."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.schema_form_layouts import FormGridBlock

from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def revision():
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-union"]


def _calculate(revision, *, services_country="DE", include_ni_goods=False):
    grids = {
        block.id: block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock) and block.id != "resultado-estados"
    }
    amounts, texts, occupancy = {}, {}, {}
    entries = {
        "union-servicios": [(services_country, Decimal(190))],
        "union-bienes": [("DE", Decimal(380))],
        "union-ep": [("DE", Decimal(19))],
        "union-envio": [("DE", Decimal(38))],
        "correcciones": [("DE", Decimal(-20))],
    }
    if include_ni_goods:
        entries["union-bienes"].append(("XI", Decimal(10)))
    for name, grid in grids.items():
        columns = {column.key: i for i, column in enumerate(grid.columns)}
        for index, row in enumerate(grid.rows):
            country = row.cells[columns["pais-consumo"]].binding_id
            amount = row.cells[columns["correccion" if name == "correcciones" else "cuota"]].binding_id
            occupancy[country] = index < len(entries[name])
            if occupancy[country]:
                texts[country], amounts[amount] = entries[name][index]
    values = {}
    for formula in revision.formulas:
        if not str(formula.target_casilla_id).startswith(("iva.union.control.", "iva.union.resultado.")):
            continue
        values[formula.target_casilla_id] = evaluate_expression(
            formula.expression,
            values=values,
            binding_values=amounts,
            enum_binding_values=texts,
            record_row_occupancy=occupancy,
            parameters={},
            date_context={},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
        )
    return values


def test_spain_and_other_state_operations_keep_their_own_subtotals(revision):
    values = _calculate(revision)
    expected = {
        "servicios-espana": 190,
        "bienes-espana": 380,
        "total-espana": 570,
        "servicios-otros": 19,
        "bienes-otros": 38,
        "total-otros": 57,
        "total-periodo": 627,
        "correcciones-negativas": -20,
        "resultado": 607,
        "ingresar": 607,
        "devolver": 0,
    }
    assert {role: values[f"iva.union.resultado.de.{role}"] for role in expected} == expected
    assert values["iva.union.resultado.saldo-ingresar-espana"] == 607


def test_northern_ireland_goods_are_included(revision):
    values = _calculate(revision, include_ni_goods=True)
    assert values["iva.union.resultado.xi.bienes-espana"] == 10
    assert values["iva.union.resultado.xi.servicios-espana"] == 0
    assert values["iva.union.resultado.saldo-ingresar-espana"] == 617


@pytest.mark.parametrize("country", ["XI", "US", "de", ""])
def test_invalid_service_destination_cannot_disappear_from_total(revision, country):
    with pytest.raises(RegistryValidationError):
        _calculate(revision, services_country=country)


def test_official_union_result_grid_retains_every_amount_column(revision):
    page = revision.form_layouts[0].pages[5]
    grid = page.sections[0].blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert len(grid.columns) == 12
    assert len(grid.rows) == 28
    assert grid.rows[-1].official_heading == "XI"
    assert grid.official_row_heading == "Código país del Estado miembro de consumo"
    assert all(len(row.cells) == 12 for row in grid.rows)
