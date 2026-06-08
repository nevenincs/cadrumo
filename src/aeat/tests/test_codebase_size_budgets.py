"""Codebase-wide module and callable size ratchets."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEFAULT_MODULE_LINE_LIMIT = 1250
_DEFAULT_CALLABLE_LINE_LIMIT = 180


def _aeat_python_files() -> tuple[Path, ...]:
    root = PROJECT_ROOT / "src" / "aeat"
    return tuple(path for path in sorted(root.rglob("*.py")) if "__pycache__" not in path.parts)


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def test_tracked_python_modules_do_not_exceed_line_budgets() -> None:
    offenders: list[str] = []
    for path in _aeat_python_files():
        relative = _relative(path)
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > _DEFAULT_MODULE_LINE_LIMIT:
            offenders.append(f"{relative}: {line_count} lines > budget {_DEFAULT_MODULE_LINE_LIMIT}")

    assert offenders == [], "Python module size budget exceeded:\n  " + "\n  ".join(offenders)


def test_tracked_production_callables_do_not_exceed_line_budgets() -> None:
    offenders: list[str] = []
    for path in _aeat_python_files():
        relative = _relative(path)
        if "/tests/" in relative:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.end_lineno is None:
                continue
            line_count = node.end_lineno - node.lineno + 1
            if line_count > _DEFAULT_CALLABLE_LINE_LIMIT:
                offenders.append(f"{relative}:{node.name}: {line_count} lines > budget {_DEFAULT_CALLABLE_LINE_LIMIT}")

    assert offenders == [], "Python callable size budget exceeded:\n  " + "\n  ".join(offenders)
