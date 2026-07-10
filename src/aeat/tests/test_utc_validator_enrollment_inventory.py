"""Inventory test: zero inline tzinfo-is-None guards survive in production code.

Every site that previously reimplemented UTC timezone validation inline
(``if value.tzinfo is None or value.utcoffset() is None: raise ...``) must
now delegate to :func:`~core.time.validate_utc_aware`.

This test walks the production source tree with :mod:`ast` and asserts that
no ``tzinfo is None`` comparisons appear outside the canonical UTC module
itself and outside test files.

See Also:
    :mod:`~tests._inventory`
        Provides the shared production AST inventory consumed by the ratchet.
    :mod:`~core.time`
        Public home for the canonical UTC coercion and validation helpers.

A timezone-awareness check must delegate to the canonical validator so a
future rule change (leap-second handling, offset tolerance) is fixed once.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_AEAT
_CANONICAL_UTC_MODULE = _SRC_ROOT / "core" / "time" / "_utc.py"


def _tree_has_inline_tzinfo_guard(tree: ast.AST) -> bool:
    """Return True iff *tree* contains an inline ``tzinfo is None`` check."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        # Look for ``<expr>.tzinfo is None``
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            if not isinstance(op, ast.Is):
                continue
            if not (isinstance(comparator, ast.Constant) and comparator.value is None):
                continue
            # Check the left-hand side: it must be an attribute access ending in ``tzinfo``
            left = node.left if comparator is node.comparators[0] else None
            if left is None:
                # Handle chained comparisons — check all pairs
                for i, (op2, comp2) in enumerate(zip(node.ops, node.comparators, strict=False)):
                    if isinstance(op2, ast.Is) and isinstance(comp2, ast.Constant) and comp2.value is None:
                        lhs = node.left if i == 0 else node.comparators[i - 1]
                        if isinstance(lhs, ast.Attribute) and lhs.attr == "tzinfo":
                            return True
            else:
                if isinstance(left, ast.Attribute) and left.attr == "tzinfo":
                    return True
    return False


def test_no_inline_tzinfo_guards_in_production_code(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Assert zero ``tzinfo is None`` inline guards remain outside the UTC module.

    Consumes the shared production AST cache so the per-file parse cost
    is amortised across the full ratchet suite.
    """
    violations: list[str] = []
    canonical_utc = _CANONICAL_UTC_MODULE.resolve()

    for py_file, tree in production_ast_items(source_tree_ast):
        # Skip the canonical UTC module — it is the allowed home.
        if py_file.resolve() == canonical_utc:
            continue
        if _tree_has_inline_tzinfo_guard(tree):
            violations.append(str(py_file.relative_to(_SRC_ROOT.parent)))

    assert not violations, (
        f"Found {len(violations)} production file(s) with inline ``tzinfo is None`` guards "
        f"that must be migrated to validate_utc_aware:\n" + "\n".join(f"  {v}" for v in sorted(violations))
    )
