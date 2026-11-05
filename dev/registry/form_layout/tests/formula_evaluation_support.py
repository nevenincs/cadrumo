"""Evaluate one authored formula against explicit casilla values and nothing else."""

from __future__ import annotations

from decimal import Decimal

from cadrumo.domain.calculations.registry.formula_expression import evaluate_expression
from cadrumo.domain.calculations.registry.schema import FormulaDefinition


def evaluate_formula(formula: FormulaDefinition, values: dict[str, Decimal]) -> Decimal:
    return evaluate_expression(
        formula.expression,
        values=values,
        binding_values={},
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
    )
