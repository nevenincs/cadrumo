"""Gate: an unschedulable lane fails fast, and a busy one is left alone.

Both directions are load-bearing and are asserted here together, because each
without the other is indistinguishable from a broken check. A watchdog that
never fires is the exact defect it was built to remove, dressed as a green run;
a watchdog that always fires is retired by its audience within a week and then
is also a watchdog that never fires. So every behavioural test below pins BOTH
the firing case and the silent case over the same input.

The payload shapes are copied from a real run against the real offline-Windows
condition (run 31007405350), not invented: the ``labels`` array on a queued job,
the ``created_at``/``started_at`` equality while queued, and the absence of any
``runner_name``. Inventing those shapes would test the fixture rather than the
endpoint.
"""

from __future__ import annotations

import calendar
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT
from ..runner_queue_watchdog import (
    JobView,
    Verdict,
    _epoch_of,
    classify,
    confirm_unschedulable,
    occupied_label_keys,
    parse_jobs,
)
from ..workflow_run_text import executed_text
from ..workflow_runner_targets import is_unresolved, runner_targets

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_WATCHDOG_JOB_ID: Final = "runner-queue-watchdog"
#: The watchdog is invoked as a module rather than a script path, so the lane
#: runs the same code whether the checkout is a source tree or an install.
_WATCHDOG_MODULE: Final = "dev.ci.runner_queue_watchdog"

# The label set the watchdog itself runs on. A lane on this set needs no
# watchdog to notice it is unschedulable: if nothing can serve it, the watchdog
# cannot run either, and the whole repository is visibly dead rather than
# silently queued.
_WATCHDOG_LABELS: Final = ("Linux", "X64", "self-hosted")

# `calendar.timegm` is the stdlib's UTC-truth oracle and shares no code path
# with the parse under test. Deriving the test's clock from the SAME idiom the
# module used is what previously hid an hour-wide timezone defect here: both
# sides were wrong by 3600 s and the subtraction cancelled it.
_NOW: Final = float(calendar.timegm(time.strptime("2026-08-05T12:52:35Z", "%Y-%m-%dT%H:%M:%SZ")))

#: The same instant as an independently-derived absolute epoch literal, so the
#: parse is pinned to a number rather than to another computation.
_NOW_EPOCH_LITERAL: Final = 1_785_934_355.0


def _payload() -> dict[str, Any]:
    """A run holding one unschedulable lane and three schedulable ones.

    Verbatim in shape from run 31007405350: the Windows job is queued with no
    runner assigned, while Linux jobs are queued behind two busy Linux runners.
    """
    return {
        "jobs": [
            {
                "name": "Cadrumo probe / unschedulable Windows lane",
                "status": "queued",
                "labels": ["self-hosted", "Windows", "X64"],
                "created_at": "2026-08-05T12:50:25Z",
                "started_at": "2026-08-05T12:50:25Z",
                "runner_name": None,
            },
            {
                "name": "Cadrumo probe / schedulable control B",
                "status": "queued",
                "labels": ["self-hosted", "Linux", "X64"],
                "created_at": "2026-08-05T12:50:25Z",
                "started_at": "2026-08-05T12:50:25Z",
                "runner_name": None,
            },
            {
                "name": "Cadrumo probe / schedulable control A",
                "status": "in_progress",
                "labels": ["self-hosted", "Linux", "X64"],
                "created_at": "2026-08-05T12:50:25Z",
                "started_at": "2026-08-05T12:50:27Z",
                "runner_name": "cadrumo-linux-x64",
            },
            {
                "name": "Cadrumo probe / queue watchdog",
                "status": "queued",
                "labels": ["self-hosted", "Linux", "X64"],
                "created_at": "2026-08-05T12:50:25Z",
                "started_at": "2026-08-05T12:50:25Z",
                "runner_name": None,
            },
        ]
    }


def _classify(payload: dict[str, Any], **overrides: Any) -> tuple[Any, ...]:
    kwargs: dict[str, Any] = {
        "now_epoch": _NOW,
        "threshold_seconds": 120.0,
        "watchdog_job_name": "Cadrumo probe / queue watchdog",
    }
    kwargs.update(overrides)
    return classify(parse_jobs(payload), **kwargs)


def test_queued_job_reports_the_label_set_it_requested() -> None:
    """A queued job carries `runs-on` labels even with no runner assigned.

    This is the fact the whole mechanism rests on: the runners endpoint is
    forbidden to the workflow token, so the requested label set has to come
    from the job record itself.
    """
    windows = next(job for job in parse_jobs(_payload()) if "Windows" in job.labels)
    assert windows.status == "queued"
    assert windows.labels == ("self-hosted", "Windows", "X64")
    assert windows.queued_since_epoch > 0.0, "a queued job must carry a usable queued-since stamp"


def test_queued_since_is_parsed_as_utc_not_local_time() -> None:
    """The queue clock must not depend on the machine's timezone.

    `waited` is `time.time()` (true UTC epoch) minus this parse, so an error
    here lands directly on the quantity compared against the threshold. The
    original `mktime(strptime(...)) - timezone` parse read the stamp as LOCAL
    time and applied the local DST rule while subtracting the non-DST STANDARD
    offset, returning an epoch 3600 s early on this machine -- an hour of
    phantom wait, well past the 300 s threshold, on every job. That is the
    false-alarm direction: the watchdog would flag healthy lanes and cancel its
    own run.

    Both oracles are independent of the implementation: an absolute epoch
    literal, and `calendar.timegm`, which is the stdlib's UTC counterpart to
    `mktime` and shares no code path with `datetime.fromisoformat`.
    """
    assert _epoch_of("2026-08-05T12:52:35Z") == _NOW_EPOCH_LITERAL
    for stamp in ("2026-01-15T03:00:00Z", "2026-08-05T12:52:35Z", "2026-12-31T23:59:59Z"):
        expected = float(calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")))
        assert _epoch_of(stamp) == expected, (
            f"{stamp} parsed to {_epoch_of(stamp)}, not the UTC truth {expected} "
            f"(delta {_epoch_of(stamp) - expected:+.0f}s) — the parse is reading local time"
        )


def test_a_freshly_queued_job_does_not_fire_on_a_timezone_offset() -> None:
    """End-to-end guard on the defect above, at the level the operator sees.

    The unit test pins the parse; this pins the CONSEQUENCE. A job queued five
    seconds ago is classified against a real `time.time()` clock, so a parse
    carrying any whole-hour timezone error puts it past the 300 s threshold and
    produces a verdict. The correct answer is no verdict at all.
    """
    just_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 5.0))
    payload = {
        "jobs": [
            {
                "name": "Cadrumo probe / just queued",
                "status": "queued",
                "labels": ["self-hosted", "Windows", "X64"],
                "created_at": just_now,
                "started_at": just_now,
                "runner_name": None,
            }
        ]
    }
    verdicts = classify(
        parse_jobs(payload),
        now_epoch=time.time(),
        threshold_seconds=300.0,
        watchdog_job_name="",
    )
    assert verdicts == (), f"a job queued 5s ago was judged past a 300s threshold: {verdicts}"


def test_label_key_is_order_independent() -> None:
    """Runner label order is not significant to scheduling, so nor is it here.

    The fleet's Linux runners register `[self-hosted, X64, Linux]` while every
    workflow requests `[self-hosted, Linux, X64]`. Comparing authored sequences
    would call every Linux lane unoccupied and fire on all of them.
    """
    authored = JobView("a", "queued", ("self-hosted", "Linux", "X64"), 0.0)
    registered = JobView("b", "in_progress", ("self-hosted", "X64", "Linux"), 0.0)
    assert authored.label_key == registered.label_key


def test_fires_on_the_lane_no_runner_serves() -> None:
    """The Windows lane is flagged, by name, with its label set."""
    firing = [verdict for verdict in _classify(_payload()) if verdict.unschedulable]
    assert [verdict.job_name for verdict in firing] == ["Cadrumo probe / unschedulable Windows lane"]
    assert firing[0].label_key == ("Windows", "X64", "self-hosted")


def test_does_not_fire_on_a_lane_that_is_merely_busy() -> None:
    """Queued-behind-a-busy-runner is not unschedulable, and must stay silent.

    Control B waited exactly as long as the Windows job over the same input.
    The only thing separating them is that something is running on Linux.
    """
    verdicts = _classify(_payload())
    control_b = next(v for v in verdicts if v.job_name.endswith("control B"))
    assert control_b.unschedulable is False
    assert "schedulable" in control_b.reason


def test_the_discriminator_is_what_makes_the_silent_case_silent() -> None:
    """Anti-tautology: remove occupancy and the silent case must start firing.

    Without this, `test_does_not_fire_on_a_lane_that_is_merely_busy` would pass
    just as well against a watchdog that flags nothing at all. Feeding the same
    input with an empty occupancy set proves the skip is caused by the
    discriminator rather than by the check being inert.
    """
    with_occupancy = _classify(_payload())
    without_occupancy = _classify(_payload(), occupied=frozenset())

    busy_lane = next(v for v in with_occupancy if v.job_name.endswith("control B"))
    same_lane = next(v for v in without_occupancy if v.job_name.endswith("control B"))
    assert busy_lane.unschedulable is False
    assert same_lane.unschedulable is True, "occupancy is not load-bearing; the skip is inert"


def _unschedulable(name: str) -> Verdict:
    """One flagged verdict, the shape ``classify`` emits for an unserved lane."""
    return Verdict(
        job_name=name,
        label_key=("Windows", "X64", "self-hosted"),
        waited_seconds=3992.0,
        unschedulable=True,
        reason="no job anywhere in this repository is running on this label set",
    )


def test_a_lane_flagged_once_does_not_cancel_the_run() -> None:
    """The exact shape that killed run 34016654501.

    A label set falls empty for a moment between a finishing job and the queued
    job that succeeds it. The successor had started three seconds before the
    poll that read the gap, so a single observation cancelled seven lanes and
    the evidence they were about to produce. One sample is not proof.
    """
    tally, confirmed = confirm_unschedulable([_unschedulable("windows oracle")], {}, required=2)

    assert confirmed == ()
    assert tally == {"windows oracle": 1}

    # Anti-tautology: the same input under the pre-fix threshold must confirm,
    # or this passes just as well against a function that confirms nothing.
    _, unguarded = confirm_unschedulable([_unschedulable("windows oracle")], {}, required=1)
    assert [verdict.job_name for verdict in unguarded] == ["windows oracle"]


def test_a_lane_flagged_on_consecutive_polls_cancels_the_run() -> None:
    """The other direction: a real unservable lane must still be caught.

    Without this the debounce would be indistinguishable from a watchdog that
    never fires, which is the failure it was added to prevent, inverted.
    """
    first, _ = confirm_unschedulable([_unschedulable("windows oracle")], {}, required=2)
    _, confirmed = confirm_unschedulable([_unschedulable("windows oracle")], first, required=2)

    assert [verdict.job_name for verdict in confirmed] == ["windows oracle"]


def test_a_lane_that_recovers_starts_its_count_again() -> None:
    """A gap that closes must not leave a count behind to be topped up later.

    Counting down rather than rebuilding would let two unrelated handoff gaps,
    minutes apart, add up to a cancellation neither one justified.
    """
    first, _ = confirm_unschedulable([_unschedulable("windows oracle")], {}, required=2)
    recovered, _ = confirm_unschedulable([], first, required=2)
    tally, confirmed = confirm_unschedulable([_unschedulable("windows oracle")], recovered, required=2)

    assert recovered == {}
    assert confirmed == ()
    assert tally == {"windows oracle": 1}


def test_watchdog_never_reports_its_own_queue_wait() -> None:
    """The watchdog is a job in the run it watches and must exclude itself.

    It queues for a runner like anything else. A watchdog that counted its own
    wait would fire on a merely-busy fleet, every time.
    """
    reported = {verdict.job_name for verdict in _classify(_payload())}
    assert "Cadrumo probe / queue watchdog" not in reported


def test_nothing_fires_before_the_threshold() -> None:
    """A job that has only just been created is not evidence of anything."""
    assert _classify(_payload(), threshold_seconds=100_000.0) == ()


def test_occupancy_counts_only_running_jobs() -> None:
    """A queued job is not proof that its own label set can be served."""
    queued_only = {"jobs": [job for job in _payload()["jobs"] if job["status"] == "queued"]}
    assert occupied_label_keys(parse_jobs(queued_only)) == frozenset()


#: Floor for the workflow census three gates in this module iterate. The
#: directory carries sixteen today; the sibling change-class module floors
#: the same walk at eight and states why, so this matches it. A bare
#: truthiness stood here, and every assertion in those three gates runs
#: INSIDE the loop over this list: a walk narrowed to one document leaves
#: each of them passing with almost nothing executed.
_MINIMUM_WORKFLOW_DOCUMENTS = 8


def _workflow_documents() -> list[tuple[Path, dict[str, Any]]]:
    paths = sorted(
        {*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")}
    )
    assert len(paths) >= _MINIMUM_WORKFLOW_DOCUMENTS, (
        f"only {len(paths)} workflow(s) found under {_WORKFLOWS_DIR}; the gates that "
        "iterate this census assert nothing at all over a walk that reached less than "
        "the lanes this repository runs"
    )
    return [(path, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in paths]


def _off_watchdog_lane_jobs(document: dict[str, Any]) -> list[str]:
    """Jobs targeting a label set the watchdog's own lane does not cover.

    Targets come from the shared runner-target authority, so a matrix computed
    at runtime is followed to the step that emits its labels instead of raising
    on a `strategy.matrix` that is a string. A reference that authority cannot
    follow counts as off-lane: an unknown lane is the case this gate exists for,
    and a job whose labels nobody can read is precisely one that could queue
    unserved without anyone noticing.
    """
    off_lane: list[str] = []
    for job_name, job in (document.get("jobs") or {}).items():
        for target in runner_targets(job, document):
            unknown_lane = is_unresolved(target)
            other_lane = isinstance(target, list) and tuple(sorted(target)) != _WATCHDOG_LABELS
            if unknown_lane or other_lane:
                off_lane.append(job_name)
                break
    return off_lane


def test_every_workflow_with_an_off_lane_job_carries_the_watchdog() -> None:
    """A lane that can hang unwatched is the defect; this refuses to ship one.

    Scoped to label sets other than the watchdog's own: a job on the watchdog's
    lane cannot hang unobserved, because a fleet that cannot serve that lane
    cannot run the watchdog either and fails visibly everywhere at once.
    """
    unwatched: list[tuple[str, list[str]]] = []
    for path, document in _workflow_documents():
        off_lane = _off_watchdog_lane_jobs(document)
        if off_lane and _WATCHDOG_JOB_ID not in (document.get("jobs") or {}):
            unwatched.append((path.name, off_lane))
    assert unwatched == [], f"workflows with an unwatched off-lane job: {unwatched}"


def test_the_gate_refuses_a_new_unwatched_lane(tmp_path: Path) -> None:
    """Proof the gate above can fail: an off-lane job with no watchdog is caught.

    A structural gate that has only ever been observed passing is not known to
    discriminate. This drives it with an input it must reject.
    """
    (tmp_path / "unwatched.yml").write_text(
        "name: Cadrumo Unwatched\n"
        "on: workflow_dispatch\n"
        "jobs:\n"
        "  lonely-windows:\n"
        "    runs-on: [self-hosted, Windows, X64]\n"
        "    steps: []\n",
        encoding="utf-8",
    )
    document = yaml.safe_load((tmp_path / "unwatched.yml").read_text(encoding="utf-8"))
    assert _off_watchdog_lane_jobs(document) == ["lonely-windows"]
    assert _WATCHDOG_JOB_ID not in (document.get("jobs") or {})


def _runtime_matrix_document(emitted_labels: str) -> dict[str, Any]:
    """A job whose lane is decided by another job's output at run time."""
    return yaml.safe_load(
        "name: Cadrumo Runtime\n"
        "on: workflow_dispatch\n"
        "jobs:\n"
        "  inventory:\n"
        "    runs-on: [self-hosted, Linux, X64]\n"
        "    outputs:\n"
        "      matrix: ${{ steps.emit.outputs.matrix }}\n"
        "    steps:\n"
        "      - name: Emit\n"
        "        id: emit\n"
        "        run: |\n"
        f"          emit --targets {emitted_labels}\n"
        "  fanned:\n"
        "    needs: inventory\n"
        "    strategy:\n"
        "      matrix: ${{ fromJSON(needs.inventory.outputs.matrix) }}\n"
        "    runs-on: ${{ matrix.os }}\n"
        "    steps: []\n",
    )


def test_a_runtime_matrix_on_hosted_images_needs_no_watchdog() -> None:
    """A hosted lane cannot queue behind this fleet, so it is not off-lane.

    The positive control for the refusal below. A reader that treated every
    runtime matrix as unknown would demand a watchdog in the publication
    workflow, which schedules nothing on the fleet at all -- and a demand that
    is always made is not a signal.
    """
    document = _runtime_matrix_document('"ubuntu-latest" "macos-latest" "windows-latest"')

    assert runner_targets(document["jobs"]["fanned"], document) == [
        "ubuntu-latest",
        "macos-latest",
        "windows-latest",
    ]
    assert _off_watchdog_lane_jobs(document) == []


def test_a_lane_whose_labels_cannot_be_read_counts_as_off_lane() -> None:
    """Fail closed: an unreadable lane is watched, not assumed to be safe.

    This is the shape the previous reader raised on, and raising is how the
    question went unasked. Now it is asked and answered conservatively, so a
    lane nobody can classify still carries the instrument that would notice it
    queueing forever.
    """
    document = _runtime_matrix_document("--from-file targets.json")

    targets = runner_targets(document["jobs"]["fanned"], document)

    assert [target for target in targets if is_unresolved(target)] == targets
    assert _off_watchdog_lane_jobs(document) == ["fanned"]


def _watchdog_invokes_the_module(job: dict[str, Any]) -> bool:
    """Whether ``job`` actually RUNS the shared watchdog module.

    Read from what the steps execute rather than from their text. A module name
    can appear in a workflow in an explanatory comment as well as in a command,
    and a comment is a name the shell never acts on: a watchdog whose
    invocation was commented out, or replaced by a hand-copied shell loop under
    a note naming the module, satisfies a substring reading of the same block
    while running nothing.
    """
    return _WATCHDOG_MODULE in executed_text(step.get("run") for step in job.get("steps") or [])


def test_every_watchdog_job_invokes_the_shared_module() -> None:
    """One implementation of the decision, not five hand-copied shell loops."""
    examined = 0
    for path, document in _workflow_documents():
        job = (document.get("jobs") or {}).get(_WATCHDOG_JOB_ID)
        if job is None:
            continue
        examined += 1
        assert _watchdog_invokes_the_module(job), f"{path.name}: watchdog does not run {_WATCHDOG_MODULE}"
        assert job.get("runs-on") is not None and tuple(sorted(job["runs-on"])) == _WATCHDOG_LABELS, (
            f"{path.name}: the watchdog must run on a lane the fleet can always serve"
        )
    assert examined, f"no workflow declares a {_WATCHDOG_JOB_ID} job; this gate examined nothing"


def test_a_watchdog_whose_invocation_is_commented_out_is_not_invoking_it() -> None:
    """Teeth, over a copy of a real watchdog job rather than an invented one.

    Both directions across the same input: the job as it stands invokes the
    module, and the same job with its commands commented out does not -- while
    the substring reading this replaced still finds the module name in it.
    """
    job = next(
        (document.get("jobs") or {})[_WATCHDOG_JOB_ID]
        for _, document in _workflow_documents()
        if _WATCHDOG_JOB_ID in (document.get("jobs") or {})
    )

    assert _watchdog_invokes_the_module(job)

    commented = deepcopy(job)
    newline = chr(10)
    for step in commented["steps"]:
        if "run" in step:
            step["run"] = "# " + str(step["run"]).replace(newline, newline + "# ")

    assert _WATCHDOG_MODULE in "".join(str(step.get("run", "")) for step in commented["steps"])
    assert not _watchdog_invokes_the_module(commented)


def _needs_of(job: dict[str, Any]) -> frozenset[str]:
    """A job's dependency set, normalised across the string and list forms."""
    needs = job.get("needs")
    if isinstance(needs, str):
        return frozenset({needs})
    return frozenset(str(entry) for entry in needs or ())


def test_the_watchdog_is_created_no_later_than_the_lanes_it_watches() -> None:
    """A gated off-lane job must not outlive the watchdog's watch window.

    The module's own measurement is the reason: GitHub does not create a
    dependent job's record until its dependencies resolve, so a `needs:`-gated
    lane appears LATE. An ungated watchdog starts its bounded window
    immediately and can therefore stand down before the job it exists to watch
    is created — leaving exactly the silent six-hour hang the watchdog was
    built to remove, while the workflow still looks watched because a watchdog
    job is present.

    Presence is not coverage. This asserts the watchdog shares the dependency
    of every off-lane job it watches, which is what makes them appear together.
    `packaging-smoke` already had this right; `packaging-homebrew` did not.
    """
    for path, document in _workflow_documents():
        jobs = document.get("jobs") or {}
        watchdog = jobs.get(_WATCHDOG_JOB_ID)
        if watchdog is None:
            continue
        watchdog_needs = _needs_of(watchdog)
        for job_name in _off_watchdog_lane_jobs(document):
            watched_needs = _needs_of(jobs[job_name])
            assert watched_needs <= watchdog_needs, (
                f"{path.name}: '{job_name}' is gated on {sorted(watched_needs - watchdog_needs)}, "
                f"which the watchdog does not wait for — the watchdog would begin (and could "
                f"finish) its watch window before that job is created"
            )


def test_the_needs_parity_gate_refuses_an_ungated_watchdog(tmp_path: Path) -> None:
    """Proof the gate above can fail, driven with the shape it must reject.

    This is the pre-fix `packaging-homebrew` topology in miniature: a watchdog
    with no dependency alongside an off-lane job gated behind a build step.
    """
    (tmp_path / "late.yml").write_text(
        "name: Cadrumo Late\n"
        "on: workflow_dispatch\n"
        "jobs:\n"
        "  runner-queue-watchdog:\n"
        "    runs-on: [self-hosted, Linux, X64]\n"
        "    steps: []\n"
        "  build:\n"
        "    runs-on: [self-hosted, Linux, X64]\n"
        "    steps: []\n"
        "  late-macos:\n"
        "    needs: build\n"
        "    runs-on: [self-hosted, macOS, ARM64]\n"
        "    steps: []\n",
        encoding="utf-8",
    )
    document = yaml.safe_load((tmp_path / "late.yml").read_text(encoding="utf-8"))
    jobs = document["jobs"]

    assert _off_watchdog_lane_jobs(document) == ["late-macos"]
    assert not _needs_of(jobs["late-macos"]) <= _needs_of(jobs[_WATCHDOG_JOB_ID]), (
        "the gate must reject a watchdog that does not wait for a dependency its watched job waits for"
    )


def test_every_watchdog_job_can_read_jobs_and_cancel_the_run() -> None:
    """Without `actions: write` the cancel silently no-ops and the run hangs on.

    This is the failure mode that would leave the check looking healthy while
    doing nothing: it would still fail its own job, but the queued lane would
    sit for GitHub's full 24-hour ceiling, which is the original defect.
    """
    for path, document in _workflow_documents():
        job = (document.get("jobs") or {}).get(_WATCHDOG_JOB_ID)
        if job is None:
            continue
        permissions = job.get("permissions") or document.get("permissions") or {}
        assert permissions.get("actions") == "write", f"{path.name}: watchdog needs actions: write to cancel"
