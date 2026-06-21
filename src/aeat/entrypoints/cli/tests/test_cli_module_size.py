"""Static size guards for CLI modules and command functions."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
_DEFAULT_MODULE_LINE_LIMIT = 1250
# Per-module ceilings for SPLIT-CANDIDATE CLI modules grown by recovered features.
_MODULE_LINE_LIMIT_OVERRIDES = {
    "_modelo.py": 1300,  # SPLIT-CANDIDATE
    "_modelo_payloads.py": 1300,  # SPLIT-CANDIDATE
}
_DEFAULT_COMMAND_LINE_LIMIT = 180
# Per-command ceilings for command bodies pinned above the default, mirroring the
# sibling _CALLABLE_LINE_LIMIT_OVERRIDES in test_codebase_size_budgets.py. Keyed by
# (CLI-relative module path, function name). SPLIT-CANDIDATE: owners should extract
# helpers on their next pass rather than growing these further.
_COMMAND_LINE_LIMIT_OVERRIDES = {
    # SPLIT-CANDIDATE: a wide Typer signature (manual + LLM + saturate + evidence +
    # auto-split routes). The LLM-routing bodies live in `_ledger_llm_cli.py`;
    # what remains here is the option surface and the route dispatch.
    ("_ledger.py", "ledger_classify"): 220,
}


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
        budget = _MODULE_LINE_LIMIT_OVERRIDES.get(relative, _DEFAULT_MODULE_LINE_LIMIT)
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
            assert node.end_lineno is not None
            length = node.end_lineno - node.lineno + 1
            budget = _COMMAND_LINE_LIMIT_OVERRIDES.get((relative, node.name), _DEFAULT_COMMAND_LINE_LIMIT)
            if length > budget:
                offenders.append(f"{relative}:{node.name}: {length} lines > budget {budget}")

    assert offenders == [], "CLI command size budget exceeded:\n  " + "\n  ".join(offenders)
