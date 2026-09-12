"""Sequential execution of named lanes, with per-lane timings.

This replaced a pair of `[windows]`/`[unix]` recipe bodies totalling 75 lines
that implemented one algorithm twice. The two halves had drifted in ways that
mattered: the bash body ran under `set -uo pipefail` and deliberately continued
after a failing lane, while the PowerShell body opened with
`$ErrorActionPreference = 'Stop'`, so the two disagreed about the recipe's
single most important property - whether a red lane stops the sweep.

Continuing is the default behaviour and the one this module implements: the
lanes are independent, and a sweep that stops at the first failure reports one
problem where there may be five. Callers may also declare an initial preflight
prefix. Every preflight still runs, but a failed preflight blocks later lanes
whose evidence would only repeat the prerequisite failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING

from dev._paths import REPO_ROOT, UTF_8

from .paths import allocate_run_directory

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

#: The private transport variable each lane reads for the run's evidence root.
RUN_ROOT_ENV = "CADRUMO_LANE_RUN_ROOT"

#: Subdirectories every lane may write into, created before the sweep starts so
#: no lane has to defend against their absence.
RUN_SUBDIRECTORIES = ("artifacts", "cache", "scratch")

#: Width of the lane-name column in the closing summary.
_NAME_WIDTH = 34

#: Stable event vocabulary for why a lane exists. Callers declare specialized
#: purposes explicitly; ordinary lanes remain generic commands.
LANE_KINDS = frozenset({"collection", "command", "load"})


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


@dataclass(frozen=True)
class SkippedLane:
    """One lane blocked by failed preflights."""

    name: str
    blocked_by: tuple[str, ...]


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


def _summarise(results: Sequence[LaneResult | SkippedLane]) -> None:
    """Print the per-lane summary table.

    Args:
        results: Every lane's outcome, in execution order.
    """
    print("\nLane run summary", flush=True)
    for result in results:
        if isinstance(result, SkippedLane):
            print(f"  {result.name:<{_NAME_WIDTH}} blocked by {', '.join(result.blocked_by)}", flush=True)
        else:
            print(
                f"  {result.name:<{_NAME_WIDTH}} exit={result.status:<3} {result.seconds}s",
                flush=True,
            )


def _run_all(
    lanes: Sequence[str],
    env: dict[str, str],
    *,
    json_events: bool,
    preflight_count: int,
    lane_kinds: Mapping[str, str],
) -> list[LaneResult | SkippedLane]:
    """Execute lanes, blocking the non-preflight suffix after a failed preflight."""
    if not 0 <= preflight_count <= len(lanes):
        raise ValueError("preflight_count must identify a prefix of the requested lanes")
    if unknown_lanes := set(lane_kinds).difference(lanes):
        raise ValueError(f"lane kinds name unrequested lanes: {sorted(unknown_lanes)!r}")
    if unknown_kinds := set(lane_kinds.values()).difference(LANE_KINDS):
        raise ValueError(f"unknown lane kinds: {sorted(unknown_kinds)!r}")
    results: list[LaneResult | SkippedLane] = []
    for index, lane in enumerate(lanes):
        kind = lane_kinds.get(lane, "command")
        failed_preflights = tuple(
            result.name for result in results[:preflight_count] if isinstance(result, LaneResult) and result.status != 0
        )
        if index >= preflight_count and failed_preflights:
            blocked = SkippedLane(lane, failed_preflights)
            results.append(blocked)
            print(f"BLOCKED {lane} (preflight: {', '.join(failed_preflights)})", file=sys.stderr, flush=True)
            if json_events:
                print(
                    json.dumps(
                        {
                            "blocked_by": list(failed_preflights),
                            "event": "lane_skipped",
                            "kind": kind,
                            "lane": lane,
                            "reason": "preflight_failed",
                            "role": "execution",
                        },
                        separators=(",", ":"),
                    ),
                    flush=True,
                )
            continue
        if json_events:
            role = "preflight" if index < preflight_count else "execution"
            print(
                json.dumps(
                    {"event": "lane_started", "kind": kind, "lane": lane, "role": role},
                    separators=(",", ":"),
                ),
                flush=True,
            )
        result = _run_lane(lane, env)
        results.append(result)
        if json_events:
            print(
                json.dumps(
                    {
                        "event": "lane_finished",
                        "exit_status": result.status,
                        "kind": kind,
                        "lane": lane,
                        "role": "preflight" if index < preflight_count else "execution",
                        "seconds": result.seconds,
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )
    return results


def run_lanes(
    lanes: Sequence[str],
    repository: Path = REPO_ROOT,
    *,
    json_events: bool = False,
    persist_evidence: bool = True,
    preflight_count: int = 0,
    lane_kinds: Mapping[str, str] | None = None,
) -> int:
    """Run every lane in order, continuing past failures, and summarise.

    Args:
        lanes: The just recipes to run, in order.
        repository: The checkout the run evidence is written beneath.
        preflight_count: Number of leading lanes that must all pass before the
            remaining lanes may run. All leading lanes run even when one fails.
        lane_kinds: Explicit machine-readable purposes for specialized lanes.

    Returns:
        0 when every lane passed, otherwise the FIRST non-zero status any lane
        reported. Flattening that to 1 threw away the one thing a caller
        reading the number alone could use: a lane that could not run (127)
        looked exactly like a lane whose tests failed (1). See
        ``dev/EXIT-CODES.md``.
    """
    declared_kinds = lane_kinds or {}
    if not persist_evidence:
        results = _run_all(
            lanes,
            dict(os.environ),
            json_events=json_events,
            preflight_count=preflight_count,
            lane_kinds=declared_kinds,
        )
        _summarise(results)
        return next((r.status for r in results if isinstance(r, LaneResult) and r.status != 0), 0)

    run_root = allocate_run_directory(repository, family="lane-runs", label="lanes")
    for name in RUN_SUBDIRECTORIES:
        (run_root / name).mkdir(parents=True, exist_ok=True)

    env = {**os.environ, RUN_ROOT_ENV: str(run_root)}
    log_path = run_root / "run.log"

    with log_path.open("w", encoding=UTF_8) as handle:
        original_out, original_err = sys.stdout, sys.stderr
        sys.stdout = _Tee(original_out, handle)  # type: ignore[assignment]
        sys.stderr = _Tee(original_err, handle)  # type: ignore[assignment]
        try:
            print(f"lane run log: {log_path}", flush=True)
            results = _run_all(
                lanes,
                env,
                json_events=json_events,
                preflight_count=preflight_count,
                lane_kinds=declared_kinds,
            )
            _summarise(results)
            print(f"lane run log: {log_path}", flush=True)
        finally:
            sys.stdout, sys.stderr = original_out, original_err

    return next((r.status for r in results if isinstance(r, LaneResult) and r.status != 0), 0)
