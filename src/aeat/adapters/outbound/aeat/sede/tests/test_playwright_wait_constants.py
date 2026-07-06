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

_WAIT_LITERALS = {PLAYWRIGHT_WAIT_DOMCONTENTLOADED, PLAYWRIGHT_WAIT_NETWORKIDLE}


def _production_modules() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(_SEDE_DIR.glob("*.py"))
        if path.name not in {"__init__.py", "_browser_constants.py"}
    )


def _wait_state_argument_literals(source: str) -> tuple[tuple[int, str], ...]:
    """Return string literals passed to Playwright wait-state arguments."""
    tree = ast.parse(source)
    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if _is_wait_for_load_state_call(node):
            for argument in node.args[:1]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    results.append((argument.lineno, argument.value))

        for keyword in node.keywords:
            if keyword.arg != "wait_until":
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                results.append((keyword.value.lineno, keyword.value.value))

    return tuple(results)


def _is_wait_for_load_state_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "wait_for_load_state"
    return isinstance(func, ast.Name) and func.id == "wait_for_load_state"


@pytest.mark.parametrize(
    ("constant", "expected"),
    (
        (PLAYWRIGHT_WAIT_DOMCONTENTLOADED, "domcontentloaded"),
        (PLAYWRIGHT_WAIT_NETWORKIDLE, "networkidle"),
    ),
)
def test_playwright_wait_constant_values(constant: str, expected: str) -> None:
    """The constants equal the Playwright API strings they represent."""
    assert constant == expected


def test_no_bare_wait_state_literals_in_sede_modules() -> None:
    """No sede adapter wait-state call may pass bare Playwright state strings.

    The test scans only ``wait_for_load_state(...)`` and ``wait_until=...``
    call arguments so comments, docstrings, log messages, and stage labels
    cannot create false positives.
    """

    offenders: list[str] = []
    for path in _production_modules():
        source = path.read_text(encoding="utf-8")
        for lineno, value in _wait_state_argument_literals(source):
            if value in _WAIT_LITERALS:
                offenders.append(f"{path.name}:{lineno}: bare wait-state literal {value!r}")

    assert offenders == [], (
        "Bare Playwright wait-state literals found; import from _browser_constants instead:\n" + "\n".join(offenders)
    )
