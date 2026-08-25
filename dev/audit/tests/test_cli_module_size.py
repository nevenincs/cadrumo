"""Static size guards for CLI modules and command functions.

See Also:
    :func:`~cadrumo.tests._inventory.package_python_files`
        Shared source inventory used to enumerate production CLI modules
        without bespoke filesystem walking.
    :mod:`~dev.audit.tests.test_codebase_size_budgets`
        Codebase-wide sibling ratchet. Both gates now read the SAME generated
        limit table, the committed size-budget baseline, so this CLI-scoped
        view cannot drift away from it.

CLI modules must stay bounded so they decompose without breaking public
hexagonal facades. The limits are projected from the shared generated baseline
rather than restated here: a second hand-maintained copy of the same numbers is
a second surface that decays on its own, which is what happened to the pins this
projection replaces.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.tests import (
    CALLABLE_POLICY,
    MODULE_POLICY,
    REPO_ROOT,
    ast_for_path,
    package_python_files,
)

from ..size_budget import load_size_budget_baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
_CLI_PREFIX = "src/cadrumo/entrypoints/cli/"
_DEFAULT_MODULE_LINE_LIMIT = MODULE_POLICY.default_limit
_DEFAULT_COMMAND_LINE_LIMIT = CALLABLE_POLICY.default_limit


def _cli_module_limits() -> dict[str, int]:
    """Return CLI-relative module limits projected from the shared baseline.

    This gate used to keep its own hand-maintained pin dict mirroring the
    codebase-wide one. Two hand-maintained copies of the same numbers is two
    surfaces that decay independently, and both had: entries here claimed in
    prose to sit at exactly the present size with no headroom while the modules
    had since been split beneath them. The limits are now projected from the one
    generated table, so this gate cannot disagree with its sibling and cannot go
    stale on its own.
    """
    return {
        key.removeprefix(_CLI_PREFIX): limit
        for key, limit in load_size_budget_baseline().modules.items()
        if key.startswith(_CLI_PREFIX)
    }


def _cli_command_limits() -> dict[tuple[str, str], int]:
    """Return CLI-relative ``(module, function)`` limits from the shared baseline."""
    limits: dict[tuple[str, str], int] = {}
    for key, limit in load_size_budget_baseline().callables.items():
        if not key.startswith(_CLI_PREFIX):
            continue
        relative, _, name = key.partition("::")
        limits[(relative.removeprefix(_CLI_PREFIX), name)] = limit
    return limits


def _production_cli_modules() -> tuple[Path, ...]:
    return tuple(
        path
        for path in package_python_files()
        if path.is_relative_to(_CLI_ROOT)
        if not path.name.startswith("test_") and "/test_" not in path.relative_to(_CLI_ROOT).as_posix()
    )


def test_production_cli_modules_do_not_grow_into_new_monoliths() -> None:
    """CLI modules have the same hard size limit as the rest of the codebase."""
    modules = _production_cli_modules()
    assert modules, "the CLI module walk found no modules; the scan is broken, not the tree clean"

    limits = _cli_module_limits()
    offenders: list[str] = []
    for path in modules:
        relative = path.relative_to(_CLI_ROOT).as_posix()
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        budget = limits.get(relative, _DEFAULT_MODULE_LINE_LIMIT)
        if line_count > budget:
            offenders.append(f"{relative}: {line_count} lines > budget {budget}")

    assert offenders == [], "CLI module size budget exceeded:\n  " + "\n  ".join(offenders)


def test_cli_command_functions_do_not_grow_past_complexity_budget() -> None:
    """Command and command-registrar bodies have bounded line budgets."""
    modules = _production_cli_modules()
    assert modules, "the CLI module walk found no modules; the scan is broken, not the tree clean"

    limits = _cli_command_limits()
    offenders: list[str] = []
    inspected = 0
    for path in modules:
        relative = path.relative_to(_CLI_ROOT).as_posix()
        tree = ast_for_path(path)
        if tree is None:
            raise AssertionError(f"unable to parse {relative}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = tuple(ast.unparse(decorator) for decorator in node.decorator_list)
            is_command_body = any(".command" in decorator for decorator in decorators)
            is_registrar = node.name.startswith("register_") and relative.startswith("_modelo")
            if not (is_command_body or is_registrar):
                continue
            assert node.end_lineno is not None
            inspected += 1
            length = node.end_lineno - node.lineno + 1
            budget = limits.get((relative, node.name), _DEFAULT_COMMAND_LINE_LIMIT)
            if length > budget:
                offenders.append(f"{relative}:{node.name}: {length} lines > budget {budget}")

    assert inspected, "no CLI command bodies were inspected; the decorator filter matches nothing"
    assert offenders == [], "CLI command size budget exceeded:\n  " + "\n  ".join(offenders)
