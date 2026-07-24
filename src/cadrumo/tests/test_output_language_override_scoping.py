"""Output-language overrides in production are context-scoped or allowlisted.

A localized ``Notice`` on the success envelope resolves its message when
the envelope renders, so the ``--output-language`` override must still be
active at that point. The CLI guarantees this by entering the override
through ``ctx.with_resource(override_settings(...))`` — Typer tears the
context down only after the command callback (and its emission) returns.

An override entered through any *narrower* scope (a local ``with`` block
or ``ExitStack``) can unwind before the envelope renders, and every notice
emitted afterwards silently falls back to the launch locale. The wizard's
answer-derived language activation is the one sanctioned exception: the
operator picks the language on the flow's first page, so a context-scoped
flag cannot carry it, and the wizard pre-renders its operator-facing text
inside its own override instead.

This gate scans production sources for ``override_settings`` calls that
pass ``cadrumo_output_language`` and refuses any site that is neither
wrapped in ``ctx.with_resource(...)`` nor named in the sanctioned wizard
allowlist — so the post-unwind rendering class cannot silently return.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

#: The wizard's answer-derived language activation: the only production
#: sites permitted to enter the override outside ``ctx.with_resource``.
#: Each entry is (module path relative to the package root, outermost
#: enclosing function). Extending this set requires the same discipline
#: the wizard applies: every operator-facing string the command emits
#: after the override unwinds must be pre-rendered inside it.
_SANCTIONED_LOCAL_OVERRIDES = frozenset(
    {
        ("application/wizard/_commands.py", "_enter_requested_output_language"),
        ("application/wizard/_commands.py", "_build_mid_walk_language_activation"),
    },
)


def _production_modules() -> list[Path]:
    return [path for path in _PACKAGE_ROOT.rglob("*.py") if "tests" not in path.relative_to(_PACKAGE_ROOT).parts]


def _is_output_language_override(node: ast.Call) -> bool:
    callee = node.func
    name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", "")
    if name != "override_settings":
        return False
    return any(keyword.arg == "cadrumo_output_language" for keyword in node.keywords)


def _collect_sites(tree: ast.Module) -> tuple[list[ast.Call], set[int]]:
    """Return every output-language override call and the ctx-scoped subset (by id)."""
    overrides: list[ast.Call] = []
    ctx_scoped: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_output_language_override(node):
            overrides.append(node)
        callee = node.func
        if isinstance(callee, ast.Attribute) and callee.attr == "with_resource":
            for argument in node.args:
                if isinstance(argument, ast.Call) and _is_output_language_override(argument):
                    ctx_scoped.add(id(argument))
    return overrides, ctx_scoped


def _outermost_function(tree: ast.Module, target: ast.Call) -> str:
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            for descendant in ast.walk(statement):
                if descendant is target:
                    return statement.name
    return "<module>"


def test_every_production_override_is_ctx_scoped_or_sanctioned() -> None:
    seen_sanctioned: set[tuple[str, str]] = set()
    violations: list[str] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        overrides, ctx_scoped = _collect_sites(tree)
        for call in overrides:
            if id(call) in ctx_scoped:
                continue
            relative = path.relative_to(_PACKAGE_ROOT).as_posix()
            site = (relative, _outermost_function(tree, call))
            if site in _SANCTIONED_LOCAL_OVERRIDES:
                seen_sanctioned.add(site)
                continue
            violations.append(f"{relative}:{call.lineno} in {site[1]}")
    assert violations == [], (
        "Non-ctx-scoped output-language override outside the sanctioned wizard "
        "sites; enter it via ctx.with_resource or pre-render inside the override "
        f"and extend the allowlist deliberately: {violations}"
    )
    # The allowlist may not rot: every sanctioned site must still exist.
    assert seen_sanctioned == _SANCTIONED_LOCAL_OVERRIDES
