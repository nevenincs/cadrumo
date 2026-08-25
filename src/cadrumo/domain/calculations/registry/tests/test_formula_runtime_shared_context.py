"""One evaluation context, one set of provenance sinks, per formula tree.

The formula runtime accumulates a formula's operand lineage -- the
``operand_refs`` / ``operand_casilla_refs`` / ``operand_values`` triple that
becomes a :class:`~domain.calculations.registry.CasillaObservation`'s
explainability payload -- by appending into three caller-owned lists carried
on the evaluation context. Every node of the tree, at every depth, must append
into those SAME three list objects: the context is passed by reference down
the recursion, never destructured and rebuilt around fresh sinks. A recursion
that rebuilt them would still produce the right Decimal while silently
dropping the nested half of the lineage, which is a grounding defect, not a
performance one.

These are structural claims about provenance plumbing, not about AEAT
arithmetic: every operand value is supplied by the test, so no assertion here
depends on what a registry formula computes. The corpus is swept from the real
bundled registry tree so the shapes exercised are the shapes that ship.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression

from .....core import CasillaId
from ..formula_runtime import (
    _SPECIALIZED_EXPRESSION_EVALUATORS,
    _EvalContext,
    _evaluate_expression,
    _evaluate_with_ctx,
)
from ..ids import BindingId, RelationId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILING_PERIOD_DATE_CONTEXT = {"filing_period": date(2025, 12, 31)}


@dataclasses.dataclass(frozen=True, slots=True)
class _TreeCase:
    """One real registry formula tree plus the operand values it will be fed."""

    modelo_id: str
    revision_id: str
    formula_id: str
    expression: FormulaExpression
    values: dict[CasillaId, Decimal]
    binding_values: dict[BindingId, Decimal]
    relation_values: dict[RelationId, Decimal]
    expected_operand_refs: tuple[str, ...]
    expected_operand_casilla_refs: tuple[CasillaId, ...]
    expected_operand_values: tuple[Decimal, ...]
    max_leaf_depth: int


def _depth(expression: FormulaExpression) -> int:
    return 1 + max((_depth(arg) for arg in expression.args), default=0)


def _leaves_in_evaluation_order(expression: FormulaExpression, depth: int = 1) -> list[tuple[FormulaExpression, int]]:
    """Depth-first, left-to-right leaves -- the order the generic dispatcher visits them."""
    if expression.op is None:
        return [(expression, depth)]
    collected: list[tuple[FormulaExpression, int]] = []
    for arg in expression.args:
        collected.extend(_leaves_in_evaluation_order(arg, depth + 1))
    return collected


def _is_plain_arithmetic(expression: FormulaExpression) -> bool:
    """True when every node folds all of its args through the generic path.

    Specialised evaluators (``if_then_else`` short-circuits a branch,
    ``lookup_bracket`` appends a parameter ref of its own) have op-specific
    provenance rules, so a tree containing one has no structurally-derivable
    expected lineage. Parameter and date-binding leaves are excluded for the
    same reason. What is left is the generic fold, whose lineage is exactly
    its leaves in evaluation order.
    """
    if expression.op is not None:
        if expression.op in _SPECIALIZED_EXPRESSION_EVALUATORS:
            return False
        return all(_is_plain_arithmetic(arg) for arg in expression.args)
    return expression.parameter is None and expression.date_binding is None


def _build_case(
    modelo_id: str,
    revision_id: str,
    formula_id: str,
    expression: FormulaExpression,
) -> _TreeCase:
    """Assign every operand leaf a distinct non-zero value and derive the expected lineage."""
    values: dict[CasillaId, Decimal] = {}
    binding_values: dict[BindingId, Decimal] = {}
    relation_values: dict[RelationId, Decimal] = {}
    operand_refs: list[str] = []
    operand_casilla_refs: list[CasillaId] = []
    operand_values: list[Decimal] = []
    max_leaf_depth = 0

    for index, (leaf, depth) in enumerate(_leaves_in_evaluation_order(expression)):
        supplied = Decimal(index + 1)
        if leaf.casilla_id is not None:
            values.setdefault(leaf.casilla_id, supplied)
            operand_refs.append(leaf.casilla_id)
            operand_casilla_refs.append(leaf.casilla_id)
            operand_values.append(values[leaf.casilla_id])
            max_leaf_depth = max(max_leaf_depth, depth)
        elif leaf.binding is not None:
            binding_values.setdefault(leaf.binding, supplied)
            operand_refs.append(leaf.binding)
            operand_values.append(binding_values[leaf.binding])
            max_leaf_depth = max(max_leaf_depth, depth)
        elif leaf.relation is not None:
            relation_values.setdefault(leaf.relation, supplied)
            operand_refs.append(leaf.relation)
            operand_values.append(relation_values[leaf.relation])
            max_leaf_depth = max(max_leaf_depth, depth)

    return _TreeCase(
        modelo_id=modelo_id,
        revision_id=revision_id,
        formula_id=formula_id,
        expression=expression,
        values=values,
        binding_values=binding_values,
        relation_values=relation_values,
        expected_operand_refs=tuple(operand_refs),
        expected_operand_casilla_refs=tuple(operand_casilla_refs),
        expected_operand_values=tuple(operand_values),
        max_leaf_depth=max_leaf_depth,
    )


@pytest.fixture(scope="session")
def nested_formula_corpus(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> tuple[_TreeCase, ...]:
    """Every real registry formula whose lineage is structurally derivable and genuinely nested.

    Compiled from the bundled registry tree rather than a snapshot: the claim
    under test is about the runtime's recursion, which does not depend on the
    authority's revision-selection or attestation gates.
    """
    modelos, _catalogues = registry_tree
    cases: list[_TreeCase] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for formula in revision.formulas:
                expression = formula.expression
                if _depth(expression) < 3 or not _is_plain_arithmetic(expression):
                    continue
                case = _build_case(modelo.id, revision.id, formula.id, expression)
                if len(case.expected_operand_refs) < 2:
                    continue
                cases.append(case)
    return tuple(cases)


def _evaluate_collecting(case: _TreeCase) -> tuple[Decimal, list[str], list[CasillaId], list[Decimal]]:
    operand_refs: list[str] = []
    operand_casilla_refs: list[CasillaId] = []
    operand_values: list[Decimal] = []
    value = _evaluate_expression(
        case.expression,
        values=case.values,
        binding_values=case.binding_values,
        parameters={},
        date_context=_FILING_PERIOD_DATE_CONTEXT,
        relation_values=case.relation_values,
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=operand_refs,
        operand_casilla_refs=operand_casilla_refs,
        operand_values=operand_values,
    )
    return value, operand_refs, operand_casilla_refs, operand_values


def test_corpus_spans_several_modelos_and_reaches_past_the_second_level(
    nested_formula_corpus: tuple[_TreeCase, ...],
) -> None:
    """Guard against the sweep passing vacuously on a corpus that shrank to nothing.

    A shared-sink regression only shows up on a tree deep enough to have
    operands BELOW the root's immediate arguments, so the corpus must actually
    contain such trees, across more than one modelo.
    """
    assert nested_formula_corpus, "no nested registry formula trees were collected"
    assert len({case.modelo_id for case in nested_formula_corpus}) > 1
    assert any(case.max_leaf_depth >= 4 for case in nested_formula_corpus)


def test_nested_operands_land_in_the_callers_own_provenance_sinks(
    nested_formula_corpus: tuple[_TreeCase, ...],
) -> None:
    """Every leaf, at every depth, appends into the lists the CALLER passed in.

    The expected lineage is read off the expression tree's own shape -- its
    leaves in depth-first evaluation order -- so a recursion that handed
    nested nodes fresh sinks would return the same Decimal while these lists
    came back missing every operand below the root.
    """
    for case in nested_formula_corpus:
        _value, operand_refs, operand_casilla_refs, operand_values = _evaluate_collecting(case)
        where = f"{case.modelo_id}/{case.revision_id}/{case.formula_id}"
        assert tuple(operand_refs) == case.expected_operand_refs, where
        assert tuple(operand_casilla_refs) == case.expected_operand_casilla_refs, where
        assert tuple(operand_values) == case.expected_operand_values, where


def test_recursive_reentry_matches_the_loose_argument_entry_point(
    nested_formula_corpus: tuple[_TreeCase, ...],
) -> None:
    """``_evaluate_with_ctx`` on a caller-built context equals ``_evaluate_expression``.

    The two are the same dispatcher reached two ways: one builds the context
    from loose arguments, the other carries an existing one forward. They must
    agree on the value AND on all three provenance sinks, or the recursion is
    not the entry point and per-node results would depend on which door was
    used.
    """
    for case in nested_formula_corpus:
        expected_value, expected_refs, expected_casilla_refs, expected_values = _evaluate_collecting(case)

        operand_refs: list[str] = []
        operand_casilla_refs: list[CasillaId] = []
        operand_values: list[Decimal] = []
        ctx = _EvalContext(
            values=case.values,
            binding_values=case.binding_values,
            parameters={},
            date_context=_FILING_PERIOD_DATE_CONTEXT,
            relation_values=case.relation_values,
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=operand_refs,
            operand_casilla_refs=operand_casilla_refs,
            operand_values=operand_values,
            enum_binding_values={},
            date_binding_values={},
            filing_year=2025,
        )
        value = _evaluate_with_ctx(case.expression, ctx)

        where = f"{case.modelo_id}/{case.revision_id}/{case.formula_id}"
        assert value == expected_value, where
        assert operand_refs == list(expected_refs), where
        assert operand_casilla_refs == list(expected_casilla_refs), where
        assert operand_values == list(expected_values), where
        assert ctx.operand_refs is operand_refs, where
        assert ctx.operand_casilla_refs is operand_casilla_refs, where
        assert ctx.operand_values is operand_values, where


def test_eval_context_is_frozen_and_slotted() -> None:
    """The class the docstring describes: no per-instance ``__dict__``, no rebinding.

    Slotting is what makes "one context handed to every evaluator" cheap
    enough to be the design rather than an aspiration, and freezing is what
    stops a per-op evaluator from swapping a sink out from under the
    recursion. Both are load-bearing claims in the class docstring.
    """
    ctx = _EvalContext(
        values={},
        binding_values={},
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
        enum_binding_values={},
        date_binding_values={},
        filing_year=2025,
    )
    assert not hasattr(ctx, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.operand_refs = []  # type: ignore[misc]
