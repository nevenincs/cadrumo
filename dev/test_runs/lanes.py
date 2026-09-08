"""Sequential execution of the full test-lane sweep, with per-lane timings.

This replaced a pair of `[windows]`/`[unix]` recipe bodies totalling 75 lines
that implemented one algorithm twice. The two halves had drifted in ways that
mattered: the bash body ran under `set -uo pipefail` and deliberately continued
after a failing lane, while the PowerShell body opened with
`$ErrorActionPreference = 'Stop'`, so the two disagreed about the recipe's
single most important property - whether a red lane stops the sweep.

Continuing is the correct behaviour and the one this module implements: the
lanes are independent, and a sweep that stops at the first failure reports one
problem where there may be five.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING

from dev._paths import REPO_ROOT, UTF_8
from dev.test_runs.paths import allocate_run_directory

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

#: The environment variable each lane reads to find the run's evidence root.
RUN_ROOT_ENV = "CADRUMO_TEST_ALL_RUN_ROOT"

#: Subdirectories every lane may write into, created before the sweep starts so
#: no lane has to defend against their absence.
RUN_SUBDIRECTORIES = ("artifacts", "cache", "scratch")

#: Width of the lane-name column in the closing summary.
_NAME_WIDTH = 34


@dataclass(frozen=True)
class LaneResult:
    """One lane's outcome.

    Args:
        name: The just recipe that was run.
        status: Its exit code.
        seconds: Wall-clock duration, rounded to whole seconds.
    """

    name: str
    status: int
    seconds: int


class _Tee:
    """Write to the console and to the run log at the same time.

    The bash body achieved this with `exec > >(tee -a "$log") 2>&1`, a process
    substitution with no PowerShell equivalent, which is why the two recipe
    bodies could not share an implementation.
    """

    def __init__(self, stream: IO[str], handle: IO[str]) -> None:
        self._stream = stream
        self._handle = handle

    def write(self, text: str) -> int:
        """Write ``text`` to both destinations."""
        self._handle.write(text)
        self._handle.flush()
        return self._stream.write(text)

    def flush(self) -> None:
        """Flush both destinations."""
        self._handle.flush()
        self._stream.flush()


def _run_lane(lane: str, env: dict[str, str]) -> LaneResult:
    """Run one lane and time it.

    Args:
        lane: The just recipe to invoke.
        env: The environment to run it under.

    Returns:
        The lane's result. A missing `just` is reported as a failed lane rather
        than raised, so the sweep still summarises what it did reach.
    """
    print(f"\n> {lane}", flush=True)
    started = time.monotonic()
    try:
        status = subprocess.run(["just", lane], env=env, check=False).returncode
    except OSError as exc:
        print(f"{lane} could not be started: {exc}", file=sys.stderr, flush=True)
        status = 127
    elapsed = int(time.monotonic() - started)

    if status == 0:
        print(f"PASS {lane} ({elapsed}s)", flush=True)
    else:
        print(f"FAIL {lane} (exit {status}, {elapsed}s)", file=sys.stderr, flush=True)
    return LaneResult(lane, status, elapsed)


def _summarise(results: Sequence[LaneResult]) -> None:
    """Print the per-lane summary table.

    Args:
        results: Every lane's outcome, in execution order.
    """
    print("\nTest lane summary", flush=True)
    for result in results:
        print(
            f"  {result.name:<{_NAME_WIDTH}} exit={result.status:<3} {result.seconds}s",
            flush=True,
        )


def run_lanes(lanes: Sequence[str], repository: Path = REPO_ROOT) -> int:
    """Run every lane in order, continuing past failures, and summarise.

    Args:
        lanes: The just recipes to run, in order.
        repository: The checkout the run evidence is written beneath.

    Returns:
        0 when every lane passed, otherwise the FIRST non-zero status any lane
        reported. Flattening that to 1 threw away the one thing a caller
        reading the number alone could use: a lane that could not run (127)
        looked exactly like a lane whose tests failed (1). See
        ``dev/EXIT-CODES.md``.
    """
    run_root = allocate_run_directory(repository, family="test-runs", label="test-all")
    for name in RUN_SUBDIRECTORIES:
        (run_root / name).mkdir(parents=True, exist_ok=True)

    env = {**os.environ, RUN_ROOT_ENV: str(run_root)}
    log_path = run_root / "run.log"

    with log_path.open("w", encoding=UTF_8) as handle:
        original_out, original_err = sys.stdout, sys.stderr
        sys.stdout = _Tee(original_out, handle)  # type: ignore[assignment]
        sys.stderr = _Tee(original_err, handle)  # type: ignore[assignment]
        try:
            print(f"test-all run log: {log_path}", flush=True)
            results = [_run_lane(lane, env) for lane in lanes]
            _summarise(results)
            print(f"test-all run log: {log_path}", flush=True)
        finally:
            sys.stdout, sys.stderr = original_out, original_err

    return next((r.status for r in results if r.status != 0), 0)
