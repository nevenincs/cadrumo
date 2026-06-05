"""Static size guards for CLI modules and command functions."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
_DEFAULT_MODULE_LINE_LIMIT = 800
_DEFAULT_COMMAND_LINE_LIMIT = 180

_LEGACY_MODULE_LINE_BUDGETS = {
    "_app_live.py": 1882,
    "_config/__init__.py": 2890,
    "_config/_google.py": 1399,
    "_ledger.py": 3314,
    "_ledger_payloads.py": 918,
    "_modelo.py": 1648,
    "_modelo_payloads.py": 1240,
}

_LEGACY_COMMAND_LINE_BUDGETS = {
    ("_ledger.py", "ledger_classify"): 194,
    ("_modelo.py", "work_create"): 196,
    ("_modelo_iva_wallet_cli.py", "register_iva_wallet_commands"): 199,
    ("_modelo_projection_cli.py", "register_projection_commands"): 243,
}


def _production_cli_modules() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(_CLI_ROOT.rglob("*.py"))
        if not path.name.startswith("test_") and "/test_" not in path.relative_to(_CLI_ROOT).as_posix()
    )


def test_production_cli_modules_do_not_grow_into_new_monoliths() -> None:
    """Ordinary CLI modules have a hard size limit; legacy monoliths are frozen."""
    offenders: list[str] = []
    for path in _production_cli_modules():
        relative = path.relative_to(_CLI_ROOT).as_posix()
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        budget = _LEGACY_MODULE_LINE_BUDGETS.get(relative, _DEFAULT_MODULE_LINE_LIMIT)
        if line_count > budget:
            offenders.append(f"{relative}: {line_count} lines > budget {budget}")

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
            length = node.end_lineno - node.lineno + 1
            budget = _LEGACY_COMMAND_LINE_BUDGETS.get(
                (relative, node.name),
                _DEFAULT_COMMAND_LINE_LIMIT,
            )
            if length > budget:
                offenders.append(f"{relative}:{node.name}: {length} lines > budget {budget}")

    assert offenders == [], "CLI command size budget exceeded:\n  " + "\n  ".join(offenders)
