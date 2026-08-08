"""Every durable catalogue write must go through the atomic helper.

A plain ``path.write_text`` or ``open(path, "w")`` truncates the target before
it writes.  A crash, an ``ENOSPC``, or a concurrent reader landing inside that
window leaves a truncated catalogue that fails to parse, which takes down every
test that resolves a locale key.  The four shipped catalogues are ~3 MB each, so
the truncation window is wide enough to hit in practice.

This gate is structural rather than behavioural because the failure it guards
is a crash mid-write, which cannot be provoked from inside the process without
a test double.  It reds the moment a non-atomic durable write is reintroduced
into the manager, which is the regression that actually happens.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE = Path(__file__).resolve().parents[1]
_CATALOGUE_WRITERS = (_PACKAGE / "manager.py", _PACKAGE / "_write_guard.py")
"""Every module that persists catalogue content. The guard performs the write;
the manager builds it. A plain write reintroduced in either one is the defect."""

_TRUNCATING_WRITE_ATTRIBUTES = frozenset({"write_text", "write_bytes"})
_WRITE_MODES = frozenset({"w", "wb", "wt", "w+", "w+b", "wb+"})
_SANCTIONED_WRITER_RECEIVER = "guard"
"""The catalogue write guard's own writer, which performs the atomic replace.

``guard.write_text(...)`` shares a method name with ``Path.write_text`` but is
the sanctioned path, so the receiver -- not the method name -- decides.
"""


def _enclosing_functions(tree: ast.Module) -> dict[ast.AST, str]:
    """Map every node in ``tree`` to the name of the function that encloses it."""
    owners: dict[ast.AST, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for child in ast.walk(node):
            owners.setdefault(child, node.name)
    return owners


def _truncating_writes(tree: ast.Module) -> list[str]:
    """Return ``function:line`` for each truncating durable write in ``tree``."""
    owners = _enclosing_functions(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        is_truncating_method = (
            isinstance(target, ast.Attribute)
            and target.attr in _TRUNCATING_WRITE_ATTRIBUTES
            and not (isinstance(target.value, ast.Name) and target.value.id == _SANCTIONED_WRITER_RECEIVER)
        )
        is_truncating_open = (
            isinstance(target, ast.Name)
            and target.id == "open"
            and any(isinstance(arg, ast.Constant) and arg.value in _WRITE_MODES for arg in node.args[1:])
        )
        if is_truncating_method or is_truncating_open:
            found.append(f"{owners.get(node, '<module>')}:{node.lineno}")
    return sorted(found)


@pytest.mark.parametrize("module", _CATALOGUE_WRITERS, ids=lambda path: path.name)
def test_catalogue_writers_have_no_truncating_durable_write(module: Path) -> None:
    """Every catalogue writer must persist atomically."""
    tree = ast.parse(module.read_text(encoding="utf-8"))

    assert _truncating_writes(tree) == [], (
        f"dev/locales/{module.name} performs a truncating durable write. A locale catalogue "
        "is ~3 MB; truncate-then-write leaves it unparseable if the write does not "
        "complete. Route the write through cadrumo.core.atomic_write.atomic_write_text."
    )


def test_the_gate_detects_a_truncating_write() -> None:
    """Anti-vacuity: the detector must fire on the shape it claims to catch.

    Without this the gate would pass just as happily against a manager that
    contained no write calls at all, or against a detector whose matcher had
    silently stopped matching.
    """
    method_form = ast.parse("def save(path, text):\n    path.write_text(text)\n")
    open_form = ast.parse("def save(path, text):\n    with open(path, 'w') as fh:\n        fh.write(text)\n")
    atomic_form = ast.parse("def save(path, text):\n    atomic_write_text(path, text)\n")
    guarded_form = ast.parse("def save(guard, path, text):\n    guard.write_text(path, text)\n")

    assert _truncating_writes(method_form) == ["save:2"]
    assert _truncating_writes(open_form) == ["save:2"]
    assert _truncating_writes(atomic_form) == []
    assert _truncating_writes(guarded_form) == []
