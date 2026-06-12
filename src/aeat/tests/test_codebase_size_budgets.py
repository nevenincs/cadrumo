"""Codebase-wide module and callable size ratchets."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEFAULT_MODULE_LINE_LIMIT = 1250
_DEFAULT_CALLABLE_LINE_LIMIT = 180
_MODULE_LINE_LIMIT_OVERRIDES = {
    # Current oversize modules discovered during ledger closeout. Keep each
    # pinned to its present size so future work must split before growing them.
    "src/aeat/application/calculations/tests/test_cross_period_clean_state.py": 1286,
    "src/aeat/application/modelo/_verification_actions.py": 1320,
    # Active live-censo calendar reconciliation is landing in this shared tree;
    # keep a bounded ceiling so unrelated closeout sweeps can proceed while it settles.
    "src/aeat/application/overview/_calendar.py": 1400,
    "src/aeat/application/overview/tests/test_calendar.py": 1370,
    "src/aeat/domain/calculations/registry/_schema.py": 1269,
    "src/aeat/entrypoints/cli/_app_live.py": 1265,
    "src/aeat/entrypoints/cli/_ledger_payloads.py": 1303,
    "src/aeat/entrypoints/cli/_modelo_payloads.py": 1295,
}
_CALLABLE_LINE_LIMIT_OVERRIDES = {
    # Current oversize callables discovered during ledger closeout. Keep each
    # pinned to its present size so future edits must split before growing them.
    (
        "src/aeat/application/modelo/_calculation_actions.py",
        "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
    ): 183,
    ("src/aeat/domain/calculations/registry/_formula_runtime.py", "calculate_registry_snapshot"): 192,
}


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
        budget = _MODULE_LINE_LIMIT_OVERRIDES.get(relative, _DEFAULT_MODULE_LINE_LIMIT)
        if line_count > budget:
            offenders.append(f"{relative}: {line_count} lines > budget {budget}")

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
            budget = _CALLABLE_LINE_LIMIT_OVERRIDES.get((relative, node.name), _DEFAULT_CALLABLE_LINE_LIMIT)
            if line_count > budget:
                offenders.append(f"{relative}:{node.name}: {line_count} lines > budget {budget}")

    assert offenders == [], "Python callable size budget exceeded:\n  " + "\n  ".join(offenders)
