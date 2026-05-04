"""Runtime graph helpers for validated registry formulas."""

from __future__ import annotations

from graphlib import TopologicalSorter

from ._schema import FormulaExpression, ModeloRevision


def expression_casilla_refs(expression: FormulaExpression) -> tuple[str, ...]:
    """Return all casilla ids referenced by a formula expression."""

    refs: list[str] = []
    _collect_casilla_refs(expression, refs)
    return tuple(refs)


def _collect_casilla_refs(expression: FormulaExpression, refs: list[str]) -> None:
    if expression.casilla is not None:
        refs.append(expression.casilla)
    for arg in expression.args:
        _collect_casilla_refs(arg, refs)


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
