"""Gate: a workspace area is wired completely or not at all, never in part.

The Ledger workspace decides whether to open an area by testing a group of
injected dependencies together -- an action, the target it acts on, and the
submitter that carries the result. Supplying SOME of a group is the one state
that cannot be read from the call site: the door is refused at runtime exactly
as if nothing had been supplied, while the launcher plainly appears to
configure it.

That is the shape found in production. The launcher passes ``classify_action``
and never ``classification_target`` or ``classification_submitter``, so the
classification door can never open, and the passed action is the only evidence
a reader has that it was ever meant to. An absent area is a supported state and
this gate permits it; a HALF-absent one is a wiring defect and this refuses it.

The requirement is read out of the controller's own guard rather than restated
here, so an area that gains or loses a dependency cannot drift away from it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CONTROLLER: Final[Path] = REPO_ROOT / "src/cadrumo/entrypoints/tui/ledger/controller.py"
_LAUNCHER: Final[Path] = REPO_ROOT / "src/cadrumo/entrypoints/tui/launcher.py"
_FACTORY: Final = "ledger_screen_factory"


def door_requirements(source: str) -> dict[str, frozenset[str]]:
    """Return, per area, the injected fields whose absence refuses the door.

    A clause reads ``area is LedgerWorkspaceArea.X and (self.a is None or ...)``,
    so the area name and the fields it depends on sit in one boolean node.
    """
    requirements: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.And):
            continue
        areas = {
            c.comparators[0].attr
            for c in ast.walk(node)
            if isinstance(c, ast.Compare)
            and c.comparators
            and isinstance(c.comparators[0], ast.Attribute)
            and isinstance(c.comparators[0].value, ast.Name)
            and c.comparators[0].value.id == "LedgerWorkspaceArea"
        }
        if len(areas) != 1:
            continue
        fields = {
            a.attr
            for a in ast.walk(node)
            if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == "self"
        }
        if fields:
            requirements.setdefault(areas.pop(), set()).update(fields)
    return {area: frozenset(fields) for area, fields in requirements.items()}


def supplied_fields(source: str, factory: str = _FACTORY) -> frozenset[str]:
    """Return the keyword names production passes to the workspace factory."""
    supplied: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == factory:
            supplied.update(kw.arg for kw in node.keywords if kw.arg)
    return frozenset(supplied)


def partially_wired_doors(controller: str, launcher: str) -> dict[str, tuple[str, ...]]:
    """Return, per area, the required fields production forgot beside those it gave."""
    supplied = supplied_fields(launcher)
    partial: dict[str, tuple[str, ...]] = {}
    for area, required in door_requirements(controller).items():
        given = required & supplied
        if given and given != required:
            partial[area] = tuple(sorted(required - supplied))
    return partial


def test_the_guard_still_yields_areas_and_their_dependencies() -> None:
    """A population floor: an unreadable guard would pass every assertion below."""
    requirements = door_requirements(_CONTROLLER.read_text(encoding="utf-8"))
    assert len(requirements) >= 3, (
        f"read only {len(requirements)} guarded area(s) from the controller; the "
        "guard shape has drifted and this gate is inert rather than satisfied"
    )
    assert all(requirements.values()), f"an area was read with no dependencies: {requirements}"


def test_the_launcher_still_supplies_something() -> None:
    """A matches floor: zero supplied fields would make every door read absent."""
    supplied = supplied_fields(_LAUNCHER.read_text(encoding="utf-8"))
    assert len(supplied) >= 3, (
        f"the launcher was read as supplying only {sorted(supplied)}; the call "
        "site has moved and this gate no longer sees production wiring"
    )


def test_no_workspace_door_is_wired_in_part() -> None:
    """The direction the gate exists for."""
    partial = partially_wired_doors(_CONTROLLER.read_text(encoding="utf-8"), _LAUNCHER.read_text(encoding="utf-8"))
    assert not partial, (
        "these workspace areas are given some of their dependencies and not the "
        "rest, so the door is refused at runtime while the call site reads as "
        f"configured; supply the missing fields or none of them: {partial}"
    )


def test_the_gate_catches_a_planted_half_wired_door() -> None:
    """Detector teeth: an action supplied without the submitter beside it."""
    controller = (
        "def route(self, area):\n"
        "    missing = area is LedgerWorkspaceArea.CLASSIFICATION and (\n"
        "        self.classify_action is None or self.classification_submitter is None\n"
        "    )\n"
    )
    launcher = "def make():\n    return ledger_screen_factory(p, classify_action=a)\n"

    assert partially_wired_doors(controller, launcher) == {"CLASSIFICATION": ("classification_submitter",)}


def test_an_area_supplied_in_full_is_left_alone() -> None:
    """The normal case, so the gate is not merely always-red."""
    controller = (
        "def route(self, area):\n"
        "    missing = area is LedgerWorkspaceArea.EVIDENCE and (\n"
        "        self.evidence_action is None or self.evidence_items is None\n"
        "    )\n"
    )
    launcher = "def make():\n    return ledger_screen_factory(p, evidence_action=a, evidence_items=i)\n"

    assert partially_wired_doors(controller, launcher) == {}


def test_an_area_supplied_not_at_all_is_left_alone() -> None:
    """An unoffered area is a supported state; only a half-offered one is not."""
    controller = (
        "def route(self, area):\n"
        "    missing = area is LedgerWorkspaceArea.IMPORT and (\n"
        "        not self.prepared_imports or self.import_submitter is None\n"
        "    )\n"
    )
    launcher = "def make():\n    return ledger_screen_factory(p, review_action=r)\n"

    assert partially_wired_doors(controller, launcher) == {}
