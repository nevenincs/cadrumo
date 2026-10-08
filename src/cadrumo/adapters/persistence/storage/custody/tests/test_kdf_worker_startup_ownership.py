"""Partial KDF startup closes each acquired real pipe descriptor exactly once."""

from __future__ import annotations

import errno
import os
import time
from collections import Counter
from collections.abc import Generator
from pathlib import Path
from typing import Literal

import pytest

from ......core.config import Settings
from .. import _kdf_worker_supervision as supervision
from .._kdf_worker_supervision import _SupervisedKdfWorker
from ..errors import ProfileCustodyRefusal, ProfileCustodyRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

type _FailurePoint = Literal["second_pipe", "mkdir", "temporary_directory", "launch"]


@pytest.fixture
def real_pipe_closes(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[list[int], Counter[int]]]:
    """Observe actual closes, then settle any descriptors leaked by a failing regression."""
    pipe = os.pipe
    close = os.close
    allocated: list[int] = []
    closes: Counter[int] = Counter()

    def tracked_pipe() -> tuple[int, int]:
        descriptors = pipe()
        allocated.extend(descriptors)
        return descriptors

    def tracked_close(descriptor: int) -> None:
        if descriptor in allocated:
            closes[descriptor] += 1
        close(descriptor)

    monkeypatch.setattr(supervision.os, "pipe", tracked_pipe)
    monkeypatch.setattr(supervision.os, "close", tracked_close)
    # Avoid unrelated logger file opens reusing the pipe descriptor numbers.
    # Diagnostic behavior is independently exercised by test_kdf_worker_diagnostics.
    monkeypatch.setattr(supervision, "diagnostic_event", lambda *_args, **_kwargs: None)
    try:
        yield allocated, closes
    finally:
        for descriptor in allocated:
            try:
                os.fstat(descriptor)
            except OSError:
                continue
            close(descriptor)


@pytest.mark.parametrize("point", ["second_pipe", "mkdir", "temporary_directory", "launch"])
@pytest.mark.parametrize("interrupted", [False, True])
def test_partial_start_closes_every_acquired_descriptor_once(
    point: _FailurePoint,
    interrupted: bool,
    real_pipe_closes: tuple[list[int], Counter[int]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    worker = _SupervisedKdfWorker(
        deadline=time.monotonic() + 30, settings=Settings(cadrumo_local_storage_root=tmp_path)
    )
    primary = (
        KeyboardInterrupt("synthetic startup interruption") if interrupted else OSError("synthetic startup failure")
    )
    allocated, closes = real_pipe_closes
    tracked_pipe = os.pipe
    mkdir = Path.mkdir
    launch_calls = 0

    def pipe() -> tuple[int, int]:
        if point == "second_pipe" and allocated:
            raise primary
        return tracked_pipe()

    def root_mkdir(path: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False) -> None:
        if path == worker._temporary_root:
            raise primary
        mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    def temporary_directory(*_args: object, **_kwargs: object) -> None:
        raise primary

    def launch(*_args: object, **_kwargs: object) -> None:
        nonlocal launch_calls
        launch_calls += 1
        raise primary

    monkeypatch.setattr(supervision.os, "pipe", pipe)
    if point == "mkdir":
        monkeypatch.setattr(Path, "mkdir", root_mkdir)
    elif point == "temporary_directory":
        monkeypatch.setattr(supervision.tempfile, "TemporaryDirectory", temporary_directory)
    monkeypatch.setattr(supervision, "_launch_worker", launch)

    translated = point == "launch" and not interrupted
    with pytest.raises(ProfileCustodyRefusedError if translated else type(primary)) as escaped, worker:
        pytest.fail("Partial-start fault must prevent ready admission")

    if translated:
        assert isinstance(escaped.value, ProfileCustodyRefusedError)
        assert escaped.value.refusal == ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE
    else:
        assert escaped.value is primary
    assert launch_calls == int(point == "launch")
    assert len(allocated) == (2 if point == "second_pipe" else 4)
    assert all(closes[descriptor] == 1 for descriptor in allocated)
    for descriptor in allocated:
        with pytest.raises(OSError) as closed:
            os.fstat(descriptor)
        assert closed.value.errno == errno.EBADF
    assert worker._request_fd is None and worker._result_fd is None
    assert worker._process is None and worker._job is None and worker._neutral_directory is None

    # A subsequent cleanup must never touch descriptor numbers already released.
    prior_closes = closes.copy()
    worker._close(failed=True)
    assert closes == prior_closes
