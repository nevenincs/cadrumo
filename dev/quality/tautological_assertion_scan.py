"""Scan for assertions decidable without knowing what the operand means.

The property, stated deliberately as a property rather than as a list of
forms: an assertion is tautological when its truth value is fixed before any
operand is understood. ``assert value or True`` holds whatever ``value`` is;
``assert value == value`` holds whatever ``value`` is; ``assert True`` holds
with no operand at all. Naming the property rather than the instances is what
lets the scan cover constructions nobody has written yet -- a list of forms
only ever catches the forms someone thought of.

WHAT THIS SCAN CANNOT DO, which matters more than what it can. This is the
only member of the gate-integrity family a linter can catch. Every other
instance in that family needed a person to ask what the assertion was ABOUT: a
gate whose assertion is perfectly well-formed and simply irrelevant to its
subject is indistinguishable, to any scan, from one that is on point. A green
result here says no assertion is trivially true; it does not say any assertion
is meaningful. Reading this gate as the general answer to gate integrity would
reproduce the exact error it exists to record.

The reflexive comparisons are split by outcome rather than lumped together,
because ``x == x`` and ``x != x`` fail differently: the first is an assertion
that can never fail, the second is one that can never pass. Both are decided
without the operand, so both belong here, but a reader fixing one wants to
know which they have.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import override

__all__ = [
    "TautologicalAssertion",
    "scan_paths_for_tautological_assertions",
    "scan_tautological_assertions",
]

_ALWAYS_TRUE_OPS = (ast.Eq, ast.Is, ast.LtE, ast.GtE)
_ALWAYS_FALSE_OPS = (ast.NotEq, ast.IsNot, ast.Lt, ast.Gt)


@dataclass(frozen=True, slots=True)
class TautologicalAssertion:
    """One assertion whose verdict does not depend on its operands."""

    path: Path
    lineno: int
    reason: str

    @override
    def __str__(self) -> str:
        """Render the finding as a locator a reader can open."""
        return f"{self.path}:{self.lineno} {self.reason}"


def _is_constant_truthy(node: ast.expr) -> bool:
    """Whether the node is a literal the interpreter always finds truthy.

    Container literals are included because ``assert [x]`` and ``assert (a, b)``
    are truthy for their length alone, no matter what the elements are -- a
    shape that reads like a real check and never is. An EMPTY container is
    not truthy, so it falls through to :func:`_is_constant_literal` and is
    reported as never-passing rather than never-failing.
    """
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return bool(node.elts)
    if isinstance(node, ast.Dict):
        return bool(node.keys)
    return False


def _is_constant_literal(node: ast.expr) -> bool:
    """Whether the node is a literal at all, truthy or not."""
    return isinstance(node, (ast.Constant, ast.List, ast.Tuple, ast.Set, ast.Dict))


def _describes_same_operand(left: ast.expr, right: ast.expr) -> bool:
    """Whether both sides are the same expression written twice.

    Compared by unparsed source rather than by node identity, so
    ``payload.total == payload.total`` is caught alongside ``x == x``. Any
    expression containing a call is refused: ``next(it) == next(it)`` is two
    different evaluations that only LOOK identical, and calling that reflexive
    would fire the gate on code doing real work.
    """
    if any(isinstance(node, ast.Call) for side in (left, right) for node in ast.walk(side)):
        return False
    return ast.unparse(left) == ast.unparse(right)


def _reason_for(test: ast.expr) -> str | None:
    """Why this assertion is decided without its operands, or None."""
    if _is_constant_truthy(test):
        return f"asserts the literal {ast.unparse(test)}, which is true before any operand is read"
    if _is_constant_literal(test):
        return f"asserts the literal {ast.unparse(test)}, which can never pass"
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
        for value in test.values:
            if _is_constant_truthy(value):
                return (
                    f"is an or-expression against the always-true {ast.unparse(value)}, "
                    "so the rest of the expression cannot change the verdict"
                )
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        right = test.comparators[0]
        if _describes_same_operand(test.left, right):
            if isinstance(test.ops[0], _ALWAYS_TRUE_OPS):
                return f"compares {ast.unparse(test.left)} with itself, so it can never fail"
            if isinstance(test.ops[0], _ALWAYS_FALSE_OPS):
                return f"compares {ast.unparse(test.left)} with itself, so it can never pass"
    if (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Name)
        and test.func.id == "isinstance"
        and len(test.args) == 2
        and isinstance(test.args[1], ast.Name)
        and test.args[1].id == "object"
    ):
        return "asserts isinstance(..., object), which holds for every value in the language"
    return None


def scan_tautological_assertions(path: Path, source: str) -> tuple[TautologicalAssertion, ...]:
    """Return every tautological assertion in one module's source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()
    found: list[TautologicalAssertion] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        reason = _reason_for(node.test)
        if reason is not None:
            found.append(TautologicalAssertion(path=path, lineno=node.lineno, reason=reason))
    return tuple(found)


def scan_paths_for_tautological_assertions(paths: tuple[Path, ...]) -> tuple[TautologicalAssertion, ...]:
    """Return every tautological assertion across the given modules."""
    found: list[TautologicalAssertion] = []
    for path in paths:
        found.extend(scan_tautological_assertions(path, path.read_text(encoding="utf-8")))
    return tuple(found)
