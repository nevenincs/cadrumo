"""Lexically bound expressions carried by declaration provenance."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceExpression:
    """An expression with the lexical bindings supplied by its caller."""

    module: str
    node: ast.AST
    bindings: Mapping[str, tuple[SourceExpression, ...]] = field(default_factory=dict)
    wrapped_node: bool = False
