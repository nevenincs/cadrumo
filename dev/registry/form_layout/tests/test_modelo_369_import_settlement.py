"""Import settlement keeps country refunds separate from payments."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.formula_runtime_ops import UnresolvedFormulaDependencyError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormGridBlock

from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def revision():
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-importacion"]


def _scenario(revision, *, country="XI", quota=Decimal(30), close_rows=True):
    grids = {
        block.id: block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
    }
    amounts, texts, occupancy = {}, {}, {}
    for name, entries in (
        ("importaciones", [("DE", Decimal(190)), ("FR", Decimal(100)), (country, quota)]),
        ("correcciones", [("DE", Decimal(-20)), ("FR", Decimal(-140))]),
    ):
        grid = grids[name]
        columns = {column.key: index for index, column in enumerate(grid.columns)}
        amount_column = columns["cuota" if name == "importaciones" else "correccion"]
        for index, row in enumerate(grid.rows):
            country_binding = row.cells[columns["pais-consumo"]].binding_id
            amount_binding = row.cells[amount_column].binding_id
            if close_rows:
                occupancy[country_binding] = index < len(entries)
            if index < len(entries):
                text, amount = entries[index]
                if text is not None:
                    texts[country_binding] = text
                if amount is not None:
                    amounts[amount_binding] = amount
    values = {}
    for formula in revision.formulas:
        if not str(formula.target_casilla_id).startswith(("iva.importacion.control.", "iva.importacion.resultado.")):
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


def test_imports_include_northern_ireland_without_netting_french_refund(revision):
    values = _scenario(revision)
    assert values["iva.importacion.resultado.de.ingresar"] == 170
    assert values["iva.importacion.resultado.fr.resultado"] == -40
    assert values["iva.importacion.resultado.fr.devolver"] == 40
    assert values["iva.importacion.resultado.fr.ingresar"] == 0
    assert values["iva.importacion.resultado.xi.importaciones"] == 30
    assert values["iva.importacion.resultado.saldo-ingresar-espana"] == 200


@pytest.mark.parametrize("country", ["US", "GB", "xi", "", None])
def test_invalid_import_country_cannot_disappear_from_total(revision, country):
    with pytest.raises(RegistryValidationError):
        _scenario(revision, country=country)


def test_missing_import_amount_is_not_zero(revision):
    with pytest.raises(RegistryValidationError):
        _scenario(revision, quota=None)
    assert _scenario(revision, quota=Decimal(0))["iva.importacion.resultado.saldo-ingresar-espana"] == 170


def test_unclosed_import_rows_do_not_claim_a_complete_total(revision):
    with pytest.raises(UnresolvedFormulaDependencyError):
        _scenario(revision, close_rows=False)


def test_import_result_matches_official_page_columns(revision):
    page = revision.form_layouts[0].pages[2]
    assert "74102" in page.official_ref
    grid = page.sections[0].blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [column.key for column in grid.columns] == [
        "importaciones",
        "correcciones-positivas",
        "correcciones-negativas",
        "resultado",
        "ingresar",
        "devolver",
    ]
    assert len(grid.rows) == 28
    assert grid.rows[-1].official_heading == "XI"
    assert all(str(cell.casilla_id).startswith("iva.importacion.resultado.") for row in grid.rows for cell in row.cells)
