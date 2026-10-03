"""Owned native-boundary fault ports; these cases do not prove OS transport."""

from __future__ import annotations

import asyncio
import threading
import time
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError

from ..framing import write_document
from ..startup import RuntimeLaunchDoor

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _BlockedChannel:
    """Hold native handshake/release until explicit owning events settle them."""

    def __init__(self, *, close_failures: int, foreign_version: bool = False) -> None:
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
        self.loop = asyncio.get_running_loop()
        self.started = asyncio.Event()
        self.close_started = asyncio.Event()
        self.release_handshake = threading.Event()
        self.release_close = threading.Event()
        self.inbound = bytearray()
        self.writes: list[bytes] = []
        self.close_calls = 0
        self.close_failures = close_failures
        self.close_threads: list[int] = []
        self.released = False
        write_document(
            self,
            RuntimeServerHello(
                product_version="foreign" if foreign_version else "cleanup-test",
                storage_identity="a" * 64,
                boot_id=uuid4(),
            ),
            deadline=time.monotonic() + 5,
        )
        self.inbound.extend(b"".join(self.writes))
        self.writes.clear()

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        self.loop.call_soon_threadsafe(self.started.set)
        assert self.release_handshake.wait(5), "test did not settle its held handshake"
        assert len(self.inbound) >= count
        result = bytes(self.inbound[:count])
        del self.inbound[:count]
        return result

    def read_ready(self) -> bool:
        return bool(self.inbound)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.writes.append(bytes(payload))

    def close(self) -> None:
        self.close_threads.append(threading.get_ident())
        self.close_calls += 1
        self.loop.call_soon_threadsafe(self.close_started.set)
        assert self.release_close.wait(5), "test did not settle its held release"
        if self.close_calls <= self.close_failures:
            raise OSError("synthetic native release failure")
        self.released = True


class _Endpoint:
    storage_identity = "a" * 64

    def __init__(self, channel: _BlockedChannel) -> None:
        self.channel = channel

    def connect(self, *, timeout: float) -> _BlockedChannel:
        return self.channel


def _door(channel: _BlockedChannel) -> RuntimeLaunchDoor:
    return RuntimeLaunchDoor(
        _Endpoint(channel), expected=RuntimeClientHello(product_version="cleanup-test", storage_identity="a" * 64)
    )


def _cleanup(error: BaseException) -> AsyncResourceCleanupError:
    cleanup = error.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    return cleanup


@pytest.mark.asyncio
@pytest.mark.parametrize("close_failures", [1, 2])
async def test_repeated_cancel_retains_late_connection_failed_release_off_event_loop(close_failures: int) -> None:
    channel = _BlockedChannel(close_failures=close_failures)
    opening = asyncio.create_task(_door(channel).open(timeout=5))
    try:
        await asyncio.wait_for(channel.started.wait(), timeout=2)
        opening.cancel("first cancellation")
        channel.release_handshake.set()
        await asyncio.wait_for(channel.close_started.wait(), timeout=2)
        assert not opening.done()
        assert all(identity != threading.get_ident() for identity in channel.close_threads)
        opening.cancel("second cancellation")
        channel.release_close.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await opening
        assert caught.value.args == ("first cancellation",)
        assert channel.close_calls == 1
        cleanup = _cleanup(caught.value)
        if close_failures == 2:
            with pytest.raises(AsyncResourceCleanupError) as retry_failed:
                await cleanup.retry_cleanup()
            assert not channel.released
            cleanup = retry_failed.value
        await cleanup.retry_cleanup()
        await cleanup.retry_cleanup()
        assert channel.close_calls == close_failures + 1
        assert channel.released
        assert all(identity != threading.get_ident() for identity in channel.close_threads)
    finally:
        channel.release_handshake.set()
        channel.release_close.set()
        if not opening.done():
            opening.cancel()
            with pytest.raises(asyncio.CancelledError):
                await opening


@pytest.mark.asyncio
async def test_cancelled_rejected_handshake_adopts_nested_failed_owner() -> None:
    channel = _BlockedChannel(close_failures=1, foreign_version=True)
    opening = asyncio.create_task(_door(channel).open(timeout=5))
    try:
        await asyncio.wait_for(channel.started.wait(), timeout=2)
        opening.cancel("cancelled admission")
        channel.release_handshake.set()
        await asyncio.wait_for(channel.close_started.wait(), timeout=2)
        channel.release_close.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await opening
        body = caught.value.__dict__.get("cleanup_error")
        assert isinstance(body, RuntimeRefusalError)
        assert body.reason is RuntimeRefusalCode.VERSION_MISMATCH
        assert _cleanup(caught.value) is _cleanup(body)
        await _cleanup(caught.value).retry_cleanup()
        assert channel.released
        assert channel.close_calls == 2
    finally:
        channel.release_handshake.set()
        channel.release_close.set()
        if not opening.done():
            opening.cancel()
            with pytest.raises(asyncio.CancelledError):
                await opening


@pytest.mark.asyncio
async def test_deadline_mapping_preserves_cause_and_retryable_late_connection_owner() -> None:
    channel = _BlockedChannel(close_failures=1)
    channel.release_close.set()
    # The actual asyncio timeout fires first. A separate timer then settles
    # the deliberately held native port, as a late native completion would.
    release = asyncio.get_running_loop().call_later(0.1, channel.release_handshake.set)
    try:
        with pytest.raises(RuntimeRefusalError) as caught:
            await _door(channel).open(timeout=0.05)
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        assert isinstance(caught.value.__cause__, TimeoutError)
        cancellation = caught.value.__cause__.__cause__
        assert isinstance(cancellation, asyncio.CancelledError)
        assert _cleanup(caught.value) is _cleanup(cancellation)
        assert channel.close_calls == 1
        await _cleanup(caught.value).retry_cleanup()
        assert channel.released
        assert channel.close_calls == 2
    finally:
        release.cancel()
        channel.release_handshake.set()
        channel.release_close.set()
