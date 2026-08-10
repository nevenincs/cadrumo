"""The reviewed complexity allowlist refuses to become a mute button.

Two properties make this file an allowlist rather than a silencer, and both are
pinned here because either one lapsing turns it into the thing it replaced:

* an entry with no reason is REFUSED, so the judgement cannot be omitted;
* an entry pins the score it was accepted AT, so a row that grows past the
  reviewed value fails again instead of riding the old acceptance.

The committed file is checked too, because a mechanism that only holds for
synthetic input says nothing about the acceptances actually in the tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..complexity_allowlist import ALLOWLIST_PATH, ComplexityAllowlistError, load_allowlist

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    target = tmp_path / "complexity_allowlist.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_an_entry_without_a_reason_is_refused(tmp_path: Path) -> None:
    """A reasonless acceptance is the mute button this file exists to prevent."""
    target = _write(tmp_path, {"production": {"cyclomatic": {"a.py::f": {"score": 12}}}})

    with pytest.raises(ComplexityAllowlistError, match="must state a non-empty reason"):
        load_allowlist(is_test_run=False, path=target)


def test_a_blank_reason_is_refused_too(tmp_path: Path) -> None:
    """Whitespace is not a reason; the check is on content, not presence."""
    target = _write(tmp_path, {"production": {"cyclomatic": {"a.py::f": {"score": 12, "reason": "   "}}}})

    with pytest.raises(ComplexityAllowlistError, match="must state a non-empty reason"):
        load_allowlist(is_test_run=False, path=target)


def test_an_entry_without_a_score_is_refused(tmp_path: Path) -> None:
    """Acceptance is pinned to a value, so an entry that names none is meaningless."""
    target = _write(tmp_path, {"production": {"cyclomatic": {"a.py::f": {"reason": "flat chain"}}}})

    with pytest.raises(ComplexityAllowlistError, match="must state the numeric score"):
        load_allowlist(is_test_run=False, path=target)


def test_the_accepted_score_is_what_a_later_run_is_measured_against(tmp_path: Path) -> None:
    """The ceiling is the reviewed value, which is what makes further growth fail.

    Anti-vacuity: the assertion would hold for any number if the loader dropped
    the score, so it is compared against the value written rather than merely
    checked non-empty.
    """
    target = _write(
        tmp_path,
        {"production": {"cyclomatic": {"a.py::f": {"score": 12, "reason": "flat guard chain, depth 2"}}}},
    )

    allowlist = load_allowlist(is_test_run=False, path=target)

    assert allowlist.ceilings("cyclomatic") == {"a.py::f": 12.0}
    assert allowlist.cyclomatic["a.py::f"].reason == "flat guard chain, depth 2"


def test_a_missing_file_accepts_nothing(tmp_path: Path) -> None:
    """Absence must mean "no acceptances", never "accept everything"."""
    allowlist = load_allowlist(is_test_run=False, path=tmp_path / "absent.json")

    assert allowlist.ceilings("cyclomatic") == {}
    assert allowlist.ceilings("maintainability") == {}
    assert allowlist.ceilings("cognitive") == {}


def test_the_committed_allowlist_states_a_reason_for_every_entry() -> None:
    """The real file, not a fixture: every acceptance in the tree is justified."""
    allowlist = load_allowlist(is_test_run=False, path=ALLOWLIST_PATH)

    entries = {
        **allowlist.cyclomatic,
        **allowlist.maintainability,
        **allowlist.cognitive,
    }
    assert entries, "the committed allowlist is empty; this gate would pass vacuously"
    unreasoned = sorted(key for key, entry in entries.items() if len(entry.reason) < 20)
    assert unreasoned == [], f"acceptances whose reason is too short to be one: {unreasoned}"
