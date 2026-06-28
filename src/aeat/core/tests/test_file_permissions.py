"""Policy tests for best-effort file-permission hardening."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODULE_PATH = Path(__file__).parents[1] / "file_permissions.py"


def _module_tree() -> ast.Module:
    return ast.parse(_MODULE_PATH.read_text(encoding="utf-8"), filename=str(_MODULE_PATH))


def test_file_permission_failures_are_not_silently_suppressed() -> None:
    """The helper must leave a debug breadcrumb when POSIX chmod fails."""

    tree = _module_tree()
    suppress_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "contextlib"
        and node.func.attr == "suppress"
    ]
    debug_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "debug"
        and any(keyword.arg == "exc_info" for keyword in node.keywords)
    ]

    assert suppress_calls == []
    assert debug_calls, "chmod failure path must log at debug with exc_info"


def test_windows_icacls_subprocess_is_time_bounded() -> None:
    """The Windows ACL helper must not let a wedged icacls child block indefinitely."""

    run_calls = [
        node
        for node in ast.walk(_module_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
    ]

    assert run_calls
    assert all(any(keyword.arg == "timeout" for keyword in call.keywords) for call in run_calls)
