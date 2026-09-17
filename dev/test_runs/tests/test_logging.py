"""Integration contract for pytest's per-run storage confinement."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from io import StringIO
from pathlib import Path
from typing import IO

import pytest

from dev._paths import REPO_ROOT
from dev.test_runs.logging import RunLog, _redirect_collection_output

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
    environment = os.environ.copy()
    environment.pop("CADRUMO_TEST_RUN_ROOT", None)
    environment["CADRUMO_INTERNAL_ERROR_PROBE"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n0",
            "-p",
            "dev.test_runs.tests.internal_error_probe",
            "dev/test_runs/tests/path_probe.py",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == pytest.ExitCode.INTERNAL_ERROR, result.stdout + result.stderr
    match = re.search(r"test run log: (?P<path>.+?run\.log)", result.stdout)
    assert match is not None, result.stdout
    transcript = Path(match.group("path")).read_text(encoding="utf-8")
    assert "INTERNALERROR" in transcript
    assert "RuntimeError: internal error persistence probe" in transcript


def test_real_child_pytest_confines_cache_and_basetemp_to_its_run(tmp_path: Path) -> None:
    report = tmp_path / "pytest-paths.json"
    environment = os.environ.copy()
    environment.pop("CADRUMO_TEST_RUN_ROOT", None)
    environment["CADRUMO_PYTEST_PATH_PROBE"] = str(report)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n0",
            "dev/test_runs/tests/path_probe.py",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    paths = json.loads(report.read_text(encoding="utf-8"))
    run_root = Path(paths["run_root"]).resolve()
    assert Path(paths["cache"]).resolve() == run_root / "cache" / "pytest"
    assert Path(paths["basetemp"]).resolve() == run_root / "scratch" / "pytest"
    assert Path(paths["stdlib_temp"]).resolve() == run_root / "scratch"
    assert Path(paths["storage_root"]).resolve().parent == run_root / "scratch"


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
    environment = os.environ.copy()
    environment.pop("CADRUMO_TEST_RUN_ROOT", None)
    environment["CADRUMO_WORKER_BASETEMP_PROBE"] = str(records)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n",
            "2",
            # `each` rather than the default `load`: the probe's tests are fast
            # enough that load-balancing hands every one of them to the first
            # free worker, which proves nothing about two workers at once.
            "--dist",
            "each",
            "dev/test_runs/tests/worker_basetemp_probe.py",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
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
        assert basetemp.parent.parent.name == "scratch"
