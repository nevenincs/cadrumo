"""Override-seam singularity gate: no process-wide test-hook state in production.

Two production seams shipped the same shape and both hid until found by
accident: ``override_wizard_prompter`` (deleted) and ``override_secret_store``
(deleted in ``relocation:override_secret_store``). Each installed a
process-wide, module-global mutable slot that a production factory consulted
(``_override_store`` + ``if _override_store is not None:`` inside
``get_secret_store``) and exposed a public ``override_*`` setter for tests to
swap it. That is a test double living in the production tree: it bypasses the
real dependency-injection seam, it is invisible to type checking, and nothing
structural stopped a third from appearing.

This gate is that structural prevention. Two rules, recomputed from the real
``ast`` module every run against the production tree (test modules, conftest,
and bundled ``_data`` excluded), with NO stored baseline and NO allowlist:

1. No production module declares a module-global mutable ``_override_*`` slot
   (the ``_override_store`` shape). Real DI threads the dependency through a
   parameter (``store=`` / ``settings=`` / ``objects=``) or resolves it from
   the active session — never through a swappable process-global.
2. No production module defines a public ``override_*`` function (the
   ``override_secret_store`` / ``override_wizard_prompter`` setter shape).

Exactly ONE carve-out is sanctioned: ``cadrumo.core.config.override_settings``.
It is a scoped context manager (not a swappable slot) backed by a
``contextvars.ContextVar`` named ``_settings_override`` — NOT an ``_override_*``
global, so rule 1 never touches it — and it has real production callers
(``application.auth.sessions``, ``operator_scope``, ``credentials``,
``application.workflow.profile_health``) that scope active-profile settings for
one call tree. The carve-out is pinned to exactly one function name in exactly
one module, so a second ``override_*`` cannot hide behind it: an
``override_settings`` defined anywhere else, or any other ``override_*`` in
``core/config.py`` itself, still fails rule 2.

The detectors are pure ``(display_path, tree) -> list[str]`` functions so the
discrimination tests below can feed each one a synthetic violator and the
sanctioned shape, proving it fires on the first and stays silent on the second.
A gate that cannot fail pins a false green, which is the exact failure mode this
whole campaign exists to undo.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from .inventory import aeat_relative, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


SANCTIONED_CARVEOUT_MODULE = "core/config.py"
"""The single production module allowed to define the sanctioned ``override_*``."""

SANCTIONED_OVERRIDE_FUNCTION = "override_settings"
"""The one public ``override_*`` name the gate exempts, and only in the carve-out module.

``override_settings`` is a scoped ``contextvars``-backed context manager with
real production callers, not a swappable process-global test hook. Pinning the
exemption to one name in one module keeps a second ``override_*`` from hiding
behind the carve-out.
"""

OVERRIDE_STATE_PREFIX = "_override"
"""Name prefix of the forbidden module-global test-hook slot (``_override_store``)."""

PUBLIC_OVERRIDE_PREFIX = "override_"
"""Name prefix of the forbidden public test-hook setter (``override_secret_store``)."""


def _is_sanctioned_carveout_module(path: Path) -> bool:
    return aeat_relative(path) == SANCTIONED_CARVEOUT_MODULE


def _assignment_target_names(node: ast.Assign | ast.AnnAssign) -> list[tuple[int, str]]:
    """Return ``(lineno, name)`` for every simple ``Name`` target of an assignment."""
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return [(node.lineno, target.id) for target in targets if isinstance(target, ast.Name)]


def override_global_state_violations(display_path: str, tree: ast.AST) -> list[str]:
    """Return rule-1 violations: any assignment binding an ``_override_*`` name.

    Walks the whole tree, not just module scope, so a slot declared through a
    ``global _override_x`` reassignment inside a factory is caught alongside the
    module-level ``_override_store: T | None = None`` declaration.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign | ast.AnnAssign):
            for lineno, name in _assignment_target_names(node):
                if name.startswith(OVERRIDE_STATE_PREFIX):
                    violations.append(
                        f"{display_path}:{lineno}: module-global override slot {name!r}; "
                        f"a process-wide mutable test hook is not production DI — thread the "
                        f"dependency through a parameter or resolve it from the active session"
                    )
        elif isinstance(node, ast.Global):
            violations.extend(
                f"{display_path}:{node.lineno}: 'global {name}' rebinds an override slot {name!r}; "
                f"a process-wide mutable test hook is not production DI"
                for name in node.names
                if name.startswith(OVERRIDE_STATE_PREFIX)
            )
    return violations


def override_setter_function_violations(
    display_path: str,
    tree: ast.AST,
    *,
    is_sanctioned_carveout: bool,
) -> list[str]:
    """Return rule-2 violations: any public ``override_*`` function definition.

    The sole exemption is ``override_settings`` in the carve-out module; every
    other ``override_*`` — including one named ``override_settings`` outside the
    carve-out module, or a second ``override_*`` inside it — is a violation.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.name.startswith(PUBLIC_OVERRIDE_PREFIX):
            continue
        if is_sanctioned_carveout and node.name == SANCTIONED_OVERRIDE_FUNCTION:
            continue
        violations.append(
            f"{display_path}:{node.lineno}: public override setter {node.name!r}; "
            f"a test-hook setter is not production DI. The only sanctioned override_* is "
            f"{SANCTIONED_OVERRIDE_FUNCTION} in {SANCTIONED_CARVEOUT_MODULE}"
        )
    return violations


# --------------------------------------------------------------------------
# Anti-vacuity: pin the scan surface and the carve-out anchor. Were the
# production surface empty or ``override_settings`` renamed away, both rules
# would pass by scanning nothing / exempting a name that no longer exists --
# silently green, enforcing nothing.
# --------------------------------------------------------------------------


def test_production_surface_is_non_empty(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """The gate scans a real production tree; an empty scan would pass vacuously."""
    assert production_ast_items(source_tree_ast), "production AST surface is empty; the gate would enforce nothing"


def test_sanctioned_carveout_exists(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Exactly one ``override_settings`` ships, and it lives in the carve-out module.

    This pins the rule-2 exemption to a live anchor: a rename or move would
    otherwise leave the exemption exempting a phantom while the relocated
    function is (correctly) flagged, but the drift should surface here first.
    """
    sites = [
        f"{repo_relative(path)}:{node.lineno}"
        for path, tree in production_ast_items(source_tree_ast)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == SANCTIONED_OVERRIDE_FUNCTION
    ]

    assert len(sites) == 1, f"expected exactly one {SANCTIONED_OVERRIDE_FUNCTION} definition; found {sites}"
    assert sites[0].endswith(f"{SANCTIONED_CARVEOUT_MODULE}:{sites[0].rsplit(':', 1)[1]}"), (
        f"{SANCTIONED_OVERRIDE_FUNCTION} must live in src/cadrumo/{SANCTIONED_CARVEOUT_MODULE}; found {sites[0]}"
    )


# --------------------------------------------------------------------------
# The two rules, over the real production tree. Both ship allowlist-empty: the
# tree is clean after relocation:override_secret_store, so any hit is a straight
# failure, the strongest posture.
# --------------------------------------------------------------------------


def test_no_module_global_override_state_in_production(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Rule 1: no production module declares an ``_override_*`` process-global slot."""
    violations = [
        violation
        for path, tree in production_ast_items(source_tree_ast)
        for violation in override_global_state_violations(repo_relative(path), tree)
    ]

    assert violations == [], (
        "no production module may declare a module-global override slot; use real DI instead:\n" + "\n".join(violations)
    )


def test_no_public_override_setter_in_production(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Rule 2: no production module defines a public ``override_*`` setter but the carve-out."""
    violations = [
        violation
        for path, tree in production_ast_items(source_tree_ast)
        for violation in override_setter_function_violations(
            repo_relative(path), tree, is_sanctioned_carveout=_is_sanctioned_carveout_module(path)
        )
    ]

    assert violations == [], (
        f"the only sanctioned public override_* is {SANCTIONED_OVERRIDE_FUNCTION} in "
        f"{SANCTIONED_CARVEOUT_MODULE}:\n" + "\n".join(violations)
    )


# --------------------------------------------------------------------------
# Discrimination: each detector is fed the seam shape it exists to catch, plus
# the sanctioned shape it must NOT flag.
# --------------------------------------------------------------------------

_OVERRIDE_STATE_SEAM = """
from __future__ import annotations

_override_store = None


def get_secret_store():
    global _override_store
    if _override_store is not None:
        return _override_store
    return _build()


def override_secret_store(store) -> None:
    global _override_store
    _override_store = store
"""

_SANCTIONED_SETTINGS_SHAPE = """
from __future__ import annotations

import contextvars
from contextlib import contextmanager

_settings_override: contextvars.ContextVar = contextvars.ContextVar("_settings_override", default=None)


@contextmanager
def override_settings(**overrides):
    token = _settings_override.set(overrides)
    try:
        yield overrides
    finally:
        _settings_override.reset(token)
"""


def test_rule_one_fires_on_a_module_global_override_slot() -> None:
    violations = override_global_state_violations(
        "src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py",
        ast.parse(_OVERRIDE_STATE_SEAM),
    )

    assert any("_override_store" in v for v in violations), violations
    assert any("global override slot" in v for v in violations), violations


def test_rule_one_ignores_the_sanctioned_settings_contextvar() -> None:
    """The ``_settings_override`` ContextVar is not an ``_override_*`` slot; rule 1 stays silent."""
    assert (
        override_global_state_violations(
            f"src/cadrumo/{SANCTIONED_CARVEOUT_MODULE}", ast.parse(_SANCTIONED_SETTINGS_SHAPE)
        )
        == []
    )


def test_rule_two_fires_on_a_public_override_setter() -> None:
    violations = override_setter_function_violations(
        "src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py",
        ast.parse(_OVERRIDE_STATE_SEAM),
        is_sanctioned_carveout=False,
    )

    assert len(violations) == 1
    assert "override_secret_store" in violations[0]
    assert SANCTIONED_OVERRIDE_FUNCTION in violations[0]


def test_rule_two_exempts_override_settings_only_in_the_carveout_module() -> None:
    """``override_settings`` in the carve-out module is sanctioned and not flagged."""
    assert (
        override_setter_function_violations(
            f"src/cadrumo/{SANCTIONED_CARVEOUT_MODULE}",
            ast.parse(_SANCTIONED_SETTINGS_SHAPE),
            is_sanctioned_carveout=True,
        )
        == []
    )


def test_rule_two_flags_override_settings_defined_outside_the_carveout_module() -> None:
    """A second module cannot borrow the carve-out name; ``override_settings`` elsewhere is flagged."""
    violations = override_setter_function_violations(
        "src/cadrumo/application/other/_impostor.py",
        ast.parse(_SANCTIONED_SETTINGS_SHAPE),
        is_sanctioned_carveout=False,
    )

    assert len(violations) == 1
    assert SANCTIONED_OVERRIDE_FUNCTION in violations[0]


def test_rule_two_flags_a_second_override_function_inside_the_carveout_module() -> None:
    """Only ``override_settings`` is exempt in the carve-out; a sibling ``override_*`` still fails."""
    source = """
from contextlib import contextmanager


@contextmanager
def override_settings(**overrides):
    yield overrides


def override_route(store) -> None:
    pass
"""
    violations = override_setter_function_violations(
        f"src/cadrumo/{SANCTIONED_CARVEOUT_MODULE}", ast.parse(source), is_sanctioned_carveout=True
    )

    assert len(violations) == 1
    assert "override_route" in violations[0]
