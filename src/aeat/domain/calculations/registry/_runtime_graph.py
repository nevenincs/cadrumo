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


#: Formula operators that consume a binding leaf as a string-valued enum
#: dispatch key (``args[1]``) rather than as a Decimal operand. The
#: runtime resolves the ``args[1]`` binding of these ops from
#: ``enum_binding_values`` (string channel); every other binding leaf is
#: resolved from ``binding_values`` (Decimal channel).
_ENUM_DISPATCH_OPS: frozenset[str] = frozenset(
    {"lookup_bracket_by_ccaa", "lookup_parameter_by_entity_type"}
)


def _collect_enum_dispatch_binding_refs(expression: FormulaExpression, refs: list[str]) -> None:
    if expression.op in _ENUM_DISPATCH_OPS and len(expression.args) >= 2:
        dispatch_binding = expression.args[1].binding
        if dispatch_binding is not None:
            refs.append(dispatch_binding)
    for arg in expression.args:
        _collect_enum_dispatch_binding_refs(arg, refs)


def enum_consumed_binding_ids(revision: ModeloRevision) -> frozenset[str]:
    """Return binding ids the revision's formulas consume as string enums.

    A registry binding leaf is resolved from one of two engine
    channels. When a binding is the ``args[1]`` enum-key argument of a
    dispatch op (``lookup_bracket_by_ccaa`` /
    ``lookup_parameter_by_entity_type``) the runtime reads it from the
    string-valued ``enum_binding_values`` channel. Every other binding
    leaf is read from the Decimal-valued ``binding_values`` channel.

    The engine channel is therefore a property of *how the formula
    consumes the binding*, not of the binding's ``typed_enum``
    annotation. A binding may carry ``typed_enum`` yet still be
    consumed as a Decimal operand (the Modelo 100 estimacion-directa
    modality binding is compared against a numeric literal). Routing a
    binding into the wrong channel makes the engine raise
    ``binding ... has no supplied value``; this query is the
    authoritative discriminator that prevents that mismatch.
    """

    refs: list[str] = []
    for formula in revision.formulas:
        _collect_enum_dispatch_binding_refs(formula.expression, refs)
    return frozenset(refs)


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


def input_casilla_alias_map(revision: ModeloRevision) -> dict[str, str]:
    """Return a token-to-canonical-id map for operator-supplied casilla input.

    A casilla's canonical handle is its within-revision ``id``. Spanish
    taxpayers, however, know a casilla by the number printed on the
    paper AEAT form. This map sends every operator-facing token an
    operator could reasonably type — the canonical ``id``, the registry
    ``number``, and the BOE ``form_number`` — to the canonical ``id``.

    A token is included only when it resolves unambiguously: an ``id``
    always maps to itself; a ``number`` or ``form_number`` maps to a
    casilla ``id`` only when exactly one casilla in the revision carries
    that value. An ambiguous ``number`` / ``form_number`` (one shared
    across record segments) is omitted — it must be named by the
    canonical ``id``. The canonical ``id`` always wins a collision so
    the canonical handle is never shadowed by an alias.
    """

    canonical_ids = {casilla.id for casilla in revision.casillas}
    number_counts: dict[str, int] = {}
    form_number_counts: dict[str, int] = {}
    for casilla in revision.casillas:
        number_counts[casilla.number] = number_counts.get(casilla.number, 0) + 1
        if casilla.form_number is not None:
            form_number_counts[casilla.form_number] = form_number_counts.get(casilla.form_number, 0) + 1
    resolver: dict[str, str] = {casilla.id: casilla.id for casilla in revision.casillas}
    for casilla in revision.casillas:
        if casilla.number not in canonical_ids and number_counts[casilla.number] == 1:
            resolver.setdefault(casilla.number, casilla.id)
        if (
            casilla.form_number is not None
            and casilla.form_number not in canonical_ids
            and form_number_counts[casilla.form_number] == 1
        ):
            resolver.setdefault(casilla.form_number, casilla.id)
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
