"""Arithmetic oracle shared by the workbook demonstration acceptance tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cadrumo.application.storage.calc_sheets.records import OperatorInputs
from cadrumo.domain.calculations.registry.formula_expression import evaluate_expression
from cadrumo.domain.calculations.registry.formula_runtime_ops import apply_rounding
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression


def numeric_inputs(inputs: OperatorInputs) -> dict[str, Decimal]:
    """Pass numeric operands to the arithmetic oracle, excluding typed context."""
    return {item.casilla_id: item.value for item in inputs.values if isinstance(item.value, Decimal)}


def expected_result(
    snapshot: RegistrySnapshot, values: dict[str, Decimal], bindings: dict[str, Decimal], target: str
) -> Decimal:
    """Check fictional arithmetic through the domain interpreter, not sheet formulas."""
    values = values.copy()
    casillas = {c.id: c for c in snapshot.revision.casillas}
    if any(casillas[key].formula is not None for key in values):
        raise ValueError("oracle inputs cannot override calculated casillas")
    formulas = {f.id: f for f in snapshot.revision.formulas}
    parameters = {p.id: p for p in snapshot.revision.parameters}

    def resolve(identifier: str) -> Decimal:
        if identifier in values:
            return values[identifier]
        formula_id = casillas[identifier].formula
        assert formula_id is not None
        formula = formulas[formula_id]
        visit(formula.expression)
        unresolved: set[str] = set()
        result = evaluate_expression(
            formula.expression,
            values=values,
            binding_values=bindings,
            parameters=parameters,
            date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=unresolved,
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
            filing_year=snapshot.filing_year,
        )
        assert not unresolved
        values[identifier] = apply_rounding(result, formula.rounding)
        return values[identifier]

    def visit(expression: FormulaExpression) -> None:
        if expression.casilla_id is not None:
            resolve(expression.casilla_id)
        for argument in expression.args:
            visit(argument)

    return resolve(target)
