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


def _casilla_reference_resolver(revision: ModeloRevision) -> dict[str, str]:
    """Return a token-to-canonical-id map for segment-aware casilla lookup.

    A casilla's identity is the pair ``(segmento, number)``; ``id`` is
    the canonical within-revision handle. A formula leaf or target may
    name a casilla either by its ``id`` directly, or by its bare
    ``number`` when that number is unambiguous within the revision.

    The returned map sends every such reference token to the canonical
    casilla ``id``: each ``id`` maps to itself, and a bare ``number``
    that occurs on exactly one casilla maps to that casilla's ``id``. A
    bare ``number`` that recurs across distinct record segments is
    omitted — it is ambiguous on its own and must be named by the
    segment-qualified ``id``.

    For a single-segment modelo every casilla sets ``id == number``, so
    the map is the identity on the casilla ids and resolution is a
    no-op: multi-segment numbers resolve correctly while single-segment
    dependency ordering is unchanged.
    """
    resolver: dict[str, str] = {casilla.id: casilla.id for casilla in revision.casillas}
    number_counts: dict[str, int] = {}
    for casilla in revision.casillas:
        number_counts[casilla.number] = number_counts.get(casilla.number, 0) + 1
    for casilla in revision.casillas:
        if number_counts[casilla.number] == 1:
            resolver.setdefault(casilla.number, casilla.id)
    return resolver


def formula_evaluation_order(revision: ModeloRevision) -> tuple[str, ...]:
    """Return computed casilla ids in dependency order.

    Casilla references in a formula expression and the formula
    ``target`` are resolved segment-aware to their canonical casilla
    ``id`` before the dependency graph is built, so a multi-segment
    bare-number reference is matched against the correct casilla
    occurrence. For single-segment modelos the resolution is the
    identity and the ordering is unchanged.
    """

    resolver = _casilla_reference_resolver(revision)
    computed_targets = {resolver.get(formula.target, formula.target) for formula in revision.formulas}
    sorter: TopologicalSorter[str] = TopologicalSorter()
    for formula in revision.formulas:
        target = resolver.get(formula.target, formula.target)
        dependencies = [
            resolved
            for casilla in expression_casilla_refs(formula.expression)
            if (resolved := resolver.get(casilla, casilla)) in computed_targets
        ]
        sorter.add(target, *dependencies)
    return tuple(sorter.static_order())
