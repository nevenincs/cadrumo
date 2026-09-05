"""No development test may block forever waiting on a child process.

The repository sets a 300-second per-test ceiling, and its own configuration
records what that ceiling cannot do: a test whose thread is blocked in
``subprocess.wait()`` is not interruptible by the thread timeout method, so the
worker exits uncleanly rather than reporting. With ``--max-worker-restart=0``
that stops the whole session, naming the test the worker died on -- which is
rarely the test that hung. One unbounded wait therefore costs a result set, not
a test.

``subprocess.run`` without ``timeout=`` blocks the same way. It is not gated
here because sixty of them are ``git`` invocations that return promptly, and a
gate nobody can make pass gets deleted rather than obeyed. ``Popen`` is the
narrow, unambiguous case: the caller has already taken responsibility for the
child's lifetime, so leaving the wait unbounded is a decision rather than a
default.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEV_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _popen_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return the local names bound to a ``subprocess.Popen`` result."""
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        callee = node.value.func
        if isinstance(callee, ast.Attribute) and callee.attr == "Popen":
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def _unbounded_waits(tree: ast.Module) -> list[tuple[int, str]]:
    """Return ``(lineno, name)`` for every unbounded wait on a Popen handle."""
    found: list[tuple[int, str]] = []
    for function in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        handles = _popen_names(function)
        if not handles:
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            if not (isinstance(callee, ast.Attribute) and callee.attr == "wait"):
                continue
            if not (isinstance(callee.value, ast.Name) and callee.value.id in handles):
                continue
            if not any(keyword.arg == "timeout" for keyword in node.keywords) and not node.args:
                found.append((node.lineno, callee.value.id))
    return found


def _test_modules() -> tuple[pathlib.Path, ...]:
    return tuple(sorted(_DEV_ROOT.rglob("test_*.py")))


def test_the_walk_reaches_a_real_population() -> None:
    """Anti-vacuity: an empty walk would pass this file over any tree at all."""
    modules = _test_modules()

    assert len(modules) > 100, f"only {len(modules)} development test modules found under {_DEV_ROOT}"


def test_no_development_test_waits_unbounded_on_a_child_process() -> None:
    """A bare ``wait()`` on a Popen handle costs the run, not the test."""
    offenders: list[str] = []
    unreadable: list[str] = []

    for module in _test_modules():
        try:
            tree = ast.parse(module.read_text(encoding="utf-8"))
        except (SyntaxError, OSError) as refusal:
            # A sibling agent mid-write is not this gate's finding, but a file
            # this screen could not read is not evidence of absence either.
            unreadable.append(f"{module}: {refusal}")
            continue
        offenders.extend(
            f"{module.relative_to(_DEV_ROOT.parent).as_posix()}:{line} {name}.wait() has no timeout"
            for line, name in _unbounded_waits(tree)
        )

    assert not offenders, (
        "an unbounded wait on a child process cannot be interrupted by the per-test "
        "ceiling; the worker dies and the session stops naming an unrelated test:\n"
        + "\n".join(offenders)
    )
    assert not unreadable, (
        "this screen could not read every test module, so its clean result covers less "
        "than it appears to:\n" + "\n".join(unreadable)
    )


def test_the_screen_detects_a_planted_unbounded_wait() -> None:
    """Teeth: the gate above is worthless if it cannot see the defect it forbids."""
    planted = ast.parse(
        "import subprocess\n"
        "\n"
        "def helper():\n"
        "    child = subprocess.Popen(['x'])\n"
        "    child.wait()\n"
    )
    bounded = ast.parse(
        "import subprocess\n"
        "\n"
        "def helper():\n"
        "    child = subprocess.Popen(['x'])\n"
        "    child.wait(timeout=60)\n"
    )

    assert _unbounded_waits(planted) == [(5, "child")]
    assert _unbounded_waits(bounded) == []
