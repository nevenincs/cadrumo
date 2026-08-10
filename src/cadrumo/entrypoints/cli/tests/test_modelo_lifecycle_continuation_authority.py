"""AST authority guard for modelo lifecycle continuation projection."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = Path(__file__).parents[1]


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, f"expected exactly one {name} function"
    return matches[0]


def _called_names(node: ast.AST) -> set[str]:
    return {call.func.id for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}


def _has_translation_default(node: ast.AST) -> bool:
    return any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "tr"
        and any(keyword.arg == "default" for keyword in call.keywords)
        for call in ast.walk(node)
    )


def test_lifecycle_cli_surfaces_delegate_action_selection_to_application_continuations() -> None:
    """List, status, and history cannot recreate a lifecycle action or fallback prose."""
    lifecycle_tree = ast.parse((_CLI_ROOT / "_modelo_work_lifecycle_cli.py").read_text(encoding="utf-8"))
    modelo_tree = ast.parse((_CLI_ROOT / "_modelo.py").read_text(encoding="utf-8"))

    for function in (_function(lifecycle_tree, "work_list"), _function(lifecycle_tree, "work_status")):
        calls = _called_names(function)
        assert "resolve_lifecycle_continuation_notice" in calls
        assert "resolve_notice_action" not in calls
        assert "ActionReference" not in calls
        assert "ResolvedActionArgument" not in calls
        assert not _has_translation_default(function)

    history = _function(modelo_tree, "work_history")
    history_calls = _called_names(history)
    assert "lifecycle_continuation_for_work_history" in history_calls
    assert "resolve_lifecycle_continuation_notice" in history_calls
    assert "resolve_notice_action" not in history_calls
    assert "ActionReference" not in history_calls
    assert "ResolvedActionArgument" not in history_calls
    assert not _has_translation_default(history)
