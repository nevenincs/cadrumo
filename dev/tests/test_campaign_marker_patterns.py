"""The campaign-marker pattern table is proven, and its newest case bites live.

The table in :mod:`._marker_metadata_patterns` is the declarative half of a gate
whose walk was deleted. Nothing imported it afterwards, so its firing fixtures
and near-miss fixtures stopped being checked, and a pattern that has stopped
being checked is indistinguishable from one that matches nothing -- the failure
the table itself keeps a retired scrambled pattern to illustrate.

This module is the table's consumer again. It does not restore the deleted walk
over every module's prose; it proves the table discriminates, and it pins the
one case added after the deletion to the population that case exists to find.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from .._paths import REPO_ROOT
from ..ci.lane_reachability import tracked_test_files
from ._marker_metadata_patterns import (
    CAMPAIGN_METADATA_CASES,
    PROCESS_SYMBOL_METADATA_CASES,
    RETIRED_SCRAMBLED_PLAN_PATTERN,
    assert_cases_discriminate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_STEP_ID_CASE: Final = PROCESS_SYMBOL_METADATA_CASES[-1]


def _tracked_test_modules() -> tuple[Path, ...]:
    """Every tracked test module, through the reachability gate's own accessor.

    Tracked rather than on-disk, for the reason that accessor states: an
    untracked file is a peer's uncommitted work, and counting it reds a shared
    gate on private state. Reused rather than reimplemented -- a second git
    invocation here would be a parallel declaration of the same population.
    """
    return tuple(REPO_ROOT / path for path in tracked_test_files(REPO_ROOT))


def _test_symbol_names(path: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return ()
    return tuple(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")
    )


def test_every_declared_case_matches_its_target_and_rejects_its_near_miss() -> None:
    """The table's own control, run again after the deletion left it unrun."""
    assert_cases_discriminate(CAMPAIGN_METADATA_CASES)
    assert_cases_discriminate(PROCESS_SYMBOL_METADATA_CASES)


def test_the_retired_scrambled_pattern_still_matches_nothing_in_this_tree() -> None:
    """The negative control stays negative, or it is not a control.

    A transposed pattern matched nothing from the day it was written, which is
    why it is kept: it is the shape a silently useless case takes. If this ever
    fires, the token it found is real and the lesson beside it needs rewriting.
    """
    matches = [
        name
        for path in _tracked_test_modules()
        for name in _test_symbol_names(path)
        if RETIRED_SCRAMBLED_PLAN_PATTERN.search(name)
    ]
    assert matches == [], f"the retired control matched live symbols: {matches}"


def test_the_step_id_case_finds_the_development_tree_names_that_carry_one() -> None:
    """The newest case bites on the live tree, measured over `dev/` alone.

    Pinned to a live defect, and this note is what the pin owes. Both names are
    addresses of plan Steps rather than descriptions of behaviour, which the
    Code Stands Alone mandate forbids in a durable symbol. The plan carries the
    rename, and when it lands this test fails: that failure is the correction.
    Replace the expectation with an empty set and keep the assertion, because
    the value of this test afterwards is that it stays empty.

    Measured over `dev/` deliberately. The same case finds a larger population
    under `src/`, which this work does not own and must not half-rename; that
    count belongs in the record, not in an assertion that would go stale on
    somebody else's schedule.
    """
    carrying = {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for path in _tracked_test_modules()
        if str(path.relative_to(REPO_ROOT)).replace("\\", "/").startswith("dev/")
        for name in _test_symbol_names(path)
        if _STEP_ID_CASE.pattern.search(name)
    }
    assert carrying == {
        "dev/locales/tests/test_ledger_notice_action_conformance.py",
        "dev/registry/tests/test_modelo_303_semantic_maps.py",
        "dev/source_connectivity/tests/test_census_completeness.py",
        "dev/tests/test_suggestion_command_conformance.py",
    }, f"the development-tree step-id population moved: {sorted(carrying)}"
