"""Attribute real native journal lock holds without retaining application data.

Events remain in memory until successful worker drain or observation scope exit. No trace publication
runs on a request's event-loop path. Abruptly contained workers may lose their
buffer; a missing worker trace is incomplete evidence, never a fast result. Timings are
inclusive; spans identify their parent and lock, so nested costs are not sums.
Wall minus thread CPU includes I/O, lock waits and scheduling, not just disk.
Record writes include serialization and persistence; serialization is not timed separately.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT, UTF_8


@dataclass
class _Span:
    identifier: int
    boundary: str
    parent: int | None
    lock: int | None
    thread: int
    start: int
    utc: int
    cpu: int
    thread_cpu: int
    kind: str = "phase"
    payload_chars: int | None = None


@dataclass(frozen=True)
class _Clock:
    wall: int
    utc: int
    cpu: int
    thread_cpu: int


def _clock() -> _Clock:
    return _Clock(time.perf_counter_ns(), time.time_ns(), time.process_time_ns(), time.thread_time_ns())


class _ThreadState(threading.local):
    def __init__(self) -> None:
        self.stack: list[_Span] = []
        self.holds: dict[int, _Span] = {}


class JournalRecorder:
    """Collect metadata only; keep measurement and publication separate."""

    def __init__(self, output: Path, role: str) -> None:
        """Select an output owner without opening its file on the measured path."""
        self.path = output / f"journal-{role}-{os.getpid()}.jsonl"
        self.local = _ThreadState()
        self.guard = threading.Lock()
        self.publish_guard = threading.Lock()
        self.next_id = 0
        self.records: list[dict[str, object]] = []

    def _stack(self) -> list[_Span]:
        return self.local.stack

    def _holds(self) -> dict[int, _Span]:
        return self.local.holds

    def start(self, label: str, *, kind: str = "phase", clock: _Clock | None = None) -> _Span:
        """Capture clocks and code-only correlation before entering a boundary."""
        stack, holds = self._stack(), self._holds()
        with self.guard:
            self.next_id += 1
            identifier = self.next_id
        clock = clock or _clock()
        return _Span(
            identifier,
            label,
            stack[-1].identifier if stack else None,
            next(reversed(holds.values())).identifier if holds else None,
            threading.get_native_id(),
            clock.wall,
            clock.utc,
            clock.cpu,
            clock.thread_cpu,
            kind,
        )

    def finish(self, span: _Span, outcome: str = "ok", *, clock: _Clock | None = None) -> None:
        """Buffer one completed boundary without publishing application values."""
        clock = clock or _clock()
        end, cpu, thread_cpu = clock.wall, clock.cpu, clock.thread_cpu
        record: dict[str, object] = {
            "id": span.identifier,
            "boundary": span.boundary,
            "kind": span.kind,
            "parent_id": span.parent,
            "lock_id": span.lock,
            "pid": os.getpid(),
            "thread_id": span.thread,
            "start_ns": span.start,
            "end_ns": end,
            "utc_start_ns": span.utc,
            "wall_seconds": (end - span.start) / 1e9,
            "process_cpu_seconds": (cpu - span.cpu) / 1e9,
            "thread_cpu_seconds": (thread_cpu - span.thread_cpu) / 1e9,
            "outcome": outcome,
            "payload_chars": span.payload_chars,
        }
        with self.guard:
            self.records.append(record)

    @contextmanager
    def measure(self, label: str) -> Generator[_Span]:
        """Preserve a synchronous call's outcome and its nesting on this thread."""
        span = self.start(label)
        self._stack().append(span)
        outcome = "ok"
        try:
            yield span
        except BaseException as error:
            outcome = type(error).__name__
            raise
        finally:
            self._stack().pop()
            self.finish(span, outcome)

    def flush(self) -> None:
        """Publish completed spans without holding the collection mutex during I/O."""
        if self._holds():
            raise RuntimeError("cannot publish observer data while owning a journal lock")
        with self.publish_guard:
            with self.guard:
                records, self.records = self.records, []
            if records:
                with self.path.open("a", encoding=UTF_8) as target:
                    for record in records:
                        target.write(json.dumps(record, allow_nan=False) + "\n")


def _wrap(patch: pytest.MonkeyPatch, recorder: JournalRecorder, owner: Any, name: str, label: str) -> None:
    original = getattr(owner, name)

    @functools.wraps(original)
    def measured(*args: Any, **kwargs: Any) -> Any:
        with recorder.measure(label) as span:
            result = original(*args, **kwargs)
            if isinstance(result, str):
                span.payload_chars = len(result)
            return result

    patch.setattr(owner, name, measured)


@contextmanager
def observe_journal(recorder: JournalRecorder) -> Generator[None]:
    """Wrap the real lock primitive and synchronous owners without changing results."""
    from cadrumo.adapters.persistence.operations import financial_journal_purge, journal, lease
    from cadrumo.application.journal_repository import JournalRepositoryBase
    from cadrumo.core import locks

    acquire, release = locks._lock_acquired_before_deadline, locks._release_lock

    @functools.wraps(acquire)
    def acquired(fd: int, lock_path: Path, **kwargs: Any) -> bool:
        if lock_path.name != ".repository.lock" or lock_path.parent.name != "operation-journals":
            return acquire(fd, lock_path, **kwargs)
        attempt = recorder.start("lock.acquire_attempt")
        try:
            result = acquire(fd, lock_path, **kwargs)
        except BaseException as error:
            recorder.finish(attempt, type(error).__name__, clock=_clock())
            raise
        acquired_at = _clock()
        if result:
            recorder._holds()[fd] = recorder.start("lock.held", kind="lock", clock=acquired_at)
        recorder.finish(attempt, clock=acquired_at)
        return result

    @functools.wraps(release)
    def released(fd: int, **kwargs: Any) -> None:
        span = recorder._holds().get(fd)
        if span is None:
            release(fd, **kwargs)
            return
        outcome = "ok"
        releasing = recorder.start("lock.release")
        try:
            release(fd, **kwargs)
        except BaseException as error:
            outcome = type(error).__name__
            raise
        finally:
            released_at = _clock()
            recorder._holds().pop(fd)
            recorder.finish(releasing, outcome, clock=released_at)
            recorder.finish(span, outcome, clock=released_at)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(locks, "_lock_acquired_before_deadline", acquired)
        patch.setattr(locks, "_release_lock", released)
        for name in (
            "load",
            "read_existing",
            "read_observation",
            "create",
            "commit",
            "commit_settlement",
            "inventory_page",
            "resolve_idempotency",
            "_advance_unlocked",
            "_load_unlocked",
        ):
            _wrap(patch, recorder, journal._SnapshotJournalRepository, name, "journal." + name)
        for name in ("_read_payload", "_decode_payload", "_write", "_write_payload"):
            _wrap(patch, recorder, JournalRepositoryBase, name, "record." + name.removeprefix("_"))
        for name in ("require_live_exact_unlocked", "replace_unlocked", "_record_unlocked"):
            _wrap(patch, recorder, lease.OperationLeaseStorage, name, "lease." + name)
        for name in ("_inspect", "_acquire", "_compare_and_swap", "_release"):
            _wrap(patch, recorder, lease.OperationLeaseFilesystemRepository, name, "lease." + name)
        _wrap(patch, recorder, journal, "purge_legacy_financial_edit_journal", "purge.inspect")
        _wrap(patch, recorder, financial_journal_purge, "_decode_object", "purge.json_decode")
        for name in ("fsync", "replace", "chmod"):
            original = getattr(os, name)

            def observed_os(*args: Any, _original: Any = original, _name: str = name, **kwargs: Any) -> Any:
                if not recorder._stack() and not recorder._holds():
                    return _original(*args, **kwargs)
                with recorder.measure("filesystem." + _name):
                    return _original(*args, **kwargs)

            patch.setattr(os, name, observed_os)
        original_log = logging.Logger._log

        def observed_log(*args: Any, **kwargs: Any) -> Any:
            if not recorder._holds():
                return original_log(*args, **kwargs)
            with recorder.measure("diagnostics.emit_under_lock"):
                return original_log(*args, **kwargs)

        patch.setattr(logging.Logger, "_log", observed_log)
        try:
            yield
        finally:
            recorder.flush()


@contextmanager
def publish_after_worker_drain(recorder: JournalRecorder) -> Generator[None]:
    """Publish off-loop after successful drain, before the parent contains its worker."""
    from cadrumo_runtime.host.operation_host import ProfileWorkerOperationHost

    original = ProfileWorkerOperationHost.close

    @functools.wraps(original)
    async def closed(self: Any) -> Any:
        result = await original(self)
        if not result.needs_containment:
            with recorder.measure("worker.operations_drained"):
                pass
            await asyncio.to_thread(recorder.flush)
        return result

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ProfileWorkerOperationHost, "close", closed)
        yield


def _worker_script(output: Path) -> Path:
    from dev.docs.sequences import runtime_fixture

    source = Path(runtime_fixture.__file__).read_text(encoding=UTF_8)
    source = source.replace("str(Path(__file__).resolve().parents[3])", repr(str(REPO_ROOT)))
    original = "    raise SystemExit(run(composition_factory=_worker_composition))"
    if source.count(original) != 1:
        raise ValueError("runtime fixture bootstrap changed")
    bootstrap = (
        "    from dev.ci.runtime_journal_benchmark import (\n"
        "        JournalRecorder, observe_journal, publish_after_worker_drain)\n"
        "    @contextmanager\n"
        "    def _measured_composition():\n"
        f"        recorder = JournalRecorder(Path({str(output)!r}), 'worker')\n"
        "        with _worker_composition(), observe_journal(recorder), publish_after_worker_drain(recorder):\n"
        "            yield\n"
        "    raise SystemExit(run(composition_factory=_measured_composition))"
    )
    destination = output / "journal_worker.py"
    source = source.replace(original, bootstrap)
    compile(source, str(destination), "exec")
    destination.write_text(source, encoding=UTF_8)
    return destination


def summarize(output: Path) -> None:
    """Retain lock owners and nested phase evidence without conflating inclusive costs."""
    processes = []
    for path in sorted(output.glob("journal-*.jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding=UTF_8).splitlines()]
        by_id = {row["id"]: row for row in rows}
        holds = sorted(
            (row for row in rows if row["kind"] == "lock"), key=lambda row: row["wall_seconds"], reverse=True
        )
        longest = []
        for hold in holds[:10]:
            owner = by_id.get(hold["parent_id"])
            phases = [row for row in rows if row["lock_id"] == hold["id"]]
            longest.append(
                {
                    "hold": hold,
                    "owner": owner["boundary"] if owner else None,
                    "phases_inclusive": sorted(phases, key=lambda row: row["wall_seconds"], reverse=True),
                }
            )
        processes.append(
            {
                "trace": path.name,
                "operations_drained": any(row["boundary"] == "worker.operations_drained" for row in rows),
                "lock_count": len(holds),
                "max_hold_seconds": holds[0]["wall_seconds"] if holds else None,
                "longest_holds": longest,
                "failed_spans": [row for row in rows if row["outcome"] != "ok"],
            }
        )
    (output / "summary.json").write_text(
        json.dumps(
            {
                "notes": [
                    "Phases are nested and inclusive: never add them to explain a hold.",
                    "Missing worker drain markers mean incomplete evidence.",
                    "Wall minus thread CPU includes both I/O and scheduling delay.",
                ],
                "processes": processes,
            },
            indent=2,
        )
        + "\n",
        encoding=UTF_8,
    )


def benchmark(output: Path, page: str, authority_root: Path) -> None:
    """Execute and check a cumulative native page with the journal observer installed."""
    from cadrumo.core.config import override_settings
    from cadrumo.tests.env_scope import derived_storage_settings
    from dev.docs.build import ensure_isolated_storage_root
    from dev.docs.sequences.checks import discover_sequences
    from dev.docs.sequences.compare import evaluate_expectations
    from dev.docs.sequences.runner import execute_page_sequences
    from dev.docs.sequences.runtime_fixture import sequence_worker_script

    ensure_isolated_storage_root()
    items, problems = discover_sequences(page=page)
    executable = [item for item in items if item.sequence.executed_frames]
    if problems or not executable:
        raise ValueError("one valid executable documentation page is required")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = (
        "dev/ci/runtime_journal_benchmark.py",
        "src/cadrumo/adapters/persistence/operations/journal.py",
        "src/cadrumo/adapters/persistence/operations/financial_journal_purge.py",
        "src/cadrumo/application/journal_repository.py",
        "src/cadrumo/core/locks.py",
        "src/cadrumo/core/atomic_write.py",
    )
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "page": page,
                "source_sha256": {
                    path: hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest() for path in sources
                },
                "notes": [
                    "Synthetic native page; no payload or exception messages in phase events.",
                    "Nested phase durations are inclusive; do not add them.",
                    "Wall minus thread CPU is non-CPU time, not a disk-I/O measurement.",
                    "Record writes include serialization and persistence; serialization is not timed separately.",
                    "Worker traces publish off-loop after successful drain, before containment; "
                    "absent traces are incomplete.",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding=UTF_8,
    )
    recorder = JournalRecorder(output, "parent")
    worker = _worker_script(output)
    with (
        derived_storage_settings(output / "storage-base"),
        override_settings(cadrumo_authority_root=authority_root.resolve()),
        sequence_worker_script(worker),
        observe_journal(recorder),
    ):
        with recorder.measure("page.total"):
            transcripts = execute_page_sequences(
                [item.sequence for item in executable], label=page, sandbox_root=output / "sandbox"
            )
        for item, transcript in zip(executable, transcripts, strict=True):
            if evaluate_expectations(item.sequence, transcript, page=page):
                raise ValueError("page expectations failed")


def main(argv: list[str] | None = None) -> int:
    """Run the instrumented page, disclosing only safe failure metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page", default="how-to/filing-readiness")
    parser.add_argument("--authority-root", type=Path, default=REPO_ROOT / ".authority")
    args = parser.parse_args(argv)
    try:
        benchmark(args.output, args.page, args.authority_root)
    except Exception as error:
        print(f"Journal measurement failed: {type(error).__name__}; payload-free spans retained")
        return 1
    summarize(args.output)
    print("Journal measurement completed; payload-free spans retained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
