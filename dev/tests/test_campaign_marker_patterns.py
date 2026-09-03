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
    PRODUCTION_SCOPED_CAMPAIGN_METADATA_CASES,
    RETIRED_SCRAMBLED_PLAN_PATTERN,
    assert_cases_discriminate,
    campaign_metadata_findings,
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


def test_no_development_tree_test_name_carries_a_step_id() -> None:
    """The newest case is held against the live tree, measured over `dev/` alone.

    The pin this test carried has been redeemed. Four `dev/` test names were
    addresses of plan Steps rather than descriptions of behaviour, which the
    Code Stands Alone mandate forbids in a durable symbol; all four were
    renamed, and the expectation became the empty set exactly as the pin's own
    instruction said it should. The assertion stays, because its value now is
    that the set remains empty: this is the gate that keeps the next such name
    from landing, and an empty expectation is what a closed gate looks like.

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
    assert carrying == set(), f"a step id returned to a development-tree test name: {sorted(carrying)}"


def test_a_module_explaining_its_own_lint_suppression_is_not_campaign_metadata() -> None:
    """The explanation beside a suppression carries the code without the directive.

    The scrub removes the directive, so a line-scoped check reports the prose
    that explains it. The sentence also wraps in the two live cases, which is
    why the judgement has to see the whole module rather than one line.
    """
    module = (
        "# the only variable is the integer port rendered via str() - hence\n"
        "# the S603 suppression.\n"
        "result = subprocess.run(  # noqa: S603\n"
    )
    assert campaign_metadata_findings(module, PRODUCTION_SCOPED_CAMPAIGN_METADATA_CASES) == ()


def test_a_step_id_the_module_does_not_suppress_is_still_reported() -> None:
    """Discrimination, not silence: the exemption is keyed to this module's own codes.

    Without this the previous test would be satisfied by a helper that reports
    nothing at all, which is the failure mode the retired transposed pattern
    exists to name.
    """
    module = "# carried in S42, which nothing here suppresses.\n"
    assert campaign_metadata_findings(module, PRODUCTION_SCOPED_CAMPAIGN_METADATA_CASES) == ("S42",)


def test_the_suppression_exemption_does_not_leak_between_modules() -> None:
    """A code suppressed in one module buys no exemption in another."""
    suppressing = "x = run()  # noqa: S603\n# hence the S603 suppression.\n"
    borrowing = "# carried in S603 of the campaign.\n"
    assert campaign_metadata_findings(suppressing, PRODUCTION_SCOPED_CAMPAIGN_METADATA_CASES) == ()
    assert campaign_metadata_findings(borrowing, PRODUCTION_SCOPED_CAMPAIGN_METADATA_CASES) == ("S603",)
