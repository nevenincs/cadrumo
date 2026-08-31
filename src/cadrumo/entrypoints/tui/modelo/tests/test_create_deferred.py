"""Proofs that work-unit creation stays deferred and unreachable from C1-C5.

A deferral is only real if nothing can invoke the deferred thing. This module
asserts the second half: the classification says `modelo.work.create` is owned
outside this interface plan, and no surface in the cohort offers it.

The distinction matters because a deferral is easy to state and easy to leak.
An action can acquire a caller through a dispatch row, a route, or a direct
import long after the classification was written, and nothing about the
classification itself would notice.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.actions`
        The dispatch table this action must stay out of.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from ..actions import MODELO_ACTION_DISPATCH, MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CREATE = "modelo.work.create"
_TUI_ROOT = pathlib.Path(__file__).resolve().parents[2]
"""The whole shipped TUI package -- C1 through C5 live under here."""


def _tui_modules() -> list[pathlib.Path]:
    """Every non-test TUI module, which is the surface area C1-C5 occupies."""
    return [path for path in sorted(_TUI_ROOT.rglob("*.py")) if "tests" not in path.parts]


def test_the_tui_surface_is_actually_scanned() -> None:
    """Anti-vacuity: the sweep below means nothing over an empty module set."""
    modules = _tui_modules()

    assert len(modules) > 20, f"only {len(modules)} TUI modules found; the deferral sweep would be vacuous"
    assert any(path.name == "actions.py" for path in modules), "the dispatch table itself was not scanned"


def test_create_is_not_dispatchable_from_any_workspace_surface() -> None:
    """The dispatch table is the one door a C4 action can be invoked through."""
    assert _CREATE not in MODELO_ACTION_DISPATCH


def test_create_is_not_listed_as_a_pending_c4_mutation() -> None:
    """Deferred and pending are different claims about who owns something.

    The pending list means "in scope for this plan, not yet built". Creation
    is owned outside the plan entirely, so listing it there would misstate
    ownership and invite a later reader to enrol it.
    """
    assert _CREATE not in MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS


def test_no_tui_module_names_the_create_action() -> None:
    """A deferral leaks the moment some surface reaches for the action.

    Scanned over the whole shipped TUI package rather than the dispatch table
    alone, because a route, a screen or a direct import could invoke the
    operation without ever appearing in the table.
    """
    offenders: list[str] = []
    for path in _tui_modules():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _CREATE in text:
            offenders.append(str(path.relative_to(_TUI_ROOT)))

    assert not offenders, f"TUI modules naming the deferred create action: {offenders}"


def test_no_tui_module_imports_a_work_unit_creation_writer() -> None:
    """The action id is not the only way to reach creation.

    Checked on the AST so a writer reached through a deferred function-local
    import is caught too -- naming the id is the obvious leak, importing the
    writer is the quiet one.
    """
    offenders: list[str] = []
    for path in _tui_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:  # pragma: no cover - a peer mid-write, not this cohort's concern
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [f"{node.module}.{alias.name}" for alias in node.names]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            offenders.extend(
                f"{path.relative_to(_TUI_ROOT)}: {name}" for name in names if "create_work_unit" in name
            )

    assert not offenders, f"TUI modules importing a work-unit creation writer: {offenders}"


def test_the_sweep_finds_an_action_that_is_actually_present() -> None:
    """Anti-tautology: the same scan, run against a reachable action, must hit.

    Without this, both sweeps above pass equally well against a scanner that
    reads nothing. `modelo.work.rename` is enrolled and named by a TUI module,
    so a scan that cannot see it cannot be trusted to have seen the absence of
    creation either.
    """
    present = [
        str(path.relative_to(_TUI_ROOT))
        for path in _tui_modules()
        if "modelo.work.rename" in path.read_text(encoding="utf-8", errors="ignore")
    ]

    assert present, "the sweep found no module naming an action known to be enrolled"
