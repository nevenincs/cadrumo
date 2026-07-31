"""Formula expression and dependency graph validation helpers.

Validates formula expressions and the DAG formed by formula targets
declared on a :class:`~cadrumo.domain.calculations.registry.ModeloRevision`,
checking casilla, binding, parameter, and relation reference closure and
detecting cycles.

See Also:
    :func:`cadrumo.domain.calculations.registry._runtime_graph.expression_casilla_refs`
        Formula-expression walker used to derive target dependencies.
    :func:`cadrumo.domain.calculations.registry._runtime_graph.formula_evaluation_order`
        Runtime topological order builder that assumes this validator has
        rejected cycles.
"""

from __future__ import annotations

from graphlib import CycleError

from ._ids import BindingId, CasillaId, RelationId
from ._runtime_graph import formula_evaluation_order
from ._schema import FormulaExpression, ModeloRevision


def validate_formula_dag(scope: str, revision: ModeloRevision) -> list[str]:
    """Return dependency-cycle failures for a revision's computed formulas.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    formula targets and expressions. Only dependencies that point at another
    computed target participate in the DAG; registry membership and reference
    existence are handled by :func:`validate_formula_expression`.
    """
    try:
        formula_evaluation_order(revision)
    except CycleError as exc:
        return [f"{scope}: formula graph cycle: {exc}"]
    return []


def validate_formula_expression(
    scope: str,
    formula_id: str,
    expression: FormulaExpression,
    *,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    parameters: set[str],
    relations: set[RelationId],
) -> list[str]:
    """Return reference-closure failures for one formula expression tree.

    The :class:`~cadrumo.domain.calculations.registry.FormulaExpression` may refer
    to :class:`~cadrumo.domain.calculations.registry.CasillaId`,
    :class:`~cadrumo.domain.calculations.registry.BindingId`, parameter, and
    :class:`~cadrumo.domain.calculations.registry.RelationId` values. This recursive
    validator keeps every nested expression node inside the selected revision's
    declared id sets.
    """
    failures: list[str] = []
    if expression.casilla_id is not None and expression.casilla_id not in casillas:
        failures.append(f"{scope}: formula {formula_id!r} references unknown casilla {expression.casilla_id!r}")
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
