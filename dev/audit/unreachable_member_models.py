"""Typed call records and bounded expression traversal."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedCall:
    """A call's qualified receiver and statically named argument types."""

    target: str
    keywords: tuple[tuple[str | None, str], ...]
    arguments: frozenset[str]
    positionals: tuple[str, ...]


def expression_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Walk an expression without descending into nested comprehensions."""
    yield node
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, ast.stmt):
            yield from expression_nodes(child)
