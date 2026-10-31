"""Shared absolute-import name reader for the packaging import gates."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path


def top_level_imports(path: Path) -> Iterator[str]:
    """Yield the top-level module name of every absolute import in ``path``.

    Relative imports are skipped: they address this project, which is not a
    declarable dependency of itself.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module is not None and node.module):
            yield node.module.split(".")[0]
