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
from pydantic import ValidationError

from dev.release.readiness import ReadinessCheck, ReadinessReport
from dev.release.release_candidate import (
    CANDIDATE_TAG_RE,
    ReleaseCandidate,
    ReleaseCandidateError,
    SoakWindow,
    candidate_tag,
    candidate_tags_in,
    consumed_tag,
    seal_candidate,
)
from dev.release.soak_promoter import promote_once, select_promotable

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


def _clean_report() -> ReadinessReport:
    return ReadinessReport(checks=(ReadinessCheck("version-surfaces-agree", "blocking", True, "all seven agree"),))


def _red_report() -> ReadinessReport:
    return ReadinessReport(
        checks=(ReadinessCheck("distribution-evidence-set", "blocking", False, "scoop row missing for 1.0.0"),)
    )


def test_a_regressed_candidate_is_invalidated_rather_than_promoted() -> None:
    """The re-verification is the point of re-running the gate at promotion time.

    The seal-time gate proved the cohort sound two or three days ago, which is
    not the same claim as "sound now" - that gap is exactly why the soak
    exists. A blocking regression discovered during the window invalidates the
    candidate; it is never repaired in place and never promoted on an expired
    green.
    """
    candidate = _candidate()
    dispatched: list[ReleaseCandidate] = []

    decision = promote_once(
        (candidate,),
        now=candidate.soak_deadline + timedelta(hours=1),
        readiness_for=lambda _: _red_report(),
        dispatch=dispatched.append,
    )

    assert decision.promotes is False
    assert dispatched == [], "a regressed candidate must not reach the dispatch at all"
    assert "invalidated" in decision.reason
    # The refusal names WHICH check reds, so the operator is not left to guess.
    assert "distribution-evidence-set" in decision.reason
    assert "scoop row missing" in decision.reason


def test_a_clean_candidate_is_dispatched_after_re_verification() -> None:
    """Positive control: the refusal above is a verdict, not a promoter that never fires."""
    candidate = _candidate()
    dispatched: list[ReleaseCandidate] = []

    decision = promote_once(
        (candidate,),
        now=candidate.soak_deadline + timedelta(hours=1),
        readiness_for=lambda _: _clean_report(),
        dispatch=dispatched.append,
    )

    assert decision.promotes is True
    assert dispatched == [candidate]


def test_readiness_is_never_consulted_for_a_candidate_still_soaking() -> None:
    """Ordering: the cheap clock check precedes the expensive gate.

    Also a correctness statement rather than only an efficiency one - a gate
    run against a candidate that cannot promote produces a verdict nobody acts
    on, and a red one would be reported as though it mattered now.
    """
    candidate = _candidate()
    consulted: list[ReleaseCandidate] = []

    def _record(subject: ReleaseCandidate) -> ReadinessReport:
        consulted.append(subject)
        return _clean_report()

    decision = promote_once(
        (candidate,),
        now=candidate.soak_deadline - timedelta(hours=1),
        readiness_for=_record,
        dispatch=lambda _: None,
    )

    assert decision.promotes is False
    assert consulted == []


def test_two_overlapping_ticks_dispatch_exactly_once() -> None:
    """Idempotence across ticks: consumption removes the candidate from selection.

    The promoter is scheduled, so a slow tick and its successor can overlap. A
    second dispatch of the same cohort would attempt a second publication of a
    version the first already burned.
    """
    candidate = _candidate()
    forge: list[ReleaseCandidate] = [candidate]
    dispatched: list[ReleaseCandidate] = []
    now = candidate.soak_deadline + timedelta(hours=1)

    for _ in range(2):
        promote_once(
            tuple(forge),
            now=now,
            readiness_for=lambda _: _clean_report(),
            dispatch=dispatched.append,
            consume=forge.remove,
        )

    assert dispatched == [candidate]
    assert forge == []


def test_a_candidate_is_consumed_only_after_its_dispatch_returns() -> None:
    """Ordering: a failed dispatch must leave the candidate selectable.

    Consuming first would retire a candidate whose dispatch then failed,
    stranding a sealed cohort no later tick can select - a release that
    silently never happens. Re-dispatch is the recoverable direction, since the
    identity authority refuses an owned version anyway.
    """
    candidate = _candidate()
    forge: list[ReleaseCandidate] = [candidate]

    def _failing_dispatch(_: ReleaseCandidate) -> None:
        raise RuntimeError("forge dispatch rejected the request")

    with pytest.raises(RuntimeError, match="forge dispatch rejected"):
        promote_once(
            tuple(forge),
            now=candidate.soak_deadline + timedelta(hours=1),
            readiness_for=lambda _: _clean_report(),
            dispatch=_failing_dispatch,
            consume=forge.remove,
        )

    assert forge == [candidate], "a failed dispatch must leave the candidate promotable by a later tick"


def test_the_consumed_tag_leaves_the_selectable_namespace_but_keeps_the_record() -> None:
    """Consumption retags rather than deletes, so the promotion stays auditable.

    The record names which runs produced a published version, which is exactly
    the evidence a later audit needs; deleting it would buy the same idempotence
    at the cost of the trail.
    """
    retired = consumed_tag(candidate_tag("4242"))

    assert retired == "release-candidate-consumed-4242"
    assert CANDIDATE_TAG_RE.fullmatch(retired) is None
    assert candidate_tags_in([{"tag_name": retired, "draft": True}]) == ()


def _hotfix_candidate(*, incident: str = "INC-2026-08-02", approval: str = "release-owner:gergely") -> ReleaseCandidate:
    return seal_candidate(
        cohort_id="a" * 64,
        version="1.2.4",
        source_commit=_COMMIT,
        packaging_run_id="9001",
        claimed_channels=("python",),
        dry_run=False,
        window=_WINDOW,
        opened_at=_OPENED,
        soak_hours_override=6,
        incident_reference=incident,
        release_owner_approval=approval,
    )


def test_an_authorised_hotfix_shortens_the_window() -> None:
    """The carve-out is honoured when its two recorded conditions are present."""
    candidate = _hotfix_candidate()

    assert candidate.hotfix is True
    assert candidate.soak_deadline == _OPENED + timedelta(hours=6)
    # It really is shorter than the standard window, not merely different.
    assert candidate.soak_deadline < _OPENED + timedelta(hours=_WINDOW.minimum_hours)

    decision = select_promotable((candidate,), now=_OPENED + timedelta(hours=7))
    assert decision.promotes is True


def test_a_shortened_window_without_an_incident_reference_is_refused() -> None:
    """A shortening with no incident record cannot exist as a candidate at all."""
    with pytest.raises(ValidationError, match="incident_reference"):
        _hotfix_candidate(incident="   ")


def test_a_shortened_window_without_release_owner_approval_is_refused() -> None:
    """Both authorisations are required, and each is asserted separately.

    Checking only one would let a candidate carrying an incident number but no
    approval through - the shape an automated emergency path would produce by
    accident.
    """
    with pytest.raises(ValidationError, match="release_owner_approval"):
        _hotfix_candidate(approval="")


def test_an_override_that_does_not_shorten_the_window_is_refused() -> None:
    """The carve-out shortens an emergency window; it is not a general dial.

    An override at or above the declared minimum is either a no-op wearing an
    incident number or a way to EXTEND a window through the emergency path,
    and neither is what the policy permits.
    """
    with pytest.raises(ReleaseCandidateError, match="does not shorten"):
        seal_candidate(
            cohort_id="a" * 64,
            version="1.2.4",
            source_commit=_COMMIT,
            packaging_run_id="9001",
            claimed_channels=("python",),
            dry_run=False,
            window=_WINDOW,
            opened_at=_OPENED,
            soak_hours_override=_WINDOW.minimum_hours,
            incident_reference="INC-1",
            release_owner_approval="release-owner:gergely",
        )


def test_a_hotfix_still_faces_the_full_readiness_gate() -> None:
    """The carve-out shortens the CLOCK and weakens no gate.

    The policy allows an emergency to shorten elapsed time only with every
    applicable gate still green, so a hotfix whose readiness reds is
    invalidated exactly like an ordinary candidate. A carve-out that also
    skipped the gate would be the weakening this Step exists to avoid.
    """
    candidate = _hotfix_candidate()
    dispatched: list[ReleaseCandidate] = []

    decision = promote_once(
        (candidate,),
        now=_OPENED + timedelta(hours=7),
        readiness_for=lambda _: _red_report(),
        dispatch=dispatched.append,
    )

    assert decision.promotes is False
    assert dispatched == []
    assert "invalidated" in decision.reason


def test_a_dry_run_candidate_completes_its_soak_and_never_publishes() -> None:
    """The rehearsal proves the whole chain including the wait, and stops there.

    Refused rather than filtered out of selection, deliberately: a silently
    skipped rehearsal candidate is indistinguishable from no candidate having
    been sealed, which is precisely the failure the rehearsal exists to rule
    out. It must be visible in the promoter's own output.
    """
    candidate = seal_candidate(
        cohort_id="a" * 64,
        version="1.2.3",
        source_commit=_COMMIT,
        packaging_run_id="4242",
        claimed_channels=("python",),
        dry_run=True,
        window=_WINDOW,
        opened_at=_OPENED,
    )
    dispatched: list[ReleaseCandidate] = []
    consulted: list[ReleaseCandidate] = []

    def _record(subject: ReleaseCandidate) -> ReadinessReport:
        consulted.append(subject)
        return _clean_report()

    decision = promote_once(
        (candidate,),
        now=candidate.soak_deadline + timedelta(hours=1),
        readiness_for=_record,
        dispatch=dispatched.append,
    )

    assert decision.promotes is False
    assert dispatched == [], "a rehearsal candidate must never reach the publication dispatch"
    assert "dry_run" in decision.reason
    # Selection still ran (the soak was observed) and the refusal happens
    # before the expensive re-verification.
    assert consulted == []


def test_a_rehearsal_candidate_does_not_starve_a_real_one() -> None:
    """The deadlock the honesty review found, pinned so it cannot return.

    A rehearsal seals a REAL draft in the garbage-collector-exempt namespace,
    which is correct for a real candidate and permanent for a rehearsal one.
    Refusing it without retiring it left it selectable forever, so every real
    candidate sealed afterwards sat behind it - and the tick still reported
    success, so nothing alerted.

    The fixture is deliberately multi-candidate with the rehearsal ELDEST, so
    it is selected first. A single-element fixture is what let the original
    bug ship green.
    """
    rehearsal = seal_candidate(
        cohort_id="a" * 64,
        version="9.9.9-rehearsal",
        source_commit=_COMMIT,
        packaging_run_id="100",
        claimed_channels=("python",),
        dry_run=True,
        window=_WINDOW,
        opened_at=_OPENED,
    )
    real = seal_candidate(
        cohort_id="b" * 64,
        version="1.0.0",
        source_commit=_COMMIT,
        packaging_run_id="200",
        claimed_channels=("python",),
        dry_run=False,
        window=_WINDOW,
        opened_at=_OPENED + timedelta(hours=1),
    )
    assert rehearsal.soak_deadline < real.soak_deadline, "the rehearsal must be selected first for this to bite"

    forge: list[ReleaseCandidate] = [rehearsal, real]
    dispatched: list[ReleaseCandidate] = []

    decision = promote_once(
        tuple(forge),
        now=real.soak_deadline + timedelta(hours=1),
        readiness_for=lambda _: _clean_report(),
        dispatch=dispatched.append,
        consume=forge.remove,
    )

    assert decision.promotes is True
    assert decision.candidate == real, "the real candidate must be reached past the rehearsal"
    assert dispatched == [real]
    # The rehearsal is retired out of the selectable set, so it cannot block a
    # later tick either.
    assert forge == []


def test_a_tick_holding_only_a_completed_rehearsal_retires_it_and_says_so() -> None:
    """A rehearsal is still reported, so a dry_run seal stays distinguishable from no seal."""
    rehearsal = seal_candidate(
        cohort_id="a" * 64,
        version="9.9.9-rehearsal",
        source_commit=_COMMIT,
        packaging_run_id="100",
        claimed_channels=("python",),
        dry_run=True,
        window=_WINDOW,
        opened_at=_OPENED,
    )
    forge: list[ReleaseCandidate] = [rehearsal]
    dispatched: list[ReleaseCandidate] = []

    decision = promote_once(
        tuple(forge),
        now=rehearsal.soak_deadline + timedelta(hours=1),
        readiness_for=lambda _: _clean_report(),
        dispatch=dispatched.append,
        consume=forge.remove,
    )

    assert decision.promotes is False
    assert dispatched == []
    assert "dry_run" in decision.reason
    assert forge == [], "a completed rehearsal must not remain selectable"
