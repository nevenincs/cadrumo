"""Formula expression and dependency graph validation helpers.

Validates formula expressions and the DAG formed by formula targets
declared on a :class:`ModeloRevision`, checking casilla and binding
reference closure and detecting cycles.
"""

from __future__ import annotations

from graphlib import CycleError, TopologicalSorter

from ._runtime_graph import expression_casilla_refs
from ._schema import FormulaExpression, ModeloRevision


def validate_formula_dag(scope: str, revision: ModeloRevision) -> list[str]:
    formula_targets = {formula.target for formula in revision.formulas}
    sorter: TopologicalSorter[str] = TopologicalSorter()
    for formula in revision.formulas:
        dependencies = [
            casilla for casilla in expression_casilla_refs(formula.expression) if casilla in formula_targets
        ]
        sorter.add(formula.target, *dependencies)
    try:
        tuple(sorter.static_order())
    except CycleError as exc:
        return [f"{scope}: formula graph cycle: {exc}"]
    return []


def validate_formula_expression(
    scope: str,
    formula_id: str,
    expression: FormulaExpression,
    *,
    casillas: set[str],
    bindings: set[str],
    parameters: set[str],
    relations: set[str],
) -> list[str]:
    failures: list[str] = []
    if expression.casilla is not None and expression.casilla not in casillas:
        failures.append(f"{scope}: formula {formula_id!r} references unknown casilla {expression.casilla!r}")
    if expression.binding is not None and expression.binding not in bindings:
        failures.append(f"{scope}: formula {formula_id!r} references unknown binding {expression.binding!r}")
    if expression.parameter is not None and expression.parameter not in parameters:
        failures.append(f"{scope}: formula {formula_id!r} references unknown parameter {expression.parameter!r}")
    if expression.dispatch_table:
        for key, dispatched in expression.dispatch_table.items():
            if dispatched not in parameters:
                failures.append(
                    f"{scope}: formula {formula_id!r} dispatch_table[{key!r}] "
                    f"references unknown parameter {dispatched!r}",
                )
    if expression.relation is not None and expression.relation not in relations:
        failures.append(f"{scope}: formula {formula_id!r} references unknown relation {expression.relation!r}")
    for arg in expression.args:
        failures.extend(
            validate_formula_expression(
                scope,
                formula_id,
                arg,
                casillas=casillas,
                bindings=bindings,
                parameters=parameters,
                relations=relations,
            ),
        )
    return failures
