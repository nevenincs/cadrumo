"""Find scenario inputs through the registered formula graph."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression


def scenario_leaves(snapshot: RegistrySnapshot, result: str) -> tuple[set[str], set[str]]:
    """Find the selected synthetic result's inputs through the actual formula DAG."""
    casillas = {str(c.id): c for c in snapshot.revision.casillas}
    formulas = {f.id: f for f in snapshot.revision.formulas}
    visited: set[str] = set()
    leaves: set[str] = set()
    bindings: set[str] = set()

    def visit_casilla(identifier: str) -> None:
        if identifier in visited:
            return
        visited.add(identifier)
        casilla = casillas[identifier]
        if casilla.formula is None:
            leaves.add(identifier)
        else:
            visit_expression(formulas[casilla.formula].expression)

    def visit_expression(expression: FormulaExpression) -> None:
        if expression.casilla_id is not None:
            visit_casilla(str(expression.casilla_id))
        if expression.binding is not None:
            bindings.add(str(expression.binding))
        for argument in expression.args:
            visit_expression(argument)

    visit_casilla(result)
    return leaves, bindings
