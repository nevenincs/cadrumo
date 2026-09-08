"""Development-owned per-invocation pytest logs under ``.logs``."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any
from uuid import uuid4

import pytest

_STATE_KEY = pytest.StashKey["RunLog"]()
_ACTIVE: RunLog | None = None


class RunLog:
    """Live, flush-on-write record for one pytest controller invocation."""

    def __init__(self, config: pytest.Config) -> None:
        now = datetime.now(UTC)
        repository = Path(config.rootpath).resolve()
        marker = f"{now:%Y%m%dT%H%M%S.%fZ}-pytest-{os.getpid()}-{uuid4().hex[:8]}"
        self.root = repository / ".logs" / "test-runs" / f"{now:%Y-%m-%d}" / marker
        self.root.mkdir(parents=True, exist_ok=False)
        self.artifacts = self.root / "artifacts"
        self.cache = self.root / "cache"
        self.scratch = self.root / "scratch"
        for path in (self.artifacts, self.cache, self.scratch):
            path.mkdir()
        self.path = self.root / "run.log"
        self.metadata_path = self.root / "run.json"
        self.started = now
        self.stream: IO[str] = self.path.open("x", encoding="utf-8", newline="\n")
        os.environ["COVERAGE_FILE"] = str(self.artifacts / ".coverage")
        os.environ["PYTEST_DEBUG_TEMPROOT"] = str(self.scratch)
        self.write(f"START {now.isoformat()} pid={os.getpid()}")
        self.write(f"COMMAND {' '.join(sys.argv)}")

    def write(self, text: str) -> None:
        """Write and flush a record so failures survive a later hung lane."""
        self.stream.write(text.rstrip() + "\n")
        self.stream.flush()

    def finish(self, exitstatus: int | pytest.ExitCode) -> None:
        """Close the log and atomically leave machine-readable run metadata."""
        finished = datetime.now(UTC)
        self.write(f"FINISH {finished.isoformat()} exit={int(exitstatus)}")
        self.stream.close()
        payload: dict[str, Any] = {
            "artifacts": str(self.artifacts),
            "cache": str(self.cache),
            "command": sys.argv,
            "exit_status": int(exitstatus),
            "finished_at": finished.isoformat(),
            "log": str(self.path),
            "run_id": self.root.name,
            "scratch": str(self.scratch),
            "started_at": self.started.isoformat(),
        }
        self.metadata_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def configure(config: pytest.Config) -> None:
    """Create and announce the controller's unique run directory."""
    if hasattr(config, "workerinput"):
        return
    global _ACTIVE
    run_log = RunLog(config)
    _ACTIVE = run_log
    config.stash[_STATE_KEY] = run_log
    terminal = config.pluginmanager.getplugin("terminalreporter")
    message = f"test run log: {run_log.path}"
    if terminal is not None:
        terminal.write_line(message, yellow=True)
    else:
        print(message, flush=True)


def log_start(nodeid: str) -> None:
    """Record a test identity before its body starts."""
    if _ACTIVE is not None:
        _ACTIVE.write(f"RUN {nodeid}")


def log_report(report: pytest.TestReport) -> None:
    """Record every terminal phase and flush failure detail immediately."""
    if _ACTIVE is None:
        return
    if report.when == "call" or report.failed:
        _ACTIVE.write(f"{report.outcome.upper()} {report.nodeid} phase={report.when} duration={report.duration:.6f}s")
    if report.failed:
        _ACTIVE.write(str(report.longrepr))
        if report.capstdout:
            _ACTIVE.write("CAPTURED STDOUT\n" + report.capstdout)
        if report.capstderr:
            _ACTIVE.write("CAPTURED STDERR\n" + report.capstderr)


def log_collection_report(report: pytest.CollectReport) -> None:
    """Persist collection failures before test execution can begin."""
    if not report.failed:
        return
    if _ACTIVE is not None:
        _ACTIVE.write(f"COLLECTION FAILED {report.nodeid}\n{report.longrepr}")


def finish(config: pytest.Config, exitstatus: int | pytest.ExitCode) -> None:
    """Finalize controller metadata."""
    global _ACTIVE
    run_log = config.stash.get(_STATE_KEY, None)
    if run_log is not None:
        run_log.finish(exitstatus)
        _ACTIVE = None
