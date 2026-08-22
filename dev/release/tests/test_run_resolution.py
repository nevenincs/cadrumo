"""Behavioural proof for fire-and-forget dispatch, MY-run resolution, and polling.

Three properties matter more than any individual assertion. First, the
identify-MY-run hazard: ``resolve_dispatched_run`` and ``wait_for_run`` must
refuse — never guess — when a competing run lands in the same dispatch window,
because ``packaging-smoke.yml`` queues rather than cancels a newer dispatch.
Second, budget exhaustion must be provable without ever really sleeping: every
poll test drives a deterministic fake clock whose ``sleep`` advances its own
``now``, so the whole suite runs in milliseconds regardless of the budgets it
exercises. Third, the one real-subprocess boundary (``gh`` itself) is proven
with a genuine executable stub, matching
:mod:`dev.release.tests.test_environment_inventory` — nothing here mocks or
patches ``subprocess``.
"""

from __future__ import annotations

import json
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var

from .. import run_resolution as rr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKFLOW = ".github/workflows/packaging-smoke.yml"
_HEAD_SHA = "a" * 40
_OTHER_SHA = "b" * 40


class _DeterministicClock:
    """A deterministic clock/sleep pair: ``sleep`` advances ``now`` by the requested amount.

    No real waiting occurs anywhere in this module's poll tests; the budget
    math is exercised purely by advancing this clock.
    """

    def __init__(self, start: datetime) -> None:
        self._now = start
        self.slept: list[float] = []

    def now(self) -> datetime:
        return self._now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self._now += timedelta(seconds=seconds)


def _run_record(
    *,
    run_id: int,
    path: str = _WORKFLOW,
    head_sha: str = _HEAD_SHA,
    created_at: datetime,
    event: str = "workflow_dispatch",
    html_url: str = "https://example.invalid/run",
) -> dict[str, object]:
    return {
        "id": run_id,
        "path": path,
        "head_sha": head_sha,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
        "event": event,
        "html_url": html_url,
    }


def _escape_bat_line(line: str) -> str:
    """Escape one line of literal text for a Windows batch ``echo`` statement."""
    return line.replace("%", "%%").replace("^", "^^").replace(">", "^>").replace("<", "^<").replace("|", "^|")


def _write_probe_gh(bin_dir: Path, *, payload: str, exit_code: int = 0) -> Path:
    """Write a real executable ``gh`` stub emitting fixed real process output, one or more lines."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        script = bin_dir / "gh.bat"
        # One `echo` statement per output line: a single `echo` cannot carry an
        # embedded literal newline, and a multi-line JSON-lines payload
        # (list_workflow_runs' one-record-per-line shape) needs every line
        # emitted, not just the first.
        body = "\r\n".join(f"echo {_escape_bat_line(line)}" for line in payload.splitlines() or [""])
        script.write_text(f"@echo off\r\n{body}\r\nexit /b {exit_code}\r\n", encoding="utf-8")
    else:
        script = bin_dir / "gh"
        script.write_text(
            f"#!/usr/bin/env bash\ncat <<'PAYLOAD'\n{payload}\nPAYLOAD\nexit {exit_code}\n", encoding="utf-8"
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _write_argv_capture_gh(bin_dir: Path, *, capture_path: Path, exit_code: int = 0) -> Path:
    """Write a real executable ``gh`` stub that records its argv as whitespace-separated tokens.

    None of this module's dispatched arguments carry embedded whitespace
    (workflow paths, flags, ``key=value`` input pairs), so a single-line
    capture split on whitespace is sufficient and avoids ``cmd.exe``'s ``for``
    loop, whose default delimiters include ``=`` and would corrupt an
    ``-f key=value`` token.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        script = bin_dir / "gh.bat"
        script.write_text(f'@echo off\r\necho %*>"{capture_path}"\r\nexit /b {exit_code}\r\n', encoding="utf-8")
    else:
        script = bin_dir / "gh"
        script.write_text(
            f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{capture_path.as_posix()}"\nexit {exit_code}\n',
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _read_argv(capture_path: Path) -> list[str]:
    """Return the captured argv tokens, tolerating either one-per-line or one-line-whitespace-joined."""
    text = capture_path.read_text(encoding="utf-8")
    return text.split()


# ---------------------------------------------------------------------------
# resolve_dispatched_run — the identify-MY-run hazard, over pure injected data
# ---------------------------------------------------------------------------


def test_resolve_matches_the_single_dispatch_run() -> None:
    """One matching candidate resolves cleanly to that run."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    own = _run_record(run_id=101, created_at=created_after + timedelta(seconds=1))
    resolved = rr.resolve_dispatched_run(
        workflow_path=_WORKFLOW,
        head_sha=_HEAD_SHA,
        created_after=created_after,
        run_records=(own,),
    )
    assert resolved == rr.DispatchedRun(
        run_id="101",
        workflow_path=_WORKFLOW,
        head_sha=_HEAD_SHA,
        html_url="https://example.invalid/run",
    )


def test_resolve_raises_not_yet_visible_when_no_run_matches() -> None:
    """No candidate at all is the retryable outcome, not a hard refusal."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    with pytest.raises(rr.RunNotYetVisibleError):
        rr.resolve_dispatched_run(
            workflow_path=_WORKFLOW,
            head_sha=_HEAD_SHA,
            created_after=created_after,
            run_records=(),
        )


def test_resolve_ignores_a_run_created_before_the_dispatch() -> None:
    """A pre-existing run at the same commit must never be mistaken for this dispatch."""
    created_after = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)
    stale = _run_record(run_id=99, created_at=created_after - timedelta(minutes=5))
    with pytest.raises(rr.RunNotYetVisibleError):
        rr.resolve_dispatched_run(
            workflow_path=_WORKFLOW,
            head_sha=_HEAD_SHA,
            created_after=created_after,
            run_records=(stale,),
        )


def test_resolve_ignores_a_run_of_a_different_workflow_path() -> None:
    """A run of a neighbouring workflow at the same commit must never match."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    neighbour = _run_record(
        run_id=5,
        path=".github/workflows/packaging-scoop.yml",
        created_at=created_after + timedelta(seconds=1),
    )
    with pytest.raises(rr.RunNotYetVisibleError):
        rr.resolve_dispatched_run(
            workflow_path=_WORKFLOW,
            head_sha=_HEAD_SHA,
            created_after=created_after,
            run_records=(neighbour,),
        )


def test_resolve_ignores_a_run_of_a_different_head_sha() -> None:
    """A run of the same workflow at a different commit must never match."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    other_commit = _run_record(run_id=6, head_sha=_OTHER_SHA, created_at=created_after + timedelta(seconds=1))
    with pytest.raises(rr.RunNotYetVisibleError):
        rr.resolve_dispatched_run(
            workflow_path=_WORKFLOW,
            head_sha=_HEAD_SHA,
            created_after=created_after,
            run_records=(other_commit,),
        )


def test_resolve_ignores_a_non_dispatch_event() -> None:
    """A push-triggered run at the same commit is not this workflow_dispatch."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    pushed = _run_record(run_id=7, created_at=created_after + timedelta(seconds=1), event="push")
    with pytest.raises(rr.RunNotYetVisibleError):
        rr.resolve_dispatched_run(
            workflow_path=_WORKFLOW,
            head_sha=_HEAD_SHA,
            created_after=created_after,
            run_records=(pushed,),
        )


def test_resolve_refuses_two_candidate_runs_naming_both_ids() -> None:
    """The core hazard: a competing dispatch queued in the same window. Never guess."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    mine = _run_record(run_id=200, created_at=created_after + timedelta(seconds=1))
    competitor = _run_record(run_id=201, created_at=created_after + timedelta(seconds=2))
    with pytest.raises(rr.RunResolutionError) as excinfo:
        rr.resolve_dispatched_run(
            workflow_path=_WORKFLOW,
            head_sha=_HEAD_SHA,
            created_after=created_after,
            run_records=(mine, competitor),
        )
    message = str(excinfo.value)
    assert "200" in message
    assert "201" in message
    assert "ambiguous" in message.lower()
    # It must not be the retryable subtype: ambiguity is a hard refusal.
    assert not isinstance(excinfo.value, rr.RunNotYetVisibleError)


def test_resolve_rejects_a_malformed_head_sha() -> None:
    """A non-SHA head_sha is refused before any candidate matching is attempted."""
    with pytest.raises(rr.RunResolutionError, match="40-character"):
        rr.resolve_dispatched_run(
            workflow_path=_WORKFLOW,
            head_sha="not-a-sha",
            created_after=datetime(2026, 8, 2, tzinfo=UTC),
            run_records=(),
        )


def test_resolve_normalizes_uppercase_sha_to_github_canonical_identity() -> None:
    """Uppercase input matches GitHub's lowercase run record and returns lowercase."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    own = _run_record(run_id=102, created_at=created_after + timedelta(seconds=1))

    resolved = rr.resolve_dispatched_run(
        workflow_path=_WORKFLOW,
        head_sha=_HEAD_SHA.upper(),
        created_after=created_after,
        run_records=(own,),
    )

    assert resolved.head_sha == _HEAD_SHA
    assert resolved.run_id == "102"


# ---------------------------------------------------------------------------
# wait_for_run — bounded poll over an injected clock; the competing-run hazard
# ---------------------------------------------------------------------------


def test_wait_for_run_retries_until_the_dispatch_run_becomes_visible() -> None:
    """A run absent on the first polls resolves once it appears, backing off in between."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    clock = _DeterministicClock(created_after)
    own = _run_record(run_id=42, created_at=created_after + timedelta(seconds=1))
    calls = {"n": 0}

    def list_runs() -> tuple[dict[str, object], ...]:
        calls["n"] += 1
        return () if calls["n"] < 3 else (own,)

    resolved = rr.wait_for_run(
        workflow_path=_WORKFLOW,
        head_sha=_HEAD_SHA,
        created_after=created_after,
        budget=rr.PollBudget(total_seconds=120, initial_interval_seconds=5, max_interval_seconds=30),
        list_runs=list_runs,
        now=clock.now,
        sleep=clock.sleep,
    )
    assert resolved.run_id == "42"
    assert calls["n"] == 3
    assert clock.slept, "the poll must have backed off at least once before the run appeared"


def test_wait_for_run_refuses_immediately_when_a_competing_run_appears_between_dispatch_and_poll() -> None:
    """The exact hazard this waiter exists for: a competing run lands between dispatch and poll.

    First poll: nothing visible. Second poll: BOTH this dispatch's own run and
    a competing run are now visible at once. The waiter must refuse instantly
    rather than retrying it away or promoting either candidate.
    """
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    clock = _DeterministicClock(created_after)
    mine = _run_record(run_id=42, created_at=created_after + timedelta(seconds=1))
    competitor = _run_record(run_id=43, created_at=created_after + timedelta(seconds=2))
    calls = {"n": 0}

    def list_runs() -> tuple[dict[str, object], ...]:
        calls["n"] += 1
        return () if calls["n"] == 1 else (mine, competitor)

    with pytest.raises(rr.RunResolutionError) as excinfo:
        rr.wait_for_run(
            workflow_path=_WORKFLOW,
            head_sha=_HEAD_SHA,
            created_after=created_after,
            budget=rr.PollBudget(total_seconds=120, initial_interval_seconds=5, max_interval_seconds=30),
            list_runs=list_runs,
            now=clock.now,
            sleep=clock.sleep,
        )
    assert not isinstance(excinfo.value, rr.RunNotYetVisibleError)
    assert "42" in str(excinfo.value)
    assert "43" in str(excinfo.value)
    # Exactly two polls: it did not retry past the ambiguity.
    assert calls["n"] == 2


def test_wait_for_run_exhausts_its_budget_and_names_the_watched_dispatch() -> None:
    """A dispatch that never becomes visible times out naming the workflow and commit."""
    created_after = datetime(2026, 8, 2, tzinfo=UTC)
    clock = _DeterministicClock(created_after)
    with pytest.raises(rr.PollBudgetExhaustedError) as excinfo:
        rr.wait_for_run(
            workflow_path=_WORKFLOW,
            head_sha=_HEAD_SHA,
            created_after=created_after,
            budget=rr.PollBudget(total_seconds=20, initial_interval_seconds=5, max_interval_seconds=10),
            list_runs=tuple,
            now=clock.now,
            sleep=clock.sleep,
        )
    assert _WORKFLOW in str(excinfo.value)
    assert _HEAD_SHA in str(excinfo.value)
    # No real time elapsed; the fake clock alone crossed the budget.
    assert clock.now() >= created_after + timedelta(seconds=20)


# ---------------------------------------------------------------------------
# wait_for_conclusion — success / failure / cancellation / budget exhaustion
# ---------------------------------------------------------------------------


def _resolved_run() -> rr.DispatchedRun:
    return rr.DispatchedRun(run_id="900", workflow_path=_WORKFLOW, head_sha=_HEAD_SHA, html_url="https://x/900")


@pytest.mark.parametrize("conclusion", ["success", "failure", "cancelled"])
def test_wait_for_conclusion_reports_every_terminal_conclusion(conclusion: str) -> None:
    """Success, failure, and cancellation all resolve normally on the first poll."""
    clock = _DeterministicClock(datetime(2026, 8, 2, tzinfo=UTC))
    outcome = rr.wait_for_conclusion(
        _resolved_run(),
        budget=rr.PollBudget(total_seconds=60),
        fetch=lambda: {"status": "completed", "conclusion": conclusion},
        now=clock.now,
        sleep=clock.sleep,
    )
    assert outcome == rr.RunOutcome(run_id="900", workflow_path=_WORKFLOW, status="completed", conclusion=conclusion)
    assert not clock.slept, "a run already concluded on the first poll must never sleep"


def test_wait_for_conclusion_retries_while_the_run_is_still_in_progress() -> None:
    """An in-progress run is polled again rather than treated as concluded."""
    clock = _DeterministicClock(datetime(2026, 8, 2, tzinfo=UTC))
    calls = {"n": 0}

    def fetch() -> dict[str, object]:
        calls["n"] += 1
        if calls["n"] < 3:
            return {"status": "in_progress", "conclusion": None}
        return {"status": "completed", "conclusion": "success"}

    outcome = rr.wait_for_conclusion(
        _resolved_run(),
        budget=rr.PollBudget(total_seconds=120, initial_interval_seconds=5, max_interval_seconds=30),
        fetch=fetch,
        now=clock.now,
        sleep=clock.sleep,
    )
    assert outcome.conclusion == "success"
    assert calls["n"] == 3
    assert clock.slept


def test_wait_for_conclusion_exhausts_its_budget_and_names_the_watched_run() -> None:
    """A run that never concludes times out naming its id, workflow, and URL."""
    clock = _DeterministicClock(datetime(2026, 8, 2, tzinfo=UTC))
    run = _resolved_run()
    with pytest.raises(rr.RunResolutionError) as excinfo:
        rr.wait_for_conclusion(
            run,
            budget=rr.PollBudget(total_seconds=15, initial_interval_seconds=5, max_interval_seconds=10),
            fetch=lambda: {"status": "in_progress", "conclusion": None},
            now=clock.now,
            sleep=clock.sleep,
        )
    message = str(excinfo.value)
    assert run.run_id in message
    assert run.workflow_path in message
    assert run.html_url in message
    assert not isinstance(excinfo.value, rr.RunNotYetVisibleError)


# ---------------------------------------------------------------------------
# The one real-subprocess boundary: gh itself, via a genuine executable stub
# ---------------------------------------------------------------------------


def test_dispatch_workflow_invokes_gh_workflow_run_with_expected_arguments(tmp_path: Path) -> None:
    """The real gh invocation carries the workflow path, repo, and ref."""
    capture = tmp_path / "argv.txt"
    script = _write_argv_capture_gh(tmp_path / "bin", capture_path=capture)

    rr.dispatch_workflow(
        _WORKFLOW,
        ref=_HEAD_SHA,
        repo_slug="nevenincs/cadrumo",
        gh_executable=str(script),
    )

    argv = _read_argv(capture)
    assert argv[:2] == ["workflow", "run"]
    assert _WORKFLOW in argv
    assert "--repo" in argv and "nevenincs/cadrumo" in argv
    assert "--ref" in argv and _HEAD_SHA in argv


def test_dispatch_workflow_passes_inputs_as_repeated_f_flags(tmp_path: Path) -> None:
    """Each dispatch input becomes its own ``-f key=value`` argument."""
    capture = tmp_path / "argv.txt"
    script = _write_argv_capture_gh(tmp_path / "bin", capture_path=capture)

    rr.dispatch_workflow(
        _WORKFLOW,
        ref=_HEAD_SHA,
        inputs={"source_run_id": "123", "source_commit": _HEAD_SHA},
        gh_executable=str(script),
    )

    argv = _read_argv(capture)
    assert argv.count("-f") == 2
    assert f"source_commit={_HEAD_SHA}" in argv
    assert "source_run_id=123" in argv


def test_dispatch_workflow_raises_on_gh_failure(tmp_path: Path) -> None:
    """A non-zero gh exit becomes a RunResolutionError, never a silent no-op."""
    script = _write_probe_gh(tmp_path / "bin", payload="boom", exit_code=1)
    with pytest.raises(rr.RunResolutionError, match="failed"):
        rr.dispatch_workflow(_WORKFLOW, ref=_HEAD_SHA, gh_executable=str(script))


@pytest.mark.parametrize("mutable_or_malformed_ref", ["main", "abc123", "g" * 40])
def test_dispatch_workflow_refuses_non_immutable_ref_before_invoking_gh(
    tmp_path: Path,
    mutable_or_malformed_ref: str,
) -> None:
    """A branch or malformed ref produces no external dispatch side effect."""
    capture = tmp_path / "argv.txt"
    script = _write_argv_capture_gh(tmp_path / "bin", capture_path=capture)

    with pytest.raises(rr.RunResolutionError, match="40-character"):
        rr.dispatch_workflow(
            _WORKFLOW,
            ref=mutable_or_malformed_ref,
            gh_executable=str(script),
        )

    assert not capture.exists()


def test_list_workflow_runs_parses_real_subprocess_output(tmp_path: Path) -> None:
    """Multi-line JSON output from a real gh stub parses into one record per line."""
    lines = "\n".join(
        json.dumps(record)
        for record in (
            {"id": 1, "path": _WORKFLOW, "head_sha": _HEAD_SHA, "created_at": "2026-08-02T00:00:00Z"},
            {"id": 2, "path": _WORKFLOW, "head_sha": _HEAD_SHA, "created_at": "2026-08-02T00:05:00Z"},
        )
    )
    script = _write_probe_gh(tmp_path / "bin", payload=lines)

    records = rr.list_workflow_runs(_WORKFLOW, gh_executable=str(script))

    assert [record["id"] for record in records] == [1, 2]


def test_fetch_run_parses_real_subprocess_output(tmp_path: Path) -> None:
    """A single-run JSON object from a real gh stub parses into a plain dict."""
    payload = json.dumps({"status": "completed", "conclusion": "success"})
    script = _write_probe_gh(tmp_path / "bin", payload=payload)

    record = rr.fetch_run("900", gh_executable=str(script))

    assert record == {"status": "completed", "conclusion": "success"}


def test_an_explicit_nonexistent_gh_executable_raises_instructively(tmp_path: Path) -> None:
    """Mirrors ``environment_inventory``'s injection contract: an explicit path is trusted, not searched."""
    missing = tmp_path / "bin" / "definitely-not-gh"
    with pytest.raises(rr.RunResolutionError, match="could not be run"):
        rr.dispatch_workflow(_WORKFLOW, ref=_HEAD_SHA, gh_executable=str(missing))


def test_gh_absent_from_path_raises_instructively() -> None:
    """With no explicit override, resolution falls back to a real PATH search."""
    with scoped_env_var("PATH", ""), pytest.raises(rr.RunResolutionError, match="not found on PATH"):
        rr.dispatch_workflow(_WORKFLOW, ref=_HEAD_SHA, gh_executable=None)


# ---------------------------------------------------------------------------
# dispatch_and_resolve — the orchestrator's one entry point
# ---------------------------------------------------------------------------


def test_dispatch_and_resolve_composes_dispatch_then_resolve(tmp_path: Path) -> None:
    """Real gh dispatch (stub) plus injected resolution, proving the two compose."""
    script = _write_probe_gh(tmp_path / "bin", payload="")
    fixed_now = datetime(2026, 8, 2, 9, 0, 0, tzinfo=UTC)
    own = _run_record(run_id=77, created_at=fixed_now + timedelta(seconds=1))

    resolved = rr.dispatch_and_resolve(
        _WORKFLOW,
        head_sha=_HEAD_SHA,
        resolve_budget=rr.PollBudget(total_seconds=30, initial_interval_seconds=1, max_interval_seconds=5),
        gh_executable=str(script),
        list_runs=lambda: (own,),
        now=lambda: fixed_now,
        sleep=lambda _seconds: None,
    )
    assert resolved.run_id == "77"


def test_dispatch_and_resolution_share_the_same_immutable_revision_when_main_advances(tmp_path: Path) -> None:
    """A moved ``main`` cannot make dispatch and resolution watch different commits.

    The release chose ``_HEAD_SHA`` before another commit advanced ``main`` to
    ``_OTHER_SHA``. The real subprocess boundary must receive the chosen SHA as
    ``--ref`` while resolution ignores the newer main run and selects the run
    created at that same chosen SHA.
    """
    capture = tmp_path / "argv.txt"
    script = _write_argv_capture_gh(tmp_path / "bin", capture_path=capture)
    fixed_now = datetime(2026, 8, 2, 9, 0, 0, tzinfo=UTC)
    advanced_main = _run_record(
        run_id=78,
        head_sha=_OTHER_SHA,
        created_at=fixed_now + timedelta(milliseconds=500),
    )
    chosen_revision = _run_record(run_id=77, created_at=fixed_now + timedelta(seconds=1))

    resolved = rr.dispatch_and_resolve(
        _WORKFLOW,
        head_sha=_HEAD_SHA,
        resolve_budget=rr.PollBudget(total_seconds=30, initial_interval_seconds=1, max_interval_seconds=5),
        gh_executable=str(script),
        list_runs=lambda: (advanced_main, chosen_revision),
        now=lambda: fixed_now,
        sleep=lambda _seconds: None,
    )

    argv = _read_argv(capture)
    assert argv[argv.index("--ref") + 1] == _HEAD_SHA
    assert _OTHER_SHA not in argv
    assert resolved.head_sha == _HEAD_SHA
    assert resolved.run_id == "77"


def test_dispatch_and_resolve_normalizes_uppercase_before_dispatch_and_matching(tmp_path: Path) -> None:
    """One canonical lowercase SHA crosses both the gh and run-record boundaries."""
    capture = tmp_path / "argv.txt"
    script = _write_argv_capture_gh(tmp_path / "bin", capture_path=capture)
    fixed_now = datetime(2026, 8, 2, 9, 0, 0, tzinfo=UTC)
    own = _run_record(run_id=79, created_at=fixed_now + timedelta(seconds=1))

    resolved = rr.dispatch_and_resolve(
        _WORKFLOW,
        head_sha=_HEAD_SHA.upper(),
        resolve_budget=rr.PollBudget(total_seconds=30),
        gh_executable=str(script),
        list_runs=lambda: (own,),
        now=lambda: fixed_now,
        sleep=lambda _seconds: None,
    )

    argv = _read_argv(capture)
    assert argv[argv.index("--ref") + 1] == _HEAD_SHA
    assert resolved.head_sha == _HEAD_SHA


def test_dispatch_and_resolve_rejects_mutable_head_before_clock_or_gh_side_effect(tmp_path: Path) -> None:
    """Composite validation precedes both timestamp capture and external dispatch."""
    capture = tmp_path / "argv.txt"
    script = _write_argv_capture_gh(tmp_path / "bin", capture_path=capture)
    clock_read = False

    def observe_clock() -> datetime:
        nonlocal clock_read
        clock_read = True
        return datetime(2026, 8, 2, tzinfo=UTC)

    with pytest.raises(rr.RunResolutionError, match="40-character"):
        rr.dispatch_and_resolve(
            _WORKFLOW,
            head_sha="main",
            resolve_budget=rr.PollBudget(total_seconds=30),
            gh_executable=str(script),
            list_runs=tuple,
            now=observe_clock,
            sleep=lambda _seconds: None,
        )

    assert not clock_read
    assert not capture.exists()


# ---------------------------------------------------------------------------
# PollBudget — declared, validated budgets
# ---------------------------------------------------------------------------


def test_poll_budget_rejects_non_positive_total_seconds() -> None:
    """A zero or negative budget is refused at construction, not at first poll."""
    with pytest.raises(rr.RunResolutionError, match="total_seconds"):
        rr.PollBudget(total_seconds=0)


def test_poll_budget_rejects_backoff_factor_below_one() -> None:
    """A shrinking backoff factor would make retries faster, not slower; refuse it."""
    with pytest.raises(rr.RunResolutionError, match="backoff_factor"):
        rr.PollBudget(total_seconds=60, backoff_factor=0.5)
