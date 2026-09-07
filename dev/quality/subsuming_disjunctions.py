"""Detect membership disjunctions whose broader needle subsumes a sibling.

For ``assert specific in output or broad in output``, the specific operand can
never decide the assertion when ``broad`` is a strict substring of ``specific``
and both operands read the same haystack.  The detector deliberately accepts
only that closed AST shape; mixed predicates and different haystacks remain
outside its claim.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import override

__all__ = [
    "SubsumingDisjunction",
    "scan_paths_for_subsuming_disjunctions",
    "scan_subsuming_disjunctions",
]


@dataclass(frozen=True, slots=True)
class SubsumingDisjunction:
    """One disjunction where a broad membership makes a specific one redundant."""

    path: Path
    lineno: int
    broad_needle: str
    specific_needle: str
    haystack: str

    @override
    def __str__(self) -> str:
        """Render an openable locator and the exact subsumption relation."""
        return f"{self.path}:{self.lineno} {self.broad_needle!r} subsumes {self.specific_needle!r} in {self.haystack}"


def _string_membership(node: ast.expr) -> tuple[str, ast.expr] | None:
    """Return ``(needle, haystack)`` for one exact string-membership operand."""
    if not (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.In)
        and len(node.comparators) == 1
        and isinstance(node.left, ast.Constant)
        and isinstance(node.left.value, str)
    ):
        return None
    return node.left.value, node.comparators[0]


def _is_stable_reference(node: ast.expr) -> bool:
    """Whether repeated syntax denotes one reference without evaluating an operation."""
    return isinstance(node, ast.Name)


def scan_subsuming_disjunctions(path: Path, source: str) -> tuple[SubsumingDisjunction, ...]:
    """Return every exact subsuming-membership disjunction in one module."""
    tree = ast.parse(source, filename=str(path))
    findings: list[SubsumingDisjunction] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assert) and isinstance(node.test, ast.BoolOp)):
            continue
        if not isinstance(node.test.op, ast.Or):
            continue
        operands = tuple(_string_membership(value) for value in node.test.values)
        if any(operand is None for operand in operands):
            continue
        memberships = tuple(operand for operand in operands if operand is not None)
        if any(not _is_stable_reference(haystack) for _needle, haystack in memberships):
            continue
        haystack_keys = {ast.dump(haystack, include_attributes=False) for _needle, haystack in memberships}
        if len(haystack_keys) != 1:
            continue
        haystack = ast.unparse(memberships[0][1])
        for broad_needle, _ in memberships:
            for specific_needle, _ in memberships:
                if broad_needle != specific_needle and broad_needle in specific_needle:
                    findings.append(
                        SubsumingDisjunction(
                            path=path,
                            lineno=node.lineno,
                            broad_needle=broad_needle,
                            specific_needle=specific_needle,
                            haystack=haystack,
                        ),
                    )
    return tuple(findings)


def scan_paths_for_subsuming_disjunctions(paths: tuple[Path, ...]) -> tuple[SubsumingDisjunction, ...]:
    """Return every subsuming disjunction across the supplied modules."""
    findings: list[SubsumingDisjunction] = []
    for path in paths:
        findings.extend(scan_subsuming_disjunctions(path, path.read_text(encoding="utf-8")))
    return tuple(findings)
