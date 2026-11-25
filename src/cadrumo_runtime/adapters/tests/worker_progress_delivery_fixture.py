"""Contained native child reporting one committed operation through production IPC."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from threading import Event
from typing import Literal

from pydantic import BaseModel

from cadrumo.application.operations.models import OperationId
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.host.operation_progress_reporter import OperationProgressReporter

from ..worker_authorization_client import WorkerAuthorizationClient


class ProgressSeed(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: ProfileWorkerIdentity
    parent_pid: int
    records_changed: bool


class ProgressMark(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    stage: Literal["commit", "send", "refused", "ack"]
    ticks: int


class ProgressResult(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    marks: tuple[ProgressMark, ...]
    opened: int


def wait_for_marker(path: Path) -> None:
    """Bound test coordination; this does not drive the production reporter's retry."""
    deadline = time.monotonic() + 30
    wait = Event()
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(path.name)
        wait.wait(0.01)


def _publish_marker(path: Path, value: str) -> None:
    """Publish complete coordination contents before the parent observes existence."""
    pending = path.with_name(f"{path.name}.pending")
    pending.write_text(value, encoding="utf-8")
    pending.replace(path)


def exercise(root: Path) -> None:
    seed = ProgressSeed.model_validate_json((root / "seed.json").read_bytes())
    _publish_marker(root / "worker.pid", str(os.getpid()))
    wait_for_marker(root / "listening")
    client = WorkerAuthorizationClient(identity=seed.identity, root=root, parent_pid=seed.parent_pid)
    marks: list[ProgressMark] = []

    def mark(stage: Literal["commit", "send", "refused", "ack"]) -> None:
        marks.append(ProgressMark(stage=stage, ticks=time.perf_counter_ns()))

    def send(operation_ids: tuple[OperationId, ...], settled: tuple[OperationId, ...]) -> None:
        mark("send")
        try:
            client.operations_advanced(operation_ids, records_changed=seed.records_changed, settled=settled)
        except Exception:
            mark("refused")
            raise
        else:
            mark("ack")
            _publish_marker(root / "acknowledged", "1")

    reporter = OperationProgressReporter(send)
    try:
        mark("commit")
        reporter.committed("c" * 64)
        wait_for_marker(root / "finish")
    finally:
        reporter.close()
        result = ProgressResult(marks=tuple(marks), opened=client.connections.opened)
        client.close()
        _publish_marker(root / "result.json", result.model_dump_json())


if __name__ == "__main__":
    exercise(Path(sys.argv[1]))
