"""Run a development command with a live, command-identified transcript."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from dev._paths import REPO_ROOT

from .dead_weight_signal import _AUDIT_DEAD_WEIGHT_SIGNAL, _DeadWeightSignalProcessor
from .import_boundaries_signal import _IMPORT_BOUNDARIES_SIGNAL, _ImportBoundariesProcessor
from .locales_status_signal import _LOCALES_STATUS_SIGNAL, _LocalesStatusSignalProcessor
from .paths import (
    ScratchAllocation,
    ScratchOwnershipError,
    allocate_run_directory,
    allocate_scratch_directory,
    remove_scratch_directory,
    scratch_base,
    scratch_environment,
)
from .pytest_summary_signal import _PYTEST_SUMMARY_SIGNAL, _PytestSummaryProcessor
from .reaper import sweep_scratch_directories
from .registry_health_signal import _BINDING_SIGNAL, _REGISTRY_HEALTH_SIGNAL, _RegistryHealthProcessor
from .signal_values import _UTF_8

_INTERRUPTED_EXIT_STATUS: Final[int] = 130


_CHILD_STOP_TIMEOUT_SECONDS: Final[float] = 5.0


_STREAM_CHUNK_BYTES: Final[int] = 64 * 1024


async def _stop_interrupted_process(process: asyncio.subprocess.Process) -> None:
    """Bound cleanup of a child when the command wrapper receives Ctrl+C."""
    if process.returncode is not None:
        return
    try:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=_CHILD_STOP_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=_CHILD_STOP_TIMEOUT_SECONDS)
    except OSError:
        # The child can exit between poll() and terminate() after receiving the
        # same console interrupt as this wrapper.
        pass


async def _stream_lines(stream: asyncio.StreamReader) -> AsyncIterator[bytes]:
    """Yield each newline-terminated line of ``stream`` whatever its length.

    ``StreamReader.readline`` refuses a line longer than the reader's buffer
    limit, and a child's machine-readable payload is one JSON line of unbounded
    size. The final line is yielded even without a trailing newline.
    """
    pending = bytearray()
    while chunk := await stream.read(_STREAM_CHUNK_BYTES):
        scanned = len(pending)
        pending.extend(chunk)
        start = 0
        while (end := pending.find(b"\n", max(start, scanned))) != -1:
            yield bytes(pending[start : end + 1])
            start = end + 1
        del pending[:start]
    if pending:
        yield bytes(pending)


async def _stream_process(
    command: tuple[str, ...],
    *,
    repository: Path,
    environment: dict[str, str],
    processor: Any,
    label: str,
    run_id: str,
    transcript: Any,
) -> tuple[int, bool]:
    """Stream one explicit child command and report whether interruption handled it."""
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(repository),
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert process.stdout is not None
    try:
        async for line in _stream_lines(process.stdout):
            decoded = line.decode(_UTF_8, errors="replace")
            if processor is None:
                print(decoded, end="", flush=True)
            else:
                progress = processor.consume(decoded)
                if isinstance(progress, dict):
                    progress_text = json.dumps(
                        {
                            "command": label,
                            **progress,
                            "run_id": run_id,
                            "schema_version": 1,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    print(progress_text, flush=True)
                    transcript.write(progress_text + "\n")
            transcript.write(decoded)
            transcript.flush()
        return await process.wait(), False
    except (KeyboardInterrupt, asyncio.CancelledError):
        await _stop_interrupted_process(process)
        return _INTERRUPTED_EXIT_STATUS, True


def _write_run_metadata(
    *,
    run_dir: Path,
    artifacts: Path,
    cache: Path,
    command: tuple[str, ...],
    exit_status: int,
    finished: datetime,
    log_path: Path,
    scratch: Path,
    started: datetime,
) -> None:
    """Atomically persist the canonical run contract."""
    payload = {
        "artifacts": str(artifacts),
        "cache": str(cache),
        "command": list(command),
        "exit_status": exit_status,
        "finished_at": finished.isoformat(),
        "log": str(log_path),
        "run_id": run_dir.name,
        "scratch": str(scratch),
        "started_at": started.isoformat(),
    }
    temporary = run_dir / "run.json.tmp"
    temporary.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    os.replace(temporary, run_dir / "run.json")


def run(
    command: tuple[str, ...],
    *,
    repository: Path,
    family: str,
    label: str,
    signal: str | None = None,
    expected_lanes: tuple[str, ...] = (),
) -> int:
    """Stream ``command`` while retaining its full transcript and metadata.

    Dead-owner scratch is swept before this run allocates its own, and this
    run's scratch is removed on every exit Python can observe: success,
    failure, an exception or a catchable interrupt. A run killed outright
    leaves its scratch for the next run's sweep.
    """
    if not command:
        raise ValueError("a command is required")
    sweep_scratch_directories(scratch_base())
    scratch = allocate_scratch_directory()
    allocation = ScratchAllocation.record(scratch)
    try:
        return _run_in_scratch(
            command,
            repository=repository,
            family=family,
            label=label,
            signal=signal,
            expected_lanes=expected_lanes,
            scratch=scratch,
        )
    finally:
        try:
            remove_scratch_directory(allocation)
        except (ScratchOwnershipError, OSError) as error:
            print(f"run scratch {scratch} not removed: {type(error).__name__}: {error}", file=sys.stderr, flush=True)


def _run_in_scratch(
    command: tuple[str, ...],
    *,
    repository: Path,
    family: str,
    label: str,
    signal: str | None,
    expected_lanes: tuple[str, ...],
    scratch: Path,
) -> int:
    """Run ``command`` with ``scratch`` as its temporary directory; the caller owns the scratch."""
    started = datetime.now(tz=UTC)
    run_dir = allocate_run_directory(repository, family=family, label=label, now=started)
    artifacts = run_dir / "artifacts"
    cache = run_dir / "cache"
    artifacts.mkdir(parents=True)
    cache.mkdir()
    log_path = run_dir / "run.log"
    # PowerShell can terminate every native process in a Ctrl+C pipeline before
    # Python receives a catchable KeyboardInterrupt. Seed a fail-closed record
    # before entering that process tree; normal and catchable-interrupt exits
    # atomically replace it with their actual completion timestamp and status.
    _write_run_metadata(
        run_dir=run_dir,
        artifacts=artifacts,
        cache=cache,
        command=command,
        exit_status=_INTERRUPTED_EXIT_STATUS,
        finished=started,
        log_path=log_path,
        scratch=scratch,
        started=started,
    )
    processor = _new_signal_processor(signal, expected_lanes)
    start_envelope_text: str | None = None
    if processor is None:
        print(f"{label} run log: {log_path}", flush=True)
    else:
        start_envelope_text = json.dumps(
            {
                "command": label,
                "event": "run_started",
                "run_id": run_dir.name,
                "run_outputs": {
                    "log": str(log_path),
                    "metadata": str(run_dir / "run.json"),
                },
                "schema_version": 1,
                "status": "running",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        print(start_envelope_text, flush=True)

    environment = os.environ.copy()
    environment["CADRUMO_DEV_RUN_ROOT"] = str(run_dir)
    environment["CADRUMO_DEV_ARTIFACTS_DIR"] = str(artifacts)
    environment["CADRUMO_DEV_CACHE_DIR"] = str(cache)
    environment["CADRUMO_DEV_SCRATCH_DIR"] = str(scratch)
    # Tool caches such as uv's keep their own homes; only temporary files move.
    environment.update(scratch_environment(scratch))
    with log_path.open("x", encoding=_UTF_8, newline="\n") as transcript:
        transcript.write(f"START {started.isoformat()} pid={os.getpid()}\n")
        transcript.write(f"COMMAND {' '.join(command)}\n")
        if start_envelope_text is not None:
            transcript.write(start_envelope_text + "\n")
        transcript.flush()
        try:
            exit_status, interrupted = asyncio.run(
                _stream_process(
                    command,
                    repository=repository,
                    environment=environment,
                    processor=processor,
                    label=label,
                    run_id=run_dir.name,
                    transcript=transcript,
                )
            )
            normalized_processors = (
                _ImportBoundariesProcessor,
                _LocalesStatusSignalProcessor,
                _PytestSummaryProcessor,
            )
            if not interrupted and isinstance(processor, normalized_processors):
                exit_status = processor.effective_exit_status(exit_status)
        except KeyboardInterrupt:
            exit_status = _INTERRUPTED_EXIT_STATUS
            interrupted = True
        if interrupted:
            transcript.write(f"INTERRUPTED exit={exit_status}\n")
        finished = datetime.now(tz=UTC)
        transcript.write(f"FINISH {finished.isoformat()} exit={exit_status}\n")

    _write_run_metadata(
        run_dir=run_dir,
        artifacts=artifacts,
        cache=cache,
        command=command,
        exit_status=exit_status,
        finished=finished,
        log_path=log_path,
        scratch=scratch,
        started=started,
    )
    if processor is None:
        print(f"{label} run log: {log_path} (exit={exit_status}, metadata={run_dir / 'run.json'})", flush=True)
    else:
        envelope_text = json.dumps(
            processor.envelope(
                label=label,
                run_dir=run_dir,
                log_path=log_path,
                exit_status=exit_status,
                started=started,
                finished=finished,
            ),
            sort_keys=True,
            separators=(",", ":"),
        )
        with log_path.open("a", encoding=_UTF_8, newline="\n") as transcript:
            transcript.write(envelope_text + "\n")
        print(envelope_text, flush=True)
    return exit_status


def main() -> int:
    """Parse the evidence family/label and execute the remaining argv."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--signal",
        choices=(
            _AUDIT_DEAD_WEIGHT_SIGNAL,
            _BINDING_SIGNAL,
            _IMPORT_BOUNDARIES_SIGNAL,
            _LOCALES_STATUS_SIGNAL,
            _PYTEST_SUMMARY_SIGNAL,
            _REGISTRY_HEALTH_SIGNAL,
        ),
    )
    parser.add_argument("--expected-lane", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = tuple(args.command)
    if command[:1] == ("--",):
        command = command[1:]
    return run(
        command,
        repository=REPO_ROOT,
        family=args.family,
        label=args.label,
        signal=args.signal,
        expected_lanes=tuple(args.expected_lane),
    )


type _SignalProcessor = (
    _ImportBoundariesProcessor
    | _RegistryHealthProcessor
    | _PytestSummaryProcessor
    | _DeadWeightSignalProcessor
    | _LocalesStatusSignalProcessor
)


def _new_signal_processor(signal: str | None, expected_lanes: tuple[str, ...]) -> _SignalProcessor | None:
    """Select the declared signal reducer without changing the transcript protocol."""
    if signal == _IMPORT_BOUNDARIES_SIGNAL:
        processor = _ImportBoundariesProcessor()
    elif signal in {_BINDING_SIGNAL, _REGISTRY_HEALTH_SIGNAL}:
        processor = _RegistryHealthProcessor()
    elif signal == _PYTEST_SUMMARY_SIGNAL:
        processor = _PytestSummaryProcessor(expected_lanes)
    elif signal == _AUDIT_DEAD_WEIGHT_SIGNAL:
        processor = _DeadWeightSignalProcessor()
    elif signal == _LOCALES_STATUS_SIGNAL:
        processor = _LocalesStatusSignalProcessor()
    else:
        processor = None
    return processor


if __name__ == "__main__":
    sys.exit(main())
