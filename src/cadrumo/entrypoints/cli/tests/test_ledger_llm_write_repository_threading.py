"""A command that opened a repository must not let the write open a second one.

The auto-split route resolved a transaction repository, produced a suggestion
from it, and then called the write without passing it — so the applier ran
``resolve_transaction_repository(repository=None)`` and constructed another one
for the bucket the command was already holding. Four of that module's five
write sites forwarded it and one did not, which is what marked it an omission
rather than a design.

The rule is deliberately narrow: it fires only where the calling function
actually BINDS a repository. A command that holds none — ``ledger rule apply``
takes only a bucket id, and the modelo verification verb holds a workflow-state
repository, not a catalogue one — is right to let the application resolve its
own, and that is the documented default of every one of those signatures. A
check that flagged those too would need an allowlist, and an allowlist of
"known-fine" sites decays into a baseline nobody rereads.

Scope is the whole CLI tree rather than the one module that was wrong, because
the defect is a wiring habit and nothing about it is specific to the LLM route.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SOURCE_ROOT = Path(__file__).resolve().parents[4]
_APPLICATION = _SOURCE_ROOT / "cadrumo" / "application"
_CLI = _SOURCE_ROOT / "cadrumo" / "entrypoints" / "cli"
_REPOSITORY_KEYWORD = "transaction_repository"


def _python_sources(root: Path) -> list[Path]:
    """Return the package's production modules, excluding test trees."""
    return [path for path in root.rglob("*.py") if "tests" not in path.parts]


def _functions_accepting_a_repository(root: Path) -> set[str]:
    """Names of application functions whose signature takes a catalogue repository."""
    accepting: set[str] = set()
    for path in _python_sources(root):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parameters = [argument.arg for argument in node.args.args + node.args.kwonlyargs]
                if _REPOSITORY_KEYWORD in parameters:
                    accepting.add(node.name)
    return accepting


def _repositories_held_by(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Repository-shaped names this function receives or binds."""
    held = {argument.arg for argument in function.args.args + function.args.kwonlyargs if "repository" in argument.arg}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            held.update(
                target.id for target in node.targets if isinstance(target, ast.Name) and "repository" in target.id
            )
    return held


def _sites_dropping_a_held_repository(source: str, *, accepting: set[str], origin: str = "") -> list[str]:
    """Return calls made from a repository-holding function that forward none."""
    dropped: list[str] = []
    for function in ast.walk(ast.parse(source)):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _repositories_held_by(function):
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in accepting:
                continue
            if not any(keyword.arg == _REPOSITORY_KEYWORD for keyword in node.keywords):
                dropped.append(f"{origin}{function.name} -> {node.func.id} (line {node.lineno})")
    return dropped


def test_no_cli_command_makes_the_write_reopen_a_repository_it_holds() -> None:
    """Tree-wide, because this is a wiring habit rather than one route's bug."""
    accepting = _functions_accepting_a_repository(_APPLICATION)
    dropped: list[str] = []
    for path in _python_sources(_CLI):
        dropped.extend(
            _sites_dropping_a_held_repository(
                path.read_text(encoding="utf-8"),
                accepting=accepting,
                origin=f"{path.name}:",
            ),
        )

    assert not dropped, f"CLI commands holding a repository whose write resolves another: {dropped}"


def test_the_check_rejects_the_shape_that_actually_shipped() -> None:
    """Proof the assertion above can fail, using the real defect.

    A structural check that never fires reads identically to one that cannot,
    so this pins it against the exact code the module carried.
    """
    shipped = (
        "def _emit_split(ctx, suggestion, *, bucket_id, apply, actor, transaction_repository):\n"
        "    applied = execute_reviewed_decision(suggestion, bucket_id=bucket_id, actor=actor)\n"
    )

    assert _sites_dropping_a_held_repository(shipped, accepting={"execute_reviewed_decision"})


def test_the_check_ignores_a_command_that_holds_no_repository() -> None:
    """``ledger rule apply``'s shape: a bucket id only, so there is nothing to drop."""
    holds_nothing = (
        "def rule_apply(ctx):\n    bucket_id = _rule_bucket_id()\n    return apply_rules(s, bucket_id=bucket_id)\n"
    )

    assert _sites_dropping_a_held_repository(holds_nothing, accepting={"apply_rules"}) == []


def test_the_check_accepts_a_write_that_forwards_what_it_holds() -> None:
    """And does not simply reject every call it can see."""
    forwarded = (
        "def _emit_split(ctx, *, transaction_repository):\n"
        "    return execute_reviewed_decision(s, transaction_repository=transaction_repository)\n"
    )

    assert _sites_dropping_a_held_repository(forwarded, accepting={"execute_reviewed_decision"}) == []
