"""Fire-and-forget workflow dispatch, MY-run resolution, and a cheap conclusion poll.

``gh workflow run`` returns no run id, and this tree has no prior precedent
for resolving the run a dispatch started: ``packaging-campaign-trigger.yml``
fires and forgets. ``packaging-smoke.yml`` queues rather than cancels on a
newer dispatch, so a naive "newest run of this workflow" query can return a
neighbour's competing run rather than this dispatch's own — the
identify-MY-run hazard this module exists to close. It closes both gaps:

* :func:`dispatch_workflow` fires the dispatch and returns nothing — there is
  nothing to return.
* :func:`resolve_dispatched_run` matches the run the dispatch started by
  workflow path, head commit, the ``workflow_dispatch`` event, and a
  created-after timestamp the caller captures BEFORE dispatching. Zero matches
  raises :class:`RunNotYetVisibleError` (retryable: the run has not appeared
  in the API yet). More than one match raises :class:`RunResolutionError`
  naming every candidate — a competing run landed in the same window, and this
  module never guesses which is "mine".
* :func:`dispatch_and_resolve` composes both, dispatching the exact immutable
  ``head_sha`` it will use for resolution and capturing the created-after
  timestamp itself immediately before dispatching.
* :func:`wait_for_run` and :func:`wait_for_conclusion` wrap resolution and
  conclusion polling in a bounded exponential-backoff loop against an
  INJECTABLE clock and sleep function, so a test proves timeout behaviour with
  no real waiting, and so production sizing stays a cheap poll rather than a
  busy hold. The fleet is four self-hosted runners shared across products; a
  waiting orchestrator occupies one for the length of the campaign it watches,
  so a badly sized wait starves the fleet for hours per release.

See Also:
    :mod:`dev.release._asset_transport`
        The sibling per-run identity verification (Gate 2-shape) this
        module's resolved run id feeds into; every dispatched run is checked
        exactly as a hand-typed one is, so a machine-supplied run id carries
        no more trust than an operator-typed one.
    :mod:`dev.release.environment_inventory`
        The other read-only ``gh api`` probe in this package, sharing the
        explicit-executable injection pattern for testability.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from .._paths import UTF_8
from ..packaging._command import run_command

_GH_TIMEOUT_SECONDS: Final[float] = 60.0
_DEFAULT_REPO_SLUG: Final[str] = "nevenincs/cadrumo"
_UTF_8: Final[str] = UTF_8

#: Bounded backoff poll defaults. A cheap poll on a short-lived job: the fleet
#: is four self-hosted runners shared across products, so a poll that busy-holds
#: a runner for a 90-minute campaign starves it.
DEFAULT_INITIAL_INTERVAL_SECONDS: Final[float] = 5.0
DEFAULT_MAX_INTERVAL_SECONDS: Final[float] = 60.0
DEFAULT_BACKOFF_FACTOR: Final[float] = 2.0


class RunResolutionError(RuntimeError):
    """A dispatch, resolution, or wait invariant failed; the message names the mismatch."""


class RunNotYetVisibleError(RunResolutionError):
    """No run matching the dispatch has appeared in the Actions API yet.

    Distinct from :class:`RunResolutionError` proper so a bounded poll can
    retry this specific outcome while still raising immediately on a hard
    failure such as ambiguity or a ``gh`` invocation error.
    """


class PollBudgetExhaustedError(RunResolutionError):
    """A bounded poll exhausted its budget without a successful attempt."""


def _default_clock() -> datetime:
    """Return the real current UTC instant; the production default for every ``now`` parameter."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class DispatchedRun:
    """The single run resolved as belonging to one dispatch."""

    run_id: str
    workflow_path: str
    head_sha: str
    html_url: str


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """A resolved run's terminal state.

    Carries any conclusion — success, failure, or cancellation all resolve
    normally. Interpreting the outcome is the caller's job: what a failed
    acquisition lane should do differs from what a failed campaign should do,
    and this module stays a mechanism, not a policy.
    """

    run_id: str
    workflow_path: str
    status: str
    conclusion: str | None


@dataclass(frozen=True, slots=True)
class PollBudget:
    """A bounded exponential-backoff poll budget.

    Sized as a cheap poll on a short-lived job, never a busy hold: the fleet is
    four self-hosted runners shared across products, and a waiting orchestrator
    occupies one for the length of the campaign it watches.
    """

    total_seconds: float
    initial_interval_seconds: float = DEFAULT_INITIAL_INTERVAL_SECONDS
    max_interval_seconds: float = DEFAULT_MAX_INTERVAL_SECONDS
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR

    def __post_init__(self) -> None:
        """Validate the declared budget, refusing a non-positive or degenerate configuration."""
        if self.total_seconds <= 0:
            raise RunResolutionError(f"poll budget total_seconds must be positive, got {self.total_seconds}")
        if self.initial_interval_seconds <= 0 or self.max_interval_seconds <= 0:
            raise RunResolutionError("poll budget interval bounds must be positive")
        if self.backoff_factor < 1:
            raise RunResolutionError(f"poll budget backoff_factor must be >= 1, got {self.backoff_factor}")


def _resolve_gh(gh_executable: str | None) -> str:
    resolved = gh_executable if gh_executable is not None else shutil.which("gh")
    if resolved is None:
        raise RunResolutionError("gh (GitHub CLI) not found on PATH; pass an explicit executable")
    return resolved


def _run_gh(gh: str, arguments: Sequence[str]) -> str:
    """Run one real ``gh`` subprocess and return stdout, raising on failure."""
    try:
        result = run_command([gh, *arguments], cwd=Path.cwd(), timeout_seconds=_GH_TIMEOUT_SECONDS)
    except OSError as error:
        raise RunResolutionError(f"gh executable {gh!r} could not be run: {error}") from error
    if result.returncode != 0:
        raise RunResolutionError(
            f"gh {' '.join(arguments)} failed (rc={result.returncode}): {result.stderr.strip()[:500]}",
        )
    return result.stdout


def _canonical_commit_sha(value: str, *, field_name: str) -> str:
    """Return one immutable full commit SHA in GitHub's lowercase spelling.

    Validation belongs before dispatch, not only in run resolution: accepting a
    branch name or malformed token long enough to invoke ``gh workflow run``
    creates an external side effect that the later resolver can never undo.
    """
    if len(value) != 40 or not all(character in "0123456789abcdefABCDEF" for character in value):
        raise RunResolutionError(f"{field_name} must be one full 40-character commit SHA, got {value!r}")
    return value.lower()


def dispatch_workflow(
    workflow_path: str,
    *,
    ref: str,
    inputs: Mapping[str, str] | None = None,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
) -> None:
    """Fire ``gh workflow run`` for one workflow.

    Returns nothing: ``gh workflow run`` itself yields no run id — that is the
    entire reason :func:`resolve_dispatched_run` exists. Callers wanting strict
    happens-before semantics must capture their own created-after timestamp
    BEFORE calling this function (:func:`dispatch_and_resolve` does this).
    """
    immutable_ref = _canonical_commit_sha(ref, field_name="ref")
    gh = _resolve_gh(gh_executable)
    arguments = ["workflow", "run", workflow_path, "--repo", repo_slug, "--ref", immutable_ref]
    for key, value in sorted((inputs or {}).items()):
        arguments += ["-f", f"{key}={value}"]
    _run_gh(gh, arguments)


def _parse_run_records(raw: str) -> tuple[dict[str, object], ...]:
    return tuple(json.loads(line) for line in raw.splitlines() if line.strip())


def list_workflow_runs(
    workflow_path: str,
    *,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
) -> tuple[dict[str, object], ...]:
    """Return every run record the Actions API reports for ``workflow_path``.

    ``workflow_path`` is the full ``.github/workflows/<file>.yml`` path; the
    Actions API workflow-runs endpoint takes the bare filename, so it is
    derived here rather than demanded twice from callers.
    """
    gh = _resolve_gh(gh_executable)
    workflow_file = workflow_path.rsplit("/", 1)[-1]
    raw = _run_gh(
        gh,
        [
            "api",
            f"repos/{repo_slug}/actions/workflows/{workflow_file}/runs",
            "--paginate",
            "--jq",
            ".workflow_runs[] | {id, path, head_sha, created_at, status, conclusion, event, "
            "head_repository: .head_repository.full_name, html_url}",
        ],
    )
    return _parse_run_records(raw)


def _parse_created_at(record: Mapping[str, object]) -> datetime:
    raw = record.get("created_at")
    if not isinstance(raw, str):
        raise RunResolutionError(f"run record carries no created_at timestamp: {record!r}")
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def resolve_dispatched_run(
    *,
    workflow_path: str,
    head_sha: str,
    created_after: datetime,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    run_records: Sequence[Mapping[str, object]] | None = None,
    gh_executable: str | None = None,
) -> DispatchedRun:
    """Resolve the ONE run this dispatch started; refuse rather than guess.

    Matches on workflow path, head commit, the ``workflow_dispatch`` event, and
    a creation time at or after ``created_after`` (captured by the caller
    BEFORE the dispatch). Zero matches raises :class:`RunNotYetVisibleError` —
    the run has not appeared in the API yet, and a caller polling via
    :func:`wait_for_run` retries this outcome specifically. More than one match
    raises :class:`RunResolutionError` naming every candidate:
    ``packaging-smoke.yml`` queues rather than cancels a competing dispatch, so
    the newest run at this commit may belong to a neighbour, and this function
    never promotes one candidate over another by guessing.

    ``run_records`` is the test injection point. Production omits it and the
    records are fetched live via :func:`list_workflow_runs`.

    Raises:
        RunResolutionError: ``head_sha`` is malformed, more than one run
            matches, or the live ``gh`` call fails.
        RunNotYetVisibleError: No run matches yet.
    """
    canonical_head_sha = _canonical_commit_sha(head_sha, field_name="head_sha")
    records = (
        run_records
        if run_records is not None
        else list_workflow_runs(workflow_path, repo_slug=repo_slug, gh_executable=gh_executable)
    )
    candidates = [
        record
        for record in records
        if record.get("path") == workflow_path
        and record.get("head_sha") == canonical_head_sha
        and str(record.get("event")) == "workflow_dispatch"
        and _parse_created_at(record) >= created_after
    ]
    if not candidates:
        raise RunNotYetVisibleError(
            f"no workflow_dispatch run of {workflow_path!r} at {canonical_head_sha!r} created at/after "
            f"{created_after.isoformat()} is visible yet",
        )
    if len(candidates) > 1:
        ids = sorted(str(candidate.get("id")) for candidate in candidates)
        raise RunResolutionError(
            f"ambiguous dispatch: {len(candidates)} workflow_dispatch run(s) of {workflow_path!r} at "
            f"{canonical_head_sha!r} created at/after {created_after.isoformat()} match: {ids}. Refusing to guess "
            "which is this dispatch's own run — a competing dispatch queued in the same window.",
        )
    record = candidates[0]
    return DispatchedRun(
        run_id=str(record["id"]),
        workflow_path=workflow_path,
        head_sha=canonical_head_sha,
        html_url=str(record.get("html_url", "")),
    )


def _poll_until[T](
    attempt: Callable[[], T],
    *,
    not_ready: type[Exception],
    budget: PollBudget,
    now: Callable[[], datetime],
    sleep: Callable[[float], None],
    watching: str,
) -> T:
    """Retry ``attempt`` on ``not_ready`` with exponential backoff until the budget is spent.

    Any exception other than ``not_ready`` propagates immediately and is never
    retried — an ambiguous-run refusal, for instance, is a hard failure the
    poll must not paper over by waiting it out. Always tries at least once,
    even when the budget is already spent at entry.
    """
    deadline = now() + timedelta(seconds=budget.total_seconds)
    interval = budget.initial_interval_seconds
    while True:
        try:
            return attempt()
        except not_ready as error:
            remaining = (deadline - now()).total_seconds()
            if remaining <= 0:
                raise PollBudgetExhaustedError(
                    f"{watching} did not become ready within {budget.total_seconds:.0f}s: {error}",
                ) from error
            sleep(max(0.0, min(interval, remaining)))
            interval = min(interval * budget.backoff_factor, budget.max_interval_seconds)


def wait_for_run(
    *,
    workflow_path: str,
    head_sha: str,
    created_after: datetime,
    budget: PollBudget,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
    list_runs: Callable[[], Sequence[Mapping[str, object]]] | None = None,
    now: Callable[[], datetime] = _default_clock,
    sleep: Callable[[float], None] = time.sleep,
) -> DispatchedRun:
    """Poll :func:`resolve_dispatched_run` until the dispatch's own run is visible.

    ``list_runs`` is the test injection point, called fresh on every attempt so
    a fixture can hand back a different snapshot per poll — including a
    competing run appearing on a later attempt, the exact identify-MY-run
    hazard this module exists to close. A resolution ambiguity is NOT
    retried: it propagates immediately, because
    waiting longer cannot resolve which run is this dispatch's own.
    """

    def attempt() -> DispatchedRun:
        records = list_runs() if list_runs is not None else None
        return resolve_dispatched_run(
            workflow_path=workflow_path,
            head_sha=head_sha,
            created_after=created_after,
            repo_slug=repo_slug,
            run_records=records,
            gh_executable=gh_executable,
        )

    return _poll_until(
        attempt,
        not_ready=RunNotYetVisibleError,
        budget=budget,
        now=now,
        sleep=sleep,
        watching=f"dispatch of {workflow_path!r} at {head_sha!r}",
    )


def dispatch_and_resolve(
    workflow_path: str,
    *,
    head_sha: str,
    inputs: Mapping[str, str] | None = None,
    resolve_budget: PollBudget,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
    list_runs: Callable[[], Sequence[Mapping[str, object]]] | None = None,
    now: Callable[[], datetime] = _default_clock,
    sleep: Callable[[float], None] = time.sleep,
) -> DispatchedRun:
    """Dispatch one workflow and resolve the run IT started.

    Captures ``created_after`` from ``now()`` immediately before dispatching,
    dispatches the workflow at the same immutable ``head_sha`` resolution will
    match, then polls for that run. A mutable branch ref is deliberately not an
    option here: if ``main`` advances between the release bump and dispatch,
    dispatching ``main`` while resolving the bumped SHA can never converge.
    This is the single entry point the orchestrator is expected to call;
    :func:`dispatch_workflow` and :func:`resolve_dispatched_run` stay exposed
    separately for finer-grained composition and testing.
    """
    canonical_head_sha = _canonical_commit_sha(head_sha, field_name="head_sha")
    created_after = now()
    dispatch_workflow(
        workflow_path,
        ref=canonical_head_sha,
        inputs=inputs,
        repo_slug=repo_slug,
        gh_executable=gh_executable,
    )
    return wait_for_run(
        workflow_path=workflow_path,
        head_sha=canonical_head_sha,
        created_after=created_after,
        budget=resolve_budget,
        repo_slug=repo_slug,
        gh_executable=gh_executable,
        list_runs=list_runs,
        now=now,
        sleep=sleep,
    )


class _RunNotConcludedError(RunResolutionError):
    """Internal retry signal: the run has not reached ``status=completed`` yet."""


def fetch_run(
    run_id: str,
    *,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
) -> dict[str, object]:
    """Return the live Actions API record for one run id."""
    gh = _resolve_gh(gh_executable)
    raw = _run_gh(gh, ["api", f"repos/{repo_slug}/actions/runs/{run_id}"])
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RunResolutionError(f"run {run_id} returned a non-object payload: {payload!r}")
    return payload


def wait_for_conclusion(
    run: DispatchedRun,
    *,
    budget: PollBudget,
    repo_slug: str = _DEFAULT_REPO_SLUG,
    gh_executable: str | None = None,
    fetch: Callable[[], Mapping[str, object]] | None = None,
    now: Callable[[], datetime] = _default_clock,
    sleep: Callable[[float], None] = time.sleep,
) -> RunOutcome:
    """Poll a resolved run until it concludes, refusing instructively on budget exhaustion.

    Returns the outcome for ANY conclusion — success, failure, and cancellation
    all resolve normally; only a run that never reaches ``status=completed``
    inside its budget raises, naming the run it was watching. Sized as a cheap
    poll on a short-lived job: a waiting orchestrator occupies one of four
    shared self-hosted runner slots for the whole campaign it watches.

    ``fetch`` is the test injection point, called fresh on every attempt.
    """

    def attempt() -> RunOutcome:
        record = (
            fetch() if fetch is not None else fetch_run(run.run_id, repo_slug=repo_slug, gh_executable=gh_executable)
        )
        status = str(record.get("status"))
        if status != "completed":
            raise _RunNotConcludedError(f"run {run.run_id} status is {status!r}, not yet completed")
        conclusion = record.get("conclusion")
        return RunOutcome(
            run_id=run.run_id,
            workflow_path=run.workflow_path,
            status=status,
            conclusion=str(conclusion) if conclusion is not None else None,
        )

    try:
        return _poll_until(
            attempt,
            not_ready=_RunNotConcludedError,
            budget=budget,
            now=now,
            sleep=sleep,
            watching=f"run {run.run_id} of {run.workflow_path!r}",
        )
    except PollBudgetExhaustedError as error:
        raise RunResolutionError(
            f"run {run.run_id} of {run.workflow_path!r} ({run.html_url}) did not reach a conclusion within "
            f"{budget.total_seconds:.0f}s",
        ) from error


__all__ = [
    "DEFAULT_BACKOFF_FACTOR",
    "DEFAULT_INITIAL_INTERVAL_SECONDS",
    "DEFAULT_MAX_INTERVAL_SECONDS",
    "DispatchedRun",
    "PollBudget",
    "PollBudgetExhaustedError",
    "RunNotYetVisibleError",
    "RunOutcome",
    "RunResolutionError",
    "dispatch_and_resolve",
    "dispatch_workflow",
    "fetch_run",
    "list_workflow_runs",
    "resolve_dispatched_run",
    "wait_for_conclusion",
    "wait_for_run",
]


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch one workflow, resolve MY run, wait for it, and report the outcome.

    This is the entry point the release orchestrator invokes per chained stage.
    It composes the three library steps in the only safe order: capture the
    clock, dispatch, then resolve the run started AFTER that instant at this
    head commit.

    Resolving by identity rather than recency is the whole point. The packaging
    campaign queues rather than cancels on a newer dispatch, so the newest run
    of that workflow can easily belong to a neighbouring campaign; promoting it
    would carry a cohort this release never built.

    Exits non-zero when the dispatched run did not succeed, so a failed stage
    stops the chain rather than letting it seal a candidate over a red campaign.
    """
    parser = argparse.ArgumentParser(description="Dispatch a workflow and wait for the run this dispatch started.")
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--input", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--repository", default=_DEFAULT_REPO_SLUG)
    parser.add_argument("--resolve-seconds", type=float, default=600.0)
    parser.add_argument("--conclude-seconds", type=float, default=7200.0)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT", ""))
    parser.add_argument("--output-name", default="run_id")
    args = parser.parse_args(argv)

    inputs: dict[str, str] = {}
    for pair in args.input:
        key, separator, value = pair.partition("=")
        if not separator:
            raise RunResolutionError(f"--input expects KEY=VALUE, got {pair!r}")
        inputs[key] = value

    run = dispatch_and_resolve(
        args.workflow,
        head_sha=args.head_sha,
        inputs=inputs,
        resolve_budget=PollBudget(total_seconds=args.resolve_seconds),
        repo_slug=args.repository,
    )
    print(f"resolved {args.workflow} run {run.run_id}")

    outcome = wait_for_conclusion(
        run,
        budget=PollBudget(total_seconds=args.conclude_seconds),
        repo_slug=args.repository,
    )
    print(f"run {run.run_id} concluded {outcome.conclusion}")

    if args.github_output:
        with Path(args.github_output).open("a", encoding=_UTF_8, newline="\n") as handle:
            handle.write(f"{args.output_name}={run.run_id}\n")

    if outcome.conclusion != "success":
        print(f"REFUSED: {args.workflow} run {run.run_id} concluded {outcome.conclusion}, not success")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
