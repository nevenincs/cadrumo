"""Integration contract for pytest's per-run storage confinement."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from io import StringIO
from pathlib import Path
from typing import IO

import pytest
from coverage import CoverageData

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import CommandResult, run_command
from dev.test_runs.logging import RunLog, _redirect_collection_output
from dev.test_runs.paths import (
    SCRATCH_PREFIX,
    SCRATCH_SEPARATOR,
    ScratchAllocation,
    allocate_scratch_directory,
)
from dev.test_runs.tests.authority_probe import LEAK_LEASE_ENV
from dev.test_runs.tests.failing_probe import FAILURE_MESSAGE
from dev.test_runs.tests.setup_skip_probe import SKIP_REASON

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.serial]


class _FakeTerminalWriter:
    """A stand-in for the terminal reporter's underlying writer."""

    def __init__(self, file: StringIO) -> None:
        self._file: StringIO = file


class _FakeTerminalReporter:
    """A stand-in for the ``terminalreporter`` plugin, exposing only ``_tw``."""

    def __init__(self, file: StringIO) -> None:
        self._tw = _FakeTerminalWriter(file)


class _FakeRunLog(RunLog):
    """A run-log stand-in carrying only the stream ``_redirect_collection_output`` writes to."""

    def __init__(self, stream: IO[str]) -> None:
        self.stream = stream


class _FinishedRunLog(RunLog):
    """A finished run log carrying only what ``release_scratch`` reads.

    Built without the real constructor, which would repoint this process's own
    temporary directory at a new scratch and register a second exit release.
    """

    def __init__(self, path: Path, scratch_allocation: ScratchAllocation, exit_status: int | None) -> None:
        self.path = path
        self.scratch_allocation = scratch_allocation
        self.exit_status = exit_status


def _top_level_environment() -> dict[str, str]:
    """Return an environment in which a child pytest mints its own run rather than joining this one."""
    environment = os.environ.copy()
    environment.pop("CADRUMO_TEST_RUN_ROOT", None)
    environment.pop("CADRUMO_TEST_RUN_SCRATCH", None)
    return environment


def _coverage_environment(log_root: Path) -> dict[str, str]:
    """Give an independent configured pytest no injected module search path or inherited collector."""
    environment = _top_level_environment()
    for name in ("PYTHONPATH", "COVERAGE_FILE", "CADRUMO_TEST_COVERAGE_FILE", "CADRUMO_TEST_COVERAGE_WORKER_PID"):
        environment.pop(name, None)
    environment["CADRUMO_TEST_LOG_ROOT"] = str(log_root)
    return environment


def _coverage_probe(directory: Path, records: Path) -> Path:
    directory.mkdir()
    subject = directory / "coverage_subject.py"
    subject.write_text(
        'def choose(worker):\n    if worker == "gw0":\n        return 11\n    return 29\n', encoding="utf-8"
    )
    (directory / "test_coverage_probe.py").write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "import pytest\n"
        "from coverage_subject import choose\n"
        "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n"
        "def test_probe():\n"
        "    worker = os.environ['PYTEST_XDIST_WORKER']\n"
        "    assert choose(worker) in (11, 29)\n"
        f"    (Path({str(records)!r}) / (worker + '.json')).write_text(json.dumps({{\n"
        "        'coverage': os.environ['COVERAGE_FILE'],\n"
        "        'run_root': os.environ['CADRUMO_TEST_RUN_ROOT'],\n"
        "    }))\n",
        encoding="utf-8",
    )
    return subject


@pytest.mark.parametrize("invocation", ["console", "configured-temporary-cwd"])
@pytest.mark.parametrize("explicit_destination", [False, True], ids=["default", "explicit"])
def test_coverage_controller_combines_both_workers_in_one_admitted_file(
    tmp_path: Path, invocation: str, explicit_destination: bool
) -> None:
    records = tmp_path / "records"
    records.mkdir()
    fixture = tmp_path / "fixture"
    subject = _coverage_probe(fixture, records)
    report = tmp_path / "coverage.json"
    environment = _coverage_environment(tmp_path / "logs")
    explicit = tmp_path / "explicit" / ".coverage"
    if explicit_destination:
        environment["COVERAGE_FILE"] = str(explicit)
    if invocation == "console":
        uv = shutil.which("uv")
        assert uv is not None
        command = [uv, "run", "--no-sync", "pytest"]
        cwd = REPO_ROOT
    else:
        command = [sys.executable, "-m", "pytest", "-c", str(REPO_ROOT / "pyproject.toml")]
        cwd = fixture
    result = run_command(
        [
            *command,
            "-q",
            "-n2",
            "--dist=each",
            f"--cov={fixture}",
            f"--cov-config={REPO_ROOT / 'pyproject.toml'}",
            f"--cov-report=json:{report}",
            "--cov-fail-under=100",
            str(fixture),
        ],
        cwd=cwd,
        environment=environment,
        errors="replace",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    observed = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in records.glob("*.json")}
    assert set(observed) == {"gw0", "gw1"}
    destinations = {Path(record["coverage"]) for record in observed.values()}
    assert len(destinations) == 1
    (destination,) = destinations
    if explicit_destination:
        assert destination == explicit
    else:
        (run_root,) = {Path(record["run_root"]) for record in observed.values()}
        assert destination == run_root / "artifacts" / ".coverage"
    assert list(destination.parent.glob(destination.name + ".*")) == []
    data = CoverageData(basename=str(destination))
    data.read()
    assert set(data.lines(str(subject)) or ()) == {1, 2, 3, 4}
    assert {(2, 3), (2, 4)} <= set(data.arcs(str(subject)) or ())
    totals = json.loads(report.read_text(encoding="utf-8"))["totals"]
    assert totals["percent_covered"] == 100
    assert totals["covered_branches"] == totals["num_branches"] == 2


def test_nested_coverage_gets_its_own_destination_without_replacing_its_parent(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = tmp_path / "child"
    parent.mkdir()
    child.mkdir()
    subject = parent / "parent_subject.py"
    subject.write_text("def before():\n    return 11\n\ndef after():\n    return 29\n", encoding="utf-8")
    child_subject = child / "child_subject.py"
    child_subject.write_text("def value():\n    return 7\n", encoding="utf-8")
    child_file = tmp_path / "child-file.txt"
    child_report = tmp_path / "child-report.json"
    child_probe = child / "test_child_probe.py"
    child_probe.write_text(
        "import os\nfrom pathlib import Path\nimport pytest\nfrom child_subject import value\n"
        "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n"
        "def test_child():\n    assert value() == 7\n"
        f"    Path({str(child_file)!r}).write_text(os.environ['COVERAGE_FILE'])\n",
        encoding="utf-8",
    )
    child_arguments = [
        "-m",
        "pytest",
        "-c",
        str(REPO_ROOT / "pyproject.toml"),
        "-q",
        "-n0",
        f"--cov={child}",
        f"--cov-config={REPO_ROOT / 'pyproject.toml'}",
        f"--cov-report=json:{child_report}",
        "--cov-fail-under=100",
        str(child_probe),
    ]
    parent_file = tmp_path / "parent-file.txt"
    (parent / "test_parent_probe.py").write_text(
        "import os, subprocess, sys\nfrom pathlib import Path\nimport pytest\n"
        "from parent_subject import before, after\n"
        "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n"
        "def test_parent():\n    assert before() == 11\n"
        f"    Path({str(parent_file)!r}).write_text(os.environ['COVERAGE_FILE'])\n"
        f"    result = subprocess.run([sys.executable, *{child_arguments!r}], cwd={str(child)!r}, "
        "capture_output=True, text=True, check=False)\n"
        "    assert result.returncode == 0, result.stdout + result.stderr\n"
        "    assert after() == 29\n",
        encoding="utf-8",
    )
    parent_report = tmp_path / "parent-report.json"
    result = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(REPO_ROOT / "pyproject.toml"),
            "-q",
            "-n1",
            f"--cov={parent}",
            f"--cov-config={REPO_ROOT / 'pyproject.toml'}",
            f"--cov-report=json:{parent_report}",
            "--cov-fail-under=100",
            str(parent),
        ],
        cwd=parent,
        environment=_coverage_environment(tmp_path / "logs"),
        errors="replace",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    parent_destination = Path(parent_file.read_text(encoding="utf-8"))
    child_destination = Path(child_file.read_text(encoding="utf-8"))
    assert parent_destination != child_destination
    for destination, measured, expected in (
        (parent_destination, subject, {1, 2, 4, 5}),
        (child_destination, child_subject, {1, 2}),
    ):
        data = CoverageData(basename=str(destination))
        data.read()
        assert set(data.lines(str(measured)) or ()) == expected
        assert set(data.measured_files()) == {str(measured)}
        assert list(destination.parent.glob(destination.name + ".*")) == []


def test_coverage_startup_failure_releases_its_reserved_run_directory(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "conftest.py").write_text('raise RuntimeError("coverage bootstrap probe failure")\n', encoding="utf-8")
    logs = tmp_path / "logs"
    result = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(REPO_ROOT / "pyproject.toml"),
            "-n0",
            f"--confcutdir={fixture}",
            f"--cov={fixture}",
            str(fixture),
        ],
        cwd=fixture,
        environment=_coverage_environment(logs),
        errors="replace",
    )

    assert result.returncode == pytest.ExitCode.USAGE_ERROR, result.stdout + result.stderr
    assert "coverage bootstrap probe failure" in result.stderr
    assert list(logs.rglob("*-pytest-*")) == []


def test_coverage_refuses_output_outside_the_admitted_temporary_tree(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    environment = _coverage_environment(tmp_path / "logs")
    refused = REPO_ROOT / "coverage-refused-output" / ".coverage"
    assert not refused.parent.exists()
    environment["COVERAGE_FILE"] = str(refused)
    result = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(REPO_ROOT / "pyproject.toml"),
            "-n0",
            f"--cov={fixture}",
            str(fixture),
        ],
        cwd=fixture,
        environment=environment,
        errors="replace",
    )

    assert result.returncode == pytest.ExitCode.USAGE_ERROR, result.stdout + result.stderr
    assert "COVERAGE_FILE" in result.stderr
    assert not refused.parent.exists()


def _run_child_pytest(*pytest_arguments: str, env: dict[str, str]) -> CommandResult:
    return run_command(
        [sys.executable, "-m", "pytest", *pytest_arguments],
        cwd=REPO_ROOT,
        environment=env,
        errors="replace",
    )


def _child_run_log(result: CommandResult) -> Path:
    """Return the run log a finished child pytest controller announced."""
    match = re.search(r"test run log: (?P<path>.+?run\.log)", result.stdout)
    assert match is not None, result.stdout + result.stderr
    return Path(match.group("path"))


def _scratch_of(run_log: Path) -> Path:
    """Return the scratch a finished child run recorded in its metadata."""
    return Path(json.loads(run_log.with_name("run.json").read_text(encoding="utf-8"))["scratch"])


@pytest.mark.parametrize("exit_status", [0, 1, None])
def test_every_exit_status_removes_the_scratch(tmp_path: Path, exit_status: int | None) -> None:
    scratch = allocate_scratch_directory()
    (scratch / "left-by-a-test.txt").write_text("scratch content", encoding="utf-8")
    run_log = _FinishedRunLog(tmp_path / "run.log", ScratchAllocation.record(scratch), exit_status)
    try:
        line = run_log.release_scratch()

        assert line == f"SCRATCH REMOVED {scratch}", line
        assert not scratch.exists()
        assert (tmp_path / "run.log").read_text(encoding="utf-8") == line + "\n"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_a_refused_removal_is_recorded_in_the_run_log_and_never_raised(tmp_path: Path) -> None:
    """A passing run whose scratch record points outside its allocation keeps that path and says why."""
    unrelated = tmp_path / "not-a-scratch"
    unrelated.mkdir()
    status = unrelated.stat()
    run_log = _FinishedRunLog(
        tmp_path / "run.log", ScratchAllocation(unrelated, os.getpid(), (status.st_dev, status.st_ino)), 0
    )

    line = run_log.release_scratch()

    assert line.startswith(f"SCRATCH NOT REMOVED {unrelated}: ScratchOwnershipError: "), line
    assert unrelated.is_dir()
    assert (tmp_path / "run.log").read_text(encoding="utf-8") == line + "\n"


def test_a_passing_run_removes_its_scratch_and_leaves_its_run_log() -> None:
    result = _run_child_pytest(
        "-q",
        "-n0",
        "dev/test_runs/tests/setup_skip_probe.py",
        env=_top_level_environment(),
    )
    output, run_log = result.stdout + result.stderr, _child_run_log(result)

    assert result.returncode == pytest.ExitCode.OK, output
    scratch = _scratch_of(run_log)
    assert not scratch.exists(), f"a passing run left its scratch behind: {scratch}"
    # The run's own logs sit under `.tmp/logs/test-runs`, not in the scratch, and survive it.
    assert run_log.with_name("run.json").is_file()
    assert run_log.read_text(encoding="utf-8").splitlines()[-1] == f"SCRATCH REMOVED {scratch}"


def test_a_failing_run_removes_its_scratch() -> None:
    result = _run_child_pytest(
        "-q",
        "-n0",
        "dev/test_runs/tests/failing_probe.py",
        env=_top_level_environment(),
    )
    output, run_log = result.stdout + result.stderr, _child_run_log(result)

    assert result.returncode == pytest.ExitCode.TESTS_FAILED, output
    assert FAILURE_MESSAGE in output
    scratch = _scratch_of(run_log)
    assert not scratch.exists(), f"a failing run left its scratch behind: {scratch}"
    assert run_log.read_text(encoding="utf-8").splitlines()[-1] == f"SCRATCH REMOVED {scratch}"


def _registry_reading_environment(*, leak_lease: bool = False) -> dict[str, str]:
    """Return an environment in which a child run freezes its own authority snapshot."""
    environment = _top_level_environment()
    environment["CADRUMO_AUTHORITY_ROOT"] = str(REPO_ROOT / ".authority")
    if leak_lease:
        environment[LEAK_LEASE_ENV] = "1"
    return environment


def test_a_passing_run_that_read_the_registry_removes_its_scratch() -> None:
    """The shared owner held the run's frozen snapshot open, which Windows will not let anything delete.

    Released at session end, the snapshot and the scratch around it go with the run.
    """
    result = _run_child_pytest(
        "-q",
        "-n0",
        "dev/test_runs/tests/authority_probe.py",
        env=_registry_reading_environment(),
    )
    output, run_log = result.stdout + result.stderr, _child_run_log(result)

    assert result.returncode == pytest.ExitCode.OK, output
    scratch = _scratch_of(run_log)
    assert run_log.read_text(encoding="utf-8").splitlines()[-1] == f"SCRATCH REMOVED {scratch}"
    assert not scratch.exists()


def test_deselected_prorrata_suite_does_not_retain_authority_at_collection() -> None:
    """A collected but deselected suite never starts its authority lease lifetime."""
    result = _run_child_pytest(
        "--collect-only",
        "-q",
        "-n0",
        "-m",
        "serial",
        "src/cadrumo/adapters/persistence/profile/tests/test_prorrata_lifecycle_atomic_sources.py",
        env=_registry_reading_environment(),
    )
    output, run_log = result.stdout + result.stderr, _child_run_log(result)
    scratch = _scratch_of(run_log)
    try:
        assert result.returncode == pytest.ExitCode.NO_TESTS_COLLECTED, output
        assert "the shared registry authority stayed open" not in output, output
        assert "was created in a different Context" not in output, output
        assert run_log.read_text(encoding="utf-8").splitlines()[-1] == f"SCRATCH REMOVED {scratch}"
        assert not scratch.exists()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_a_parallel_run_that_read_the_registry_removes_its_scratch() -> None:
    """Workers read the controller's snapshot and are gone before the controller removes it."""
    result = _run_child_pytest(
        "-q",
        "-n",
        "2",
        "dev/test_runs/tests/authority_probe.py",
        env=_registry_reading_environment(),
    )
    output, run_log = result.stdout + result.stderr, _child_run_log(result)

    assert result.returncode == pytest.ExitCode.OK, output
    scratch = _scratch_of(run_log)
    assert run_log.read_text(encoding="utf-8").splitlines()[-1] == f"SCRATCH REMOVED {scratch}"
    assert not scratch.exists()


def test_a_failing_run_that_read_the_registry_removes_its_scratch() -> None:
    result = _run_child_pytest(
        "-q",
        "-n0",
        "dev/test_runs/tests/authority_probe.py",
        "dev/test_runs/tests/failing_probe.py",
        env=_registry_reading_environment(),
    )
    output, run_log = result.stdout + result.stderr, _child_run_log(result)
    scratch = _scratch_of(run_log)
    try:
        assert result.returncode == pytest.ExitCode.TESTS_FAILED, output
        assert run_log.read_text(encoding="utf-8").splitlines()[-1] == f"SCRATCH REMOVED {scratch}"
        assert not scratch.exists()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_a_lease_left_open_is_reported_and_leaves_the_runs_verdict_alone() -> None:
    """A release refused under a live lease is reported, never raised, and the run still passes."""
    result = _run_child_pytest(
        "-q",
        "-n0",
        "dev/test_runs/tests/authority_probe.py",
        env=_registry_reading_environment(leak_lease=True),
    )
    output, run_log = result.stdout + result.stderr, _child_run_log(result)
    scratch = _scratch_of(run_log)
    try:
        assert result.returncode == pytest.ExitCode.OK, output
        assert "the shared registry authority stayed open at session end" in result.stderr, output
        assert run_log.read_text(encoding="utf-8").splitlines()[-1].startswith("SCRATCH "), output
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_collect_only_terminal_output_is_redirected_to_the_run_log(tmp_path: Path) -> None:
    transcript = (tmp_path / "run.log").open("w", encoding="utf-8")
    console = StringIO()
    terminal = _FakeTerminalReporter(console)
    pluginmanager = pytest.PytestPluginManager()
    pluginmanager.register(terminal, name="terminalreporter")
    config = pytest.Config(pluginmanager)
    config.option.collectonly = True
    run_log = _FakeRunLog(transcript)

    assert _redirect_collection_output(config, run_log)
    terminal._tw._file.write("<Module noisy_collection.py>\n")
    transcript.close()

    assert console.getvalue() == ""
    assert (tmp_path / "run.log").read_text(encoding="utf-8") == "<Module noisy_collection.py>\n"


def test_real_child_pytest_persists_internal_error_traceback() -> None:
    environment = _top_level_environment()
    environment["CADRUMO_INTERNAL_ERROR_PROBE"] = "1"
    result = _run_child_pytest(
        "-q",
        "-n0",
        "-p",
        "dev.test_runs.tests.internal_error_probe",
        "dev/test_runs/tests/path_probe.py",
        env=environment,
    )

    assert result.returncode == pytest.ExitCode.INTERNAL_ERROR, result.stdout + result.stderr
    match = re.search(r"test run log: (?P<path>.+?run\.log)", result.stdout)
    assert match is not None, result.stdout
    transcript = Path(match.group("path")).read_text(encoding="utf-8")
    assert "INTERNALERROR" in transcript
    assert "RuntimeError: internal error persistence probe" in transcript


def test_real_child_pytest_records_a_setup_skip_as_the_tests_verdict() -> None:
    """A test skipped before its body still ends its ``RUN`` line with a verdict."""
    environment = _top_level_environment()
    result = _run_child_pytest(
        "-q",
        "-n0",
        "dev/test_runs/tests/setup_skip_probe.py",
        env=environment,
    )

    assert result.returncode == pytest.ExitCode.OK, result.stdout + result.stderr
    match = re.search(r"test run log: (?P<path>.+?run\.log)", result.stdout)
    assert match is not None, result.stdout
    transcript = Path(match.group("path")).read_text(encoding="utf-8").splitlines()
    nodeid = "dev/test_runs/tests/setup_skip_probe.py::test_skipped_before_its_body"
    started = transcript.index(f"RUN {nodeid}")
    verdicts = [line for line in transcript[started + 1 :] if line.startswith(f"SKIPPED {nodeid} phase=setup ")]
    assert len(verdicts) == 1, transcript
    assert f"Skipped: {SKIP_REASON}" in transcript


def test_real_child_pytest_confines_cache_and_basetemp_to_its_run(tmp_path: Path) -> None:
    report = tmp_path / "pytest-paths.json"
    ambient_cache = tmp_path / "ambient-cache"
    environment = _top_level_environment()
    environment["CADRUMO_PYTEST_PATH_PROBE"] = str(report)
    environment["XDG_CACHE_HOME"] = str(ambient_cache)
    configured_storage = tmp_path / "configured-storage"
    environment["CADRUMO_STORAGE_ROOT"] = str(configured_storage)
    result = _run_child_pytest(
        "-q",
        "-n0",
        "dev/test_runs/tests/path_probe.py",
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    paths = json.loads(report.read_text(encoding="utf-8"))
    run_root = Path(paths["run_root"]).resolve()
    scratch = Path(paths["scratch"]).resolve()
    assert Path(paths["cache"]).resolve() == run_root / "cache" / "pytest"
    # The child inherits machine-managed tool paths unchanged.
    assert paths["tool_cache_home"] == str(ambient_cache)
    assert Path(paths["basetemp"]).resolve() == scratch / "pytest"
    assert Path(paths["stdlib_temp"]).resolve() == scratch
    storage_root = Path(paths["storage_root"]).resolve()
    assert storage_root.parent == Path(paths["stdlib_temp"]).resolve()
    assert Path(json.loads((run_root / "run.json").read_text(encoding="utf-8"))["scratch"]).resolve() == scratch


def test_parallel_workers_each_get_a_private_basetemp_inside_the_run(tmp_path: Path) -> None:
    """Prove the confinement survives xdist rather than having workers clear each other.

    ``TempPathFactory.getbasetemp`` ``rm_rf``s an explicitly given basetemp and
    then ``mkdir``s it without ``exist_ok``. When every worker was handed the
    same directory, the second one to start deleted the first one's live
    ``tmp_path`` trees and one of them died at fixture setup. The child run
    below uses ``tmp_path`` on every test precisely so that path is exercised.
    """
    records = tmp_path / "records"
    records.mkdir()
    environment = _top_level_environment()
    environment["CADRUMO_WORKER_BASETEMP_PROBE"] = str(records)
    result = _run_child_pytest(
        "-q",
        "-n",
        "2",
        # `each` rather than the default `load`: the probe's tests are fast
        # enough that load-balancing hands every one of them to the first
        # free worker, which proves nothing about two workers at once.
        "--dist",
        "each",
        "dev/test_runs/tests/worker_basetemp_probe.py",
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    written = [json.loads(path.read_text(encoding="utf-8")) for path in records.glob("*.json")]
    assert len(written) == 16, written

    basetemps = {record["worker"]: Path(record["basetemp"]).resolve() for record in written}
    assert len(basetemps) == 2, f"the child run did not reach both workers: {basetemps}"
    assert len(set(basetemps.values())) == len(basetemps), f"workers shared a basetemp: {basetemps}"
    for worker, basetemp in basetemps.items():
        assert basetemp.name == worker, f"{worker} did not own its basetemp: {basetemp}"
        assert basetemp.parent.name == "pytest"
        assert basetemp.parent.parent.name.startswith(f"{SCRATCH_PREFIX}{SCRATCH_SEPARATOR}")
    assert len({basetemp.parent.parent for basetemp in basetemps.values()}) == 1, f"workers split the run: {basetemps}"

    # Every worker wrote into the shared scratch until its last test, so a removal
    # by anything but the controller, after they were gone, would have failed a
    # test above; the controller's removal then took the whole scratch.
    (scratch,) = {basetemp.parent.parent for basetemp in basetemps.values()}
    match = re.search(r"test run log: (?P<path>.+?run\.log)", result.stdout)
    assert match is not None, result.stdout
    released = Path(match.group("path")).read_text(encoding="utf-8").splitlines()[-1]
    assert released.startswith("SCRATCH REMOVED "), released
    assert Path(released.removeprefix("SCRATCH REMOVED ")).resolve() == scratch
    assert not scratch.exists()
