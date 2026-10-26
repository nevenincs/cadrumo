"""Country settlement uses the authored registry formulas and exact detail cells."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.storage.calc_sheets.errors import CalcSheetsEngineError
from cadrumo.application.storage.calc_sheets.fictional_rows import fictional_unused_form_rows
from cadrumo.application.storage.calc_sheets.formula_guards import conditional_missing_input_guard
from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.formula_runtime_ops import UnresolvedFormulaDependencyError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormGridBlock

from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_compiled_settlement_guards_do_not_expand_transitive_formula_trees(revision):
    layout = plan_layout(revision)
    formulas = {formula.target_casilla_id: formula.expression for formula in revision.formulas}
    for expression in formulas.values():
        guard = conditional_missing_input_guard(expression, formulas=formulas, layout=layout)
        assert len(guard or "") < 30000
    total = formulas["iva.exterior.resultado.saldo-ingresar-espana"]
    assert len(conditional_missing_input_guard(total, formulas=formulas, layout=layout) or "") < 1000


@pytest.fixture(scope="module")
def revision():
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-exterior"]


def _scenario(revision, *, country="DE", quota=Decimal(190), close_rows=True):
    grids = {
        block.id: block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
    }
    amounts, texts, occupancy = {}, {}, {}
    for name, entries in (
        ("exterior-servicios", [(country, quota), ("FR", Decimal(100))]),
        ("correcciones", [("DE", Decimal(-20)), ("FR", Decimal(-140))]),
    ):
        grid = grids[name]
        columns = {column.key: index for index, column in enumerate(grid.columns)}
        amount_column = columns["cuota" if name == "exterior-servicios" else "correccion"]
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
        if not str(formula.target_casilla_id).startswith(("iva.exterior.control.", "iva.exterior.resultado.")):
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


def test_country_refund_never_offsets_another_country_payment(revision):
    values = _scenario(revision)
    assert values["iva.exterior.resultado.de.ingresar"] == 170
    assert values["iva.exterior.resultado.fr.resultado"] == -40
    assert values["iva.exterior.resultado.fr.devolver"] == 40
    assert values["iva.exterior.resultado.fr.ingresar"] == 0
    assert values["iva.exterior.resultado.saldo-ingresar-espana"] == 170


@pytest.mark.parametrize("country", ["US", "XI", "de", "", None])
def test_invalid_or_missing_country_cannot_disappear_from_settlement(revision, country):
    with pytest.raises(RegistryValidationError):
        _scenario(revision, country=country)


def test_missing_quota_is_not_zero(revision):
    with pytest.raises(RegistryValidationError):
        _scenario(revision, quota=None)


def test_unclosed_blank_rows_do_not_claim_a_complete_total(revision):
    with pytest.raises(UnresolvedFormulaDependencyError):
        _scenario(revision, close_rows=False)


def test_result_page_covers_all_countries_without_internal_controls(revision):
    page = revision.form_layouts[0].pages[2]
    grids = [block for section in page.sections for block in section.blocks if isinstance(block, FormGridBlock)]
    assert len(grids) == 1
    grid = grids[0]
    assert len(grid.columns) == 6
    assert len(grid.rows) == 27
    assert {row.official_heading for row in grid.rows} == set(
        [
            "AT",
            "BE",
            "BG",
            "CY",
            "CZ",
            "DE",
            "DK",
            "EE",
            "ES",
            "FI",
            "FR",
            "GR",
            "HR",
            "HU",
            "IE",
            "IT",
            "LT",
            "LU",
            "LV",
            "MT",
            "NL",
            "PL",
            "PT",
            "RO",
            "SE",
            "SI",
            "SK",
        ]
    )
    assert all(str(cell.casilla_id).startswith("iva.exterior.resultado.") for row in grid.rows for cell in row.cells)


def test_fictional_unused_rows_preserve_every_member_binding(revision):
    rows = fictional_unused_form_rows(revision, {"exterior-servicios": ("fila-3",)})
    assert len(rows) == 5
    assert all(row.row_index == 3 and not row.occupied for row in rows.values())
    assert all(set(row.binding_ids) == set(rows) for row in rows.values())
    assert fictional_unused_form_rows(revision, {}) == {}


@pytest.mark.parametrize(
    "selections",
    [
        {"unknown": ("fila-1",)},
        {"exterior-servicios": ("fila-29",)},
        {"exterior-servicios": ("fila-3", "fila-3")},
        {"resultado-estados": ("de",)},
    ],
)
def test_fictional_unused_rows_refuse_undeclared_or_non_input_geometry(revision, selections):
    with pytest.raises(CalcSheetsEngineError):
        fictional_unused_form_rows(revision, selections)
