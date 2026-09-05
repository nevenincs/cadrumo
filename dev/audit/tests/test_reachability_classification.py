"""The reachability classification ledger must stay complete, closed and evidenced.

The ledger's whole value is that every module finding outside the deferred TUI
prefix carries a reviewed class and the evidence that established it. Three ways
it could quietly stop being worth anything: a new finding appears and nobody
classifies it; a class is invented that no remedy is defined for; or an entry
claims a class with no evidence behind it. Each has a gate here.

These read the live audit rather than a recorded count, so the coverage check
tracks the tree instead of a frozen number.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT
from ..unreachable_code import run_unreachable_code_scan

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_LEDGER_PATH: Final[Path] = REPO_ROOT / "dev" / "audit" / "reachability_classification.toml"

#: The closed taxonomy. Each names a distinct remedy; adding one is a decision,
#: not an edit, which is why membership is asserted rather than inferred.
_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "harness-code",
        "design-time-authority",
        "test-support",
        "superseded",
        "staged-capability",
        "orphaned",
        "should-be-live",
        "deferred-by-ownership",
    }
)

#: Findings under this prefix belong to another in-flight campaign and are out
#: of this ledger's scope. Deferral is scope, never permission.
_DEFERRED_PREFIX: Final[str] = "cadrumo.entrypoints.tui"


def _ledger() -> dict[str, object]:
    """Parse the committed classification ledger."""
    return tomllib.loads(_LEDGER_PATH.read_text(encoding="utf-8"))


def _entries() -> list[dict[str, str]]:
    """Return the ledger's module entries."""
    modules = _ledger()["module"]
    assert isinstance(modules, list)
    return [dict(entry) for entry in modules]


def _reported_modules() -> set[str]:
    """Return the in-scope module names the live audit reports."""
    result = run_unreachable_code_scan(REPO_ROOT)
    return {finding.module for finding in result.modules if not finding.module.startswith(_DEFERRED_PREFIX)}


def test_every_reported_module_carries_a_classification() -> None:
    """A finding with no entry is an unreviewed finding, whatever the count says."""
    reported = _reported_modules()

    assert reported, "the audit reported no in-scope modules; coverage would pass vacuously"
    unclassified = sorted(reported - {entry["name"] for entry in _entries()})

    assert unclassified == [], (
        f"the live audit reports module(s) with no entry in reachability_classification.toml: {unclassified}"
    )


def test_the_ledger_carries_no_entry_the_audit_no_longer_reports() -> None:
    """A stale entry describes a module that is already resolved.

    Unlike the duplication ledger, this one is not permitted to over-declare: a
    module that became reachable has had its finding answered, and leaving the
    entry would let a future regression land on a name that already looks
    reviewed.
    """
    reported = _reported_modules()
    stale = sorted({entry["name"] for entry in _entries()} - reported)

    assert stale == [], (
        f"entries describe module(s) the audit no longer reports: {stale}. "
        "Remove them rather than leaving a reviewed-looking name behind."
    )


def test_every_entry_uses_a_class_from_the_closed_taxonomy() -> None:
    """An invented class names no remedy while reading as a decision."""
    entries = _entries()

    assert entries, "the ledger parsed empty; the vocabulary check has no subject"
    unknown = sorted({entry.get("class", "<missing>") for entry in entries} - _CLASSES)

    assert unknown == [], f"unrecognised class(es) in the ledger: {unknown}"


def test_every_entry_states_the_evidence_behind_its_class() -> None:
    """A class without evidence is relabelling, which is what this ledger must not be.

    Supersession and staging are claims about intent that a name cannot
    establish; both were required to name a live module or an accepted decision.
    Requiring evidence on every entry keeps that from decaying into an
    unsupported label once the population grows.
    """
    entries = _entries()

    assert entries, "the ledger parsed empty; the evidence check has no subject"
    unevidenced = sorted(entry["name"] for entry in entries if not entry.get("evidence", "").strip())

    assert unevidenced == [], f"entries claiming a class with no stated evidence: {unevidenced}"


def test_the_deferred_prefix_is_not_smuggled_into_the_ledger() -> None:
    """Classifying a deferred module here would move scope without a decision."""
    smuggled = sorted(entry["name"] for entry in _entries() if entry["name"].startswith(_DEFERRED_PREFIX))

    assert smuggled == [], (
        f"entries classify module(s) under the deferred prefix: {smuggled}. "
        "That population belongs to its owning campaign."
    )


def _test_entries() -> list[dict[str, object]]:
    """Return the ledger's orphaned-test entries."""
    modules = _ledger()["test_module"]
    assert isinstance(modules, list)
    return [dict(entry) for entry in modules]


def _reported_test_modules() -> set[str]:
    """Return the in-scope orphaned-test module names the live audit reports."""
    result = run_unreachable_code_scan(REPO_ROOT)
    return {finding.module for finding in result.tests if not finding.module.startswith(_DEFERRED_PREFIX)}


def test_every_orphaned_test_module_is_covered() -> None:
    """An orphaned test nothing accounts for is a test nobody decided the fate of.

    Coverage is satisfied two ways, and the second is not a loophole. A test may
    carry its own entry, or it may live under a module this ledger already
    classifies -- because the whole orphaned-test population is derivative, a
    test inside a classified package is already accounted for by that package's
    class and shares its remedy.

    The distinction matters against a tree under concurrent development. A peer
    landing a new domain package adds test modules to it over several commits,
    and requiring a fresh entry per file would fail this gate on work that is
    already classified at the level where the decision was actually made.
    """
    reported = _reported_test_modules()

    assert reported, "the audit reported no in-scope orphaned tests; coverage would pass vacuously"
    named = {str(entry["name"]) for entry in _test_entries()}
    classified = {str(entry["name"]) for entry in _entries()}
    uncovered = sorted(
        module
        for module in reported
        if module not in named and not any(module.startswith(f"{owner}.") for owner in classified)
    )

    assert uncovered == [], f"orphaned test module(s) neither entered nor under a classified module: {uncovered}"


def test_every_orphaned_test_entry_anchors_to_the_finding_it_follows() -> None:
    """A derivative entry without its anchor cannot be resolved with its subject.

    The whole non-TUI orphaned-test population is derivative: each follows a
    module finding or an unused symbol, and none carries an independent remedy.
    An entry that does not name what it follows breaks that chain, and the test
    would then look reviewed while nothing connects it to the work that retires
    it.
    """
    entries = _test_entries()

    assert entries, "the ledger parsed no orphaned-test entries; the anchor check has no subject"
    broken = sorted(
        str(entry["name"])
        for entry in entries
        if entry.get("follows") not in {"module", "symbol"} or not str(entry.get("anchor", "")).strip()
    )

    assert broken == [], f"orphaned-test entries missing a valid follows/anchor pair: {broken}"


def test_a_test_following_a_module_anchors_to_a_classified_module() -> None:
    """A module-following test must point at a module this ledger actually classifies.

    Otherwise the chain dead-ends: the test claims to retire with its subject
    while no entry states what that subject's remedy is.
    """
    classified = {str(entry["name"]) for entry in _entries()}
    dangling = sorted(
        str(entry["name"])
        for entry in _test_entries()
        if entry.get("follows") == "module" and not any(str(entry["anchor"]).startswith(name) for name in classified)
    )

    assert dangling == [], f"module-following test entries whose anchor is not classified: {dangling}"


def test_no_unresolved_cluster_names_a_symbol_the_audit_stopped_reporting() -> None:
    """An unresolved cluster claims work is outstanding; the tree must agree.

    Nothing checked the symbol clusters against the tree, and one drifted: a
    staged-capability cluster went on naming ``build_related_party_rows`` after
    that public alias was deleted, so the ledger asserted outstanding work on a
    symbol that no longer existed. A record whose claim has quietly become
    false is the failure this whole classification exists to prevent, and it is
    worse in the ledger than in ordinary prose.

    Matching is by name within the cluster's own area, because a private helper
    name can legitimately recur in unrelated packages.
    """
    reported: dict[str, set[str]] = {}
    for finding in run_unreachable_code_scan(REPO_ROOT).symbols:
        reported.setdefault(finding.name, set()).add(finding.module)

    stale: list[str] = []
    for cluster in _ledger().get("symbol_cluster", ()):
        if cluster.get("resolved"):
            continue
        area = cluster["area"].replace("/", ".")
        for name in cluster["symbols"]:
            if not any(area in module for module in reported.get(name, ())):
                stale.append(f"{cluster['name']}: {name}")

    assert not stale, "unresolved clusters naming symbols the audit no longer reports: " + "; ".join(stale)
