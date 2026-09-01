"""Deleted ``core._time`` import-survivor inventory.

Confirms the dormant ``cadrumo.core.time`` shim remains deleted and that
production source imports the canonical :mod:`~core.time` package instead of
the retired module. The direct import assertion catches importable survivors;
the AST inventory catches source-level references before they can reintroduce
the deleted clock surface.

See Also:
    :mod:`~core.time`
        Canonical UTC clock, frozen-clock seam, and UTC datetime helpers.
    :mod:`~tests._inventory`
        Shared production AST inventory surface used by structural ratchets.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from .inventory import production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# cadrumo.core.time deletion verification
# ---------------------------------------------------------------------------


def test_aeat_core_time_module_deleted() -> None:
    """cadrumo.core.time must not be importable — the module has been deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cadrumo.core.time")


def _imports_deleted_core_time(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == "cadrumo.core.time" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "cadrumo.core.time":
            return True
    return False


def test_no_source_imports_aeat_core_time(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No production source file may import from cadrumo.core.time."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _imports_deleted_core_time(tree):
            violations.append(repo_relative(path))
    if violations:
        raise AssertionError(
            f"{len(violations)} source file(s) still reference cadrumo.core.time:\n  " + "\n  ".join(violations),
        )
