"""A test shard's log says what its runner had left, and the shard has the browser its tests drive.

A hosted runner that runs out of memory or disk is stopped without failing a
test, so a shard's log ended with no reason. The sampler is proven here over
real ``/proc``-shaped files, and the shard step that runs it is pinned with
planted defects:

- the sampler reads numbers and process names, never a command line;
- it starts before the tests, in the background of the same step, so its lines
  reach the log while the tests run;
- the tests stay the step's last command, so their exit status is the step's;
- a failed shard prints the kernel's kill records, and only a failed one;
- a job that runs the shard population provisions Chromium.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from dev.paths import REPO_ROOT

from ..lane_recipe_commands import recipes_invoked_by
from ..runner_resources import (
    MemoryReading,
    ProcessReading,
    largest_processes,
    main,
    memory_reading,
    sample_line,
)
from ..workflow_run_text import executed_lines

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MERGE_GATE: Final = REPO_ROOT / ".github" / "workflows" / "merge-gate.yml"
_SETUP_ACTION: Final = "./.github/actions/setup"
_SHARD_RECIPE: Final = "test-gate-shard"
_SAMPLER: Final = "uv run --no-sync python -m dev.ci.runner_resources --every "
_KILL_RECORDS: Final = "dmesg"
_ONLY_WHEN_FAILED: Final = "${{ failure() }}"
_SHELL_OPERATORS: Final = ("|", "&", ";")
_LONGEST_INTERVAL: Final = 60
#: Each test worker holds 1 to 1.7 GB before its first test and levels off at
#: 3 to 5 GB (one reached 6.8 GB). Four of them, and then three, used the hosted
#: runner's 16 GB and 3 GB swap whatever the shard size, and the runner was lost
#: mid-test.
_MOST_SHARD_WORKERS: Final = 2
#: Tests in the population bundle frontend sources whose ``@fixtures`` imports
#: resolve only into a build tree, which a hosted runner holds only once the
#: window projections are placed there. One job seeds them for every shard.
_WINDOW_PROJECTIONS: Final = "just fixtures-seed-window"
#: A job stopped at its own limit keeps no log; the shard step stops this many
#: minutes before the job so a stalled shard's log survives.
_LOG_MARGIN_MINUTES: Final = 5
_WINDOW_ARTIFACT: Final = "cadrumo-window-projections"
_UPLOAD: Final = "actions/upload-artifact@"
_DOWNLOAD: Final = "actions/download-artifact@"

_MEMINFO: Final = (
    "MemTotal:       16384000 kB\n"
    "MemFree:          102400 kB\n"
    "MemAvailable:    4096000 kB\n"
    "SwapCached:            0 kB\n"
    "SwapTotal:       4194304 kB\n"
    "SwapFree:        3145728 kB\n"
    "HugePages_Total:       0\n"
)


def _process(proc_root: Path, pid: str, status: str | None, *, command_line: str = "") -> None:
    directory = proc_root / pid
    directory.mkdir(parents=True)
    if status is not None:
        (directory / "status").write_text(status, encoding="utf-8", newline="\n")
    if command_line:
        (directory / "cmdline").write_text(command_line, encoding="utf-8", newline="\n")


# --- the sampler --------------------------------------------------------------


def test_memory_is_read_from_meminfo_in_mebibytes() -> None:
    assert memory_reading(_MEMINFO) == MemoryReading(total=16000, available=4000, swap_total=4096, swap_free=3072)


@pytest.mark.parametrize("absent", ["MemTotal", "MemAvailable", "SwapTotal", "SwapFree"])
def test_a_meminfo_without_a_field_is_refused_not_read_as_zero(absent: str) -> None:
    text = "".join(line for line in _MEMINFO.splitlines(keepends=True) if not line.startswith(f"{absent}:"))
    with pytest.raises(ValueError, match=absent):
        memory_reading(text)


def test_the_largest_processes_are_ranked_by_resident_memory(tmp_path: Path) -> None:
    _process(tmp_path, "311", "Name:\tpython\nVmRSS:\t  512000 kB\n")
    _process(tmp_path, "312", "Name:\tpython\nVmRSS:\t 3072000 kB\n")
    _process(tmp_path, "45", "Name:\tnode\nVmRSS:\t    1024 kB\n")
    # A kernel thread has no resident set, an ended process has no status file,
    # and /proc holds entries that are not processes.
    _process(tmp_path, "7", "Name:\tkworker/0:1\n")
    _process(tmp_path, "9", None)
    _process(tmp_path, "self", "Name:\tpython\nVmRSS:\t 9999999 kB\n")

    assert largest_processes(tmp_path, count=2) == (
        ProcessReading(pid=312, name="python", resident=3000),
        ProcessReading(pid=311, name="python", resident=500),
    )
    assert [process.pid for process in largest_processes(tmp_path)] == [312, 311, 45]


def test_a_command_line_never_reaches_the_sample(tmp_path: Path) -> None:
    _process(tmp_path, "311", "Name:\tpython\nVmRSS:\t  512000 kB\n", command_line="python --token planted-secret")

    line = sample_line(
        clock="12:00:00Z",
        memory=memory_reading(_MEMINFO),
        disk_free=9000,
        load="4.10 3.90 3.00",
        processes=largest_processes(tmp_path),
    )

    assert "planted-secret" not in line
    assert line == (
        "runner resources 12:00:00Z | memory 12000 of 16000 MiB used, 4000 available"
        " | swap 1024 of 4096 MiB used | disk 9000 MiB free | load 4.10 3.90 3.00"
        " | largest: python 311 500 MiB"
    )


def test_a_sample_with_no_readable_process_says_so() -> None:
    line = sample_line(clock="12:00:00Z", memory=memory_reading(_MEMINFO), disk_free=1, load="0 0 0", processes=())
    assert line.endswith("| largest: none read")


@pytest.mark.parametrize("interval", ["0", "-5"])
def test_the_sampler_refuses_an_interval_that_is_not_positive(interval: str) -> None:
    with pytest.raises(SystemExit) as refused:
        main(["--every", interval])
    assert refused.value.code == 2


# --- the shard step -----------------------------------------------------------


def _shard_steps(job: Mapping[str, Any]) -> list[int]:
    return [
        index
        for index, step in enumerate(job.get("steps") or [])
        if _SHARD_RECIPE in recipes_invoked_by(str(step.get("run") or ""))
    ]


def _interval(sampler_line: str) -> int | None:
    text = sampler_line.removeprefix(_SAMPLER).removesuffix("&").strip()
    return int(text) if text.isascii() and text.isdigit() else None


def _step_violations(job_name: str, step: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    lines = executed_lines(step.get("run"))
    samplers = [index for index, line in enumerate(lines) if line.startswith(_SAMPLER)]
    tests = [index for index, line in enumerate(lines) if _SHARD_RECIPE in recipes_invoked_by(line)]
    if step.get("shell") != "bash":
        violations.append(f"{job_name} runs its shard in a shell that may not stop at a failed command")
    if any(line.startswith("set +e") or line.startswith("set +o errexit") for line in lines):
        violations.append(f"{job_name} lets its shard step go on after a failed command")
    if len(samplers) != 1:
        violations.append(f"{job_name} starts {len(samplers)} resource samplers beside its shard, not one")
        return violations
    sampler = lines[samplers[0]]
    interval = _interval(sampler)
    if not sampler.endswith(" &"):
        violations.append(f"{job_name} waits for a sampler that never ends before its tests")
    if interval is None or not 1 <= interval <= _LONGEST_INTERVAL:
        violations.append(f"{job_name} samples its runner less often than every {_LONGEST_INTERVAL} seconds")
    if samplers[0] > tests[0]:
        violations.append(f"{job_name} starts its resource sampler after its tests")
    last = lines[-1]
    if tests[-1] != len(lines) - 1 or any(operator in last for operator in _SHELL_OPERATORS):
        violations.append(f"{job_name} does not end its shard step on the tests' own exit status")
    return violations


def _kill_record_violations(job_name: str, job: Mapping[str, Any], shard_step: int) -> list[str]:
    reports = [
        (index, step)
        for index, step in enumerate(job.get("steps") or [])
        if any(_KILL_RECORDS in line.split() for line in executed_lines(step.get("run")))
    ]
    if len(reports) != 1:
        return [f"{job_name} holds {len(reports)} reports of the kernel's kill records, not one"]
    index, step = reports[0]
    violations: list[str] = []
    if str(step.get("if", "")).strip() != _ONLY_WHEN_FAILED:
        violations.append(f"{job_name} does not report the kernel's kill records exactly when the job failed")
    if index < shard_step:
        violations.append(f"{job_name} reports the kernel's kill records before its tests have run")
    return violations


def _step_limit_violations(job_name: str, job: Mapping[str, Any], shard_steps: list[Mapping[str, Any]]) -> list[str]:
    """Report a shard step that could run until the job's own limit, which keeps no log."""
    job_limit = job.get("timeout-minutes")
    for step in shard_steps:
        limit = step.get("timeout-minutes")
        if not isinstance(limit, int) or not isinstance(job_limit, int) or limit > job_limit - _LOG_MARGIN_MINUTES:
            return [f"{job_name} lets its shard step run until the job's limit, where its log is lost"]
    return []


def _moves_window_artifact(step: Mapping[str, Any], action: str) -> bool:
    named = str((step.get("with") or {}).get("name") or "")
    return str(step.get("uses") or "").startswith(action) and named == _WINDOW_ARTIFACT


def _window_producer_violations(document: Mapping[str, Any], job_name: str, job: Mapping[str, Any]) -> list[str]:
    """Report a shard job whose window projections no job it needs seeds and uploads."""
    needs = job.get("needs") or []
    needs = [needs] if isinstance(needs, str) else list(needs)
    for name in needs:
        steps = ((document.get("jobs") or {}).get(name) or {}).get("steps") or []
        seeds = [index for index, step in enumerate(steps) if _WINDOW_PROJECTIONS in str(step.get("run") or "")]
        uploads = [index for index, step in enumerate(steps) if _moves_window_artifact(step, _UPLOAD)]
        if seeds and uploads and seeds[0] < uploads[0]:
            return []
    return [f"{job_name} needs no job that seeds and uploads the window projections"]


def _shard_violations(document: Mapping[str, Any]) -> list[str]:
    """Report every way a shard could lose its resource lines, its exit status or its browser."""
    violations: list[str] = []
    for job_name, job in (document.get("jobs") or {}).items():
        shard_steps = _shard_steps(job)
        if not shard_steps:
            continue
        steps = job["steps"]
        for index in shard_steps:
            violations.extend(_step_violations(job_name, steps[index]))
        violations.extend(_kill_record_violations(job_name, job, shard_steps[-1]))
        violations.extend(_step_limit_violations(job_name, job, [steps[index] for index in shard_steps]))
        workers = str((job.get("env") or {}).get("CADRUMO_PYTEST_WORKERS", ""))
        if not workers.isdigit() or not 1 <= int(workers) <= _MOST_SHARD_WORKERS:
            violations.append(
                f"{job_name} runs its shard with {workers or 'no'} test workers, not 1 to {_MOST_SHARD_WORKERS}"
            )
        placed = [index for index, step in enumerate(steps) if _moves_window_artifact(step, _DOWNLOAD)]
        if not placed or placed[0] > shard_steps[0]:
            violations.append(f"{job_name} runs the shard population before placing the window projections")
        violations.extend(_window_producer_violations(document, job_name, job))
        setups = [step for step in steps if step.get("uses") == _SETUP_ACTION]
        if not any((step.get("with") or {}).get("browser") in (True, "true") for step in setups):
            violations.append(f"{job_name} runs the shard population without provisioning Chromium")
    return violations


def _live() -> dict[str, Any]:
    return yaml.safe_load(_MERGE_GATE.read_text(encoding="utf-8"))


def _shard_step(document: dict[str, Any]) -> dict[str, Any]:
    job = document["jobs"]["tests"]
    (index,) = _shard_steps(job)
    return job["steps"][index]


def _with_run(*lines: str) -> dict[str, Any]:
    document = _live()
    _shard_step(document)["run"] = "\n".join(lines) + "\n"
    return document


def test_the_shard_job_samples_its_runner_keeps_its_exit_status_and_has_chromium() -> None:
    document = _live()
    assert _shard_violations(document) == []
    # Anchor: the rule judges the one job that runs the shard population.
    assert [name for name, job in document["jobs"].items() if _shard_steps(job)] == ["tests"]


# --- teeth --------------------------------------------------------------------

_SAMPLE: Final = f"{_SAMPLER}30 &"
_TESTS: Final = 'just test-gate-shard "$SHARD" "$CHANGED_FILES"'


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        ((_TESTS,), "tests starts 0 resource samplers beside its shard, not one"),
        ((_SAMPLE, _SAMPLE, _TESTS), "tests starts 2 resource samplers beside its shard, not one"),
        ((f"{_SAMPLER}30", _TESTS), "tests waits for a sampler that never ends before its tests"),
        ((f"{_SAMPLER}600 &", _TESTS), "tests samples its runner less often than every 60 seconds"),
        ((f"{_SAMPLER}0 &", _TESTS), "tests samples its runner less often than every 60 seconds"),
        ((_SAMPLE, f"{_TESTS} || true"), "tests does not end its shard step on the tests' own exit status"),
        ((_SAMPLE, f"{_TESTS} | tee shard.log"), "tests does not end its shard step on the tests' own exit status"),
        ((_SAMPLE, _TESTS, "echo finished"), "tests does not end its shard step on the tests' own exit status"),
        (("set +e", _SAMPLE, _TESTS), "tests lets its shard step go on after a failed command"),
    ],
)
def test_the_shard_rule_reports_each_defect_planted_in_the_step(lines: tuple[str, ...], expected: str) -> None:
    assert _shard_violations(_with_run(*lines)) == [expected]


def test_the_shard_rule_reports_a_sampler_started_after_the_tests_and_another_shell() -> None:
    late = _with_run(f"{_TESTS} &", _SAMPLE)
    assert _shard_violations(late) == [
        "tests starts its resource sampler after its tests",
        "tests does not end its shard step on the tests' own exit status",
    ]

    other_shell = _live()
    _shard_step(other_shell)["shell"] = "sh"
    assert _shard_violations(other_shell) == ["tests runs its shard in a shell that may not stop at a failed command"]


def test_the_shard_rule_reports_a_missing_an_unconditional_and_an_early_kill_record_report() -> None:
    def report(document: dict[str, Any]) -> dict[str, Any]:
        steps = document["jobs"]["tests"]["steps"]
        return next(step for step in steps if _KILL_RECORDS in str(step.get("run") or ""))

    removed = _live()
    removed["jobs"]["tests"]["steps"].remove(report(removed))
    assert _shard_violations(removed) == ["tests holds 0 reports of the kernel's kill records, not one"]

    always = _live()
    report(always)["if"] = "${{ always() }}"
    assert _shard_violations(always) == ["tests does not report the kernel's kill records exactly when the job failed"]

    early = _live()
    steps = early["jobs"]["tests"]["steps"]
    steps.insert(0, steps.pop(steps.index(report(early))))
    assert _shard_violations(early) == ["tests reports the kernel's kill records before its tests have run"]


def test_the_shard_rule_reports_a_shard_job_without_chromium() -> None:
    document = _live()
    setup = next(step for step in document["jobs"]["tests"]["steps"] if step.get("uses") == _SETUP_ACTION)
    del setup["with"]["browser"]
    assert _shard_violations(document) == ["tests runs the shard population without provisioning Chromium"]


@pytest.mark.parametrize("workers", ["3", "4", "auto", ""])
def test_the_shard_rule_reports_more_workers_than_the_runner_holds(workers: str) -> None:
    document = _live()
    env = document["jobs"]["tests"]["env"]
    if workers:
        env["CADRUMO_PYTEST_WORKERS"] = workers
    else:
        del env["CADRUMO_PYTEST_WORKERS"]
    assert _shard_violations(document) == [
        f"tests runs its shard with {workers or 'no'} test workers, not 1 to {_MOST_SHARD_WORKERS}"
    ]


def test_the_shard_rule_reports_window_projections_missing_placed_late_or_never_produced() -> None:
    def download(steps: list[dict[str, Any]]) -> int:
        return next(index for index, step in enumerate(steps) if _moves_window_artifact(step, _DOWNLOAD))

    removed = _live()
    steps = removed["jobs"]["tests"]["steps"]
    del steps[download(steps)]
    assert _shard_violations(removed) == ["tests runs the shard population before placing the window projections"]

    late = _live()
    steps = late["jobs"]["tests"]["steps"]
    steps.append(steps.pop(download(steps)))
    assert _shard_violations(late) == ["tests runs the shard population before placing the window projections"]

    unneeded = _live()
    unneeded["jobs"]["tests"]["needs"] = [name for name in unneeded["jobs"]["tests"]["needs"] if name != "window"]
    assert _shard_violations(unneeded) == ["tests needs no job that seeds and uploads the window projections"]

    unseeded = _live()
    producer = unseeded["jobs"]["window"]["steps"]
    for step in producer:
        if _WINDOW_PROJECTIONS in str(step.get("run") or ""):
            step["run"] = "true"
    assert _shard_violations(unseeded) == ["tests needs no job that seeds and uploads the window projections"]


@pytest.mark.parametrize("limit", [None, 60, 56])
def test_the_shard_rule_reports_a_shard_step_without_a_limit_inside_the_jobs(limit: int | None) -> None:
    document = _live()
    step = _shard_step(document)
    if limit is None:
        del step["timeout-minutes"]
    else:
        step["timeout-minutes"] = limit
    assert _shard_violations(document) == ["tests lets its shard step run until the job's limit, where its log is lost"]
