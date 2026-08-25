"""Profile-fact write door contract.

Every surface that writes profile facts publishes through one shared writer
and names itself with a closed
:class:`~cadrumo.application.user_profile.ProfileFactWriteDoor` member.  The
lifecycle event that write emits is the same for all of them, so the door key
in the event payload is the ONLY axis a history query has for telling the
wizard, the manager screens and the ``config profile`` verbs apart.

The two assertions below are deliberately structural rather than textual.  A
text needle naming a symbol is satisfied by any occurrence of that symbol,
including a prose cross-reference in a docstring, and it cannot tell two call
sites in one module apart -- a module carrying two doors stays green when one
of them regresses.  Reading the call arguments out of the AST, and requiring
every declared member to be reached by some site, bites on a single reverted
door regardless of how many its module holds.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core import scan_directory
from .._fact_write import ProfileFactWriteDoor

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_WRITER = "apply_profile_fact_changes"
_AEAT_ROOT = Path(__file__).resolve().parents[3]

_PRODUCTION_ROOTS: tuple[Path, ...] = (
    _AEAT_ROOT / "application",
    _AEAT_ROOT / "adapters",
    _AEAT_ROOT / "entrypoints",
    _AEAT_ROOT / "domain",
)

_ENROLLED_DOOR_MODULES: frozenset[str] = frozenset(
    {
        "application/wizard/_persistence.py",
        "application/wizard/_commands.py",
        "application/wizard/_descendant_door.py",
        "application/user_profile/_fact_write.py",
        "application/user_profile/_section_rows.py",
        "entrypoints/cli/_config/_manager_actions.py",
        "entrypoints/cli/_config/_capabilities_cli.py",
        "entrypoints/cli/_config/_descendiente.py",
    }
)
"""Modules permitted to open a profile-fact write door, by repository path.

Enrolment is the review gate: a new door is a new surface identity, and it must
declare a member and be listed here rather than quietly reusing another
surface's name.
"""


def _production_files() -> tuple[Path, ...]:
    return tuple(
        path
        for root in _PRODUCTION_ROOTS
        for path in scan_directory(root, pattern="*.py", recursive=True)
        if "tests" not in path.parts
    )


def _door_calls() -> tuple[tuple[Path, ast.Call], ...]:
    """Return every production call to the shared profile-fact writer."""
    found: list[tuple[Path, ast.Call]] = []
    for path in _production_files():
        source = path.read_text(encoding="utf-8")
        if _WRITER not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name == _WRITER:
                found.append((path, node))
    return tuple(found)


def _declared_door(call: ast.Call) -> str | None:
    """Return the member name the call passes as ``door``, when it passes one."""
    for keyword in call.keywords:
        if keyword.arg != "door":
            continue
        value = keyword.value
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == ProfileFactWriteDoor.__name__
        ):
            return value.attr
        return None
    return None


def test_the_writer_corpus_did_not_collapse() -> None:
    """Floor the scan, so 'every site is typed' cannot mean 'no site was read'."""
    files = _production_files()
    assert len(files) > 200, (
        f"scanned only {len(files)} production modules under {_PRODUCTION_ROOTS}; "
        "the scan corpus collapsed, so the door assertions below would pass vacuously"
    )
    calls = _door_calls()
    assert len(calls) >= len(_ENROLLED_DOOR_MODULES), (
        f"found {len(calls)} calls to {_WRITER} across {len(_ENROLLED_DOOR_MODULES)} enrolled modules; "
        "every enrolled module must still contain at least one call"
    )


def test_every_profile_fact_write_names_a_closed_door() -> None:
    """No production site may reach the shared writer with an untyped door."""
    untyped = [
        f"{path.relative_to(_AEAT_ROOT).as_posix()}:{call.lineno}"
        for path, call in _door_calls()
        if _declared_door(call) is None
    ]
    assert untyped == [], (
        f"these {_WRITER} calls do not pass door=ProfileFactWriteDoor.<MEMBER>: {untyped}. "
        "The surface identity travels in the event payload; the event type is the data "
        "change and is not the caller's to choose."
    )


def test_door_sites_live_only_in_enrolled_modules() -> None:
    """A new profile-fact write surface must be enrolled, not merely added."""
    modules = {path.relative_to(_AEAT_ROOT).as_posix() for path, _call in _door_calls()}
    assert modules == _ENROLLED_DOOR_MODULES, (
        f"profile-fact write doors moved: unenrolled {sorted(modules - _ENROLLED_DOOR_MODULES)}, "
        f"vanished {sorted(_ENROLLED_DOOR_MODULES - modules)}. Enrol the new surface with its own "
        "member, or remove the stale entry."
    )


def test_every_declared_door_is_reached_by_a_production_site() -> None:
    """A member nobody passes is a surface identity that never reaches history."""
    reached = {door for _path, call in _door_calls() if (door := _declared_door(call)) is not None}
    declared = {member.name for member in ProfileFactWriteDoor}
    assert declared - reached == set(), (
        f"these door members reach no production site: {sorted(declared - reached)}. Either the "
        "surface regressed to an untyped event stamp, or the member is dead and should go."
    )
    assert reached - declared == set(), (
        f"these sites name doors the enum does not declare: {sorted(reached - declared)}"
    )
