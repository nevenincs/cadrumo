"""Development-owned per-invocation pytest logs under ``.logs``."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any
from uuid import uuid4

import pytest

_STATE_KEY = pytest.StashKey["RunLog"]()
_ACTIVE: RunLog | None = None


class RunLog:
    """Live, flush-on-write record for one pytest controller invocation."""

    def __init__(self, repository: Path) -> None:
        now = datetime.now(UTC)
        repository = repository.resolve()
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
        self.exit_status: int | None = None
        self.stream: IO[str] = self.path.open("x", encoding="utf-8", newline="\n")
        _apply_run_environment(self.root)
        product_logs = self.artifacts / "product-logs" / f"pid-{os.getpid()}"
        product_logs.mkdir(parents=True)
        os.environ["CADRUMO_LOG_DIR"] = str(product_logs)
        os.environ["CADRUMO_TEST_RUN_ROOT"] = str(self.root)
        self.write(f"START {now.isoformat()} pid={os.getpid()}")
        self.write(f"COMMAND {' '.join(sys.argv)}")

    def write(self, text: str) -> None:
        """Write and flush a record so failures survive a later hung lane."""
        self.stream.write(text.rstrip() + "\n")
        self.stream.flush()

    def finish(self, exitstatus: int | pytest.ExitCode) -> None:
        """Close the log and atomically leave machine-readable run metadata."""
        finished = datetime.now(UTC)
        self.exit_status = int(exitstatus)
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


def prepare_environment(repository: Path) -> None:
    """Mint the controller run before any production import can bind logging."""
    global _ACTIVE
    inherited_root = os.environ.get("CADRUMO_TEST_RUN_ROOT")
    if inherited_root:
        root = Path(inherited_root).resolve()
        _apply_run_environment(root)
        product_logs = root / "artifacts" / "product-logs" / f"pid-{os.getpid()}"
        product_logs.mkdir(parents=True, exist_ok=True)
        os.environ["CADRUMO_LOG_DIR"] = str(product_logs)
        return
    _ACTIVE = RunLog(repository)


def _apply_run_environment(root: Path) -> None:
    """Confine generic temporary, cache, coverage, and pytest scratch paths."""
    artifacts = root / "artifacts"
    cache = root / "cache"
    scratch = root / "scratch"
    for path in (artifacts, cache, scratch):
        path.mkdir(parents=True, exist_ok=True)
    os.environ["CADRUMO_TEST_RUN_ROOT"] = str(root)
    os.environ["COVERAGE_FILE"] = str(artifacts / ".coverage")
    os.environ["PYTEST_DEBUG_TEMPROOT"] = str(scratch)
    os.environ["XDG_CACHE_HOME"] = str(cache)
    os.environ["TEMP"] = str(scratch)
    os.environ["TMP"] = str(scratch)
    os.environ["TMPDIR"] = str(scratch)
    tempfile.tempdir = str(scratch)


def _worker_id(config: pytest.Config) -> str | None:
    """Return this process's xdist worker id, or ``None`` on the controller."""
    workerinput = getattr(config, "workerinput", None)
    if workerinput is None:
        return None
    identity = workerinput.get("workerid")
    return str(identity) if identity else None


def _confine_pytest_storage(config: pytest.Config, root: Path) -> None:
    """Rebind pytest objects created by its own early ``pytest_configure`` hooks.

    The basetemp is per-process, never shared. ``TempPathFactory.getbasetemp``
    treats an explicitly given basetemp as its own to own: it calls ``rm_rf`` on
    the path and then ``mkdir`` with no ``exist_ok``. Handing every xdist worker
    the same directory therefore did worse than collide -- whichever worker
    started second could delete the live ``tmp_path`` trees of one already
    running, and the loser of the ``mkdir`` race died at fixture setup with
    ``FileExistsError``. Suffixing the worker id keeps the run's temporary files
    confined to the run root while giving each process a directory no other
    process will clear.
    """
    cache = root / "cache" / "pytest"
    basetemp = root / "scratch" / "pytest"
    worker = _worker_id(config)
    if worker is not None:
        basetemp = basetemp / worker
    cache.mkdir(parents=True, exist_ok=True)
    basetemp.parent.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(basetemp)
    pytest_cache = getattr(config, "cache", None)
    if pytest_cache is not None:
        pytest_cache._cachedir = cache
    temp_factory = getattr(config, "_tmp_path_factory", None)
    if temp_factory is not None:
        temp_factory._given_basetemp = basetemp


def _announce(config: pytest.Config, message: str) -> None:
    """Write one notice to the terminal, falling back to stdout when headless."""
    terminal = config.pluginmanager.getplugin("terminalreporter")
    if terminal is not None:
        terminal.write_line(message, yellow=True)
    else:
        print(message, flush=True)


def configure(config: pytest.Config) -> None:
    """Create and announce the controller's unique run directory."""
    root = Path(os.environ["CADRUMO_TEST_RUN_ROOT"]).resolve()
    _confine_pytest_storage(config, root)
    if hasattr(config, "workerinput"):
        return
    global _ACTIVE
    run_log = _ACTIVE
    if run_log is None:
        run_log = RunLog(Path(config.rootpath))
        _ACTIVE = run_log
    config.stash[_STATE_KEY] = run_log
    _announce(config, f"test run log: {run_log.path} (cache={root / 'cache'}, scratch={root / 'scratch'})")


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


def restate(config: pytest.Config) -> None:
    """Repeat the run-log location as the session's last line.

    The opening notice scrolls out of reach on any run long enough to need it,
    and a caller who pipes the tail of a run -- the usual shape for a lane that
    takes minutes -- keeps only the end, which is precisely the part that did
    not say where the evidence went.

    This runs at unconfigure rather than session finish because pytest's own
    terminal reporter implements ``pytest_sessionfinish`` as a hookwrapper and
    prints the failure list and count line *after* every plain implementation
    yields. No ordinary session hook, ``trylast`` included, can land beneath
    that; unconfigure can. It prints rather than writing through the terminal
    reporter for the same reason: by now the reporter has said its last word.
    """
    run_log = config.stash.get(_STATE_KEY, None)
    if run_log is None:
        return
    print(
        f"test run log: {run_log.path} (exit={run_log.exit_status}, metadata={run_log.metadata_path})",
        flush=True,
    )
