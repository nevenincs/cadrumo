"""Runtime graph helpers for validated registry formulas."""

from __future__ import annotations

from graphlib import TopologicalSorter

from ._schema import FormulaExpression, ModeloRevision


def expression_casilla_refs(expression: FormulaExpression) -> tuple[str, ...]:
    """Return all casilla ids referenced by a formula expression."""

    refs: list[str] = []
    _collect_casilla_refs(expression, refs)
    return tuple(refs)


def expression_relation_refs(expression: FormulaExpression) -> tuple[str, ...]:
    """Return all relation ids referenced by a formula expression."""

    refs: list[str] = []
    _collect_relation_refs(expression, refs)
    return tuple(refs)


def expression_binding_refs(expression: FormulaExpression) -> tuple[str, ...]:
    """Return all binding ids referenced by a formula expression."""

    refs: list[str] = []
    _collect_binding_refs(expression, refs)
    return tuple(refs)


def expression_parameter_refs(expression: FormulaExpression) -> tuple[str, ...]:
    """Return all parameter ids referenced by a formula expression.

    Walks both the direct ``parameter = "..."`` leaf and the
    ``dispatch_table = { key = "param_id" }`` leaf introduced by the
    ``lookup_bracket_by_ccaa`` op; dispatch_table values reference
    parameters just like the direct leaf.
    """

    refs: list[str] = []
    _collect_parameter_refs(expression, refs)
    return tuple(refs)


def _collect_casilla_refs(expression: FormulaExpression, refs: list[str]) -> None:
    if expression.casilla is not None:
        refs.append(expression.casilla)
    for arg in expression.args:
        _collect_casilla_refs(arg, refs)


def _collect_relation_refs(expression: FormulaExpression, refs: list[str]) -> None:
    if expression.relation is not None:
        refs.append(expression.relation)
    for arg in expression.args:
        _collect_relation_refs(arg, refs)


def _collect_binding_refs(expression: FormulaExpression, refs: list[str]) -> None:
    if expression.binding is not None:
        refs.append(expression.binding)
    for arg in expression.args:
        _collect_binding_refs(arg, refs)


def _collect_parameter_refs(expression: FormulaExpression, refs: list[str]) -> None:
    if expression.parameter is not None:
        refs.append(expression.parameter)
    if expression.dispatch_table:
        refs.extend(expression.dispatch_table.values())
    for arg in expression.args:
        _collect_parameter_refs(arg, refs)


def formula_evaluation_order(revision: ModeloRevision) -> tuple[str, ...]:
    """Return computed casilla ids in dependency order."""

    computed_targets = {formula.target for formula in revision.formulas}
    sorter: TopologicalSorter[str] = TopologicalSorter()
    for formula in revision.formulas:
        dependencies = [
            casilla for casilla in expression_casilla_refs(formula.expression) if casilla in computed_targets
        ]
        sorter.add(formula.target, *dependencies)
    return tuple(sorter.static_order())
