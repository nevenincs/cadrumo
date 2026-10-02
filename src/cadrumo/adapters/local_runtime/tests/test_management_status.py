"""Passive listener probe verifies the existing handshake and status correlation."""

from __future__ import annotations

import asyncio
import json
import struct
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.application.runtime.management_status import RuntimeListenerState
from cadrumo.application.runtime.transport import RuntimeTransportStatus
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, async_cleanup_failures, close_async_resources

from ..framing import RuntimeTransportCleanup, VerifiedRuntimeConnection
from ..management_status import probe_runtime_listener

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_IDENTITY = "a" * 64


def _frame(document: BaseModel) -> bytes:
    payload = json.dumps(document.model_dump(mode="json"), separators=(",", ":")).encode()
    return b"J" + struct.pack("!I", len(payload)) + payload


class _Channel:
    def __init__(self, *, expected: RuntimeClientHello, accepting: bool, wrong_boot: bool = False) -> None:
        self.boot = uuid4()
        self.connection = uuid4()
        self.accepting = accepting
        self.wrong_boot = wrong_boot
        self.read_buffer = bytearray(
            _frame(
                RuntimeServerHello(
                    product_version=expected.product_version,
                    storage_identity=expected.storage_identity,
                    boot_id=self.boot,
                )
            )
        )
        self.closed = False
        self.requests = 0

    @property
    def peer(self) -> RuntimePeer:
        return RuntimePeer(os_owner_id="test-owner", process_id=1)

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        assert deadline > 0
        assert len(self.read_buffer) >= count
        data = bytes(self.read_buffer[:count])
        del self.read_buffer[:count]
        return data

    def read_ready(self) -> bool:
        return bool(self.read_buffer)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > 0
        if b'"action":"runtime_status"' not in payload:
            return
        self.requests += 1
        request_id = UUID(json.loads(payload[5:])["request_id"])
        self.read_buffer.extend(
            _frame(
                RuntimeTransportStatus(
                    request_id=request_id,
                    runtime_boot_id=uuid4() if self.wrong_boot else self.boot,
                    connection_id=self.connection,
                    accepting_connections=self.accepting,
                )
            )
        )

    def close(self) -> None:
        self.closed = True


class _Endpoint:
    storage_identity = _IDENTITY

    def __init__(self, channel: _Channel | None = None, *, refusal: RuntimeRefusalCode | None = None) -> None:
        self.channel = channel
        self.refusal = refusal
        self.connects = 0

    def connect(self, *, timeout: float) -> _Channel:
        assert 0 < timeout <= 3
        self.connects += 1
        if self.refusal is not None:
            raise RuntimeRefusalError(self.refusal)
        assert self.channel is not None
        return self.channel


@pytest.mark.parametrize("accepting", [True, False])
def test_verified_status_distinguishes_ready_and_draining(accepting: bool) -> None:
    expected = RuntimeClientHello(product_version="test", storage_identity=_IDENTITY)
    channel = _Channel(expected=expected, accepting=accepting)
    endpoint = _Endpoint(channel)
    observed = probe_runtime_listener(endpoint, expected=expected)
    assert observed is (RuntimeListenerState.READY if accepting else RuntimeListenerState.DRAINING)
    assert channel.requests == 1 and channel.closed and endpoint.connects == 1


def test_wrong_boot_refuses_and_closes_without_claiming_readiness() -> None:
    expected = RuntimeClientHello(product_version="test", storage_identity=_IDENTITY)
    channel = _Channel(expected=expected, accepting=True, wrong_boot=True)
    assert probe_runtime_listener(_Endpoint(channel), expected=expected) is RuntimeListenerState.REFUSED
    assert channel.closed


def test_missing_endpoint_is_unavailable_and_root_mismatch_never_connects() -> None:
    expected = RuntimeClientHello(product_version="test", storage_identity=_IDENTITY)
    missing = _Endpoint(refusal=RuntimeRefusalCode.ENDPOINT_NOT_READY)
    assert probe_runtime_listener(missing, expected=expected) is RuntimeListenerState.UNAVAILABLE
    different = _Endpoint(refusal=RuntimeRefusalCode.PEER_UNTRUSTED)
    mismatch = RuntimeClientHello(product_version="test", storage_identity="b" * 64)
    assert probe_runtime_listener(different, expected=mismatch) is RuntimeListenerState.REFUSED
    assert different.connects == 0
    untrusted = _Endpoint(refusal=RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
    assert probe_runtime_listener(untrusted, expected=expected) is RuntimeListenerState.REFUSED


class _ReleaseFaultChannel(_Channel):
    """Expose native release faults through actual verified framing."""

    def __init__(
        self,
        *,
        expected: RuntimeClientHello,
        failures: int,
        primary: BaseException | None = None,
        handshake: bool = False,
        release_cancellation: asyncio.CancelledError | None = None,
    ) -> None:
        super().__init__(expected=expected, accepting=True)
        self.failures = failures
        self.primary = primary
        self.handshake = handshake
        self.release_cancellation = release_cancellation
        self.close_calls = 0

    @override
    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        super().write_all(payload, deadline=deadline)
        is_status = b'"action":"runtime_status"' in payload
        if self.primary is not None and is_status != self.handshake:
            raise self.primary

    @override
    def close(self) -> None:
        self.close_calls += 1
        if self.close_calls <= self.failures:
            if self.release_cancellation is not None:
                raise self.release_cancellation
            raise OSError("synthetic probe release failure")
        super().close()


@pytest.mark.asyncio
async def test_probe_success_retains_failed_verified_connection_for_one_retry() -> None:
    expected = RuntimeClientHello(product_version="test", storage_identity=_IDENTITY)
    channel = _ReleaseFaultChannel(expected=expected, failures=1)
    with pytest.raises(AsyncResourceCleanupError) as failed:
        probe_runtime_listener(_Endpoint(channel), expected=expected)
    assert channel.requests == 1 and channel.close_calls == 1 and not channel.closed
    (owner,) = failed.value.resources
    assert isinstance(owner, RuntimeTransportCleanup)
    assert isinstance(owner.resource, VerifiedRuntimeConnection)
    await failed.value.retry_cleanup()
    await failed.value.retry_cleanup()
    assert owner.released and channel.closed and channel.close_calls == 2
    assert channel.requests == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("handshake", [False, True], ids=["status", "handshake"])
@pytest.mark.parametrize("cancelled", [False, True], ids=["typed-primary", "native-cancellation"])
async def test_probe_preserves_exact_primary_and_original_failed_framing_owner(
    handshake: bool, cancelled: bool
) -> None:
    expected = RuntimeClientHello(product_version="test", storage_identity=_IDENTITY)
    primary = (
        asyncio.CancelledError("native-probe-cancellation")
        if cancelled
        else RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    )
    channel = _ReleaseFaultChannel(expected=expected, failures=2, primary=primary, handshake=handshake)
    with pytest.raises(type(primary)) as failed:
        probe_runtime_listener(_Endpoint(channel), expected=expected)
    assert failed.value is primary
    assert channel.close_calls == 1 and not channel.closed
    (retained,) = async_cleanup_failures(primary)
    (owner,) = retained.resources
    assert owner is primary.__dict__["_runtime_transport_cleanup"]
    assert isinstance(owner, RuntimeTransportCleanup)
    assert isinstance(owner.resource, VerifiedRuntimeConnection)
    with pytest.raises(AsyncResourceCleanupError) as retry_failed:
        await retained.retry_cleanup()
    assert retry_failed.value.resources == (owner,) and channel.close_calls == 2
    await retry_failed.value.retry_cleanup()
    await retry_failed.value.retry_cleanup()
    assert owner.released and channel.closed and channel.close_calls == 3


@pytest.mark.asyncio
async def test_probe_preserves_terminal_native_release_cancellation() -> None:
    expected = RuntimeClientHello(product_version="test", storage_identity=_IDENTITY)
    primary = asyncio.CancelledError("native-probe-release-cancellation")
    earlier = _EarlierProbeOwner()
    with pytest.raises(asyncio.CancelledError) as prior:
        await close_async_resources(earlier, task_name="earlier-probe-release", primary_error=primary)
    assert prior.value is primary and earlier.calls == 1
    channel = _ReleaseFaultChannel(expected=expected, failures=1, release_cancellation=primary)
    with pytest.raises(asyncio.CancelledError) as failed:
        probe_runtime_listener(_Endpoint(channel), expected=expected)
    assert failed.value is primary and channel.close_calls == 1
    (retained,) = async_cleanup_failures(primary)
    assert primary.__dict__["async_cleanup_error"] is primary.__dict__["cleanup_error"] is retained
    assert earlier in retained.resources and len(retained.resources) == 2
    await retained.retry_cleanup()
    assert channel.closed and channel.close_calls == earlier.calls == 2 and earlier.closed


class _EarlierProbeOwner:
    """An actual earlier failed owner attached by canonical cancellation cleanup."""

    def __init__(self) -> None:
        self.calls = 0
        self.closed = False

    async def close(self) -> None:
        assert not self.closed
        self.calls += 1
        if self.calls == 1:
            raise OSError("earlier synthetic probe release failure")
        self.closed = True
