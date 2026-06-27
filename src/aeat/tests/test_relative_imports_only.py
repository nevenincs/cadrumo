"""Architecture gate: intra-package imports under ``src/aeat`` are relative.

Code inside the ``aeat`` package must reach its siblings through relative
imports (``from . import x``, ``from ..core import y``), never by re-importing
the package through its absolute path (``import aeat.core`` or
``from aeat.core import y``). Absolute self-imports make a module's position in
the package implicit, defeat straightforward relocation, and blur the layering
the hexagonal structure depends on.

The gate fails hard with a precise ``path:line`` enumeration of every absolute
self-import so the offending lines are trivial to find and fix. It is computed
from the AST on every run, so it cannot go stale.
"""

from __future__ import annotations

import ast

import pytest

from ._inventory import ast_for_path, package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _absolute_self_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, statement)`` for every absolute ``aeat`` import."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "aeat" or alias.name.startswith("aeat."):
                    hits.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and (node.module == "aeat" or node.module.startswith("aeat.")):
                hits.append((node.lineno, f"from {node.module} import ..."))
    return hits


def test_no_absolute_self_imports_in_aeat_package() -> None:
    """No source file under ``src/aeat`` may import the ``aeat`` package absolutely."""
    violations: list[str] = []
    for path in package_python_files():
        tree = ast_for_path(path)
        if tree is None:
            continue
        rel = repo_relative(path).removeprefix("src/")
        for lineno, statement in _absolute_self_imports(tree):
            violations.append(f"  {rel}:{lineno}  {statement}")

    if violations:
        pytest.fail(
            f"{len(violations)} absolute intra-aeat imports found; use relative imports "
            "(from . / .. / ...):\n" + "\n".join(violations),
        )
