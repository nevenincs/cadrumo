"""Persist bounded build phase timings without commands, environments or secrets."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .build_log import BuildLog, display_path


class BuildTimings:
    """One producer's timings, stored outside every generated payload inventory."""

    def __init__(self, build: Path, action: str, *, log: BuildLog | None = None) -> None:
        """Choose a unique record inside the admitted build's timing directory."""
        if re.fullmatch(r"[a-zA-Z0-9_.-]+", action) is None:
            raise ValueError("Build timing action must be a simple identifier")
        directory = build.resolve(strict=True) / "timings"
        if directory.is_symlink() or directory.is_junction():
            raise ValueError("Build timing directory must not be linked")
        directory.mkdir(exist_ok=True)
        self.path = directory / f"{action}-{uuid4().hex}.json"
        self.log = BuildLog(action) if log is None else log
        self._phases: list[dict[str, str | float]] = []
        self._failures = 0
        self._exit_codes: list[int] = []
        self._report: dict[str, object] = {
            "schema": 1,
            "action": action,
            "started_utc": datetime.now(UTC).isoformat(),
            "phases": self._phases,
            "command_exit_codes": self._exit_codes,
        }

    @property
    def failed(self) -> bool:
        """Whether any phase failed or any recorded command exited nonzero."""
        return self._failures > 0

    def command_completed(self, returncode: int) -> None:
        """Record command failure without retaining its arguments or output."""
        self._exit_codes.append(returncode)
        if returncode:
            self._failures += 1
            self.log.verbose(f"command exited with status {returncode}")

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Retain completed and failed intervals, including process-local CPU."""
        started = time.monotonic()
        cpu = time.process_time()
        failures = self._failures
        outcome = "pass"
        self.log.debug(f"phase {name}: started")
        try:
            yield
        except BaseException:
            self._failures += 1
            outcome = "fail"
            raise
        finally:
            if self._failures != failures:
                outcome = "fail"
            wall = time.monotonic() - started
            self._phases.append(
                {
                    "phase": name,
                    "wall_seconds": wall,
                    "own_cpu_seconds": time.process_time() - cpu,
                    "outcome": outcome,
                }
            )
            self.path.write_text(json.dumps(self._report, indent=2), encoding="utf-8")
            if name != "total":  # measure_build reports the total itself.
                self.log.verbose(f"phase {name}: {outcome} in {wall:.1f} s")


@contextmanager
def measure_build(build: Path, action: str, *, log: BuildLog | None = None) -> Iterator[BuildTimings]:
    """Retain total duration even when a producer fails or refuses moving inputs."""
    timings = BuildTimings(build, action, log=log)
    started = time.monotonic()
    failed = True
    try:
        with timings.phase("total"):
            yield timings
        failed = timings.failed
    finally:
        elapsed = time.monotonic() - started
        if failed:
            timings.log.error(f"failed after {elapsed:.1f} s; timings: {display_path(timings.path)}")
        else:
            timings.log.status(f"finished in {elapsed:.1f} s")
