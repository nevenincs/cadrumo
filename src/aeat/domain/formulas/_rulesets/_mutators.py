"""Mutation-harness primitives for ruleset regression detection.

The mutators here are *test infrastructure*. None of them is imported by
production code. Each mutator returns a fresh
:class:`aeat.domain.formulas.Ruleset` (via ``model_copy``) with one — and
only one — leaf-level value perturbed; the surrounding test then asserts
that :class:`aeat.domain.formulas.Engine` surfaces a discrepancy on the
dependent casilla.

The wired mutator classes are:

- ``sub_op`` — outermost
  :class:`aeat.domain.formulas.SubFormula` operand swap.
- ``percent_rate`` — perturb a
  :class:`aeat.domain.formulas.PercentFormula` rate operand by +/-1
  percentage point. Two underlying mechanisms: literal-rate (mutate the
  :class:`aeat.domain.formulas.Literal` value) and parameter-rate
  (mutate the entry in the ruleset's
  :class:`aeat.domain.formulas.ParameterTable`). A
  :class:`aeat.domain.formulas.FormulaCasillaRef` rate is unmutable via
  AST and is recorded in the unflagged-nodes catalogue.
- ``brackets_threshold`` — perturb a non-terminal
  :class:`aeat.domain.formulas.Bracket` ``upper_inclusive`` by +/-1 €.
- ``mul_div_scalar`` — perturb a leaf
  :class:`aeat.domain.formulas.Literal` operand of a
  :class:`aeat.domain.formulas.MulFormula` or
  :class:`aeat.domain.formulas.DivFormula` by +/-1 %.

The walker yields *paths* into the formula tree — tuples of integers
indexing the ``operands`` of each compound node along the descent from
the casilla's :class:`aeat.domain.formulas.FormulaDefinition` root. A
mutator can then rebuild the tree along a path, replacing the leaf at
the path's terminus.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from decimal import Decimal
from typing import Final, cast

from pydantic import BaseModel, ConfigDict, Field

from .._formula import (
    AddFormula,
    Bracket,
    BracketsFormula,
    ClampPositiveFormula,
    DivFormula,
    Formula,
    FormulaCasillaRef,
    FormulaDefinition,
    Literal,
    MaxFormula,
    MinFormula,
    MulFormula,
    ParamRef,
    PercentFormula,
    RoundFormula,
    SubFormula,
    _compound_operands,
    _is_compound,
)
from .._ruleset import ParameterTable, ParameterValue, Ruleset

__all__ = [
    "MUTATOR_REGISTRY",
    "NOT_MUTABLE_NODE_TYPES",
    "MutatorClass",
    "is_additive_identity_literal",
    "iter_arithmetic_op_paths",
    "iter_brackets_nodes",
    "iter_casilla_ref_paths",
    "iter_compound_descendants",
    "iter_percent_nodes",
    "iter_scalar_leaf_paths",
    "iter_threshold_literal_paths",
    "mutate_arithmetic_op",
    "mutate_brackets_threshold",
    "mutate_casilla_ref",
    "mutate_parameter_rate",
    "mutate_percent_literal_rate",
    "mutate_scalar_leaf",
    "mutate_threshold_literal",
]


# -- Pydantic models ------------------------------------------------------


class _MutatorStrictFrozenModel(BaseModel):
    """Shared strict / frozen base for every mutator-side pydantic model."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class MutatorClass(_MutatorStrictFrozenModel):
    """Identity of a mutator class.

    Attributes:
        slug: Short identifier used in test ids and catalogue rows.
        description: Human-readable label.
    """

    slug: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=256)


class PercentRateLocation(_MutatorStrictFrozenModel):
    """Where a :class:`PercentFormula` rate lives in the ruleset.

    ``mode`` — one of ``"literal"`` (rate is a :class:`Literal` inside
    the formula tree), ``"param"`` (rate is a :class:`ParamRef`
    resolving via :class:`ParameterTable`), ``"casilla_ref"`` (rate is
    a :class:`FormulaCasillaRef` resolving to a fixture input value), or
    ``"compound"`` (rate is a compound formula — e.g. a
    :class:`DivFormula` produced by ``percent_from_whole``; mutation
    is delegated to descendant mutators).
    """

    mode: str = Field(min_length=1, max_length=16)
    casilla_id: str = Field(min_length=2, max_length=5)
    formula_id: str = Field(min_length=1, max_length=128)
    path: tuple[int, ...]
    param_id: str | None = None


# -- Walker ---------------------------------------------------------------


def iter_compound_descendants(node: object) -> Iterator[object]:
    """Yield every compound node in ``node``'s subtree (post-order).

    Includes ``node`` itself if it is compound. Used by every mutator
    to enumerate candidate sites for perturbation.
    """
    if _is_compound(node):
        for child in _compound_operands(node):
            yield from iter_compound_descendants(child)
        yield node


def _walk_with_paths(node: object, prefix: tuple[int, ...]) -> Iterator[tuple[tuple[int, ...], object]]:
    """Yield ``(path, node)`` for every node in the subtree, root-first.

    ``path`` is a tuple of operand indices from the original root; an
    empty tuple identifies the root. The walker descends through every
    compound node's ``operands`` field but does NOT recurse into the
    ``brackets`` field of a :class:`BracketsFormula` — bracket-step
    enumeration is handled by :func:`mutate_brackets_threshold` and
    :func:`iter_brackets_nodes` directly.
    """
    yield prefix, node
    if _is_compound(node):
        for idx, child in enumerate(_compound_operands(node)):
            yield from _walk_with_paths(child, (*prefix, idx))


def iter_percent_nodes(formula: Formula) -> Iterator[tuple[tuple[int, ...], PercentFormula]]:
    """Yield ``(path, percent_node)`` for every :class:`PercentFormula`."""
    for path, node in _walk_with_paths(formula, ()):
        if isinstance(node, PercentFormula):
            yield path, node


def iter_brackets_nodes(formula: Formula) -> Iterator[tuple[tuple[int, ...], BracketsFormula]]:
    """Yield ``(path, brackets_node)`` for every :class:`BracketsFormula`."""
    for path, node in _walk_with_paths(formula, ()):
        if isinstance(node, BracketsFormula):
            yield path, node


def iter_scalar_leaf_paths(
    formula: Formula,
) -> Iterator[tuple[tuple[int, ...], Literal, str]]:
    """Yield ``(path, literal, parent_op_slug)`` for every mul/div scalar leaf.

    A "scalar leaf" is a :class:`Literal` that is a *direct* operand
    of a :class:`MulFormula` or :class:`DivFormula`. The parent_op_slug
    is ``"mul"`` or ``"div"`` — used in test ids and the exec summary.
    """
    for path, node in _walk_with_paths(formula, ()):
        if isinstance(node, MulFormula):
            for idx, operand in enumerate(node.operands):
                if isinstance(operand, Literal):
                    yield (*path, idx), operand, "mul"
        elif isinstance(node, DivFormula):
            for idx, operand in enumerate(node.operands):
                if isinstance(operand, Literal):
                    yield (*path, idx), operand, "div"


def iter_threshold_literal_paths(
    formula: Formula,
) -> Iterator[tuple[tuple[int, ...], Literal, str]]:
    """Yield ``(path, literal, parent_op_slug)`` for every non-Mul/Div :class:`Literal`.

    BOE-anchored numeric constants embedded as :class:`Literal` operands
    of :class:`SubFormula` (bracket boundaries, art. 20 piecewise
    thresholds), :class:`MinFormula` (cap upper bounds),
    :class:`MaxFormula` (clamp lower bounds), and :class:`AddFormula`
    (additive padding) silently miscalculate tax if mistyped. This walker
    complements :func:`iter_scalar_leaf_paths` — together the two cover
    every :class:`Literal` position in the formula tree.

    Args:
        formula: Root formula node to walk.

    Yields:
        ``(path, literal, parent_op_slug)`` triples. ``parent_op_slug``
        is one of ``"sub"``, ``"min"``, ``"max"``, ``"add"``,
        ``"round"``, ``"clamp_pos"``, ``"percent"``. The rate operand of
        a :class:`PercentFormula` is owned by
        :func:`mutate_percent_literal_rate`, so the threshold harness
        skips that position.
    """
    for path, node in _walk_with_paths(formula, ()):
        if isinstance(node, MulFormula | DivFormula):
            continue
        if isinstance(node, PercentFormula):
            # Rate operand (idx 0) is owned by the percent_rate mutator;
            # any other operand is a base reference, never a literal.
            continue
        if isinstance(node, SubFormula):
            parent_slug = "sub"
        elif isinstance(node, MinFormula):
            parent_slug = "min"
        elif isinstance(node, MaxFormula):
            parent_slug = "max"
        elif isinstance(node, AddFormula):
            parent_slug = "add"
        elif isinstance(node, RoundFormula):
            parent_slug = "round"
        elif isinstance(node, ClampPositiveFormula):
            parent_slug = "clamp_pos"
        else:
            # BracketsFormula has its own threshold mutator;
            # other compound types do not have direct Literal operands.
            continue
        if not _is_compound(node):  # narrow for the type checker
            continue
        for idx, operand in enumerate(_compound_operands(node)):
            if isinstance(operand, Literal):
                yield (*path, idx), operand, parent_slug


def is_additive_identity_literal(parent_slug: str, literal_value: Decimal) -> bool:
    """Return ``True`` if ``literal_value`` is an architectural identity at ``parent_slug``.

    Identity positions are deliberately excluded from the threshold
    harness because a small mutation has no observable effect:

    - ``Max(0, X)`` with ``X > 0`` — the literal 0 is dominated; any
      epsilon-mutation leaves the max at X.
    - ``Min(0, X)`` with ``X > 0`` — symmetric (literal 0 wins).

    The rationale doubles as documentation of why the harness skips
    these positions; a future contributor adding a new identity
    pattern (e.g. ``Add(X, 0)``) should evaluate whether the literal
    is truly identity-only or carries information that drift could
    corrupt.
    """
    if literal_value != Decimal("0"):
        return False
    return parent_slug in ("max", "min")


def iter_arithmetic_op_paths(
    formula: Formula,
) -> Iterator[tuple[tuple[int, ...], str, int]]:
    """Yield ``(path, op_kind, n_operands)`` for every :class:`AddFormula` / :class:`SubFormula` node.

    ``op_kind`` is ``"add"`` or ``"sub"``; ``n_operands`` is the
    operand count (always 2 for SubFormula; 2..N for AddFormula).
    Used by the operator-class mutator to detect + <-> - typos:

    - **Add -> Sub**: an author who meant ``sub_op(a, b)`` but typed
      ``add_op(a, b)``. For 2-operand AddFormula the swap is direct;
      for N-operand AddFormula the swap converts the *last* + into a
      - (``add_op(a, b, c)`` -> ``sub_op(add_op(a, b), c)``), which
      models the most common operator-typo pattern (a single + slipped
      to - somewhere in the chain).
    - **Sub -> Add**: an author who meant ``add_op(a, b)`` but typed
      ``sub_op(a, b)``. SubFormula is exactly 2-operand; the swap is
      direct.
    """
    for path, node in _walk_with_paths(formula, ()):
        if isinstance(node, AddFormula):
            yield path, "add", len(node.operands)
        elif isinstance(node, SubFormula):
            yield path, "sub", 2


def mutate_arithmetic_op(
    ruleset: Ruleset,
    casilla_id: str,
    op_path: tuple[int, ...],
) -> Ruleset:
    """Swap an :class:`AddFormula` <-> :class:`SubFormula` at ``op_path``.

    Three cases:

    - 2-operand ``AddFormula`` -> ``SubFormula(operands)``.
    - 2-operand ``SubFormula`` -> ``AddFormula(operands)``.
    - N-operand (>= 3) ``AddFormula`` -> ``SubFormula(AddFormula(operands[:-1]), operands[-1])``
      — flips the last + to a -, modelling a single-character typo.

    Raises:
        LookupError: ``ruleset`` has no formula for ``casilla_id``.
        TypeError: the node at ``op_path`` is neither an AddFormula
            nor a SubFormula.
    """
    fd = _formula_for(ruleset, casilla_id)
    target = _node_at_path(fd.formula, op_path)
    new_node: AddFormula | SubFormula
    if isinstance(target, AddFormula):
        if len(target.operands) == 2:
            # Direct 2-operand swap: AddFormula.operands is
            # ``tuple[Operand, ...]`` (min_length=2, no max); narrow to
            # the SubFormula's ``tuple[Operand, Operand]`` shape.
            lhs, rhs = target.operands
            new_node = SubFormula(operands=(lhs, rhs))
        else:
            head_operands = target.operands[:-1]
            last_operand = target.operands[-1]
            inner_add = AddFormula(operands=head_operands)
            new_node = SubFormula(operands=(inner_add, last_operand))
    elif isinstance(target, SubFormula):
        new_node = AddFormula(operands=target.operands)
    else:
        raise TypeError(
            f"expected AddFormula or SubFormula at path {op_path} for ruleset "
            f"{ruleset.ruleset_id} casilla {casilla_id}; got {type(target).__name__}"
        )
    new_formula = _replace_at_path(fd.formula, op_path, new_node)
    return _replace_formula_in_ruleset(ruleset, casilla_id, cast(Formula, new_formula))


def iter_casilla_ref_paths(
    formula: Formula,
) -> Iterator[tuple[tuple[int, ...], FormulaCasillaRef]]:
    """Yield ``(path, casilla_ref)`` for every :class:`FormulaCasillaRef` in ``formula``.

    Detects topology typos: writing ``ref("0431")`` instead of
    ``ref("0432")`` silently routes the wrong upstream value into the
    formula. The associated mutator :func:`mutate_casilla_ref` re-targets
    the reference; the per-class harness picks a substitute with a
    different fixture value so the typo surfaces a discrepancy.
    """
    for path, node in _walk_with_paths(formula, ()):
        if isinstance(node, FormulaCasillaRef):
            yield path, node


def mutate_casilla_ref(
    ruleset: Ruleset,
    casilla_id: str,
    ref_path: tuple[int, ...],
    *,
    new_target: str,
) -> Ruleset:
    """Return a ruleset with the :class:`FormulaCasillaRef` at ``ref_path`` re-targeted.

    Replaces ``FormulaCasillaRef(casilla_id=A)`` at ``ref_path`` with
    ``FormulaCasillaRef(casilla_id=new_target)``. The new target must be a
    valid casilla_id in the ruleset; the per-class harness selects
    a substitute whose fixture value differs from the original's so
    the swap surfaces a discrepancy.

    Raises:
        LookupError: ``ruleset`` has no formula for ``casilla_id``.
        TypeError: the node at ``ref_path`` is not a :class:`FormulaCasillaRef`.
    """
    fd = _formula_for(ruleset, casilla_id)
    target_node = _node_at_path(fd.formula, ref_path)
    if not isinstance(target_node, FormulaCasillaRef):
        raise TypeError(
            f"expected FormulaCasillaRef at path {ref_path} for ruleset {ruleset.ruleset_id} "
            f"casilla {casilla_id}; got {type(target_node).__name__}"
        )
    new_ref = FormulaCasillaRef(casilla_id=new_target)
    new_formula = _replace_at_path(fd.formula, ref_path, new_ref)
    return _replace_formula_in_ruleset(ruleset, casilla_id, cast(Formula, new_formula))


def mutate_threshold_literal(
    ruleset: Ruleset,
    casilla_id: str,
    leaf_path: tuple[int, ...],
    *,
    offset: Decimal,
) -> Ruleset:
    """Return a ruleset with one threshold-literal shifted by ``offset``.

    Targets a :class:`Literal` that is a direct operand of a
    :class:`SubFormula`, :class:`MinFormula`, :class:`MaxFormula`,
    :class:`AddFormula`, :class:`RoundFormula`, or
    :class:`ClampPositiveFormula`. Every other Literal position is
    out of scope of this mutator (rate operands of
    :class:`PercentFormula` are owned by ``mutate_percent_literal_rate``;
    direct Mul/Div leaves are owned by ``mutate_scalar_leaf``).
    """
    fd = _formula_for(ruleset, casilla_id)
    leaf = _node_at_path(fd.formula, leaf_path)
    if not isinstance(leaf, Literal):
        raise TypeError(
            f"expected Literal at path {leaf_path} for ruleset {ruleset.ruleset_id} "
            f"casilla {casilla_id}; got {type(leaf).__name__}"
        )
    new_value = leaf.value + offset
    new_leaf = Literal(value=new_value)
    new_formula = _replace_at_path(fd.formula, leaf_path, new_leaf)
    return _replace_formula_in_ruleset(ruleset, casilla_id, cast(Formula, new_formula))


# -- AST surgery ----------------------------------------------------------


def _replace_at_path(node: object, path: tuple[int, ...], replacement: object) -> object:
    """Return a new tree where ``path`` points at ``replacement``.

    ``path = ()`` means replace the entire tree; otherwise the head of
    the path picks an operand index to descend into. The frozen models
    are reconstructed via ``model_copy(update={"operands": ...})`` so
    the original tree is not mutated.
    """
    if not path:
        return replacement
    if not _is_compound(node):
        raise TypeError(f"cannot descend path into non-compound node {type(node).__name__}")
    head, *tail = path
    operands = list(_compound_operands(node))
    if head < 0 or head >= len(operands):
        raise IndexError(f"operand index {head} out of range for {type(node).__name__}")
    operands[head] = _replace_at_path(operands[head], tuple(tail), replacement)
    # Every compound branch is a pydantic v2 BaseModel subclass — the
    # _is_compound check above proved it. Cast for the type-checker.
    return cast(BaseModel, node).model_copy(update={"operands": tuple(operands)})


def _replace_formula_in_ruleset(
    ruleset: Ruleset,
    casilla_id: str,
    new_formula: Formula,
) -> Ruleset:
    """Return a new ruleset with the casilla's formula replaced by ``new_formula``."""
    updated: list[FormulaDefinition] = []
    found = False
    for fd in ruleset.formulas:
        if fd.casilla_id == casilla_id:
            updated.append(
                FormulaDefinition(
                    casilla_id=fd.casilla_id,
                    formula_id=fd.formula_id,
                    formula=new_formula,
                )
            )
            found = True
        else:
            updated.append(fd)
    if not found:
        raise LookupError(f"ruleset {ruleset.ruleset_id} has no formula for casilla {casilla_id!r}")
    return ruleset.model_copy(update={"formulas": tuple(updated)})


# -- Percent-rate mutators ------------------------------------------------


def classify_percent_rate(
    fd: FormulaDefinition,
    path: tuple[int, ...],
    node: PercentFormula,
) -> PercentRateLocation:
    """Classify the rate operand of ``node`` (which is at ``path``)."""
    rate = node.operands[0]
    if isinstance(rate, Literal):
        mode = "literal"
        param_id: str | None = None
    elif isinstance(rate, ParamRef):
        mode = "param"
        param_id = rate.param_id
    elif isinstance(rate, FormulaCasillaRef):
        mode = "casilla_ref"
        param_id = None
    else:
        mode = "compound"
        param_id = None
    return PercentRateLocation(
        mode=mode,
        casilla_id=fd.casilla_id,
        formula_id=fd.formula_id,
        path=path,
        param_id=param_id,
    )


def mutate_percent_literal_rate(
    ruleset: Ruleset,
    casilla_id: str,
    rate_path: tuple[int, ...],
    *,
    delta: Decimal,
) -> Ruleset:
    """Return a ruleset with a literal-rate :class:`PercentFormula` shifted.

    ``rate_path`` is the full path from the formula-tree root to the
    rate leaf — i.e. the path to the :class:`PercentFormula` plus
    ``(0,)`` for the rate operand.
    """
    fd = _formula_for(ruleset, casilla_id)
    rate_node = _node_at_path(fd.formula, rate_path)
    if not isinstance(rate_node, Literal):
        raise TypeError(
            f"expected Literal at path {rate_path} for ruleset {ruleset.ruleset_id} "
            f"casilla {casilla_id}; got {type(rate_node).__name__}"
        )
    new_value = rate_node.value + delta
    new_literal = Literal(value=new_value)
    new_formula = _replace_at_path(fd.formula, rate_path, new_literal)
    return _replace_formula_in_ruleset(ruleset, casilla_id, cast(Formula, new_formula))


def mutate_parameter_rate(
    ruleset: Ruleset,
    param_id: str,
    *,
    delta: Decimal,
) -> Ruleset:
    """Return a ruleset whose ``param_id`` parameter has been shifted by ``delta``.

    Every :class:`ParameterValue` for ``param_id`` is shifted; that is
    the simplest deterministic transformation and the only one that
    matters for a single-period mutation test (every ruleset's
    parameter-table entry covers the ruleset's full effective span).
    """
    table = ruleset.parameters
    if param_id not in table.entries:
        raise LookupError(f"ruleset {ruleset.ruleset_id} declares no parameter {param_id!r}")
    new_entries: dict[str, tuple[ParameterValue, ...]] = dict(table.entries)
    shifted = tuple(
        ParameterValue(
            effective_from=v.effective_from,
            effective_to=v.effective_to,
            value=v.value + delta,
        )
        for v in table.entries[param_id]
    )
    new_entries[param_id] = shifted
    new_table = ParameterTable(entries=new_entries)
    return ruleset.model_copy(update={"parameters": new_table})


def mutate_brackets_threshold(
    ruleset: Ruleset,
    casilla_id: str,
    brackets_path: tuple[int, ...],
    bracket_index: int,
    *,
    delta: Decimal,
) -> Ruleset:
    """Return a ruleset with one bracket's ``upper_inclusive`` shifted.

    ``brackets_path`` points at a :class:`BracketsFormula` inside the
    casilla's formula tree. ``bracket_index`` is the position of the
    bracket to shift in that formula's ``brackets`` tuple. The terminal
    bracket (``upper_inclusive=None``) is never shifted because shifting
    a sentinel value is not a meaningful mutation.
    """
    fd = _formula_for(ruleset, casilla_id)
    brackets_node = _node_at_path(fd.formula, brackets_path)
    if not isinstance(brackets_node, BracketsFormula):
        raise TypeError(
            f"expected BracketsFormula at path {brackets_path} for ruleset "
            f"{ruleset.ruleset_id} casilla {casilla_id}; got {type(brackets_node).__name__}"
        )
    if bracket_index < 0 or bracket_index >= len(brackets_node.brackets) - 1:
        raise IndexError(
            f"bracket_index {bracket_index} out of range for non-terminal brackets "
            f"of {brackets_node} (terminal bracket may not be shifted)"
        )
    target = brackets_node.brackets[bracket_index]
    if target.upper_inclusive is None:
        raise ValueError("non-terminal bracket must declare upper_inclusive")
    new_brackets: list[Bracket] = list(brackets_node.brackets)
    new_brackets[bracket_index] = Bracket(
        upper_inclusive=target.upper_inclusive + delta,
        value=target.value,
    )
    # Construct fresh so :func:`BracketsFormula._validate_brackets` runs
    # — model_copy skips ``mode='after'`` validators in pydantic v2 and
    # we want a malformed shift to fail loudly at mutation time.
    new_brackets_node = BracketsFormula(operands=brackets_node.operands, brackets=tuple(new_brackets))
    new_formula = _replace_at_path(fd.formula, brackets_path, new_brackets_node)
    return _replace_formula_in_ruleset(ruleset, casilla_id, cast(Formula, new_formula))


# -- Mul/Div scalar mutator ----------------------------------------------


def mutate_scalar_leaf(
    ruleset: Ruleset,
    casilla_id: str,
    leaf_path: tuple[int, ...],
    *,
    factor: Decimal,
) -> Ruleset:
    """Return a ruleset with one mul/div leaf scalar multiplied by ``factor``.

    ``leaf_path`` points at a :class:`Literal` that is a direct operand
    of a :class:`MulFormula` or :class:`DivFormula` — every other
    literal is out of scope of this mutator and must be skipped by
    callers (e.g. the literal-rate :class:`PercentFormula` operand,
    which is owned by the percent-rate mutator).
    """
    fd = _formula_for(ruleset, casilla_id)
    leaf = _node_at_path(fd.formula, leaf_path)
    if not isinstance(leaf, Literal):
        raise TypeError(
            f"expected Literal at path {leaf_path} for ruleset {ruleset.ruleset_id} "
            f"casilla {casilla_id}; got {type(leaf).__name__}"
        )
    new_value = leaf.value * factor
    new_leaf = Literal(value=new_value)
    new_formula = _replace_at_path(fd.formula, leaf_path, new_leaf)
    return _replace_formula_in_ruleset(ruleset, casilla_id, cast(Formula, new_formula))


def _formula_for(ruleset: Ruleset, casilla_id: str) -> FormulaDefinition:
    fd = ruleset.formula_for(casilla_id)
    if fd is None:
        raise LookupError(f"ruleset {ruleset.ruleset_id} has no formula for casilla {casilla_id!r}")
    return fd


def _node_at_path(node: object, path: tuple[int, ...]) -> object:
    current: object = node
    for idx in path:
        if not _is_compound(current):
            raise TypeError(f"cannot descend into non-compound node {type(current).__name__}")
        operands = _compound_operands(current)
        if idx < 0 or idx >= len(operands):
            raise IndexError(f"operand index {idx} out of range for {type(current).__name__}")
        current = operands[idx]
    return current


# -- Registry + allow-list ------------------------------------------------


SUB_OP_SWAP: Final[MutatorClass] = MutatorClass(
    slug="sub_op_swap",
    description="Swap operands of any SubFormula descendant (outer or inner).",
)
PERCENT_RATE: Final[MutatorClass] = MutatorClass(
    slug="percent_rate",
    description="Shift a PercentFormula rate by +/-1 percentage point.",
)
BRACKETS_THRESHOLD: Final[MutatorClass] = MutatorClass(
    slug="brackets_threshold",
    description="Shift a non-terminal Bracket upper_inclusive by +/-1 €.",
)
MUL_DIV_SCALAR: Final[MutatorClass] = MutatorClass(
    slug="mul_div_scalar",
    description="Multiply a Mul/Div Literal leaf by 1.01 or 0.99 (+/-1 %).",
)
THRESHOLD_LITERAL: Final[MutatorClass] = MutatorClass(
    slug="threshold_literal",
    description=(
        "Shift a non-Mul/Div Literal operand by +/-1 € (bracket boundaries, "
        "art. 20 thresholds, IVA-rate constants, additive padding, etc.)."
    ),
)
ARITHMETIC_OP_SWAP: Final[MutatorClass] = MutatorClass(
    slug="arithmetic_op_swap",
    description=(
        "Swap an AddFormula <-> SubFormula at any AST position to detect "
        "operator-class typos (+ vs -). 2-operand swaps are direct; "
        "N-operand AddFormula swaps the last + to a -."
    ),
)
CASILLA_REF_TOPOLOGY: Final[MutatorClass] = MutatorClass(
    slug="casilla_ref_topology",
    description=(
        "Re-target a FormulaCasillaRef to a different casilla_id with a "
        "differing fixture value to detect topology typos (ref('0431') "
        "vs ref('0432'))."
    ),
)


# Map every concrete formula-node type to the mutator class that owns it.
# Adding a new ``Formula`` subclass without updating this mapping (or
# the allow-list below) fails ``test_mutator_exhaustiveness``. Note
# that :class:`Literal` participates in two harnesses (mul_div_scalar
# when a direct Mul/Div leaf operand; threshold_literal otherwise)
# and is recorded against ``MUL_DIV_SCALAR`` here as the historical
# anchor; ``test_threshold_literal_mutation`` enforces coverage of
# the non-Mul/Div positions independently.
MUTATOR_REGISTRY: Final[dict[type, MutatorClass]] = {
    SubFormula: SUB_OP_SWAP,
    PercentFormula: PERCENT_RATE,
    BracketsFormula: BRACKETS_THRESHOLD,
    MulFormula: MUL_DIV_SCALAR,
    DivFormula: MUL_DIV_SCALAR,
    Literal: MUL_DIV_SCALAR,
    FormulaCasillaRef: CASILLA_REF_TOPOLOGY,
}


# Concrete formula-node types that are intentionally not mutated by any
# class. The reason for each entry must be defensible — a future author
# who proposes adding a node type to this list must justify why a
# mutation of it would not detect a meaningful regression.
NOT_MUTABLE_NODE_TYPES: Final[dict[type, str]] = {
    AddFormula: (
        "AddFormula is N-ary commutative addition; an operand swap is "
        "a no-op semantically. Order-bearing regressions surface via "
        "the SubFormula operand-swap mutator at the call site."
    ),
    MinFormula: (
        "MinFormula is N-ary commutative minimum; an operand swap is a "
        "no-op semantically. Boundary-clamp drift surfaces via downstream "
        "PercentFormula or scalar-leaf mutators."
    ),
    MaxFormula: (
        "MaxFormula is N-ary commutative maximum; an operand swap is a "
        "no-op semantically. Boundary-clamp drift surfaces via downstream "
        "PercentFormula or scalar-leaf mutators."
    ),
    ClampPositiveFormula: (
        "ClampPositiveFormula is unary; there is no parameter to mutate. "
        "Sign-flip regressions are caught by the upstream SubFormula "
        "operand-swap mutator."
    ),
    RoundFormula: (
        "RoundFormula is the terminal presentation wrapper produced by "
        "the ruleset author's formula() helper. Its parameters (digits, "
        "rounding mode) are invariants of the engine, not per-rule "
        "values, so mutation would test the engine, not the ruleset."
    ),
    # NB: Literal is intentionally absent from NOT_MUTABLE_NODE_TYPES.
    # ~120 Literal nodes across the landed rulesets are direct operands
    # of Sub/Min/Max/Add/Round/ClampPos (bracket boundaries, art. 20
    # piecewise thresholds, IVA rate constants, additive-identity
    # zeros) and are exercised by the THRESHOLD_LITERAL mutator class.
    # Architectural identities (Max(0, X) / Min(0, X) lower/upper
    # bounds with X > 0) are filtered by is_additive_identity_literal().
    # NB: FormulaCasillaRef is intentionally absent from NOT_MUTABLE_NODE_TYPES.
    # CASILLA_REF_TOPOLOGY re-targets every reference to a different
    # casilla_id with a differing fixture value. Topology typos
    # (``ref("0431")`` vs ``ref("0432")``) are detected via that harness;
    # FormulaCasillaRef is a leaf operand type whose mutation is owned
    # by the topology mutator class, but the exhaustiveness test still
    # expects it in MUTATOR_REGISTRY.
    ParamRef: (
        "ParamRef is a runtime indirection; the value it resolves to "
        "lives in the ParameterTable and is mutated by the percent-rate "
        "mutator's parameter-shift path."
    ),
}


def all_concrete_formula_types() -> Iterable[type]:
    """Return every concrete model class accepted by :data:`Formula`.

    The :data:`Formula` discriminated-union is composed via ``A | B | ...``;
    the union arms are accessible via ``__args__`` after the
    :class:`pydantic.fields.FieldInfo` annotation is unwrapped. A robust
    implementation re-derives the union from the explicit listing in
    ``aeat.domain.formulas.__init__`` and the ``op``-tagged subclasses above.
    """
    return (
        AddFormula,
        SubFormula,
        MulFormula,
        DivFormula,
        MinFormula,
        MaxFormula,
        ClampPositiveFormula,
        PercentFormula,
        BracketsFormula,
        RoundFormula,
    )


def all_concrete_operand_types() -> Iterable[type]:
    """Return every concrete model class accepted by :data:`Operand`.

    Mirrors :func:`all_concrete_formula_types` plus the leaf operands.
    """
    return (
        Literal,
        FormulaCasillaRef,
        ParamRef,
        AddFormula,
        SubFormula,
        MulFormula,
        DivFormula,
        MinFormula,
        MaxFormula,
        ClampPositiveFormula,
        PercentFormula,
        BracketsFormula,
        RoundFormula,
    )


