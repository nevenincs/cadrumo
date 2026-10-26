"""Direct development-test Popen handles retain a visible completion owner.

Ordinary test completion may wait without an elapsed-time ceiling. A timeout
argument does not establish child ownership, and its absence is not a defect.
This structural screen instead requires a direct Popen launch to have a visible
wait/communicate call, a Popen context manager, or an explicit return that
transfers its handle to a caller. An unnamed kill discards its reaping owner.

Only test_*.py modules under dev and direct Popen spellings are inspected. This
is not control-flow proof that every exception closes pipes or reaps children;
real owning cleanup/cancellation tests retain those obligations. Audited/async
process runners, returned-handle callers, src tests and native custody are not
certified by this screen. Product deadlines and deliberate expiry proofs remain
governed by their actual owners.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEV_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _is_popen_call(node: ast.AST | None) -> bool:
    """Recognize direct attribute and bare imported Popen constructors."""
    if not isinstance(node, ast.Call):
        return False
    callee = node.func
    if isinstance(callee, ast.Attribute):
        return callee.attr == "Popen"
    return isinstance(callee, ast.Name) and callee.id == "Popen"


def _local_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[ast.AST]:
    """Keep nested function/class scopes from claiming an outer handle."""
    pending: list[ast.AST] = list(reversed(function.body))
    while pending:
        node = pending.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        yield node
        pending.extend(reversed(list(ast.iter_child_nodes(node))))


def _bound_names(parent: ast.AST | None) -> set[str]:
    if isinstance(parent, ast.Assign):
        return {target.id for target in parent.targets if isinstance(target, ast.Name)}
    if isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name):
        return {parent.target.id}
    return set()


def _unowned_popen_handles(tree: ast.Module) -> list[tuple[int, str]]:
    """Find direct function-local launches with no visible completion owner.

    A visible owner is structural evidence only: conditional or exceptional
    reachability, aliases and interprocedural lifetime are not inferred here.
    """
    found: list[tuple[int, str]] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        nodes = tuple(_local_nodes(function))
        parents = {child: node for node in nodes for child in ast.iter_child_nodes(node)}
        for node in nodes:
            if not isinstance(node, ast.Call) or not _is_popen_call(node):
                continue
            parent = parents.get(node)
            if isinstance(parent, ast.withitem | ast.Return):
                # Popen.__exit__ closes its streams and waits; returning the
                # handle is an explicit transfer, not a local completion claim.
                continue
            if (
                isinstance(parent, ast.Attribute)
                and parent.attr in {"wait", "communicate"}
                and isinstance(parents.get(parent), ast.Call)
            ):
                continue
            names = _bound_names(parent)
            completed = any(
                isinstance(candidate, ast.Call)
                and candidate.lineno >= node.lineno
                and isinstance(candidate.func, ast.Attribute)
                and candidate.func.attr in {"wait", "communicate"}
                and isinstance(candidate.func.value, ast.Name)
                and candidate.func.value.id in names
                for candidate in nodes
            )
            transferred = any(
                isinstance(candidate, ast.Return)
                and candidate.lineno >= node.lineno
                and isinstance(candidate.value, ast.Name)
                and candidate.value.id in names
                for candidate in nodes
            )
            if not completed and not transferred:
                found.append((node.lineno, ", ".join(sorted(names)) or "Popen(...)"))
    return sorted(found)


def _test_modules() -> tuple[pathlib.Path, ...]:
    return tuple(sorted(_DEV_ROOT.rglob("test_*.py")))


def test_the_walk_reaches_a_real_population() -> None:
    """Anti-vacuity: an empty walk cannot establish a clean ownership result."""
    modules = _test_modules()
    assert len(modules) > 100, f"only {len(modules)} development test modules found under {_DEV_ROOT}"


def test_development_popen_handles_have_a_visible_completion_owner() -> None:
    """An elapsed limit cannot substitute for child completion ownership."""
    offenders: list[str] = []
    unreadable: list[str] = []
    for module in _test_modules():
        try:
            tree = ast.parse(module.read_text(encoding="utf-8"))
        except (SyntaxError, OSError) as refusal:
            unreadable.append(f"{module}: {refusal}")
            continue
        offenders.extend(
            f"{module.relative_to(_DEV_ROOT.parent).as_posix()}:{line} {name} has no visible completion owner"
            for line, name in _unowned_popen_handles(tree)
        )
    assert not offenders, (
        "direct child handles need a wait/communicate, context manager or explicit transfer:\n" + "\n".join(offenders)
    )
    assert not unreadable, "the ownership screen could not read every test module:\n" + "\n".join(unreadable)


def _planted(body: str) -> ast.Module:
    """Parse grammar fixtures without executing any child process."""
    return ast.parse("import subprocess\n\ndef helper():\n    " + body + "\n")


_BOUND_FORMS = {
    "plain assignment": "child = subprocess.Popen(['x'])\n    child",
    "bare imported Popen": "child = Popen(['x'])\n    child",
    "annotated assignment": "child: object = subprocess.Popen(['x'])\n    child",
    "context manager": "with subprocess.Popen(['x']) as child:\n        child",
    "unnamed handle": "subprocess.Popen(['x'])",
}


@pytest.mark.parametrize("label", sorted(_BOUND_FORMS))
@pytest.mark.parametrize("completion", ["wait", "communicate"])
@pytest.mark.parametrize("arguments", ["", "timeout=None", "timeout=60"])
def test_completion_ownership_is_independent_of_elapsed_limits(label: str, completion: str, arguments: str) -> None:
    assert _unowned_popen_handles(_planted(_BOUND_FORMS[label] + f".{completion}({arguments})")) == []


@pytest.mark.parametrize("label", sorted(set(_BOUND_FORMS) - {"context manager"}))
def test_the_screen_detects_a_child_killed_without_a_reaping_owner(label: str) -> None:
    assert _unowned_popen_handles(_planted(_BOUND_FORMS[label] + ".kill()"))


def test_a_popen_context_manager_owns_reaping_after_kill() -> None:
    assert _unowned_popen_handles(_planted(_BOUND_FORMS["context manager"] + ".kill()")) == []


@pytest.mark.parametrize(
    "body", ["return subprocess.Popen(['x'])", "child = subprocess.Popen(['x'])\n    return child"]
)
def test_returned_handles_explicitly_transfer_completion_ownership(body: str) -> None:
    assert _unowned_popen_handles(_planted(body)) == []


def test_a_nested_function_cannot_claim_completion_of_an_outer_handle() -> None:
    tree = _planted("child = subprocess.Popen(['x'])\n    def never_called():\n        child.wait()")
    assert _unowned_popen_handles(tree) == [(4, "child")]


def test_a_standalone_child_launch_has_no_completion_owner() -> None:
    assert _unowned_popen_handles(_planted("subprocess.Popen(['x'])")) == [(4, "Popen(...)")]
