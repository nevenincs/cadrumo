"""A closing pipe retains its handle until native I/O has settled."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import TYPE_CHECKING

import pytest

from ...contracts.contracts import RefusalCode, RefusalError
from .. import windows_channel
from ..windows_channel import WindowsChannel
from .test_channel_readiness_wait import pair as pair

if TYPE_CHECKING:
    from _win32typing import PyOVERLAPPED, PyOVERLAPPEDReadBuffer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows pipes"),
]


@pytest.mark.parametrize("direction", ["read", "write", "readable"])
def test_close_cancels_io_but_retains_handle_until_completion(
    pair: tuple[WindowsChannel, WindowsChannel], monkeypatch: pytest.MonkeyPatch, direction: str
) -> None:
    import win32file

    channel, _peer = pair
    submitted, cancelled, finish = Event(), Event(), Event()
    original_finish = windows_channel.finish_windows_io
    original_cancel = windows_channel.cancel_windows_io
    original_result = win32file.GetOverlappedResult

    def held_result(handle: int, overlapped: PyOVERLAPPED, wait: bool) -> int:
        if direction == "readable":
            assert finish.wait(5), "test did not release readiness completion"
            assert win32file.GetFileType(handle) == win32file.FILE_TYPE_PIPE
        return original_result(handle, overlapped, wait)

    def held_finish(handle: int, overlapped: PyOVERLAPPED, *, deadline: float) -> int:
        submitted.set()
        assert finish.wait(5), "test did not release completion"
        # A released/recycled handle cannot safely be used to join native I/O.
        assert win32file.GetFileType(handle) == win32file.FILE_TYPE_PIPE
        return original_finish(handle, overlapped, deadline=deadline)

    def cancel(handle: int) -> None:
        try:
            original_cancel(handle)
        finally:
            cancelled.set()

    monkeypatch.setattr(windows_channel, "finish_windows_io", held_finish)
    monkeypatch.setattr(windows_channel, "cancel_windows_io", cancel)
    monkeypatch.setattr(win32file, "GetOverlappedResult", held_result)

    original_read = win32file.ReadFile

    def read(handle: int, buffer: PyOVERLAPPEDReadBuffer, overlapped: PyOVERLAPPED) -> object:
        result = original_read(handle, buffer, overlapped)
        if direction == "readable":
            submitted.set()
        return result

    monkeypatch.setattr(win32file, "ReadFile", read)

    def transfer() -> None:
        try:
            if direction == "read":
                channel.read_exact(1, deadline=time.monotonic() + 10)
            elif direction == "readable":
                channel.wait_readable()
            else:
                channel.write_all(b"x" * (64 * 1024), deadline=time.monotonic() + 10)
        except RefusalError as error:
            assert error.reason is RefusalCode.CONNECTION_CLOSED

    with ThreadPoolExecutor(max_workers=2) as pool:
        transferring = pool.submit(transfer)
        closing = None
        try:
            assert submitted.wait(3)
            closing = pool.submit(channel.close)
            assert cancelled.wait(3), "close must cancel outstanding native I/O"
            assert not closing.done(), "close released a handle still used by I/O"
            with pytest.raises(RefusalError) as refused:
                channel.read_ready()
            assert refused.value.reason is RefusalCode.CONNECTION_CLOSED
        finally:
            finish.set()
        transferring.result(timeout=5)
        assert closing is not None
        closing.result(timeout=5)
    channel.close()


def test_cancel_failure_still_joins_native_completion(
    pair: tuple[WindowsChannel, WindowsChannel], monkeypatch: pytest.MonkeyPatch
) -> None:
    import pywintypes
    import win32file

    from ..windows_native_io import finish_windows_io

    channel, _peer = pair
    original_cancel, original_result = win32file.CancelIo, win32file.GetOverlappedResult
    joined = Event()

    def cancel(handle: int) -> None:
        original_cancel(handle)
        raise pywintypes.error(1168, "CancelIo", "cancellation already requested")

    def result(handle: int, overlapped: PyOVERLAPPED, wait: bool) -> int:
        try:
            return original_result(handle, overlapped, wait)
        finally:
            if wait:
                joined.set()

    def expired_finish(handle: int, overlapped: PyOVERLAPPED, *, deadline: float) -> int:
        return finish_windows_io(handle, overlapped, deadline=time.monotonic() - 1)

    monkeypatch.setattr(win32file, "CancelIo", cancel)
    monkeypatch.setattr(win32file, "GetOverlappedResult", result)
    monkeypatch.setattr(windows_channel, "finish_windows_io", expired_finish)
    with pytest.raises(RefusalError) as refused:
        channel.read_exact(1, deadline=time.monotonic() + 5)
    assert refused.value.reason is RefusalCode.TIMEOUT
    assert joined.is_set(), "cancellation errors must not skip the native completion join"
