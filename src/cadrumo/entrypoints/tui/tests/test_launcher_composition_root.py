"""Installed TUI binds public contracts without a local operation service graph."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TUI_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
_COMPOSITION_ROOT: Final[str] = "installed_session.py"

#: Building any of these is composing the operation platform.
_COMPOSITION_SYMBOLS: Final[frozenset[str]] = frozenset(
    {"compose_operation_dependencies", "build_production_operation_registry", "compose_operation_services"}
)


def _tui_modules() -> tuple[Path, ...]:
    modules = tuple(sorted(path for path in _TUI_ROOT.rglob("*.py") if "tests" not in path.parts))
    if len(modules) < 20:
        pytest.fail(f"the TUI module sweep collapsed to {len(modules)} files")
    return modules


def test_only_installed_session_loads_operation_contracts() -> None:
    """Screens cannot create a second registry or local service graph."""
    offenders: dict[str, list[str]] = {}
    for path in _tui_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        reached = sorted(
            {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
                if alias.name in _COMPOSITION_SYMBOLS
            }
        )
        if reached and path.name != _COMPOSITION_ROOT:
            offenders[path.relative_to(_TUI_ROOT).as_posix()] = reached

    assert offenders == {}, f"the TUI composes operations outside installed session: {offenders}"


def test_installed_session_uses_public_contracts_and_runtime_client() -> None:
    """Guard the sweep against passing after removing installed admission."""
    installed = (_TUI_ROOT / _COMPOSITION_ROOT).read_text(encoding="utf-8")
    launcher = (_TUI_ROOT / "launcher.py").read_text(encoding="utf-8")

    assert "build_production_operation_registry" in installed
    assert "open_installed_runtime_client" in installed
    assert "run_installed_workbench_session" in launcher
