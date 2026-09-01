"""Runtime graph helpers for validated registry formulas.

Walks :class:`~cadrumo.domain.calculations.registry.FormulaExpression` trees
declared on a :class:`~cadrumo.domain.calculations.registry.ModeloRevision` to
extract casilla, binding, parameter, relation, and date-binding references, and
produces topologically sorted evaluation orders for the formula engine.

See Also:
    :mod:`cadrumo.domain.calculations.registry._validate_formulas`
        Validation layer that rejects dangling expression refs and formula
        dependency cycles before runtime graph builders are used.
    :mod:`cadrumo.domain.calculations.registry.formula_runtime`
        Formula evaluator that consumes these graph projections.
    :mod:`cadrumo.domain.calculations.registry.queries`
        Registry query surface that exposes formula dependencies to operators.
"""

from __future__ import annotations

from graphlib import TopologicalSorter

from ....core.casilla_id import CasillaId
from .ids import BindingId, ParameterId, RelationId
from .schema import ModeloRevision
from .schema_formula import FormulaExpression

# These walkers are pure O(expression-node) traversals and intentionally
# carry NO memoization. A prior implementation keyed a module-global cache
# on ``id(expression)``; because CPython reuses an object's address after it
# is garbage-collected, a fresh short-lived expression could collide with a
# stale entry left by a now-collected expression and receive the wrong refs.
# ``FormulaExpression`` is frozen but not reliably hashable (its
# ``dispatch_table`` is a ``Mapping``), so value-keyed memoization is not
# available either. Recomputation is cheap — formula expression trees are
# small — so the walkers simply re-walk on every call.


def expression_casilla_refs(expression: FormulaExpression) -> tuple[CasillaId, ...]:
    """Return all :class:`~cadrumo.core.CasillaId` refs.

    The input is a validated
    :class:`~cadrumo.domain.calculations.registry.FormulaExpression` tree.
    """
    refs: list[CasillaId] = []
    _collect_casilla_refs(expression, refs)
    return tuple(refs)


def expression_relation_refs(expression: FormulaExpression) -> tuple[RelationId, ...]:
    """Return all :class:`~cadrumo.domain.calculations.registry.RelationId` refs.

    The input is a validated
    :class:`~cadrumo.domain.calculations.registry.FormulaExpression` tree.
    """
    refs: list[RelationId] = []
    _collect_relation_refs(expression, refs)
    return tuple(refs)


def expression_binding_refs(expression: FormulaExpression) -> tuple[BindingId, ...]:
    """Return all :class:`~cadrumo.domain.calculations.registry.BindingId` refs.

    The input is a validated
    :class:`~cadrumo.domain.calculations.registry.FormulaExpression` tree.
    """
    refs: list[BindingId] = []
    _collect_binding_refs(expression, refs)
    return tuple(refs)


def expression_date_binding_refs(expression: FormulaExpression) -> tuple[BindingId, ...]:
    """Return all date-binding :class:`~cadrumo.domain.calculations.registry.BindingId` refs.

    ``date_binding`` leaves carry date-valued profile facts (e.g.
    birth_date) consumed by the ``age_at_year_end`` op.  They are
    distinct from ``binding`` leaves (Decimal channel) and need their
    own collector so callers can populate the ``date_binding_values``
    channel selectively.
    """
    refs: list[BindingId] = []
    _collect_date_binding_refs(expression, refs)
    return tuple(refs)


def expression_parameter_refs(expression: FormulaExpression) -> tuple[ParameterId, ...]:
    """Return all :class:`~cadrumo.domain.calculations.registry.ParameterId` refs.

    Walks both the direct ``parameter = "..."`` leaf and the
    ``dispatch_table = { key = "param_id" }`` leaf introduced by the
    ``lookup_bracket_by_ccaa`` op; dispatch_table values reference
    parameters just like the direct leaf.
    """
    refs: list[ParameterId] = []
    _collect_parameter_refs(expression, refs)
    return tuple(refs)


def _collect_casilla_refs(expression: FormulaExpression, refs: list[CasillaId]) -> None:
    if expression.casilla_id is not None:
        refs.append(expression.casilla_id)
    for arg in expression.args:
        _collect_casilla_refs(arg, refs)


def _collect_relation_refs(expression: FormulaExpression, refs: list[RelationId]) -> None:
    if expression.relation is not None:
        refs.append(expression.relation)
    for arg in expression.args:
        _collect_relation_refs(arg, refs)


def _collect_binding_refs(expression: FormulaExpression, refs: list[BindingId]) -> None:
    if expression.binding is not None:
        refs.append(expression.binding)
    for arg in expression.args:
        _collect_binding_refs(arg, refs)


def _collect_date_binding_refs(expression: FormulaExpression, refs: list[BindingId]) -> None:
    if expression.date_binding is not None:
        refs.append(expression.date_binding)
    for arg in expression.args:
        _collect_date_binding_refs(arg, refs)


#: Map of op name -> arg index that carries the string-valued enum binding
#: leaf. These ops consume that leaf as a string-valued dispatch key
#: resolved from ``enum_binding_values``, rather than as a Decimal operand
#: resolved from ``binding_values`` like every other binding leaf.
_ENUM_DISPATCH_BINDING_ARG_INDEX: dict[str, int] = {
    "lookup_bracket_by_ccaa": 1,
    "lookup_parameter_by_entity_type": 1,
    "lookup_bracket_by_entity_type": 1,
}


def _enum_dispatch_binding_arg_index(expression: FormulaExpression) -> int | None:
    op = expression.op or ""
    if op == "irnr_resolve_tipo_gravamen":
        if len(expression.args) == 5:
            return 4
        return None
    return _ENUM_DISPATCH_BINDING_ARG_INDEX.get(op)


def _collect_enum_dispatch_binding_refs(expression: FormulaExpression, refs: list[BindingId]) -> None:
    arg_index = _enum_dispatch_binding_arg_index(expression)
    if arg_index is not None and len(expression.args) > arg_index:
        dispatch_binding = expression.args[arg_index].binding
        if dispatch_binding is not None:
            refs.append(dispatch_binding)
    for arg in expression.args:
        _collect_enum_dispatch_binding_refs(arg, refs)


def enum_consumed_binding_ids(revision: ModeloRevision) -> frozenset[BindingId]:
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

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            formula graph is inspected for enum dispatch binding references.
    """
    refs: list[BindingId] = []
    for formula in revision.formulas:
        _collect_enum_dispatch_binding_refs(formula.expression, refs)
    return frozenset(refs)


def revision_date_binding_ids(revision: ModeloRevision) -> frozenset[BindingId]:
    """Return every date_binding id the revision's formulas consume.

    Date bindings carry date-valued profile facts (e.g. taxpayer birth date)
    consumed by ops such as ``age_at_year_end``. They are read from the
    ``date_binding_values`` channel, distinct from the Decimal ``binding_values``
    and string ``enum_binding_values`` channels. This is the revision-level
    sibling of :func:`enum_consumed_binding_ids`: callers use it to populate the
    date channel and to refuse a date-valued binding supplied through a
    decimal/enum override.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            formula graph is inspected for ``date_binding`` leaf references.
    """
    refs: list[BindingId] = []
    for formula in revision.formulas:
        refs.extend(expression_date_binding_refs(formula.expression))
    return frozenset(refs)


def _collect_parameter_refs(expression: FormulaExpression, refs: list[ParameterId]) -> None:
    if expression.parameter is not None:
        refs.append(expression.parameter)
    if expression.dispatch_table:
        refs.extend(expression.dispatch_table.values())
    for arg in expression.args:
        _collect_parameter_refs(arg, refs)


# The id-map / evaluation-order builders below intentionally carry NO
# memoization, for the same reason the expression walkers above do not: a prior
# implementation keyed module-global caches on ``id(revision)``, but CPython
# reuses an object's address after garbage collection, so a fresh short-lived
# revision could collide with a stale entry left by a now-collected revision and
# receive the wrong order. ``ModeloRevision`` is frozen but not hashable (it
# nests ``FormulaExpression`` whose ``dispatch_table`` is a ``Mapping``), and
# same-coordinate revisions differ under ``model_copy`` (so a coordinate key is
# unsafe too). Each build is a single pass over the casilla / formula set —
# cheap — so they simply recompute on every call.


def input_casilla_id_map(revision: ModeloRevision) -> dict[CasillaId, CasillaId]:
    """Return the canonical casilla id map for a revision input.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies the
    declared :class:`~cadrumo.core.CasillaId` values.
    """
    return {casilla.id: casilla.id for casilla in revision.casillas}


def formula_evaluation_order(revision: ModeloRevision) -> tuple[CasillaId, ...]:
    """Return computed casilla ids in dependency order.

    Casilla references in formula expressions and formula ``target`` fields
    are canonical ``casilla.id`` values. Registry validation rejects
    ``number`` fallback references before runtime reaches this graph builder.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            formulas to topologically sort.
    """
    computed_targets = {formula.target_casilla_id for formula in revision.formulas}
    sorter: TopologicalSorter[CasillaId] = TopologicalSorter()
    for formula in revision.formulas:
        dependencies = [
            casilla for casilla in expression_casilla_refs(formula.expression) if casilla in computed_targets
        ]
        sorter.add(formula.target_casilla_id, *dependencies)
    return tuple(sorter.static_order())
