"""Gate: every CRUD noun-group verb the catalogue declares must exist to run.

The catalogue names itself the single source of truth for the mutating
noun-group shape and says a harness consumes it to detect drift against the
shipped command tree. That harness did not exist -- the catalogue's own tests
import only the catalogue, so they compared it against itself and stayed green
while five of its six entries went stale.

This gate performs the comparison, against the real ``COMMAND_GRAPH``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..quality.crud_contract_drift import (
    DeclaredVerbDrift,
    baseline_keys,
    declared_verb_drift,
    live_command_paths,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_the_live_catalogue_declares_no_verb_beyond_its_baseline() -> None:
    """A newly declared verb the operator cannot run fails this gate."""
    reported = {item.key for item in declared_verb_drift()}
    accepted = baseline_keys()

    regressions = sorted(reported - accepted)

    assert not regressions, (
        f"{len(regressions)} catalogue verb(s) no live command provides that the baseline does not name.\n"
        + "\n".join(f"    + {key}" for key in regressions)
    )


def test_the_baseline_names_no_drift_that_has_been_resolved() -> None:
    """The gate is shrink-only: a resolved row must leave the baseline.

    Without this the file would accumulate rows describing drift that no
    longer exists, and would stop meaning anything.
    """
    reported = {item.key for item in declared_verb_drift()}
    accepted = baseline_keys()

    stale = sorted(accepted - reported)

    assert not stale, f"{len(stale)} baseline row(s) name drift that no longer exists; delete them.\n" + "\n".join(
        f"    - {key}" for key in stale
    )


def test_a_declared_verb_absent_from_the_tree_is_reported() -> None:
    """Detector teeth: the gate sees a contract naming a command nobody mounts.

    The live path set is supplied explicitly rather than monkeypatching the
    graph, so the contributor's tree and the real registry are untouched.
    """
    catalogue_only = frozenset({("aeat", "app", "ledger", "evidence")})

    reported = declared_verb_drift(live_paths=catalogue_only)

    assert DeclaredVerbDrift("aeat app ledger evidence", "add") in reported


def test_a_fully_mounted_noun_group_reports_nothing() -> None:
    """The control: the same contract, with every declared verb mounted.

    Paired with the case above so a detector that reported everything, or
    nothing, could not pass both.
    """
    from cadrumo.application.operator_surface.crud_registry import BUILTIN_CRUD_CATALOGUE

    evidence = BUILTIN_CRUD_CATALOGUE.find("aeat app ledger evidence")
    assert evidence is not None
    group = tuple(evidence.cli_path.split())
    fully_mounted = frozenset({group, *((*group, verb) for verb in evidence.all_verb_names())})

    reported = declared_verb_drift(live_paths=fully_mounted)

    assert [item for item in reported if item.cli_path == evidence.cli_path] == []


def test_the_reference_noun_group_is_completely_mounted_in_the_live_tree() -> None:
    """The locked reference shape must hold against the real command graph.

    The evidence group is the shape every other noun-group is measured
    against, so its drifting would invalidate the contract itself.
    """
    from cadrumo.application.operator_surface.crud_registry import BUILTIN_CRUD_CATALOGUE

    evidence = BUILTIN_CRUD_CATALOGUE.find("aeat app ledger evidence")
    assert evidence is not None

    drifted = [item for item in declared_verb_drift() if item.cli_path == evidence.cli_path]

    assert drifted == []


def test_the_baseline_file_is_parseable_and_non_empty_rows_are_strings() -> None:
    """A malformed baseline must fail loudly rather than silently accepting everything."""
    keys = baseline_keys(Path(__file__).parent.parent / "quality" / "crud_contract_drift_baseline.toml")

    assert keys
    assert all(isinstance(key, str) and key.strip() for key in keys)


def test_the_live_graph_is_actually_walked() -> None:
    """Guard against a live-path source that silently returns nothing.

    An empty path set would make every declared verb look like drift, which
    is the failure mode most likely to get this gate disabled.
    """
    paths = live_command_paths()

    assert len(paths) > 100
    assert ("aeat", "app", "ledger", "evidence") in paths


@pytest.mark.parametrize("cli_path", ["aeat app ledger evidence", "aeat app ledger invoice"])
def test_every_baselined_group_still_exists_in_the_tree(cli_path: str) -> None:
    """A baselined verb is a missing VERB, never a missing group.

    If the group itself vanished the row would be describing something else,
    and the baseline comment would be wrong about why it is there.
    """
    assert tuple(cli_path.split()) in live_command_paths()
