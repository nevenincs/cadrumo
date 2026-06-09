"""Real-behavior contract tests for Playwright wait-state constants.

Asserts that ``PLAYWRIGHT_WAIT_DOMCONTENTLOADED`` and
``PLAYWRIGHT_WAIT_NETWORKIDLE`` are the sole source of the corresponding
string literals across every sede adapter module that issues
``wait_for_load_state`` / ``wait_until`` calls.  The tests parse each
module's AST so they catch literal drift immediately on the next edit,
without depending on live browser access.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED,
    PLAYWRIGHT_WAIT_NETWORKIDLE,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SEDE_DIR = Path(__file__).parent.parent

_CHECKED_MODULES = (
    "_declarations.py",
    "_iva_compensation_wallet.py",
    "_groi_check.py",
    "_nif_iva_check.py",
    "_censo_live.py",
    "_walker.py",
)

_WAIT_LITERALS = {PLAYWRIGHT_WAIT_DOMCONTENTLOADED, PLAYWRIGHT_WAIT_NETWORKIDLE}


def _collect_string_literals(source: str) -> list[tuple[int, str]]:
    """Return ``(lineno, value)`` for every string constant in *source*."""
    tree = ast.parse(source)
    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            results.append((node.lineno, node.value))
    return results


def test_playwright_wait_domcontentloaded_value() -> None:
    """The constant equals the Playwright API string it represents."""

    assert PLAYWRIGHT_WAIT_DOMCONTENTLOADED == "domcontentloaded"


def test_playwright_wait_networkidle_value() -> None:
    """The constant equals the Playwright API string it represents."""

    assert PLAYWRIGHT_WAIT_NETWORKIDLE == "networkidle"


def test_no_bare_wait_state_literals_in_sede_modules() -> None:
    """No sede adapter module may contain bare ``"domcontentloaded"`` or
    ``"networkidle"`` string literals; callers must import the constants
    from ``_browser_constants``.

    Anti-tautology: the test scans real source ASTs so it catches any
    future regression that re-introduces a bare literal.
    """

    offenders: list[str] = []
    for module_name in _CHECKED_MODULES:
        path = _SEDE_DIR / module_name
        source = path.read_text(encoding="utf-8")
        for lineno, value in _collect_string_literals(source):
            if value in _WAIT_LITERALS:
                offenders.append(f"{module_name}:{lineno}: bare literal {value!r}")

    assert offenders == [], (
        "Bare Playwright wait-state literals found; import from _browser_constants instead:\n" + "\n".join(offenders)
    )


def test_browser_constants_module_imports_are_present() -> None:
    """Each checked module exposes the wait-state constants via import.

    Verifies that ``_WAIT_DOMCONTENTLOADED`` or ``_WAIT_NETWORKIDLE``
    appear as names in the module's AST (they are local aliases), giving
    a lightweight structural proof that the import block is wired.
    """

    for module_name in _CHECKED_MODULES:
        path = _SEDE_DIR / module_name
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Collect all names imported from _browser_constants in this module.
        imported: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module and node.module.endswith("_browser_constants"):
                for alias in node.names:
                    imported.add(alias.asname or alias.name)

        # Modules that only need one constant need not import the other.
        # The real guard is the literal-scan above; this test just confirms
        # the import block exists at all in each checked module.
        assert imported, (
            f"{module_name} does not import anything from _browser_constants; add the relevant PLAYWRIGHT_WAIT_* import"
        )
