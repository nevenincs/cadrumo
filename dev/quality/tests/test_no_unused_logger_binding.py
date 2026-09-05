"""Gate: a module that binds a logger must log through it.

``get_logger`` is not inert. It installs the project logging defaults and
attaches a ``SecretScrubbingFilter`` to the named logger, so a binding reads
like a module that takes logging seriously. A binding nothing logs through
gives that impression while scrubbing nothing: a logger-level filter only sees
records emitted THROUGH that logger, and a child logger's records reach an
ancestor's HANDLERS without passing through the ancestor's FILTERS.

Eighteen such bindings had accumulated across the shipped tree, each appearing
exactly once -- its own assignment. They were removed together; this refuses
the next one, because the cost of the mistake is a module that looks
instrumented and emits nothing.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo"
#: Factories whose result is a logger. A binding of one of these is the subject.
_LOGGER_FACTORIES: Final[frozenset[str]] = frozenset({"get_logger", "getLogger"})


def _logger_bindings(tree: ast.Module) -> list[str]:
    """Return the names bound at module level to a logger factory call."""
    names: list[str] = []
    for node in tree.body:
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if called in _LOGGER_FACTORIES:
            names.append(target.id)
    return names


def _unused_bindings(text: str) -> list[str]:
    """Return logger bindings this source never references again."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    unused: list[str] = []
    for name in _logger_bindings(tree):
        uses = len(re.findall(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text))
        if uses <= 1:
            unused.append(name)
    return unused


def _shipped_modules() -> list[Path]:
    """Return the shipped, non-test modules the gate governs."""
    return [
        path
        for path in sorted(_PACKAGE_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts and "tests" not in path.parts
    ]


def test_the_scanned_population_is_not_empty() -> None:
    """An empty population would make the assertion below vacuous."""
    assert len(_shipped_modules()) > 500


def test_no_shipped_module_binds_a_logger_it_never_uses() -> None:
    """The direction the gate exists for."""
    offenders: list[str] = []
    for path in _shipped_modules():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for name in _unused_bindings(text):
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{name}")
    assert not offenders, (
        "these modules bind a logger and never log through it, so the binding "
        f"instruments nothing and scrubs nothing; remove it or log: {offenders}"
    )


def test_the_gate_catches_a_planted_unused_binding() -> None:
    """Detector teeth: the exact shape that had accumulated eighteen times."""
    planted = (
        "from ..core.logging import get_logger\n\n_log = get_logger(__name__)\n\n\ndef work() -> int:\n    return 1\n"
    )
    assert _unused_bindings(planted) == ["_log"]


def test_a_binding_that_is_logged_through_is_left_alone() -> None:
    """The normal case, so the gate is not merely always-red."""
    used = "\n".join(
        (
            "from ..core.logging import get_logger",
            "",
            "_log = get_logger(__name__)",
            "",
            "",
            "def work() -> None:",
            '    _log.info("done")',
            "",
        )
    )
    assert _unused_bindings(used) == []


def test_a_module_with_no_logger_at_all_is_not_an_offender() -> None:
    """A module that never asks for a logger makes no claim to instrument."""
    assert _unused_bindings("VALUE = 1\n") == []
