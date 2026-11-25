"""Run a gate graph concurrently under one worker budget and keep a durable record.

Every node is an independent measurement, so a red node never stops the
others; all reds are reported at the end. Each node writes its own log and its
own JUnit directory inside the record directory, so a verdict and its evidence
stay attributable after the run.

A gate result describes one tree. The source tree's content digest, over the
repository's own inclusion policy, is taken before the first node starts and
after the last one ends; when the two differ the run is ``invalid_tree_moved``,
which is neither a pass nor a failure.

The runner owns the process trees it starts. Descendants it observed are given
a short grace to exit after their node's root process ends and are then
stopped; an interruption stops every running tree. Nothing else is touched.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING, Final

import psutil

from cadrumo.core.atomic_write import atomic_write_text
from dev.exit_codes import FAILED, OK, TOOL_BROKEN, TOOL_MISSING
from dev.paths import UTF_8
from dev.source_tree import content_digest, repository_files

from .gate_schedule import FAILED as VERDICT_FAILED
from .gate_schedule import NOT_RUN, PASSED, GateSchedule

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .gate_graph import GateGraph, GateNode

RECORD_SCHEMA: Final = "cadrumo-gate-record/v1"
RECORD_NAME: Final = "gate-record.json"
REPORTS_ENV: Final = "CADRUMO_CI_REPORTS_DIR"
REPORT_NAME_ENV: Final = "CADRUMO_CI_REPORT_NAME"
WORKERS_ENV: Final = "CADRUMO_PYTEST_WORKERS"

STATUS_RUNNING: Final = "running"
STATUS_PASSED: Final = "passed"
STATUS_FAILED: Final = "failed"
STATUS_TREE_MOVED: Final = "invalid_tree_moved"
STATUS_INTERRUPTED: Final = "interrupted"

INTERRUPTED_EXIT: Final = 130

#: How long, by default, descendants of a finished node may keep running before they are stopped.
DESCENDANT_GRACE_SECONDS: Final = 5.0

#: How often a running node's descendants are re-read; a full process snapshot is not free.
_DESCENDANT_SCAN_SECONDS: Final = 1.0

_STOP_WAIT_SECONDS: Final = 10.0


@dataclass
class NodeRecord:
    """One node's outcome as the record stores it."""

    node: GateNode
    verdict: str | None = None
    exit_code: int | None = None
    started_at: str | None = None
    wall_seconds: float | None = None
    log_path: str | None = None
    reports_dir: str | None = None
    cause: str | None = None
    blocked_by: tuple[str, ...] = ()
    stray_processes_stopped: int = 0

    def to_json(self) -> dict[str, object]:
        """Return the record's JSON form."""
        node = self.node
        return {
            "name": node.name,
            "kind": node.kind,
            "command": list(node.command),
            "weight": node.weight,
            "pytest_workers": node.pytest_workers,
            "after": list(node.after),
            "exclusive": list(node.exclusive),
            "alone": node.alone,
            "verdict": self.verdict,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "wall_seconds": self.wall_seconds,
            "log_path": self.log_path,
            "reports_dir": self.reports_dir,
            "cause": self.cause,
            "blocked_by": list(self.blocked_by),
            "stray_processes_stopped": self.stray_processes_stopped,
        }


@dataclass(frozen=True)
class GateRunResult:
    """The overall outcome of one gate run."""

    status: str
    exit_code: int
    record_path: Path


@dataclass
class _Running:
    node: GateNode
    record: NodeRecord
    process: asyncio.subprocess.Process
    owner: psutil.Process | None
    log: IO[bytes]
    started: float
    descendants: dict[int, psutil.Process] = field(default_factory=dict)
    last_scan: float = 0.0
    drain_deadline: float | None = None


def tree_digest(root: Path) -> tuple[str | None, str | None]:
    """Return the content digest of ``root``'s repository files, or ``None`` and why it could not be taken.

    A file that disappears between enumeration and reading means the tree moved
    under the digest, so an unreadable tree never yields a digest.
    """
    try:
        return content_digest(root, repository_files(root)), None
    except (OSError, UnicodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class _GateRun:
    def __init__(
        self,
        graph: GateGraph,
        *,
        budget: int,
        record_dir: Path,
        head_label: str,
        tree_root: Path,
        graph_identity: Mapping[str, str],
        json_events: bool,
        stop: threading.Event | None,
        poll_seconds: float,
        descendant_grace_seconds: float,
    ) -> None:
        self.schedule = GateSchedule(graph, budget)
        self.descendant_grace_seconds = descendant_grace_seconds
        self.graph = graph
        self.budget = budget
        self.record_dir = record_dir
        self.record_path = record_dir / RECORD_NAME
        self.head_label = head_label
        self.tree_root = tree_root
        self.graph_identity = dict(graph_identity)
        self.json_events = json_events
        self.stop = stop
        self.poll_seconds = poll_seconds
        self.records = {node.name: NodeRecord(node) for node in graph.nodes}
        self.running: dict[str, _Running] = {}
        self.finish_order: list[str] = []
        self.status = STATUS_RUNNING
        self.exit_code: int | None = None
        self.started_at = _now()
        self.started = time.monotonic()
        self.wall_seconds: float | None = None
        self.digest_start: str | None = None
        self.digest_end: str | None = None
        self.digest_errors: list[str] = []
        self.base_env = {key: value for key, value in os.environ.items() if key != REPORT_NAME_ENV}

    # --- record ---------------------------------------------------------

    def write_record(self) -> None:
        payload = {
            "schema": RECORD_SCHEMA,
            "head_label": self.head_label,
            "status": self.status,
            "exit_code": self.exit_code,
            "budget": self.budget,
            "graph": self.graph_identity,
            "tree_root": str(self.tree_root),
            "tree_digest": {"start": self.digest_start, "end": self.digest_end, "errors": self.digest_errors},
            "started_at": self.started_at,
            "wall_seconds": self.wall_seconds,
            "nodes": [self.records[node.name].to_json() for node in self.graph.nodes],
        }
        atomic_write_text(self.record_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def emit(self, text: str, event: Mapping[str, object] | None = None, *, error: bool = False) -> None:
        print(text, file=sys.stderr if error else sys.stdout, flush=True)
        if self.json_events and event is not None:
            print(json.dumps(event, separators=(",", ":"), sort_keys=True), flush=True)

    # --- lifecycle ------------------------------------------------------

    def run(self) -> GateRunResult:
        self.record_dir.mkdir(parents=True, exist_ok=True)
        if self.record_path.exists():
            raise FileExistsError(f"a gate record already exists in {self.record_dir}")
        (self.record_dir / "logs").mkdir(exist_ok=True)
        (self.record_dir / "reports").mkdir(exist_ok=True)
        self.digest_start, error = tree_digest(self.tree_root)
        if error is not None:
            self.digest_errors.append(f"start: {error}")
        self.write_record()
        self.emit(f"gate record: {self.record_path}")
        interrupted = asyncio.run(self._drive())
        if interrupted:
            for node in self.schedule.abandon():
                self._settle_not_run(node, (), "interrupted")
            for record in self.records.values():
                if record.verdict is None:
                    record.verdict, record.cause = NOT_RUN, "interrupted"
        else:
            self.digest_end, error = tree_digest(self.tree_root)
            if error is not None:
                self.digest_errors.append(f"end: {error}")
        self.wall_seconds = round(time.monotonic() - self.started, 3)
        self._conclude(interrupted=interrupted)
        self.write_record()
        self._summarise()
        return GateRunResult(self.status, self.exit_code if self.exit_code is not None else FAILED, self.record_path)

    async def _drive(self) -> bool:
        """Run the loop; return whether it was interrupted. Running trees are stopped on any exit."""
        interrupted = False
        try:
            await self._loop()
        except (KeyboardInterrupt, asyncio.CancelledError):
            # asyncio.run turns Ctrl+C into cancellation of this task.
            interrupted = True
        finally:
            if self.running:
                interrupted = True
                await self._stop_all()
        return interrupted

    async def _loop(self) -> None:
        while not self.schedule.done:
            if self.stop is not None and self.stop.is_set():
                raise KeyboardInterrupt
            for node, causes in self.schedule.blocked():
                self._settle_not_run(node, causes, "a node it follows failed as a prerequisite or did not run")
            for node in self.schedule.startable():
                await self._start(node)
            progressed = False
            for name in list(self.running):
                if self._poll(self.running[name]):
                    progressed = True
            if not progressed:
                await asyncio.sleep(self.poll_seconds)

    def _conclude(self, *, interrupted: bool) -> None:
        verdicts = [record.verdict for record in self.records.values()]
        if interrupted:
            self.status, self.exit_code = STATUS_INTERRUPTED, INTERRUPTED_EXIT
        elif self.digest_start is None or self.digest_end is None or self.digest_start != self.digest_end:
            self.status, self.exit_code = STATUS_TREE_MOVED, TOOL_BROKEN
        elif all(verdict == PASSED for verdict in verdicts):
            self.status, self.exit_code = STATUS_PASSED, OK
        else:
            self.status = STATUS_FAILED
            first = next(
                (
                    code
                    for name in self.finish_order
                    if (code := self.records[name].exit_code) is not None and code != 0
                ),
                FAILED,
            )
            self.exit_code = first

    # --- nodes ----------------------------------------------------------

    def _environment(self, node: GateNode, reports: Path) -> dict[str, str]:
        env = dict(self.base_env)
        env.update(node.env)
        env[REPORTS_ENV] = str(reports)
        if (workers := node.pytest_workers) is not None:
            env[WORKERS_ENV] = str(workers)
        return env

    async def _start(self, node: GateNode) -> None:
        record = self.records[node.name]
        log_path = self.record_dir / "logs" / f"{node.name}.log"
        reports = self.record_dir / "reports" / node.name
        reports.mkdir(parents=True, exist_ok=True)
        record.log_path = log_path.relative_to(self.record_dir).as_posix()
        record.reports_dir = reports.relative_to(self.record_dir).as_posix()
        record.started_at = _now()
        env = self._environment(node, reports)
        self.schedule.start(node)
        log = log_path.open("wb")
        started = time.monotonic()
        executable = shutil.which(node.command[0], path=env.get("PATH"))
        process: asyncio.subprocess.Process | None = None
        failure: str | None = None
        if executable is None:
            failure = f"{node.command[0]} was not found on PATH"
        else:
            try:
                process = await asyncio.create_subprocess_exec(
                    executable,
                    *node.command[1:],
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=log,
                    stderr=asyncio.subprocess.STDOUT,
                    env=env,
                )
            except OSError as exc:
                failure = f"{node.command[0]} could not be started: {exc}"
        if process is None:
            log.write(f"{failure}\n".encode(UTF_8))
            log.close()
            record.exit_code = TOOL_MISSING
            self._finish(node, record, started, VERDICT_FAILED)
            return
        owner: psutil.Process | None
        try:
            owner = psutil.Process(process.pid)
        except psutil.Error:
            owner = None
        self.running[node.name] = _Running(node, record, process, owner, log, started)
        self.emit(
            f"START {node.name} ({node.kind}, weight {node.weight}, "
            f"running {self.schedule.running_weight}/{self.budget})",
            {"event": "node_started", "node": node.name, "kind": node.kind, "weight": node.weight},
        )

    def _poll(self, running: _Running) -> bool:
        """Advance one running node; return whether it finished."""
        now = time.monotonic()
        if running.drain_deadline is None:
            code = running.process.returncode
            if code is None:
                if now - running.last_scan >= _DESCENDANT_SCAN_SECONDS:
                    self._scan_descendants(running)
                    running.last_scan = now
                return False
            running.record.exit_code = code
            running.drain_deadline = now + self.descendant_grace_seconds
        alive = [process for process in running.descendants.values() if _alive(process)]
        if alive and now < running.drain_deadline:
            return False
        running.record.stray_processes_stopped = _kill(alive)
        running.log.close()
        del self.running[running.node.name]
        verdict = PASSED if running.record.exit_code == 0 else VERDICT_FAILED
        self._finish(running.node, running.record, running.started, verdict)
        return True

    def _scan_descendants(self, running: _Running) -> None:
        if running.owner is None:
            return
        with contextlib.suppress(psutil.Error):
            for child in running.owner.children(recursive=True):
                running.descendants.setdefault(child.pid, child)

    def _finish(self, node: GateNode, record: NodeRecord, started: float, verdict: str) -> None:
        record.verdict = verdict
        record.wall_seconds = round(time.monotonic() - started, 3)
        self.schedule.finish(node.name, verdict)
        self.finish_order.append(node.name)
        event = {
            "event": "node_finished",
            "node": node.name,
            "kind": node.kind,
            "verdict": verdict,
            "exit_code": record.exit_code,
            "seconds": record.wall_seconds,
        }
        if verdict == PASSED:
            self.emit(f"PASS {node.name} ({record.wall_seconds}s)", event)
        else:
            self.emit(
                f"FAIL {node.name} (exit {record.exit_code}, {record.wall_seconds}s, log {record.log_path})",
                event,
                error=True,
            )
        self.write_record()

    def _settle_not_run(self, node: GateNode, blocked_by: tuple[str, ...], cause: str) -> None:
        record = self.records[node.name]
        record.verdict = NOT_RUN
        record.cause = cause
        record.blocked_by = blocked_by
        suffix = f": {', '.join(blocked_by)}" if blocked_by else ""
        self.emit(
            f"NOT RUN {node.name} ({cause}{suffix})",
            {"event": "node_not_run", "node": node.name, "cause": cause, "blocked_by": list(blocked_by)},
            error=True,
        )
        self.write_record()

    async def _stop_all(self) -> None:
        """Stop every running tree this run started, and only those."""
        for running in list(self.running.values()):
            self._scan_descendants(running)
            members = list(running.descendants.values())
            if running.owner is not None:
                members.append(running.owner)
            _kill(members)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(running.process.wait(), timeout=_STOP_WAIT_SECONDS)
            running.log.close()
            running.record.exit_code = running.process.returncode
            running.record.cause = "interrupted"
            del self.running[running.node.name]
            self._finish(running.node, running.record, running.started, VERDICT_FAILED)

    def _summarise(self) -> None:
        print("\nGate summary", flush=True)
        for node in self.graph.nodes:
            record = self.records[node.name]
            seconds = "" if record.wall_seconds is None else f" {record.wall_seconds}s"
            exit_text = "" if record.exit_code is None else f" exit={record.exit_code}"
            print(f"  {node.name:<34} {record.verdict}{exit_text}{seconds}", flush=True)
        reds = [record for record in self.records.values() if record.verdict != PASSED]
        for record in reds:
            detail = f"log {record.log_path}" if record.log_path is not None else f"{record.cause}"
            print(f"RED {record.node.name}: {record.verdict} ({detail})", file=sys.stderr, flush=True)
        if self.status == STATUS_TREE_MOVED:
            print(
                f"INVALID: the source tree moved during the run ({self.digest_start} -> {self.digest_end})",
                file=sys.stderr,
                flush=True,
            )
        print(f"gate {self.status} (exit {self.exit_code}); record {self.record_path}", flush=True)


def _alive(process: psutil.Process) -> bool:
    try:
        return bool(process.is_running()) and bool(process.status() != psutil.STATUS_ZOMBIE)
    except psutil.Error:
        return False


def _kill(processes: list[psutil.Process]) -> int:
    """Kill ``processes`` that are still the processes observed earlier; return how many were stopped.

    psutil compares each object's creation time before signalling, so a
    recycled process id is never killed.
    """
    stopped: list[psutil.Process] = []
    for process in processes:
        if not _alive(process):
            continue
        with contextlib.suppress(psutil.Error):
            process.kill()
            stopped.append(process)
    if stopped:
        psutil.wait_procs(stopped, timeout=_STOP_WAIT_SECONDS)
    return len(stopped)


def graph_identity(path: Path) -> dict[str, str]:
    """Name a graph file by its path and content digest."""
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run_gate(
    graph: GateGraph,
    *,
    budget: int,
    record_dir: Path,
    head_label: str,
    tree_root: Path,
    graph_source: Mapping[str, str] | None = None,
    json_events: bool = False,
    stop: threading.Event | None = None,
    poll_seconds: float = 0.05,
    descendant_grace_seconds: float = DESCENDANT_GRACE_SECONDS,
) -> GateRunResult:
    """Run ``graph`` and return its overall status, exit code and record path.

    Args:
        graph: The nodes to run.
        budget: The most worker slots running nodes may occupy together.
        record_dir: Where the record, node logs and JUnit directories go. It
            must not already hold a record.
        head_label: The caller's name for the tree under test.
        tree_root: The source tree whose digest must not move during the run.
        graph_source: The graph file's identity, stored in the record.
        json_events: Also print one JSON line per node event.
        stop: Set it to interrupt the run as Ctrl+C would.
        poll_seconds: How long the loop sleeps when nothing changed.
        descendant_grace_seconds: How long observed descendants of a
            finished node may run on before they are stopped.
    """
    run = _GateRun(
        graph,
        budget=budget,
        record_dir=record_dir.resolve(),
        head_label=head_label,
        tree_root=tree_root.resolve(),
        graph_identity=graph_source or {},
        json_events=json_events,
        stop=stop,
        poll_seconds=poll_seconds,
        descendant_grace_seconds=descendant_grace_seconds,
    )
    return run.run()
