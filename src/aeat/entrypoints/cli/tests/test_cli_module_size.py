"""Static size guards for CLI modules and command functions."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
_DEFAULT_MODULE_LINE_LIMIT = 1250
_DEFAULT_COMMAND_LINE_LIMIT = 180


def _production_cli_modules() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(_CLI_ROOT.rglob("*.py"))
        if not path.name.startswith("test_") and "/test_" not in path.relative_to(_CLI_ROOT).as_posix()
    )


def test_production_cli_modules_do_not_grow_into_new_monoliths() -> None:
    """CLI modules have the same hard size limit as the rest of the codebase."""
    offenders: list[str] = []
    for path in _production_cli_modules():
        relative = path.relative_to(_CLI_ROOT).as_posix()
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > _DEFAULT_MODULE_LINE_LIMIT:
            offenders.append(f"{relative}: {line_count} lines > budget {_DEFAULT_MODULE_LINE_LIMIT}")

    assert offenders == [], "CLI module size budget exceeded:\n  " + "\n  ".join(offenders)


def test_cli_command_functions_do_not_grow_past_complexity_budget() -> None:
    """Command and command-registrar bodies have bounded line budgets."""
    offenders: list[str] = []
    for path in _production_cli_modules():
        relative = path.relative_to(_CLI_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = tuple(ast.unparse(decorator) for decorator in node.decorator_list)
            is_command_body = any(".command" in decorator for decorator in decorators)
            is_registrar = node.name.startswith("register_") and relative.startswith("_modelo")
            if not (is_command_body or is_registrar):
                continue
            assert node.end_lineno is not None
            length = node.end_lineno - node.lineno + 1
            if length > _DEFAULT_COMMAND_LINE_LIMIT:
                offenders.append(f"{relative}:{node.name}: {length} lines > budget {_DEFAULT_COMMAND_LINE_LIMIT}")

    assert offenders == [], "CLI command size budget exceeded:\n  " + "\n  ".join(offenders)
