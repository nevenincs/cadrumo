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

import argparse
import shutil
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dev.packaging.evidence_release import (
    EvidenceLane,
    download_release_assets,
    evidence_tag,
    resolve_gh,
    run_gh_with_retry,
)
from dev.release.readiness import ReadinessReport, build_report
from dev.release.release_candidate import (
    ReleaseCandidate,
    fetch_candidate,
    list_sealed_candidate_tags,
    mark_candidate_consumed,
)


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
    # Return type is `object`, not `None`: the real consumer returns the retired
    # tag it moved the candidate to, and the promoter has no use for it. Pinning
    # `None` here would force a callsite to discard a genuinely useful value.
    consume: Callable[[ReleaseCandidate], object] | None = None,
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
    if candidate.dry_run:
        # A rehearsal candidate proves the chain end to end and must never
        # publish. It is refused here rather than filtered out of selection, so
        # the rehearsal is VISIBLE in the promoter's output: silently skipping
        # it would make a dry_run seal indistinguishable from no seal at all,
        # which is the failure the whole rehearsal exists to rule out.
        return PromotionDecision(
            None,
            f"{candidate.version} is a dry_run rehearsal candidate; its soak completed and it will never publish",
        )

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


def readiness_for_sealed_cohort(
    candidate: ReleaseCandidate,
    *,
    repository: str,
    workspace: Path,
    repo_root: Path,
    gh_executable: str | None = None,
) -> ReadinessReport:
    """Re-run the readiness gate against the candidate's SEALED bytes.

    The cohort and its evidence rows are re-downloaded from the smoke run's
    evidence draft and the gate is pointed at those, never at the working tree:
    the question is whether the exact bytes that will ship are still sound, and
    a working-tree default would answer a different question with the same
    green.
    """
    rows = workspace / "rows"
    cohort = workspace / "cohort"
    raw = workspace / "raw"
    for directory in (rows, cohort, raw):
        directory.mkdir(parents=True, exist_ok=True)

    gh = resolve_gh(gh_executable)
    download_release_assets(
        gh,
        repository=repository,
        tag=evidence_tag(EvidenceLane.SMOKE, candidate.packaging_run_id),
        patterns=[],
        directory=raw,
    )
    tarball = raw / "cadrumo-release-cohort.tar.gz"
    with tarfile.open(tarball) as archive:
        archive.extractall(cohort, filter="data")
    for row in raw.glob("*.json"):
        if row.name != "evidence-manifest.json" and not row.name.startswith("debug-"):
            shutil.copy(row, rows / row.name)

    return build_report(
        repo_root,
        gh_executable=gh_executable,
        cohort_directory=cohort,
        evidence_directory=rows,
    )


def dispatch_publication(candidate: ReleaseCandidate, *, repository: str, gh_executable: str | None = None) -> None:
    """Dispatch the publication authority with the run ids the candidate recorded.

    This presses exactly the button an operator would. It adds no trust path:
    Gate 2 verifies every supplied run independently, exactly as it verifies a
    hand-typed one, and it cannot be mistyped here because nothing retypes it.
    """
    gh = resolve_gh(gh_executable)
    arguments = [
        "workflow",
        "run",
        "publish-release.yml",
        "--repo",
        repository,
        "--ref",
        "main",
        "-f",
        f"packaging_run_id={candidate.packaging_run_id}",
        "-f",
        f"dry_run={'true' if candidate.dry_run else 'false'}",
    ]
    for field, value in (
        ("scoop_run_id", candidate.scoop_run_id),
        ("homebrew_run_id", candidate.homebrew_run_id),
        ("claude_evidence_release", candidate.claude_evidence_release),
    ):
        if value:
            arguments.extend(["-f", f"{field}={value}"])
    run_gh_with_retry(gh, arguments)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one promoter tick against the live forge.

    Exit status is 0 for any DECIDED tick, including one that promotes nothing:
    most ticks land inside some candidate's window, and making the ordinary
    case non-zero would train whoever reads the alerting channel to ignore it.
    """
    parser = argparse.ArgumentParser(description="Promote the first sealed candidate whose soak window has closed.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--gh", default=None)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    tags = list_sealed_candidate_tags(repository=args.repository, gh_executable=args.gh)

    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(scratch)
        candidates = tuple(
            fetch_candidate(
                tag,
                repository=args.repository,
                download_directory=workspace / "records" / tag,
                gh_executable=args.gh,
            )
            for tag in tags
        )

        if args.report_only:
            decision = select_promotable(candidates, now=datetime.now(UTC))
            print(decision.reason)
            return 0

        decision = promote_once(
            candidates,
            now=datetime.now(UTC),
            readiness_for=lambda candidate: readiness_for_sealed_cohort(
                candidate,
                repository=args.repository,
                workspace=workspace / "verify" / candidate.packaging_run_id,
                repo_root=repo_root,
                gh_executable=args.gh,
            ),
            dispatch=lambda candidate: dispatch_publication(
                candidate,
                repository=args.repository,
                gh_executable=args.gh,
            ),
            consume=lambda candidate: mark_candidate_consumed(
                candidate.tag,
                repository=args.repository,
                gh_executable=args.gh,
            ),
        )

    print(decision.reason)
    return 0


__all__ = [
    "PromotionDecision",
    "dispatch_publication",
    "main",
    "promote_once",
    "readiness_for_sealed_cohort",
    "select_promotable",
]


if __name__ == "__main__":
    raise SystemExit(main())
