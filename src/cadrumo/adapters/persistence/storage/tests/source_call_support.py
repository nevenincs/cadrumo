"""AST call detection for source-shape gates."""

from __future__ import annotations

import ast
import textwrap

__all__ = ["source_calls"]


def source_calls(source: str, callee: str) -> bool:
    """Whether ``source`` actually CALLS ``callee``, not merely mentions it.

    A membership test on source text passes when the name appears in a
    docstring or comment, so a surface that stopped delegating while keeping
    its prose reads as compliant.
    """
    tree = ast.parse(textwrap.dedent(source))
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Attribute) and node.func.attr == callee)
            or (isinstance(node.func, ast.Name) and node.func.id == callee)
        )
        for node in ast.walk(tree)
    )
