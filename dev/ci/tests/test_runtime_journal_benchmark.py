"""Verify native lock attribution and payload-free observer publication."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.core.locks import exclusive_file_lock
from dev.ci.runtime_journal_benchmark import (
    JournalRecorder,
    _worker_script,
    observe_journal,
    publish_after_worker_drain,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_native_lock_correlates_fsync_and_diagnostics_without_retaining_arguments(tmp_path: Path) -> None:
    recorder = JournalRecorder(tmp_path, "test")
    journal_root = tmp_path / "operation-journals"
    journal_root.mkdir()
    with (
        observe_journal(recorder),
        (tmp_path / "data").open("w", encoding="utf-8") as destination,
        exclusive_file_lock(journal_root / ".repository"),
    ):
        destination.write("private-synthetic-input")
        destination.flush()
        os.fsync(destination.fileno())
        logging.getLogger(__name__).warning("private-synthetic-diagnostic")
        with pytest.raises(RuntimeError, match="while owning"):
            recorder.flush()
    rows = [json.loads(line) for line in recorder.path.read_text(encoding="utf-8").splitlines()]
    holds = [row for row in rows if row["kind"] == "lock"]
    assert len(holds) == 1
    hold = holds[0]
    fsync = next(row for row in rows if row["boundary"] == "filesystem.fsync")
    diagnostic = next(row for row in rows if row["boundary"] == "diagnostics.emit_under_lock")
    for child in (fsync, diagnostic):
        assert child["lock_id"] == hold["id"]
        assert hold["start_ns"] <= child["start_ns"] <= child["end_ns"] <= hold["end_ns"]
    assert "private-synthetic" not in recorder.path.read_text(encoding="utf-8")


def test_phase_exception_keeps_type_and_parent_without_exception_message(tmp_path: Path) -> None:
    recorder = JournalRecorder(tmp_path, "test")
    with (
        pytest.raises(ValueError, match="private-synthetic-error"),
        recorder.measure("outer"),
        recorder.measure("inner"),
    ):
        raise ValueError("private-synthetic-error")
    recorder.flush()
    inner, outer = [json.loads(line) for line in recorder.path.read_text(encoding="utf-8").splitlines()]
    assert inner["parent_id"] == outer["id"]
    assert inner["outcome"] == outer["outcome"] == "ValueError"
    assert "private-synthetic" not in recorder.path.read_text(encoding="utf-8")


def test_generated_native_worker_installs_observer_in_composition(tmp_path: Path) -> None:
    copied = _worker_script(tmp_path)
    source = copied.read_text(encoding="utf-8")
    compile(source, str(copied), "exec")
    assert "observe_journal(recorder), publish_after_worker_drain(recorder):" in source


@pytest.mark.asyncio
@pytest.mark.parametrize("needs_containment", [False, True])
async def test_worker_publication_follows_successful_drain_off_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, needs_containment: bool
) -> None:
    from cadrumo_runtime.host.operation_host import ProfileWorkerOperationHost

    events: list[str] = []
    loop_thread = threading.get_ident()
    result = SimpleNamespace(needs_containment=needs_containment)

    async def close(self: object) -> object:
        events.append("drained")
        return result

    def flush() -> None:
        assert threading.get_ident() != loop_thread
        events.append("published")

    recorder = JournalRecorder(tmp_path, "test")
    monkeypatch.setattr(ProfileWorkerOperationHost, "close", close)
    monkeypatch.setattr(recorder, "flush", flush)
    with publish_after_worker_drain(recorder):
        assert await ProfileWorkerOperationHost.close(object.__new__(ProfileWorkerOperationHost)) is result
    assert events == (["drained"] if needs_containment else ["drained", "published"])
