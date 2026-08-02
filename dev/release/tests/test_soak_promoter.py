"""Behavioural proof for the machine-held soak boundary.

Every test here is written against the EARLY-publication failure first. A
promoter that publishes late is self-reporting: the candidate sits and someone
asks why. A promoter that publishes early is silent - the release happens, it
looks ordinary, and the soak simply did not occur - so the boundary comparison
is exercised on both sides and exactly at the edge.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dev.release.release_candidate import ReleaseCandidate, SoakWindow, seal_candidate
from dev.release.soak_promoter import select_promotable

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_COMMIT = "b" * 40
_WINDOW = SoakWindow(minimum_hours=48, maximum_hours=72)
_OPENED = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _candidate(*, run_id: str = "4242", version: str = "1.2.3", opened_at: datetime = _OPENED) -> ReleaseCandidate:
    return seal_candidate(
        cohort_id="a" * 64,
        version=version,
        source_commit=_COMMIT,
        packaging_run_id=run_id,
        claimed_channels=("python",),
        dry_run=False,
        window=_WINDOW,
        opened_at=opened_at,
    )


def test_an_elapsed_candidate_is_selected() -> None:
    """The ordinary promotion: the window closed, so the candidate may publish."""
    candidate = _candidate()

    decision = select_promotable((candidate,), now=candidate.soak_deadline + timedelta(hours=1))

    assert decision.promotes is True
    assert decision.candidate == candidate
    assert "completed its soak" in decision.reason


def test_a_candidate_still_inside_its_window_is_refused() -> None:
    """The failure this mechanism exists to prevent, and it must be explicit.

    Refused rather than silently skipped: "nothing to do" and "something is
    waiting" are indistinguishable in a log that only reports promotions, and
    the difference is the entire operational signal during a soak.
    """
    candidate = _candidate()

    decision = select_promotable((candidate,), now=candidate.soak_deadline - timedelta(hours=1))

    assert decision.promotes is False
    assert decision.candidate is None
    assert "still soaking" in decision.reason
    assert candidate.soak_deadline.isoformat() in decision.reason


def test_the_boundary_instant_counts_as_served() -> None:
    """Exactly at the deadline the declared minimum has been served, so it promotes.

    Both neighbours are asserted, because an off-by-one here is invisible in
    production: one second early publishes against an unserved window, one
    second late makes every window quietly longer than the policy states.
    """
    candidate = _candidate()

    assert select_promotable((candidate,), now=candidate.soak_deadline).promotes is True
    assert select_promotable((candidate,), now=candidate.soak_deadline - timedelta(seconds=1)).promotes is False
    assert select_promotable((candidate,), now=candidate.soak_deadline + timedelta(seconds=1)).promotes is True


def test_an_empty_candidate_set_reports_nothing_to_do_rather_than_failing() -> None:
    """Most ticks find nothing. That is the expected state, never an error."""
    decision = select_promotable((), now=datetime(2026, 8, 5, tzinfo=UTC))

    assert decision.promotes is False
    assert "no sealed candidates" in decision.reason


def test_the_eldest_elapsed_candidate_wins() -> None:
    """Two elapsed candidates promote oldest-first.

    Newest-first would leave the older candidate stranded behind a version the
    newer one already burned, and the identity guard would then refuse it
    forever - a permanent stall produced entirely by selection order.
    """
    older = _candidate(run_id="100", version="1.0.0", opened_at=_OPENED)
    newer = _candidate(run_id="200", version="1.1.0", opened_at=_OPENED + timedelta(hours=6))

    decision = select_promotable((newer, older), now=_OPENED + timedelta(hours=100))

    assert decision.candidate == older


def test_a_mixed_set_promotes_only_the_elapsed_one() -> None:
    """An open window on a NEWER candidate never blocks an elapsed older one."""
    elapsed = _candidate(run_id="100", version="1.0.0", opened_at=_OPENED)
    soaking = _candidate(run_id="200", version="1.1.0", opened_at=_OPENED + timedelta(hours=40))

    decision = select_promotable((soaking, elapsed), now=_OPENED + timedelta(hours=49))

    assert decision.promotes is True
    assert decision.candidate == elapsed
    # Control: the second candidate really is still soaking at this instant, so
    # the assertion above is a selection result rather than a coincidence.
    assert soaking.window_elapsed(now=_OPENED + timedelta(hours=49)) is False
