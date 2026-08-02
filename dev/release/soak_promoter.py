"""Cross the soak boundary with a clock instead of a person.

The release-candidate soak is a wall-clock constraint on an immutable cohort,
not a human-review constraint: nothing in the policy asks for a person, only
for elapsed time against bytes that did not change. Reading it as a checkpoint
is what made it look incompatible with a single dispatch.

This module is the waiter. It runs as a short-lived scheduled tick, reads the
sealed candidates the orchestrator left on the forge, and promotes the first
one whose window has closed. Nothing here holds a runner across the window, and
no human re-enters the loop to cross it.

Two failures are possible and only one is loud. Publishing LATE is visible: a
candidate sits, someone asks why. Publishing EARLY is silent -- the release
happens, looks ordinary, and the soak simply did not occur. Every comparison
here is therefore written and tested against the early case first.

See Also:
    :func:`select_promotable`
        The selection decision, pure over already-loaded candidates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from dev.release.readiness import ReadinessReport
from dev.release.release_candidate import ReleaseCandidate


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """The outcome of one promoter tick.

    ``candidate`` is ``None`` when nothing may promote, and ``reason`` always
    explains why in operator-facing terms. A tick that promotes nothing is an
    ordinary, expected result -- most ticks land inside some candidate's window
    -- so it is never an error.
    """

    candidate: ReleaseCandidate | None
    reason: str

    @property
    def promotes(self) -> bool:
        """Whether this tick has a candidate to dispatch."""
        return self.candidate is not None


def select_promotable(candidates: tuple[ReleaseCandidate, ...], *, now: datetime) -> PromotionDecision:
    """Return the eldest candidate whose soak window has closed at ``now``.

    Eldest by soak deadline, not by discovery order: two candidates can be
    sealed close together, and promoting the newer one first would leave the
    older sitting behind a version the newer already burned.

    A candidate still inside its window is not merely skipped, it is REFUSED,
    and the refusal names the remaining time. The distinction matters because
    "nothing to do" and "something is waiting" look identical in a log that
    only reports the promotion.
    """
    if not candidates:
        return PromotionDecision(None, "no sealed candidates on the forge")

    elapsed = [candidate for candidate in candidates if candidate.window_elapsed(now=now)]
    if not elapsed:
        soonest = min(candidates, key=lambda candidate: candidate.soak_deadline)
        remaining = soonest.soak_deadline - now
        return PromotionDecision(
            None,
            f"{len(candidates)} candidate(s) still soaking; "
            f"soonest is {soonest.version} with {remaining} remaining until {soonest.soak_deadline.isoformat()}",
        )

    chosen = min(elapsed, key=lambda candidate: (candidate.soak_deadline, candidate.packaging_run_id))
    return PromotionDecision(chosen, f"{chosen.version} completed its soak at {chosen.soak_deadline.isoformat()}")


def promote_once(
    candidates: tuple[ReleaseCandidate, ...],
    *,
    now: datetime,
    readiness_for: Callable[[ReleaseCandidate], ReadinessReport],
    dispatch: Callable[[ReleaseCandidate], None],
    consume: Callable[[ReleaseCandidate], None] | None = None,
) -> PromotionDecision:
    """Run one promoter tick: select, RE-VERIFY, then dispatch.

    The readiness gate is re-run against the sealed cohort immediately before
    the dispatch, and this is the point of the whole function. The gate that
    ran at seal time proved the cohort sound two or three days ago; the soak
    policy exists precisely because that is not the same claim as "sound now".
    A blocking regression discovered during the window invalidates the
    candidate -- it is never repaired in place, and it must never be promoted
    on the strength of a green that has since expired.

    The ordering is deliberate: nothing is dispatched before the re-check, so a
    candidate that regressed is refused with its failures named rather than
    published and then reported.
    """
    decision = select_promotable(candidates, now=now)
    if decision.candidate is None:
        return decision

    candidate = decision.candidate
    report = readiness_for(candidate)
    if blocking := report.blocking_failures:
        named = "; ".join(f"{check.name}: {check.detail}" for check in blocking)
        return PromotionDecision(
            None,
            f"{candidate.version} completed its soak but its readiness gate now reds, "
            f"so the candidate is invalidated rather than promoted: {named}",
        )

    dispatch(candidate)
    # Consumed only AFTER the dispatch returns. The reverse order would retire
    # a candidate whose dispatch then failed, stranding a sealed cohort that no
    # later tick can ever select again -- a release that silently never
    # happens. This ordering can at worst re-dispatch (the unchanged
    # version-identity authority refuses an owned version, and the publication
    # itself converges per destination), which is the recoverable direction.
    if consume is not None:
        consume(candidate)
    return PromotionDecision(candidate, f"{candidate.version} promoted after a clean re-verification")


__all__ = ["PromotionDecision", "promote_once", "select_promotable"]
