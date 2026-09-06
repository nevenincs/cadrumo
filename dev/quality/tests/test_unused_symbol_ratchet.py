"""Tests for the unused-symbol ratchet's deferral reporting.

`dev.quality.module_test_reach` listed `dev/quality/unused_symbol_ratchet.py` as
unreached. The ratchet itself is carefully built - it fails in both directions,
so debt that is paid must be recorded as paid, and it deliberately gates only
the ``exact`` tier because gating name-match findings would ratchet guesses.

What it did not do is say what it left out. A prefix defers an in-flight
campaign's findings, and the module's own comment says deferral sets scope
rather than granting permission - but the verdict never mentioned it, so a run
reporting that the tree matches the baseline was silent about a documented
population sitting outside the comparison. Deferred and proven-clean are
different states, and only one of them was being reported.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..unused_symbol_ratchet import RatchetVerdict, evaluate, render

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _verdict(**overrides: object) -> RatchetVerdict:
    fields: dict[str, object] = {
        "grew": (),
        "unrecorded": (),
        "shrank": (),
        "resolved": (),
        "orphan_tests_unrecorded": (),
        "orphan_tests_resolved": (),
    }
    fields.update(overrides)
    return RatchetVerdict(**fields)  # type: ignore[arg-type]


def test_an_agreeing_tree_still_states_what_was_deferred() -> None:
    """The case that mattered: a green verdict was silent about the exclusion.

    "Tree matches baseline" over a population that was never compared reads as
    a stronger claim than the ratchet can make.
    """
    rendered = render(_verdict(deferred_symbols=22, deferred_tests=2))

    assert "tree matches baseline" in rendered
    assert "22 symbol finding(s)" in rendered
    assert "2 orphaned test module(s)" in rendered
    assert "were not compared" in rendered


def test_a_failing_verdict_states_the_deferral_too() -> None:
    """A reader triaging failures needs to know the list is not the whole tree."""
    rendered = render(_verdict(unrecorded=(("cadrumo.x", 1),), deferred_symbols=22, deferred_tests=2))

    assert "cadrumo.x" in rendered
    assert "deferred under" in rendered


def test_nothing_deferred_adds_no_note() -> None:
    """A note on every run would stop carrying information.

    When the campaign that owns the deferral ends, the line must disappear
    rather than announce a zero.
    """
    assert render(_verdict()) == "unused-symbol ratchet: tree matches baseline"


def test_the_deferral_does_not_change_the_verdict() -> None:
    """Deferred findings are excluded from the comparison, not counted as failures.

    If they flipped ``ok``, the deferral would become a permanent red and the
    prefix would stop being a deferral at all.
    """
    assert _verdict(deferred_symbols=22, deferred_tests=2).ok


def test_a_scan_that_cannot_see_the_tree_refuses_rather_than_reporting_progress(tmp_path: Path) -> None:
    """An errored scan must not be read as an empty live set.

    ``run_unreachable_code_scan`` returns an error result for a root it cannot
    read, and an error result carries no symbols. Read straight through, that
    emptiness means nothing grew, nothing was unrecorded, and every baselined
    module came back RESOLVED -- so a gate that never saw the tree did not merely
    pass, it claimed progress and invited the baseline to be shrunk on the
    strength of a scan that never ran. Both sibling gates refuse in this shape.
    """
    with pytest.raises(RuntimeError, match="ratchet unproven"):
        evaluate(tmp_path / "absent")
