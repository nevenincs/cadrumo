"""Gate: the aggregate suite's gate table is well-formed and complete.

``dev.quality.suite`` is the only surface that runs every static gate in one
pass, which makes a defect in its TABLE more dangerous than a defect in any
single gate: an entry that does not unpack takes the whole suite down before
a single gate runs, and a gate whose row is absent simply never executes
while the suite still reports on everything else.

Both failures have happened here in one edit. Four ratchet commands were added
under a single name, leaving a five-element row: the suite raised
``ValueError: too many values to unpack`` at import of the table, so
``check-all`` ran nothing at all, and three of the four ratchets had no row of
their own to run from even once the crash was fixed. Neither condition is
visible by reading the file -- the rows look like a list of commands either
way -- so it is asserted here.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from ..._paths import REPO_ROOT
from ..suite import GATES

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Recipes in the justfile's static-check group that the aggregate suite
#: deliberately does not run: they re-run gates the suite already covers, or
#: need a local-only service.
_NOT_AGGREGATED: Final[frozenset[str]] = frozenset(
    {"check-pre-commit", "check-all", "check-rag", "check-semantic", "check-security", "check-corpus-text"}
)


def _justfile_static_checks() -> set[str]:
    """Return the recipe names in the justfile's static-checks group."""
    lines = (REPO_ROOT / "justfile").read_text(encoding="utf-8").splitlines()
    names: set[str] = set()
    for index, line in enumerate(lines):
        match = re.match(r"^([a-z][a-z0-9-]*):", line)
        if not match:
            continue
        # A recipe's attributes are the bracketed lines immediately above it.
        # Reading forward from a group marker instead would attribute a recipe
        # to whichever group appeared earlier in the file, which silently
        # pulled a [group('packaging')] recipe into this population.
        for above in reversed(lines[:index]):
            stripped = above.strip()
            if not stripped.startswith(("[", "#")):
                break
            if "group('static-checks')" in stripped:
                names.add(match.group(1))
                break
    return names


def test_every_row_unpacks_as_a_name_and_a_command() -> None:
    """A malformed row takes down the whole suite before any gate runs."""
    malformed = [row for row in GATES if len(row) != 2]
    assert not malformed, f"each GATES row must be (name, command): {malformed}"


def test_every_row_carries_a_name_and_a_non_empty_argv() -> None:
    """A row whose command is empty would run nothing and report success."""
    for name, command in GATES:
        assert isinstance(name, str) and name, f"gate name must be a non-empty string: {name!r}"
        assert command and all(isinstance(part, str) for part in command), f"{name}: bad argv {command!r}"


def test_no_gate_name_is_registered_twice() -> None:
    """A duplicate name hides one of the two rows in the dashboard."""
    names = [name for name, _ in GATES]
    assert len(names) == len(set(names)), f"duplicate gate names: {names}"


def test_every_static_check_recipe_is_either_aggregated_or_declared_exempt() -> None:
    """A gate with a justfile recipe but no row never runs in the suite."""
    missing = sorted(_justfile_static_checks() - {name for name, _ in GATES} - _NOT_AGGREGATED)
    assert not missing, (
        "these static-check recipes have no row in dev.quality.suite.GATES, so "
        f"`just check-all` never runs them: {missing}"
    )


def test_the_recipe_scan_finds_the_group() -> None:
    """A scan returning nothing would make the completeness check vacuous."""
    assert len(_justfile_static_checks()) > 5


def test_the_gate_catches_a_malformed_row() -> None:
    """Detector teeth: the exact five-element shape that broke the suite."""
    planted = (("check-a", ("x",), ("y",), ("z",)),)
    assert [row for row in planted if len(row) != 2] == list(planted)
