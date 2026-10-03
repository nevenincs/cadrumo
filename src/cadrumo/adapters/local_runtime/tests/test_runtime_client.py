"""Installed opener ownership over explicit endpoint release fault ports.

The real launch door, handshake, frontend client and canonical cleanup run.
Native endpoint acquisition is a named fault seam, not OS acceptance evidence.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import (
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError

from .. import runtime_client
from ..frontend_client import RuntimeFrontendClient
from ..runtime_frame_io import write_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _ReleasePort:
    """Expose blocked, failed and successful native release separately."""

    def __init__(self, *, failures: int = 0, blocked: bool = False) -> None:
        self.failures = failures
        self.calls = 0
        self.released = False
        self.threads: list[int] = []
        self.started = asyncio.Event()
        self.gate = threading.Event()
        self.loop = asyncio.get_running_loop()
        if not blocked:
            self.gate.set()

    def close(self) -> None:
        self.calls += 1
        self.threads.append(threading.get_ident())
        self.loop.call_soon_threadsafe(self.started.set)
        assert self.gate.wait(5), "test did not settle native release"
        if self.calls <= self.failures:
            raise OSError("synthetic native release refusal")
        self.released = True


class _Channel(_ReleasePort):
    """Carry actual canonical handshake bytes with controllable release."""

    def __init__(self, *, refusal: RuntimeRefusalCode | None = None, failures: int = 0, blocked: bool = False) -> None:
        super().__init__(failures=failures, blocked=blocked)
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
        self.inbound = bytearray()
        self.writes: list[bytes] = []
        write_document(
            self,
            RuntimeServerHello(
                product_version="foreign" if refusal is RuntimeRefusalCode.VERSION_MISMATCH else "opener-test",
                storage_identity="b" * 64 if refusal is RuntimeRefusalCode.ROOT_MISMATCH else "a" * 64,
                boot_id=uuid4(),
            ),
            deadline=time.monotonic() + 5,
        )
        self.inbound.extend(b"".join(self.writes))
        self.writes.clear()

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        assert deadline > time.monotonic()
        assert len(self.inbound) >= count
        result = bytes(self.inbound[:count])
        del self.inbound[:count]
        return result

    def read_ready(self) -> bool:
        return bool(self.inbound)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > time.monotonic()
        self.writes.append(bytes(payload))


class _Endpoint(_ReleasePort):
    """Retain endpoint namespace ownership independently of its channel."""

    storage_identity = "a" * 64

    def __init__(self, channel: _Channel, *, failures: int = 0, blocked: bool = False) -> None:
        super().__init__(failures=failures, blocked=blocked)
        self.channel = channel

    def connect(self, *, timeout: float) -> _Channel:
        assert timeout > 0
        return self.channel


def _install(monkeypatch: pytest.MonkeyPatch, root: Path, endpoint: _Endpoint) -> None:
    """Substitute native acquisition only; keep actual opening and release."""
    monkeypatch.setattr(runtime_client, "effective_storage_root", lambda: root)
    monkeypatch.setattr(runtime_client, "version", lambda _: "opener-test")
    monkeypatch.setattr(runtime_client, "WindowsRuntimeEndpoint", lambda **_: endpoint)
    monkeypatch.setattr(runtime_client, "PosixRuntimeEndpoint", lambda **_: endpoint)


async def _open(profile_id: UUID) -> RuntimeFrontendClient:
    return await runtime_client.open_installed_runtime_client(
        profile_id=profile_id, frontend=OperationFrontendProjection.MCP, timeout=5
    )


def _cleanup(error: BaseException) -> AsyncResourceCleanupError:
    retained = error.__dict__.get("async_cleanup_error")
    assert isinstance(retained, AsyncResourceCleanupError)
    return retained


@pytest.mark.asyncio
async def test_success_transfers_exact_client_only_after_endpoint_retirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    channel = _Channel()
    endpoint = _Endpoint(channel)
    _install(monkeypatch, tmp_path, endpoint)
    profile_id = uuid4()
    client = await _open(profile_id)
    try:
        assert client.profile_id == profile_id
        assert client.frontend is OperationFrontendProjection.MCP
        assert endpoint.released and endpoint.calls == 1
        assert endpoint.threads[0] != threading.get_ident()
        assert not channel.released and channel.calls == 0
    finally:
        client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("refusal", [RuntimeRefusalCode.VERSION_MISMATCH, RuntimeRefusalCode.ROOT_MISMATCH])
@pytest.mark.parametrize("channel_failures", [0, 1])
async def test_failed_open_preserves_exact_handshake_refusal_and_all_retry_owners(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, refusal: RuntimeRefusalCode, channel_failures: int
) -> None:
    channel = _Channel(refusal=refusal, failures=channel_failures)
    endpoint = _Endpoint(channel, failures=1)
    _install(monkeypatch, tmp_path, endpoint)
    with pytest.raises(RuntimeRefusalError) as caught:
        await _open(uuid4())
    assert caught.value.reason is refusal
    assert endpoint.calls == channel.calls == 1
    retained = _cleanup(caught.value)
    await retained.retry_cleanup()
    await retained.retry_cleanup()
    assert endpoint.released and channel.released
    assert endpoint.calls == 2 and channel.calls == channel_failures + 1
    assert all(identity != threading.get_ident() for identity in endpoint.threads)


@pytest.mark.asyncio
@pytest.mark.parametrize("channel_failures", [0, 1, 2])
async def test_failed_endpoint_retirement_closes_unreturned_client_and_retains_both_owners(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, channel_failures: int
) -> None:
    channel = _Channel(failures=channel_failures)
    endpoint = _Endpoint(channel, failures=1)
    _install(monkeypatch, tmp_path, endpoint)
    with pytest.raises(RuntimeRefusalError) as caught:
        await _open(uuid4())
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert isinstance(caught.value.__cause__, AsyncResourceCleanupError)
    assert endpoint.calls == channel.calls == 1
    retained = _cleanup(caught.value)
    if channel_failures == 2:
        with pytest.raises(AsyncResourceCleanupError) as retry_failed:
            await retained.retry_cleanup()
        retained = retry_failed.value
        assert endpoint.released and not channel.released
    await retained.retry_cleanup()
    await retained.retry_cleanup()
    assert endpoint.released and channel.released
    assert endpoint.calls == 2 and channel.calls == channel_failures + 1
    assert all(identity != threading.get_ident() for identity in endpoint.threads + channel.threads)


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_release", [False, True])
@pytest.mark.parametrize("endpoint_failures", [1, 2])
async def test_repeated_cancel_during_endpoint_retirement_closes_unreturned_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failed_release: bool, endpoint_failures: int
) -> None:
    channel = _Channel(failures=int(failed_release))
    endpoint = _Endpoint(channel, failures=endpoint_failures if failed_release else 0, blocked=True)
    _install(monkeypatch, tmp_path, endpoint)
    opening = asyncio.create_task(_open(uuid4()))
    try:
        await asyncio.wait_for(endpoint.started.wait(), timeout=2)
        opening.cancel("first endpoint cancellation")
        await asyncio.sleep(0)
        opening.cancel("second endpoint cancellation")
        assert not opening.done()
        endpoint.gate.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await opening
        assert caught.value.args == ("first endpoint cancellation",)
        assert endpoint.calls == channel.calls == 1
        if failed_release:
            retained = _cleanup(caught.value)
            assert caught.value.__dict__["cleanup_error"] is retained
            if endpoint_failures == 2:
                with pytest.raises(AsyncResourceCleanupError) as retry_failed:
                    await retained.retry_cleanup()
                assert channel.released and not endpoint.released
                assert endpoint.calls == channel.calls == 2
                retained = retry_failed.value
            await retained.retry_cleanup()
            await retained.retry_cleanup()
        assert endpoint.released and channel.released
        assert endpoint.calls == (endpoint_failures + 1 if failed_release else 1)
        assert channel.calls == int(failed_release) + 1
        assert all(identity != threading.get_ident() for identity in endpoint.threads + channel.threads)
    finally:
        endpoint.gate.set()
        if not opening.done():
            opening.cancel()
            with pytest.raises(asyncio.CancelledError):
                await opening


@pytest.mark.asyncio
async def test_cancellation_while_refusal_cleanup_preserves_original_failed_channel_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    channel = _Channel(refusal=RuntimeRefusalCode.VERSION_MISMATCH, failures=1)
    endpoint = _Endpoint(channel, failures=1, blocked=True)
    _install(monkeypatch, tmp_path, endpoint)
    opening = asyncio.create_task(_open(uuid4()))
    try:
        await asyncio.wait_for(endpoint.started.wait(), timeout=2)
        opening.cancel("cancelled during refusal retirement")
        endpoint.gate.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await opening
        body = caught.value.__dict__.get("body_error")
        assert isinstance(body, RuntimeRefusalError)
        assert body.reason is RuntimeRefusalCode.VERSION_MISMATCH
        await _cleanup(caught.value).retry_cleanup()
        assert endpoint.released and channel.released
        assert endpoint.calls == channel.calls == 2
    finally:
        endpoint.gate.set()
        if not opening.done():
            opening.cancel()
            with pytest.raises(asyncio.CancelledError):
                await opening


@pytest.mark.asyncio
@pytest.mark.parametrize("channel_failures", [0, 1])
async def test_cancel_during_unreturned_client_release_retains_failed_endpoint_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, channel_failures: int
) -> None:
    channel = _Channel(failures=channel_failures, blocked=True)
    endpoint = _Endpoint(channel, failures=1)
    _install(monkeypatch, tmp_path, endpoint)
    opening = asyncio.create_task(_open(uuid4()))
    try:
        await asyncio.wait_for(channel.started.wait(), timeout=2)
        opening.cancel("first client cancellation")
        await asyncio.sleep(0)
        opening.cancel("second client cancellation")
        assert not opening.done()
        channel.gate.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await opening
        assert caught.value.args == ("first client cancellation",)
        body = caught.value.__dict__.get("body_error")
        assert isinstance(body, RuntimeRefusalError)
        assert body.reason is RuntimeRefusalCode.UNAVAILABLE
        assert endpoint.calls == channel.calls == 1
        retained = _cleanup(caught.value)
        await retained.retry_cleanup()
        await retained.retry_cleanup()
        assert endpoint.released and channel.released
        assert endpoint.calls == 2 and channel.calls == channel_failures + 1
        assert all(identity != threading.get_ident() for identity in endpoint.threads + channel.threads)
    finally:
        channel.gate.set()
        if not opening.done():
            opening.cancel()
            with pytest.raises(asyncio.CancelledError):
                await opening
