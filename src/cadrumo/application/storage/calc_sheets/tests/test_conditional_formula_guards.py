"""Unknown-value guards must follow the same branch as fiscal arithmetic."""

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression

from .._translator import translate_formula
from ..engine import build_export_plan
from ..errors import CalcSheetsEngineError
from ..form_workbook import add_form_workbook
from ..formula_guards import conditional_missing_input_guard
from ..layout import plan_layout
from ..records import TabName
from .test_form_workbook import form_source as form_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _conditional():
    return FormulaExpression(
        op="if_then_else",
        args=(
            FormulaExpression(
                op="greater_than", args=(FormulaExpression(casilla_id="01"), FormulaExpression(literal=Decimal(0)))
            ),
            FormulaExpression(casilla_id="02"),
            FormulaExpression(literal=Decimal(0)),
        ),
    )


def test_missing_predicate_precedes_selection_and_unselected_amount_is_not_required(form_source):
    snapshot, _ = form_source
    layout = plan_layout(snapshot.revision)
    predicate = layout.entradas_cells["01"].qualified()
    amount = layout.entradas_cells["02"].qualified()
    guard = conditional_missing_input_guard(_conditional(), formulas={}, layout=layout)
    assert guard == f"IF(ISBLANK({predicate}),TRUE,IF((IF({predicate}>0,1,0))<>0,ISBLANK({amount}),FALSE))"
    assert not guard.startswith("OR(")


def test_branch_guard_survives_transitive_calculations_and_both_visible_surfaces(form_source):
    snapshot, _ = form_source
    formulas = tuple(
        formula.model_copy(update={"expression": _conditional()}) if formula.target_casilla_id == "03" else formula
        for formula in snapshot.revision.formulas
    )
    snapshot = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"formulas": formulas})})
    plan = build_export_plan(snapshot)
    source = next(cell for cell in plan.formula_cells if cell.casilla_id == "03")
    downstream = next(cell for cell in plan.formula_cells if cell.casilla_id == "04")
    assert source.missing_input_condition is not None
    assert downstream.missing_input_condition is not None
    assert f"NOT(ISNUMBER({source.address.qualified()}))" in downstream.missing_input_condition
    rendered = add_form_workbook(plan, snapshot)
    support = next(cell for cell in rendered.formula_cells if cell.address == source.address)
    assert support.formula == f'IF({source.missing_input_condition},"Sin dato",{source.formula})'
    form = next(cell for cell in rendered.formula_cells if cell.address.tab is TabName.FORM and cell.casilla_id == "03")
    assert form.formula == f'IF({source.missing_input_condition},"Sin dato",{source.address.qualified()})'


def test_missing_input_analysis_refuses_dependency_cycles(form_source):
    snapshot, _ = form_source
    with pytest.raises(CalcSheetsEngineError, match="cycle"):
        conditional_missing_input_guard(
            FormulaExpression(casilla_id="03"),
            formulas={"03": FormulaExpression(casilla_id="03")},
            layout=plan_layout(snapshot.revision),
        )


def test_ordinary_formulas_keep_the_existing_guard_policy(form_source):
    snapshot, _ = form_source
    assert (
        conditional_missing_input_guard(
            FormulaExpression(op="add", args=(FormulaExpression(casilla_id="01"), FormulaExpression(casilla_id="02"))),
            formulas={},
            layout=plan_layout(snapshot.revision),
        )
        is None
    )


def test_text_predicate_errors_become_unknown_instead_of_broken_visible_formulas(form_source):
    snapshot, _ = form_source
    layout = plan_layout(snapshot.revision)
    predicate = FormulaExpression(
        op="text_equal", args=(FormulaExpression(casilla_id="01"), FormulaExpression(casilla_id="02"))
    )
    # Runtime type/emptiness checks belong to the translator: ISBLANK alone
    # misses empty-text formulas and numbers entered into a country field.
    missing = f"ISERROR({translate_formula(predicate, layout=layout)})"
    assert conditional_missing_input_guard(predicate, formulas={}, layout=layout) == missing
    expression = FormulaExpression(
        op="if_then_else",
        args=(predicate, FormulaExpression(literal=Decimal(190)), FormulaExpression(literal=Decimal(0))),
    )
    condition = conditional_missing_input_guard(expression, formulas={}, layout=layout)
    assert condition is not None
    assert condition.startswith(f"IF({missing},TRUE,")


def test_required_condition_rejects_missing_invalid_or_false_predicate_before_amount(form_source):
    snapshot, _ = form_source
    layout = plan_layout(snapshot.revision)
    expression = FormulaExpression(
        op="require_condition", args=(FormulaExpression(casilla_id="01"), FormulaExpression(casilla_id="02"))
    )
    predicate = layout.entradas_cells["01"].qualified()
    amount = layout.entradas_cells["02"].qualified()
    assert translate_formula(expression, layout=layout) == f"IF(({predicate})<>0,{amount},NA())"
    assert conditional_missing_input_guard(expression, formulas={}, layout=layout) == (
        f"IF(ISBLANK({predicate}),TRUE,IF(ISERROR({predicate}),TRUE,"
        f"IF(OR(ISNUMBER({predicate}),ISLOGICAL({predicate})),IF(({predicate})<>0,ISBLANK({amount}),TRUE),TRUE)))"
    )


@pytest.mark.parametrize("truth", [0, 1])
def test_required_literal_condition_still_checks_false_and_only_selected_amount(form_source, truth):
    snapshot, _ = form_source
    layout = plan_layout(snapshot.revision)
    expression = FormulaExpression(
        op="require_condition", args=(FormulaExpression(literal=Decimal(truth)), FormulaExpression(casilla_id="02"))
    )
    amount = layout.entradas_cells["02"].qualified()
    assert conditional_missing_input_guard(expression, formulas={}, layout=layout) == (
        f"IF(ISERROR({truth}),TRUE,IF(OR(ISNUMBER({truth}),ISLOGICAL({truth})),"
        f"IF(({truth})<>0,ISBLANK({amount}),TRUE),TRUE))"
    )


def test_required_text_comparison_preserves_error_guard_and_transitive_casillas(form_source):
    snapshot, _ = form_source
    layout = plan_layout(snapshot.revision)
    predicate = FormulaExpression(
        op="text_equal", args=(FormulaExpression(casilla_id="01"), FormulaExpression(text_literal="DE"))
    )
    expression = FormulaExpression(op="require_condition", args=(predicate, FormulaExpression(casilla_id="02")))
    guard = conditional_missing_input_guard(expression, formulas={}, layout=layout)
    assert guard is not None and guard.startswith(f"IF(ISERROR({translate_formula(predicate, layout=layout)}),TRUE,")
    assert (
        conditional_missing_input_guard(FormulaExpression(casilla_id="03"), formulas={"03": expression}, layout=layout)
        == f"NOT(ISNUMBER({layout.calculos_cells['03'].qualified()}))"
    )


def test_cycle_hidden_behind_a_conditional_is_rejected(form_source):
    snapshot, _ = form_source
    expression = FormulaExpression(
        op="if_then_else",
        args=(
            FormulaExpression(literal=Decimal(1)),
            FormulaExpression(casilla_id="03"),
            FormulaExpression(literal=Decimal(0)),
        ),
    )
    with pytest.raises(CalcSheetsEngineError, match="cycle"):
        conditional_missing_input_guard(expression, formulas={"03": expression}, layout=plan_layout(snapshot.revision))
