"""Mutation-harness primitives for ruleset regression detection.

The mutators here are *test infrastructure*. None of them is imported
by production code. Each mutator returns a fresh :class:`Ruleset`
(via ``model_copy``) with one — and only one — leaf-level value
perturbed; the surrounding test then asserts that the engine surfaces
a discrepancy on the dependent casilla.

Four mutator classes are wired:

- ``sub_op`` — outermost-:class:`SubFormula` operand swap (kept in
  ``test_operand_swap_mutation`` for historical-marker reasons; see
  the ADR file-organisation rationale).
- ``percent_rate`` — perturb a :class:`PercentFormula` rate operand
  by ±1 percentage point. Two underlying mechanisms: literal-rate
  (mutate the :class:`Literal` value) and parameter-rate (mutate
  the entry in the ruleset's :class:`ParameterTable`). A
  ``CasillaRef`` rate is unmuturable via AST and is recorded in the
  unflagged-nodes catalogue.
- ``brackets_threshold`` — perturb a non-terminal
  :class:`Bracket`'s ``upper_inclusive`` by ±1 €.
- ``mul_div_scalar`` — perturb a leaf :class:`Literal` operand of
  a :class:`MulFormula` or :class:`DivFormula` by ±1 %.

The walker yields *paths* into the formula tree — tuples of integers
indexing the ``operands`` of each compound node along the descent
from the casilla's :class:`FormulaDefinition.formula` root. A
mutator can then rebuild the tree along a path, replacing the leaf
at the path's terminus.
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
    CasillaRef,
    ClampPositiveFormula,
    DivFormula,
    Formula,
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
    "MutationCase",
    "MutatorClass",
    "PercentRateLocation",
    "build_percent_rate_mutants",
    "build_scalar_mutants",
    "iter_compound_descendants",
    "iter_percent_nodes",
    "iter_scalar_leaf_paths",
    "mutate_brackets_threshold",
    "mutate_parameter_rate",
    "mutate_percent_literal_rate",
    "mutate_scalar_leaf",
]


# -- Pydantic models ------------------------------------------------------


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class MutatorClass(_StrictFrozenModel):
    """Identity of a mutator class.

    ``slug`` — short identifier used in test ids and in catalogue rows.
    ``description`` — human-readable label for the exec summary.
    """

    slug: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=256)


class MutationCase(_StrictFrozenModel):
    """Result of evaluating one mutated ruleset against one fixture.

    The kill-rate aggregator collects these records across the full
    eighteen-ruleset surface and emits the catalogue used in the
    issue's exec summary.
    """

    ruleset_id: str = Field(min_length=1, max_length=128)
    casilla_id: str = Field(min_length=2, max_length=5)
    mutator_slug: str = Field(min_length=1, max_length=64)
    direction: str = Field(min_length=1, max_length=32)
    max_abs_delta: Decimal
    affected_casillas: tuple[str, ...]
    killed: bool


class PercentRateLocation(_StrictFrozenModel):
    """Where a :class:`PercentFormula` rate lives in the ruleset.

    ``mode`` — one of ``"literal"`` (rate is a :class:`Literal` inside
    the formula tree), ``"param"`` (rate is a :class:`ParamRef`
    resolving via :class:`ParameterTable`), ``"casilla_ref"`` (rate is
    a :class:`CasillaRef` resolving to a fixture input value), or
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
    empty tuple identifies the root. Paths into a :class:`Bracket`
    (the bracket array of a :class:`BracketsFormula`) are emitted as
    sentinel tuples with a string second element — the bracket
    enumerator handles those separately.
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
    elif isinstance(rate, CasillaRef):
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


def build_percent_rate_mutants(
    ruleset: Ruleset,
) -> tuple[tuple[PercentRateLocation, Decimal], ...]:
    """Return the full set of ``(location, delta)`` pairs for ``ruleset``.

    Two directions per mutable rate (``+0.01`` and ``-0.01``).
    Compound and casilla-ref rates are skipped — they appear in the
    unflagged-nodes catalogue produced by the kill-rate aggregator.
    """
    pairs: list[tuple[PercentRateLocation, Decimal]] = []
    for fd in ruleset.formulas:
        for path, node in iter_percent_nodes(fd.formula):
            location = classify_percent_rate(fd, path, node)
            if location.mode in ("literal", "param"):
                pairs.append((location, Decimal("0.01")))
                pairs.append((location, Decimal("-0.01")))
    return tuple(pairs)


# -- Brackets-threshold mutator ------------------------------------------


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


def build_scalar_mutants(
    ruleset: Ruleset,
) -> tuple[tuple[str, str, tuple[int, ...], str, Decimal], ...]:
    """Return the full set of mul/div scalar mutation seeds for ``ruleset``.

    Each entry is ``(casilla_id, formula_id, leaf_path, parent_op, factor)``.
    Two factors per mutable leaf (``Decimal("1.01")`` for +1 % and
    ``Decimal("0.99")`` for -1 %).
    """
    seeds: list[tuple[str, str, tuple[int, ...], str, Decimal]] = []
    for fd in ruleset.formulas:
        for leaf_path, _leaf, parent in iter_scalar_leaf_paths(fd.formula):
            seeds.append((fd.casilla_id, fd.formula_id, leaf_path, parent, Decimal("1.01")))
            seeds.append((fd.casilla_id, fd.formula_id, leaf_path, parent, Decimal("0.99")))
    return tuple(seeds)


# -- Internal helpers -----------------------------------------------------


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
    description="Swap operands of an outermost SubFormula (preserved from wave 60 stream 4).",
)
PERCENT_RATE: Final[MutatorClass] = MutatorClass(
    slug="percent_rate",
    description="Shift a PercentFormula rate by ±1 percentage point.",
)
BRACKETS_THRESHOLD: Final[MutatorClass] = MutatorClass(
    slug="brackets_threshold",
    description="Shift a non-terminal Bracket upper_inclusive by ±1 €.",
)
MUL_DIV_SCALAR: Final[MutatorClass] = MutatorClass(
    slug="mul_div_scalar",
    description="Multiply a Mul/Div Literal leaf by 1.01 or 0.99 (±1 %).",
)


# Map every concrete formula-node type to the mutator class that owns it.
# Adding a new ``Formula`` subclass without updating this mapping (or
# the allow-list below) fails ``test_mutator_exhaustiveness``.
MUTATOR_REGISTRY: Final[dict[type, MutatorClass]] = {
    SubFormula: SUB_OP_SWAP,
    PercentFormula: PERCENT_RATE,
    BracketsFormula: BRACKETS_THRESHOLD,
    MulFormula: MUL_DIV_SCALAR,
    DivFormula: MUL_DIV_SCALAR,
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
    Literal: (
        "Literal participates in the harness only when it is the rate "
        "of a PercentFormula or the leaf of a Mul/Div node — both "
        "scenarios are owned by their parent's mutator class. A "
        "standalone Literal (e.g. M303 casillas 02/05/08, the printed "
        "IVA rates) is a presentation value, not a calculation."
    ),
    CasillaRef: (
        "CasillaRef is a runtime indirection; mutating it would change "
        "the formula's topology, not a value. Topology errors are out "
        "of scope for the four-mutator surface."
    ),
    ParamRef: (
        "ParamRef is a runtime indirection; the value it resolves to "
        "lives in the ParameterTable and is mutated by the percent-rate "
        "mutator's parameter-shift path."
    ),
}


def all_concrete_formula_types() -> Iterable[type]:
    """Return every concrete model class accepted by :data:`Formula`.

    The :data:`Formula` discriminated-union is composed via ``A | B | …``;
    the union arms are accessible via ``__args__`` after the
    :class:`pydantic.fields.FieldInfo` annotation is unwrapped. A robust
    implementation re-derives the union from the explicit listing in
    ``aeat.formulas.__init__`` and the ``op``-tagged subclasses above.
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
        CasillaRef,
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
