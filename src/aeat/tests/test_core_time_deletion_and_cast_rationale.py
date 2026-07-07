"""Deleted ``core._time`` import-survivor inventory.

Confirms the dormant ``aeat.core._time`` shim remains deleted and that
production source imports the canonical :mod:`~core.time` package instead of
the retired module. The direct import assertion catches importable survivors;
the AST inventory catches source-level references before they can reintroduce
the deleted clock surface.

See Also:
    :mod:`~core.time`
        Canonical UTC clock, frozen-clock seam, and UTC datetime helpers.
    :mod:`~tests._inventory`
        Shared production AST inventory surface used by structural ratchets.
    ``2026-05-28-codebase-solidification-plan``
        W07.P33.S528/S530 deletion and aggregate-test closure for
        ``core._time``.
    ``2026-05-31-core-authority-plan``
        W13.P30.S103 follow-up proving the deleted module no longer has live
        import survivors after CTIMEX cleanup.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# aeat.core._time deletion verification
# ---------------------------------------------------------------------------


def test_aeat_core_time_module_deleted() -> None:
    """aeat.core._time must not be importable — the module has been deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aeat.core._time")


def _imports_deleted_core_time(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == "aeat.core._time" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "aeat.core._time":
            return True
    return False


def test_no_source_imports_aeat_core_time(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No production source file may import from aeat.core._time."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _imports_deleted_core_time(tree):
            violations.append(repo_relative(path))
    if violations:
        raise AssertionError(
            f"{len(violations)} source file(s) still reference aeat.core._time:\n  " + "\n  ".join(violations),
        )
