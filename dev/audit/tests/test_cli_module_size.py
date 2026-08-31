"""Static size guard for CLI modules.

See Also:
    :func:`~cadrumo.tests.inventory.package_python_files`
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

from pathlib import Path

import pytest

from cadrumo.tests import (
    MODULE_POLICY,
    REPO_ROOT,
    package_python_files,
)

from ..size_budget import load_size_budget_baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
_CLI_PREFIX = "src/cadrumo/entrypoints/cli/"
_DEFAULT_MODULE_LINE_LIMIT = MODULE_POLICY.default_limit


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
