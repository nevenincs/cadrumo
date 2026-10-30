"""Profile packaged store lifecycle commands against fresh, disposable agent homes.

Run with ``uv run --no-sync python -m dev.runtime_lifecycle.agent_store_profile``.
The normal mode records wall time and sampled Windows CPU, I/O, memory, thread
and handle counters. ``--spy speedscope`` or ``--spy flamegraph`` adds py-spy
stack sampling; compare performance using separate runs without the profiler.
I/O counters include cached and non-disk I/O. Sampled maxima are lower bounds,
not kernel traces or exact final totals. No provider or AEAT calls are made.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from threading import Event, Thread
from typing import Any, cast

import psutil

from cadrumo_agent_service.adapters.agent_process import WindowsAgentInvocationRunner
from cadrumo_agent_service.host.launch_environment import HOSTED_ROOT_VARIABLE
from cadrumo_runtime.application.development_root import mark_development_root

from .caller_owned_root import consumer_environment, require
from .proof_support import package_identity

_SAMPLE_INTERVAL_SECONDS = 0.05
_DISCOVERY_INTERVAL_SECONDS = 0.25


def _sample_resources(stopped: Event, observations: list[dict[str, Any]], started: float) -> None:
    """Observe only this driver's children; never enumerate unrelated command lines."""
    parent = psutil.Process(os.getpid())
    try:
        children = parent.children(recursive=True)
    except psutil.Error:
        return
    next_discovery = time.perf_counter() + _DISCOVERY_INTERVAL_SECONDS
    while not stopped.is_set():
        # Windows descendant discovery walks the host's process table. Repeating
        # it for every counter sample makes the observer a significant workload.
        now = time.perf_counter()
        if now >= next_discovery:
            try:
                children = parent.children(recursive=True)
            except psutil.Error:
                return
            next_discovery = time.perf_counter() + _DISCOVERY_INTERVAL_SECONDS
        for child in children:
            try:
                with child.oneshot():
                    observations.append(
                        {
                            "at_seconds": time.perf_counter() - started,
                            "pid": child.pid,
                            "name": child.name(),
                            "cpu": child.cpu_times()._asdict(),
                            "io": child.io_counters()._asdict(),
                            "handles": child.num_handles(),
                            "threads": child.num_threads(),
                            "rss": child.memory_info().rss,
                        }
                    )
            except psutil.Error:
                # A short-lived child can exit between any two observations.
                continue
        stopped.wait(_SAMPLE_INTERVAL_SECONDS)


def _measurement_command(
    package: Path, artifact: Path, verb: str, spy: str, spy_program: Path | None
) -> tuple[Path, list[str], Path | None]:
    """Build the package invocation and optional profiler wrapper."""
    program = package / "bin" / "cadrumo-agent.exe"
    arguments = ["-m", "cadrumo_agent.cli.main", verb]
    trace: Path | None = None
    if spy_program is not None:
        trace = artifact.with_suffix(".svg" if spy == "flamegraph" else ".speedscope.json")
        arguments = [
            "record",
            "--subprocesses",
            "--idle",
            "--rate",
            "200",
            "--format",
            spy,
            "--output",
            str(trace),
            "--",
            str(program),
            *arguments,
        ]
        program = spy_program
    return program, arguments, trace


def _measure(
    package: Path, root: Path, artifact: Path, verb: str, spy: str, spy_program: Path | None
) -> dict[str, Any]:
    environment = consumer_environment(root)
    environment[HOSTED_ROOT_VARIABLE] = str(root / "agent")
    program, arguments, trace = _measurement_command(package, artifact, verb, spy, spy_program)
    observations: list[dict[str, Any]] = []
    stopped = Event()
    started = time.perf_counter()
    sampler = Thread(target=_sample_resources, args=(stopped, observations, started), daemon=True)
    sampler.start()
    try:
        # The existing invocation runner contains and reaps the whole tree,
        # including py-spy's child, on success, failure or timeout.
        result = WindowsAgentInvocationRunner().run(
            executable=program,
            arguments=arguments,
            directory=root,
            environment=environment,
            timeout=60,
            output_limit=64 * 1024,
        )
        elapsed = time.perf_counter() - started
    finally:
        stopped.set()
        sampler.join(timeout=10)
    require(not sampler.is_alive(), "resource sampler did not stop")
    artifact.with_suffix(".stdout.txt").write_bytes(result.standard_output)
    artifact.with_suffix(".resources.json").write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    summary = _resource_summary(observations, elapsed, result.status, spy)
    if spy == "none" and result.status == 0:
        response = json.loads(result.standard_output)
        summary["reported_work_seconds"] = response.get("duration_seconds")
        summary["reported_state"] = response["stores"]["state"] if verb == "preflight" else response["status"]
    require(result.status == 0, f"packaged {verb} failed with exit status {result.status}")
    if trace is not None:
        require(trace.is_file() and trace.stat().st_size > 0, "py-spy produced no trace")
    return summary


def _resource_summary(
    observations: Sequence[Mapping[str, object]], elapsed: float, status: int | None, spy: str
) -> dict[str, object]:
    """Summarize the sampled child counters without retaining new observations."""
    agent = [row for row in observations if cast(str, row["name"]).casefold() == "cadrumo-agent.exe"]
    return {
        "wall_seconds": elapsed,
        "exit_code": status,
        "spy": spy,
        "sampled_peak_handles": max((cast(int, row["handles"]) for row in agent), default=None),
        "sampled_peak_threads": max((cast(int, row["threads"]) for row in agent), default=None),
        "last_observed_io": agent[-1]["io"] if agent else None,
        "last_observed_cpu": agent[-1]["cpu"] if agent else None,
    }


def main() -> None:
    """Preserve per-command counters and traces beside package-bound measurement results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--spy", choices=("none", "speedscope", "flamegraph"), default="none")
    arguments = parser.parse_args()
    require(sys.platform == "win32", "this profiler measures the Windows package")
    require(1 <= arguments.samples <= 10, "samples must be between 1 and 10")
    package = arguments.package.resolve(strict=True)
    identity = package_identity(package)
    spy_program = None
    if arguments.spy != "none":
        found = shutil.which("py-spy")
        if found is None:
            raise RuntimeError("install py-spy before requesting stack sampling")
        spy_program = Path(found).resolve(strict=True)
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "package": identity,
        "scope": "fresh processes and synthetic agent stores; warm OS caches; current load",
        "counter_limits": "sampled counters, including cached/non-disk I/O; not kernel file/handle events",
        "sample_interval_seconds": _SAMPLE_INTERVAL_SECONDS,
        "discovery_interval_seconds": _DISCOVERY_INTERVAL_SECONDS,
        "samples": rows,
    }
    for sample in range(arguments.samples):
        root = output / f"profile-{sample + 1}"
        root.mkdir()
        mark_development_root(root)
        (root / "agent").mkdir()
        for label, verb in (("absent-preflight", "preflight"), ("setup", "setup"), ("current-preflight", "preflight")):
            require(package_identity(package) == identity, "package changed before measurement")
            artifact = output / f"{sample + 1}-{label}"
            row = {
                "sample": sample + 1,
                "phase": label,
                **_measure(package, root, artifact, verb, arguments.spy, spy_program),
            }
            require(package_identity(package) == identity, "package changed during measurement")
            rows.append(row)
            (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(row), flush=True)
    report["median_wall_seconds"] = {
        phase: statistics.median(row["wall_seconds"] for row in rows if row["phase"] == phase)
        for phase in ("absent-preflight", "setup", "current-preflight")
    }
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
