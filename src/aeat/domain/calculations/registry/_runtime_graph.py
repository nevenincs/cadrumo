"""Runtime graph helpers for validated registry formulas."""

from __future__ import annotations

from graphlib import TopologicalSorter

from ._schema import ModeloRevision


def formula_evaluation_order(revision: ModeloRevision) -> tuple[str, ...]:
    """Return computed casilla ids in dependency order."""

    computed_targets = {formula.target for formula in revision.formulas}
    sorter: TopologicalSorter[str] = TopologicalSorter()
    for formula in revision.formulas:
        dependencies = [arg.casilla for arg in formula.args if arg.casilla in computed_targets]
        sorter.add(formula.target, *(dependency for dependency in dependencies if dependency is not None))
    return tuple(sorter.static_order())
