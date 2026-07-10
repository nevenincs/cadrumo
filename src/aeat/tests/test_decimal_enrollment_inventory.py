"""Inventory gate for canonical Decimal rounding and coercion.

Production modules under ``src/aeat/`` must not use:

1. ``value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`` inline.
   All callers must delegate to :func:`~core.money.round_to_cents`.

2. ``Decimal(str(`` bare coercion patterns inline.
   All callers must delegate to :func:`~core.decimal.coerce_decimal`.

The only production exclusions are the canonical implementation modules
themselves. Test modules may exercise decimal behaviour directly.

See Also:
    :mod:`~core.money`
        Canonical euro-cent quantum and half-up rounding helper.
    :mod:`~core.decimal`
        Canonical Decimal coercion and formatting helpers.
    :mod:`~tests._inventory`
        Shared production AST inventory surface used by this ratchet.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, leaf_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_AEAT

# Canonical modules exempt from their own rules.
_ROUNDING_MODULE = _SRC_ROOT / "core" / "money" / "__init__.py"
_COERCE_MODULE = _SRC_ROOT / "core" / "decimal" / "_coerce.py"


def _is_excluded(path: Path) -> bool:
    return path in (_ROUNDING_MODULE, _COERCE_MODULE)


def _is_decimal_literal_call(node: ast.AST, literal: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and leaf_name(node.func) == "Decimal"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == literal
    )


def _is_round_half_up_keyword(keyword: ast.keyword) -> bool:
    return keyword.arg == "rounding" and leaf_name(keyword.value) == "ROUND_HALF_UP"


def _is_cent_quantize_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "quantize"
        and len(node.args) >= 1
        and _is_decimal_literal_call(node.args[0], "0.01")
        and any(_is_round_half_up_keyword(keyword) for keyword in node.keywords)
    )


def _is_decimal_str_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and leaf_name(node.func) == "Decimal"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Call)
        and leaf_name(node.args[0].func) == "str"
    )


def _collect_quantize_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every inline quantize call."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        for node in ast.walk(tree):
            if _is_cent_quantize_call(node):
                violations.append(f"{repo_relative(path)}:{node.lineno}")
    return violations


def _collect_decimal_str_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every bare Decimal(str()) call."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        for node in ast.walk(tree):
            if _is_decimal_str_call(node):
                violations.append(f"{repo_relative(path)}:{node.lineno}")
    return violations


def test_no_inline_quantize_round_half_up(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Inline ``value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`` must be zero.

    All known sites use ``round_to_cents`` from ``aeat.core.money``.
    Any new inline call is a regression.
    """
    violations = _collect_quantize_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)"
            f" call(s) found in production code:\n  {joined}\n\n"
            "Replace each call with round_to_cents() from aeat.core.money.",
        )


def test_no_bare_decimal_str_coercion(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Bare ``Decimal(str(`` coercion must be zero in production code.

    All call-sites must delegate to :func:`~core.decimal.coerce_decimal`.
    The only permitted occurrence lives in the canonical helper module itself,
    which is excluded above.
    """
    violations = _collect_decimal_str_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare Decimal(str()) coercion call(s) found in production code:\n  {joined}\n\n"
            "Replace each call with coerce_decimal() from aeat.core.decimal.",
        )
