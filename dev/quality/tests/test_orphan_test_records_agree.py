"""Gate: the orphan-test backlog and its explanations stay in lockstep.

Two files describe the same population from different angles.
``dev/quality/unused_symbol_ratchet.toml`` records WHICH test modules exercise
only dead code, as a shrink-only backlog. ``dev/audit/reachability_classification.toml``
records WHY each one does, as a classification. Every backlog row is meant to
have an explanation, and the two are meant to move together.

They did not. Three rows resolved by retiring a package-init re-export were
removed from the ledger and left in the ratchet for four steps, where they read
as live backlog that had in fact been paid. Nothing compared the files, so the
divergence was invisible in both directions: the ledger looked complete and the
ratchet looked owed.

Cheap on purpose. Both inputs are declarations already on disk, so this runs in
milliseconds and needs no reachability scan -- a gate that required the 15-minute
audit to notice a two-line inconsistency would not be run often enough to catch one.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_RATCHET: Final[Path] = _REPO_ROOT / "dev" / "quality" / "unused_symbol_ratchet.toml"
_LEDGER: Final[Path] = _REPO_ROOT / "dev" / "audit" / "reachability_classification.toml"

#: The prefix the ratchet declines to adjudicate, so the ledger may hold rows
#: for it that the ratchet deliberately does not carry.
_DEFERRED_PREFIX: Final = "cadrumo.entrypoints.tui"


def _load(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def ratchet_orphan_tests(data: dict[str, Any]) -> frozenset[str]:
    """Return the test modules the ratchet records as exercising only dead code."""
    return frozenset(str(name) for name in data.get("orphan_tests", {}).get("modules", ()))


def ledger_test_modules(data: dict[str, Any]) -> frozenset[str]:
    """Return the test modules the classification ledger explains."""
    return frozenset(str(entry["name"]) for entry in data.get("test_module", ()))


def unexplained(recorded: frozenset[str], explained: frozenset[str]) -> tuple[str, ...]:
    """Return backlog rows with no classification behind them."""
    return tuple(sorted(recorded - explained))


def stale_explanations(recorded: frozenset[str], explained: frozenset[str]) -> tuple[str, ...]:
    """Return classifications for rows the backlog no longer carries.

    Excludes the deferred prefix, which the ratchet declines to adjudicate by
    design -- the ledger is expected to hold rows there that the ratchet does
    not, and reading those as stale would make the gate permanently red for a
    scope decision rather than an inconsistency.
    """
    return tuple(sorted(name for name in explained - recorded if not name.startswith(_DEFERRED_PREFIX)))


def test_every_recorded_orphan_test_is_explained() -> None:
    """A backlog row with no classification says what, never why."""
    recorded = ratchet_orphan_tests(_load(_RATCHET))
    explained = ledger_test_modules(_load(_LEDGER))

    assert unexplained(recorded, explained) == (), (
        "these test modules are recorded as orphaned backlog with no entry in the "
        f"classification ledger explaining why: {unexplained(recorded, explained)}"
    )


def test_no_classification_outlives_its_backlog_row() -> None:
    """The direction that actually broke: a paid row left standing."""
    recorded = ratchet_orphan_tests(_load(_RATCHET))
    explained = ledger_test_modules(_load(_LEDGER))

    assert stale_explanations(recorded, explained) == (), (
        "these test modules are classified in the ledger but no longer recorded as "
        "orphaned backlog; remove the classification in the step that resolved them: "
        f"{stale_explanations(recorded, explained)}"
    )


def test_both_files_still_record_orphan_tests() -> None:
    """A vacuity floor: two empty sets agree perfectly and prove nothing."""
    recorded = ratchet_orphan_tests(_load(_RATCHET))
    explained = ledger_test_modules(_load(_LEDGER))

    assert len(recorded) >= 5 and len(explained) >= 5, (
        f"ratchet records {len(recorded)} and the ledger explains {len(explained)}; "
        "either the backlog is genuinely near zero and these floors should be lowered "
        "deliberately, or a reader has drifted and the gate is inert"
    )


def test_the_gate_catches_an_unexplained_backlog_row() -> None:
    """Detector teeth: backlog recorded with no reason given."""
    assert unexplained(frozenset({"a.tests.test_b"}), frozenset()) == ("a.tests.test_b",)


def test_the_gate_catches_a_classification_left_behind() -> None:
    """Detector teeth: the exact four-step drift this was written for."""
    assert stale_explanations(frozenset(), frozenset({"a.tests.test_b"})) == ("a.tests.test_b",)


def test_a_deferred_prefix_classification_is_not_read_as_stale() -> None:
    """The bound: the ratchet declines that prefix, so the ledger may exceed it there."""
    deferred = f"{_DEFERRED_PREFIX}.modelo.tests.test_x"

    assert stale_explanations(frozenset(), frozenset({deferred})) == ()


def test_agreeing_files_pass() -> None:
    """The normal case, so the gate is not merely always-red."""
    both = frozenset({"a.tests.test_b"})

    assert unexplained(both, both) == () and stale_explanations(both, both) == ()
