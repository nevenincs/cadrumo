"""A journal read or replace waits out a peer's open handle instead of failing.

Journal reads take no lock. On Windows a reader holding a journal open refuses
the writer's replace, and a handle opened without sharing refuses the reader;
both clear the moment that handle closes. Reporting either as a corrupt or
unwritable journal leaves an operation that did nothing wrong unsettled.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from ...core.errors.error_codes import get_registered_error_code
from ..config_reset_repository import (
    ConfigResetJournalCorruptError,
    ConfigResetJournalError,
    ConfigResetJournalNotFoundError,
)
from ..journal_repository import JournalBusyError, JournalRepositoryBase

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32", reason="an open handle blocks a read or replace only on Windows"
)
_OPERATION_ID = "a" * 64
_GENERIC_READ = 0x80000000
_OPEN_EXISTING = 3
_NO_SHARING = 0


class _Operation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: str
    started_at: datetime
    note: str


def _repository(storage_root: Path) -> JournalRepositoryBase[_Operation]:
    return JournalRepositoryBase[_Operation](
        journal_dirname="contention-journals",
        storage_root=storage_root,
        parse_operation=_Operation.model_validate_json,
        error_type=ConfigResetJournalError,
        not_found_type=ConfigResetJournalNotFoundError,
        corrupt_type=ConfigResetJournalCorruptError,
        subject="contention journal",
        id_subject="contention journal",
    )


def _operation(note: str) -> _Operation:
    return _Operation(operation_id=_OPERATION_ID, started_at=datetime(2026, 9, 24, tzinfo=UTC), note=note)


@contextmanager
def _exclusively_held(path: Path, *, release_after: float) -> Iterator[None]:
    """Hold ``path`` open with no sharing, as a racing handle does, then close it on a timer."""
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = ctypes.c_void_p
        handle = kernel32.CreateFileW(str(path), _GENERIC_READ, _NO_SHARING, None, _OPEN_EXISTING, 0, None)
        assert handle not in (None, ctypes.c_void_p(-1).value), "the test could not take the exclusive handle"
        released = threading.Event()

        def release() -> None:
            if not released.is_set():
                released.set()
                kernel32.CloseHandle(ctypes.c_void_p(handle))

        timer = threading.Timer(release_after, release)
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
            release()
    else:
        raise AssertionError("an exclusive file handle exists only on Windows")


@_WINDOWS_ONLY
def test_a_read_blocked_by_a_briefly_held_journal_waits_it_out(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation("written"))
    with _exclusively_held(repository.path_for(_OPERATION_ID), release_after=0.3):
        loaded = repository.load(_OPERATION_ID)
    assert loaded.note == "written"


@_WINDOWS_ONLY
def test_a_replace_blocked_by_a_briefly_held_journal_lands_once_it_closes(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation("before"))
    with _exclusively_held(repository.path_for(_OPERATION_ID), release_after=0.3):
        repository.save(_operation("after"))
    assert repository.load(_OPERATION_ID).note == "after"


@_WINDOWS_ONLY
def test_a_hold_that_outlasts_the_window_is_busy_not_corrupt_and_the_journal_is_intact(tmp_path: Path) -> None:
    """A handle that never lets go is reported as busy, not retried forever and not called corruption.

    Corruption routes to different recovery than contention, so a held
    journal must never surface as the corrupt kind, on either side.
    """
    repository = _repository(tmp_path)
    repository.save(_operation("before"))
    with _exclusively_held(repository.path_for(_OPERATION_ID), release_after=60.0):
        with pytest.raises(JournalBusyError) as refused_write:
            repository.save(_operation("after"))
        with pytest.raises(JournalBusyError) as refused_read:
            repository.load(_OPERATION_ID)
    for refused in (refused_write.value, refused_read.value):
        assert not isinstance(refused, ConfigResetJournalCorruptError)
        assert get_registered_error_code(refused).code == "LOCKED_JOURNAL_BUSY"
    assert repository.load(_OPERATION_ID).note == "before"
