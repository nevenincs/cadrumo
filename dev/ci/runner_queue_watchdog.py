"""Fail a run fast when one of its lanes has no runner that can ever serve it.

A self-hosted lane whose label set no online runner carries does not go red. It
QUEUES, silently, presenting as "in progress" for as long as GitHub's 24-hour
job-queue ceiling allows. A Packaging Quick run created 2026-08-04T23:19 was
still queued when it was cancelled by hand at 05:10 the next morning: roughly
six hours in which the only signal available to anybody was a spinner. That is
strictly worse than a failure, because a spinner is indistinguishable from work.

``timeout-minutes`` does not cover this. It bounds a job that is RUNNING; the
clock does not start while a job waits for a runner, so the one control that
looks like it should apply is exactly the one that does not.

The obvious design -- ask GitHub which runners are online and compare label sets
before dispatching -- is not available to a workflow. Measured from inside
Actions rather than assumed (run 31007405350):

    GET /repos/{owner}/{repo}/actions/runners
    HTTP 403 {"message": "Resource not accessible by integration"}
    x-accepted-github-permissions: administration=read

and ``administration`` is not a key the ``permissions:`` block accepts at all --
a workflow declaring it is rejected as malformed and creates no jobs (run
31007402589). So the endpoint demands a permission the workflow token cannot be
granted, and the only route to it would be a long-lived admin PAT held as a
repository secret, which this repository's no-secrets-at-rest posture refuses.

What IS reachable with ``actions: read`` is the run's own job list, and it
carries the two facts the question actually needs: every job's REQUESTED label
set, and whether it is still queued. So the check is not a prediction made
before the fact but an observation made after it -- do not ask whether a runner
exists, watch whether the job ever starts.

Two properties make that observation trustworthy rather than merely plausible.

*A queued job is not necessarily an unschedulable one.* A job also queues when
every runner carrying its labels is busy, and failing on that would be a false
alarm that trains its audience to ignore the real one. The discriminator is that
a label set some other job is RUNNING on is demonstrably schedulable, so a
queued job whose label set is currently occupied is skipped, not flagged.
Occupancy is read repository-wide, not just within the run, because a runner
busy with another run's job is just as much proof that the lane can be served.
That is sound here specifically because every runner on this fleet is
repository-scoped -- the account is a user, not an organisation, so no runner
serves a second repository and "no job of ours is running on it" cannot be
explained away by foreign work.

*A job blocked on ``needs:`` is not queued for a runner.* This was the largest
suspected false-positive class and it turns out not to exist: GitHub does not
create a dependent job's record until its dependencies resolve. Measured in the
same run -- a job gated on the watchdog was created at 12:52:39, four seconds
AFTER the watchdog it waited on completed at 12:52:35, and never appeared in any
earlier poll. Dependency waits are therefore invisible here and need no special
handling.

The residual limit is stated rather than papered over: this cannot distinguish
"no runner carries these labels" from "the only runner carrying them has been
busy with work outside this repository for longer than the threshold". On this
fleet the second cannot happen, but the message says what was observed -- a lane
that did not start and no evidence of that label set being served -- rather than
asserting the stronger claim the evidence does not support.
It deliberately does NOT try to separate "this lane can never be scheduled" (a
label no runner carries, like the Scoop lane's) from "the fleet is temporarily
degraded" (a host asleep). Two reasons. It structurally cannot: the only
endpoint that would answer it is the forbidden one, so any such split would be
guesswork dressed as a distinction. And it should not, because the two differ
only in REMEDY, never in consequence -- a dispatched job on either lane will not
run, and the correct outcome for the run is identical. The split matters to
whoever fixes it (provision a runner, or wake a host), and naming the label set
is what tells them which; it does not matter to the verdict.

The cost of that choice is deliberate and worth stating plainly: while several
label sets are offline, every packaging run that touches them now terminates
within minutes instead of hanging. That looks like a lot of red, and it is the
point -- those runs were never going to produce a result, and the alternative on
offer is not a green run but a silent one. Suppressing the alarm because the
fleet is broadly degraded would rebuild the exact silence this exists to remove,
one level up. What must be protected instead is the check's precision, which is
why it stays quiet for a lane that is merely busy and never reports its own wait.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from .._paths import UTF_8

_API_HOST: Final = "api.github.com"
_API_VERSION: Final = "2022-11-28"
_UTF_8: Final[str] = UTF_8
_TERMINAL_RUN_STATUS: Final = frozenset({"completed"})

# How many in-progress runs to read when building repository-wide occupancy.
# Occupancy only needs to answer "is SOME job running on this label set", so a
# bounded page is sufficient and keeps the poll to a handful of API calls.
_OCCUPANCY_RUN_LIMIT: Final = 20


@dataclass(frozen=True, slots=True)
class JobView:
    """The three facts about a job this check reasons over.

    ``labels`` is the label set the job REQUESTED (``runs-on``), which the jobs
    endpoint reports even while the job is queued and has no runner assigned.
    """

    name: str
    status: str
    labels: tuple[str, ...]
    queued_since_epoch: float

    @property
    def label_key(self) -> tuple[str, ...]:
        """Order-independent identity of the requested label set.

        Runner label ORDER is not significant to scheduling -- a runner
        registered ``[self-hosted, X64, Linux]`` serves a job requesting
        ``[self-hosted, Linux, X64]`` -- so occupancy must compare labels as a
        set, never as the authored sequence.
        """
        return tuple(sorted(self.labels))


@dataclass(frozen=True, slots=True)
class Verdict:
    """One queued job's classification, carrying why it was reached."""

    job_name: str
    label_key: tuple[str, ...]
    waited_seconds: float
    unschedulable: bool
    reason: str


def parse_jobs(payload: Any) -> tuple[JobView, ...]:
    """Project a ``/actions/runs/{id}/jobs`` payload into the facts used here.

    A queued job carries no ``runner_name`` and its ``started_at`` is the moment
    the job record was created, which is precisely when it began waiting for a
    runner. ``created_at`` is preferred when present and ``started_at`` is the
    fallback, because either is the same instant for a queued job and only one
    of them is guaranteed on older payload shapes.
    """
    views: list[JobView] = []
    for job in (payload or {}).get("jobs") or []:
        stamp = job.get("created_at") or job.get("started_at")
        views.append(
            JobView(
                name=str(job.get("name", "")),
                status=str(job.get("status", "")),
                labels=tuple(str(label) for label in job.get("labels") or ()),
                queued_since_epoch=_epoch_of(stamp),
            )
        )
    return tuple(views)


def occupied_label_keys(jobs: Sequence[JobView]) -> frozenset[tuple[str, ...]]:
    """Label sets demonstrably being served right now.

    A label set carrying a job in ``in_progress`` has an online runner behind
    it by construction, so anything else queued against that same set is
    waiting on capacity rather than on a runner that does not exist.
    """
    return frozenset(job.label_key for job in jobs if job.status == "in_progress")


def classify(
    jobs: Sequence[JobView],
    *,
    now_epoch: float,
    threshold_seconds: float,
    watchdog_job_name: str,
    occupied: frozenset[tuple[str, ...]] | None = None,
) -> tuple[Verdict, ...]:
    """Classify every queued job that has waited past the threshold.

    The watchdog excludes ITSELF: it is a job in the same run, and a watchdog
    that reports its own queue wait would fire on nothing but its own existence
    the moment the fleet was merely busy.
    """
    occupancy = occupied_label_keys(jobs) if occupied is None else occupied
    verdicts: list[Verdict] = []
    for job in jobs:
        if job.status != "queued" or job.name == watchdog_job_name:
            continue
        waited = now_epoch - job.queued_since_epoch
        if waited <= threshold_seconds:
            continue
        serving = job.label_key in occupancy
        verdicts.append(
            Verdict(
                job_name=job.name,
                label_key=job.label_key,
                waited_seconds=waited,
                unschedulable=not serving,
                reason=(
                    "another job is running on this label set, so it is schedulable"
                    if serving
                    else "no job anywhere in this repository is running on this label set"
                ),
            )
        )
    return tuple(verdicts)


def _epoch_of(stamp: object) -> float:
    """Parse a GitHub ISO-8601 ``Z`` timestamp to epoch seconds.

    The parse must not consult the local timezone. ``mktime(strptime(...)) -
    timezone`` looks like a UTC conversion and is one only where the machine
    runs UTC without DST: ``mktime`` reads the struct as LOCAL time and applies
    the local DST rule, while ``time.timezone`` is the STANDARD offset and
    carries no DST term, so the two disagree by an hour for half the year.
    Measured on the workstation (Romance Summer Time) it returned an epoch
    3600 s early, which inflates every ``waited`` by an hour -- past the 300 s
    threshold on its own, so a watchdog carrying that parse would flag every
    queued job and cancel its own run. Attaching UTC explicitly is correct on
    any machine's clock, which matters because this runs unattended on a fleet
    spanning three operating systems whose timezone configuration is not this
    module's to assume.
    """
    if not isinstance(stamp, str) or not stamp:
        return 0.0
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()


def _request(path: str, token: str, *, method: str = "GET") -> Any:
    """Call the REST API, returning parsed JSON (or ``None`` for empty bodies).

    A direct HTTPS connection rather than a URL opener, so the transport cannot
    be talked into a ``file:`` or other non-HTTPS scheme by a malformed path:
    the host is fixed and only the request target varies.
    """
    connection = http.client.HTTPSConnection(_API_HOST, timeout=30)
    try:
        connection.request(
            method,
            path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": _API_VERSION,
                "User-Agent": "cadrumo-runner-queue-watchdog",
            },
        )
        body = connection.getresponse().read().decode(_UTF_8)
    finally:
        connection.close()
    return json.loads(body) if body.strip() else None


def _repository_occupancy(repository: str, token: str, own_run_id: str) -> frozenset[tuple[str, ...]]:
    """Label sets being served by any in-progress job across the repository.

    Failure here is deliberately non-fatal and falls back to the run's own
    occupancy: a transient API error must not be able to manufacture an alarm.
    Erring toward "occupied" errs toward silence, which is the correct direction
    for a check whose false alarms would cost it its audience.
    """
    keys: set[tuple[str, ...]] = set()
    try:
        runs = _request(
            f"/repos/{repository}/actions/runs?status=in_progress&per_page={_OCCUPANCY_RUN_LIMIT}",
            token,
        )
        for run in (runs or {}).get("workflow_runs") or []:
            run_id = str(run.get("id"))
            if run_id == own_run_id:
                continue
            payload = _request(f"/repos/{repository}/actions/runs/{run_id}/jobs", token)
            keys.update(occupied_label_keys(parse_jobs(payload)))
    except (OSError, http.client.HTTPException, ValueError, KeyError) as error:  # pragma: no cover - network
        print(f"note: repository-wide occupancy unavailable ({error}); using this run only")
    return frozenset(keys)


def _announce(verdicts: Sequence[Verdict], threshold_seconds: float) -> None:
    """Emit the operator-facing annotation and job summary for a firing."""
    lines = ["## Unschedulable lane detected", ""]
    for verdict in verdicts:
        labels = ", ".join(verdict.label_key)
        if verdict.unschedulable:
            message = (
                f"Job '{verdict.job_name}' has been queued {verdict.waited_seconds:.0f}s "
                f"(threshold {threshold_seconds:.0f}s) requesting a runner labelled "
                f"[{labels}], and {verdict.reason}."
            )
            print(f"::error title=Unschedulable lane::{message}")
            lines.append(f"- **{verdict.job_name}** - `[{labels}]` - {verdict.reason}")
        else:
            print(f"note: skipping '{verdict.job_name}' [{labels}] - {verdict.reason}")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding=_UTF_8, newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Poll the run's jobs and fail when a lane cannot be served.

    Cancelling the run is what converts the hang into a terminal state, and it
    is done deliberately even though it costs the run's conclusion: measured in
    both available shapes (cancel from inside the failing job, and cancel from a
    downstream job gated on its failure), GitHub reports the RUN as ``cancelled``
    rather than ``failure`` whenever a cancel is issued, regardless of a job
    having already failed. The trade was taken knowingly -- a terminal
    ``cancelled`` run carrying a failed job and a named error annotation is a
    far better signal than a green-looking spinner, and no shape available from
    inside a workflow yields ``failure`` without leaving the queue hung.
    """
    del argv
    repository = os.environ["GITHUB_REPOSITORY"]
    run_id = os.environ["GITHUB_RUN_ID"]
    token = os.environ["GH_TOKEN"]
    watchdog_job_name = os.environ.get("WATCHDOG_JOB_NAME", "")
    threshold = float(os.environ.get("THRESHOLD_SECONDS", "300"))
    poll = float(os.environ.get("POLL_SECONDS", "15"))
    window = float(os.environ.get("MAX_WATCH_SECONDS", "900"))

    started = time.monotonic()
    while True:
        payload = _request(f"/repos/{repository}/actions/runs/{run_id}/jobs", token)
        jobs = parse_jobs(payload)
        occupied = occupied_label_keys(jobs) | _repository_occupancy(repository, token, run_id)
        verdicts = classify(
            jobs,
            now_epoch=time.time(),
            threshold_seconds=threshold,
            watchdog_job_name=watchdog_job_name,
            occupied=occupied,
        )
        queued = [job.name for job in jobs if job.status == "queued" and job.name != watchdog_job_name]
        print(f"poll +{time.monotonic() - started:.0f}s | queued={len(queued)} | occupied={sorted(occupied)}")

        if any(verdict.unschedulable for verdict in verdicts):
            _announce(verdicts, threshold)
            _cancel(repository, run_id, token)
            return 1
        for verdict in verdicts:
            print(f"note: skipping '{verdict.job_name}' - {verdict.reason}")

        run = _request(f"/repos/{repository}/actions/runs/{run_id}", token)
        if str((run or {}).get("status")) in _TERMINAL_RUN_STATUS:
            print("watched run reached a terminal status; nothing queued indefinitely")
            return 0
        if time.monotonic() - started > window:
            print(f"watch window of {window:.0f}s elapsed with no unschedulable lane; standing down")
            return 0
        time.sleep(poll)


def _cancel(repository: str, run_id: str, token: str) -> None:
    """Stop the remaining queued jobs so the run terminates instead of hanging."""
    try:
        _request(f"/repos/{repository}/actions/runs/{run_id}/cancel", token, method="POST")
        print(f"cancelled run {run_id} so its unschedulable jobs stop occupying the queue")
    except (OSError, http.client.HTTPException, ValueError) as error:  # pragma: no cover - network
        print(f"warning: could not cancel run {run_id} ({error})")


if __name__ == "__main__":  # pragma: no cover - entrypoint
    sys.exit(main())
