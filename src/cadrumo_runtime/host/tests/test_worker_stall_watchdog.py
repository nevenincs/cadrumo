"""A profile worker whose event loop stalls leaves every thread's stack in its own dump file.

The tests stall a real running loop with one short synchronous block and read
what the native ``faulthandler`` timer wrote; healthy loops must write nothing.
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import cast

import pytest

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.core.config import override_settings
from cadrumo.core.logging import default_log_file_path
from cadrumo.tests.log_records import delivered_records

from ...adapters.worker_transport import WorkerChannel
from .. import worker_service
from ..operation_host import ProfileWorkerOperationHost
from ..profile_login import ProfileWorkerHumanLogin
from ..worker import _serve_watched
from ..worker_stall_watchdog import (
    DUMP_NAME_PREFIX,
    DUMP_NAME_SUFFIX,
    RETAINED_DUMP_FILES,
    watch_event_loop,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PRIVATE_LOCAL = "synthetic-private-local-canary"
_LOGGER_NAME = "cadrumo_runtime.host.worker_stall_watchdog"


def _dump_path(directory: Path) -> Path:
    return directory / f"{DUMP_NAME_PREFIX}{os.getpid()}{DUMP_NAME_SUFFIX}"


def _block_the_loop(seconds: float) -> None:
    private_local = _PRIVATE_LOCAL
    time.sleep(seconds)
    del private_local


def _hold_the_interpreter_lock(seconds: float) -> None:
    """Sleep in a native call that keeps the GIL, so no other Python thread can run meanwhile."""
    native = ctypes.PyDLL("kernel32" if sys.platform == "win32" else None)
    if sys.platform == "win32":
        native.Sleep(int(seconds * 1000))
    else:
        native.usleep(int(seconds * 1_000_000))


def _events(caplog: pytest.LogCaptureFixture, name: str) -> list[logging.LogRecord]:
    return [record for record in delivered_records(caplog, _LOGGER_NAME) if record.getMessage() == name]


@pytest.mark.asyncio
async def test_a_stalled_loop_writes_every_thread_stack_and_reports_it_once_the_loop_turns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    dump = _dump_path(tmp_path)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        async with watch_event_loop(directory=tmp_path, stall_seconds=0.2, tick_seconds=0.05):
            await asyncio.sleep(0.1)
            assert dump.stat().st_size == 0
            _block_the_loop(0.6)
            written = dump.stat().st_size
            await asyncio.sleep(0.15)

    text = dump.read_text(encoding="utf-8")
    assert written > 0
    assert re.search(r"^Timeout \(", text, re.MULTILINE)
    assert "(most recent call first):" in text
    assert "in _block_the_loop" in text
    assert _PRIVATE_LOCAL not in text
    armed = _events(caplog, "profile_worker_stall_watchdog_armed")
    dumped = _events(caplog, "profile_worker_event_loop_stall_dumped")
    assert [record.__dict__["dump_file"] for record in armed + dumped] == [dump.name] * 2
    assert dumped[0].levelno == logging.WARNING
    assert dumped[0].__dict__["outcome"] == "dumped"
    assert dumped[0].__dict__["timeout_seconds"] == 0.2
    assert dumped[0].__dict__["elapsed_seconds"] >= 0.5
    assert str(tmp_path) not in repr([record.__dict__ for record in armed + dumped])


@pytest.mark.asyncio
async def test_a_loop_stalled_while_holding_the_interpreter_lock_is_still_dumped(tmp_path: Path) -> None:
    dump = _dump_path(tmp_path)
    async with watch_event_loop(directory=tmp_path, stall_seconds=0.2, tick_seconds=0.05):
        await asyncio.sleep(0.1)
        _hold_the_interpreter_lock(0.6)
        written = dump.stat().st_size

    assert written > 0
    assert "in _hold_the_interpreter_lock" in dump.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_a_healthy_loop_writes_nothing_and_leaves_no_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    dump = _dump_path(tmp_path)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        async with watch_event_loop(directory=tmp_path, stall_seconds=0.3, tick_seconds=0.05):
            # Far longer than the stall bound: only the loop's own re-arming keeps the timer from firing.
            await asyncio.sleep(0.8)
            assert dump.stat().st_size == 0
        assert not dump.exists()
        # Disarmed on exit: a thread blocked past the bound writes nowhere.
        _block_the_loop(0.5)

    assert not dump.exists()
    assert _events(caplog, "profile_worker_event_loop_stall_dumped") == []


@pytest.mark.skipif(sys.platform == "win32", reason="Windows files take the log directory's access list")
def test_the_dump_file_is_owner_only_where_the_platform_has_modes(tmp_path: Path) -> None:
    async def scenario() -> int:
        async with watch_event_loop(directory=tmp_path, stall_seconds=5.0):
            return stat.S_IMODE(_dump_path(tmp_path).stat().st_mode)

    assert asyncio.run(scenario()) == 0o600


@pytest.mark.asyncio
async def test_a_full_dump_file_stops_taking_dumps(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    dump = _dump_path(tmp_path)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        async with watch_event_loop(directory=tmp_path, stall_seconds=0.2, tick_seconds=0.05, max_bytes=1):
            _block_the_loop(0.5)
            await asyncio.sleep(0.15)
            first = dump.stat().st_size
            _block_the_loop(0.5)
            await asyncio.sleep(0.15)
            second = dump.stat().st_size

    assert first > 0
    assert second == first
    assert [record.__dict__["outcome"] for record in _events(caplog, "profile_worker_event_loop_stall_dumped")] == [
        "capped"
    ]


@pytest.mark.asyncio
async def test_old_dump_files_are_pruned_to_the_retention_count_and_other_files_are_left(tmp_path: Path) -> None:
    stale = [
        tmp_path / f"{DUMP_NAME_PREFIX}{1000 + index}{DUMP_NAME_SUFFIX}" for index in range(RETAINED_DUMP_FILES + 3)
    ]
    for index, path in enumerate(stale):
        path.write_text("synthetic earlier dump", encoding="utf-8")
        os.utime(path, (1_000_000 + index, 1_000_000 + index))
    unrelated = tmp_path / "cadrumo.log"
    unrelated.write_text("synthetic log", encoding="utf-8")

    async with watch_event_loop(directory=tmp_path, stall_seconds=5.0):
        remaining = sorted(path for path in tmp_path.glob(f"{DUMP_NAME_PREFIX}*{DUMP_NAME_SUFFIX}"))
        assert _dump_path(tmp_path) in remaining

    newest = stale[len(stale) - (RETAINED_DUMP_FILES - 1) :]
    assert sorted([*newest, _dump_path(tmp_path)]) == remaining
    assert unrelated.read_text(encoding="utf-8") == "synthetic log"


@pytest.mark.asyncio
async def test_an_unusable_directory_never_stops_the_worker_from_serving(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the log directory should be", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        async with watch_event_loop(directory=blocker / "logs"):
            served = True

    assert served
    unavailable = _events(caplog, "profile_worker_stall_watchdog_unavailable")
    assert [record.levelno for record in unavailable] == [logging.WARNING]
    assert unavailable[0].__dict__["outcome"] == "unavailable"


@pytest.mark.asyncio
async def test_the_worker_serves_both_channels_inside_the_watchdog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    served: list[bool] = []

    async def serve(*_owners: object) -> None:
        served.append(_dump_path(default_log_file_path().parent).exists())

    monkeypatch.setattr(worker_service, "_serve", serve)
    with override_settings(cadrumo_local_storage_root=tmp_path):
        await _serve_watched(
            cast(WorkerChannel, object()),
            cast(WorkerChannel, object()),
            cast(WorkerChannel, object()),
            cast(ProfileWorkerCustody, object()),
            cast(ProfileWorkerHumanLogin, object()),
            cast(ProfileWorkerOperationHost, object()),
        )
        assert not _dump_path(default_log_file_path().parent).exists()

    assert served == [True]
