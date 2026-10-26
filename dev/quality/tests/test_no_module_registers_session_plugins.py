"""No module below the repository's own trees registers pytest plugins for the session.

A module-level ``pytest_plugins`` makes pytest register the named fixture module
for the whole session, so its autouse fixtures reach every test collected after
it, in any directory. That is how a secure-SQL fixture's English output pin once
leaked from the evaluation suites into product suites asserting the Spanish
default. Fixtures come into a module by importing and binding them instead.
"""

from __future__ import annotations

import ast

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _session_plugin_declarations(source: str) -> list[int]:
    """Return the lines of every module-level ``pytest_plugins`` binding."""
    lines: list[int] = []
    for node in ast.parse(source).body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign | ast.AugAssign):
            targets = [node.target]
        if any(isinstance(target, ast.Name) and target.id == "pytest_plugins" for target in targets):
            lines.append(node.lineno)
    return lines


def test_no_module_registers_a_session_wide_plugin() -> None:
    """Every Python module under ``dev`` and ``src`` is free of ``pytest_plugins``."""
    modules = [path for path in repository_files(REPO_ROOT, under=("dev", "src")) if path.endswith(".py")]
    assert modules, "no modules were read; the gate below would be vacuous"
    offenders = {
        path: lines
        for path in modules
        if (lines := _session_plugin_declarations((REPO_ROOT / path).read_text(encoding=UTF_8)))
    }
    assert not offenders, f"module-level pytest_plugins registers fixtures for the whole session: {offenders}"


def test_the_plugin_scan_detects_a_declaration() -> None:
    """The scan above can fail: each binding form of ``pytest_plugins`` is reported."""
    source = (
        "import pytest\n"
        'pytest_plugins = ("some.fixture.module",)\n'
        'pytest_plugins: tuple[str, ...] = ("other.fixture.module",)\n'
        'pytest_plugins += ("third.fixture.module",)\n'
        "def helper():\n"
        '    pytest_plugins = ("function.local",)\n'
    )
    assert _session_plugin_declarations(source) == [2, 3, 4]
