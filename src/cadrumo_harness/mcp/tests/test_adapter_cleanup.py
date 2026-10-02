"""MCP connection cleanup retains every client across cancellation and failure."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from threading import Event
from typing import cast, override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection, write_document
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.tests.test_enrollment_framing import MemoryChannel
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.application.runtime.transport import RuntimeStatusRequest
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo_harness.mcp.server import RuntimeMcpAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Client:
    """Observe the synchronous close boundary without owning a native transport."""

    def __init__(self, profile_id: UUID, *, blocked: bool = False, fail_once: bool = False) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.close_calls = 0
        self.started = Event()
        self.release = Event()
        self.closed = Event()
        self.fail_once = fail_once
        self.failure = RuntimeError("synthetic runtime client close failure")
        if not blocked:
            self.release.set()

    def close(self) -> None:
        self.close_calls += 1
        self.started.set()
        self.release.wait()
        if self.fail_once and self.close_calls == 1:
            raise self.failure
        self.closed.set()


def _adapter(enrollment: _Client, admitted: _Client) -> RuntimeMcpAdapter:
    assert enrollment is not admitted
    assert enrollment.profile_id == admitted.profile_id
    adapter = RuntimeMcpAdapter(
        profile_id=admitted.profile_id,
        client=cast(RuntimeFrontendClient, admitted),
    )
    adapter._enrollment_client = cast(RuntimeFrontendClient, enrollment)
    return adapter


def _assert_clients_retired(adapter: RuntimeMcpAdapter, enrollment: _Client, admitted: _Client) -> None:
    assert enrollment.closed.is_set()
    assert admitted.closed.is_set()
    assert enrollment.close_calls == admitted.close_calls == 1
    assert adapter._enrollment_client is None
    assert adapter.client is None


@pytest.mark.asyncio
async def test_cancellation_during_enrollment_close_retires_both_clients_before_propagating() -> None:
    async def scenario() -> None:
        profile_id = uuid4()
        enrollment = _Client(profile_id, blocked=True)
        admitted = _Client(profile_id)
        adapter = _adapter(enrollment, admitted)
        closing = asyncio.create_task(adapter.close())
        try:
            await asyncio.to_thread(enrollment.started.wait)
            assert not enrollment.closed.is_set()
            assert admitted.close_calls == 0
            assert not closing.done()
            closing.cancel()
            enrollment.release.set()
            with pytest.raises(asyncio.CancelledError):
                await closing
            _assert_clients_retired(adapter, enrollment, admitted)
        finally:
            enrollment.release.set()
            enrollment.started.set()
            if not closing.done():
                with suppress(asyncio.CancelledError):
                    await closing

    await asyncio.wait_for(scenario(), timeout=10)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("fail_close", [False, True])
async def test_close_preserves_prior_raw_cleanup_diagnostic_and_canonical_owner(
    cancelled: bool, fail_close: bool
) -> None:
    class EarlierOwner:
        def __init__(self) -> None:
            self.close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("synthetic earlier native release failure")

    earlier = EarlierOwner()
    with pytest.raises(AsyncResourceCleanupError) as prior_failure:
        await close_async_resources(earlier, task_name="mcp-prior-diagnostic-owner", primary_error=None)
    diagnostic = OSError("original raw cleanup diagnostic")
    primary = asyncio.CancelledError("original cancellation") if cancelled else ValueError("original body failure")
    primary.__dict__["async_cleanup_error"] = prior_failure.value
    primary.__dict__["cleanup_error"] = diagnostic
    profile_id = uuid4()
    enrollment = _Client(profile_id, fail_once=fail_close)
    admitted = _Client(profile_id)
    adapter = _adapter(enrollment, admitted)
    try:
        with pytest.raises(type(primary)) as caught:
            try:
                raise primary
            finally:
                await adapter.close()
        assert caught.value is primary
        retained = primary.__dict__.get("cleanup_error")
        assert isinstance(retained, AsyncResourceCleanupError)
        assert primary.__dict__.get("async_cleanup_error") is retained
        assert retained.__cause__ is diagnostic
        assert earlier in retained.resources
        assert len(retained.resources) == (2 if fail_close else 1)
        assert earlier.close_calls == enrollment.close_calls == admitted.close_calls == 1
        await retained.retry_cleanup()
        assert earlier.close_calls == 2
        assert enrollment.close_calls == (2 if fail_close else 1)
        assert admitted.close_calls == 1
        await adapter.close()
        assert earlier.close_calls == 2
        assert enrollment.close_calls == (2 if fail_close else 1)
        assert admitted.close_calls == 1
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_cancelled_close_waits_for_inflight_lock_then_retires_both_clients() -> None:
    async def scenario() -> None:
        profile_id = uuid4()
        enrollment = _Client(profile_id)
        admitted = _Client(profile_id)
        adapter = _adapter(enrollment, admitted)
        started = asyncio.Event()

        async def close_adapter() -> None:
            started.set()
            await adapter.close()

        await adapter._lock.acquire()
        lock_released = False
        closing = asyncio.create_task(close_adapter())
        try:
            await started.wait()
            assert enrollment.close_calls == admitted.close_calls == 0
            assert not closing.done()
            closing.cancel()
            adapter._lock.release()
            lock_released = True
            with pytest.raises(asyncio.CancelledError):
                await closing
            _assert_clients_retired(adapter, enrollment, admitted)
        finally:
            if not lock_released:
                adapter._lock.release()
            if not closing.done():
                with suppress(asyncio.CancelledError):
                    await closing

    await asyncio.wait_for(scenario(), timeout=10)


@pytest.mark.asyncio
async def test_failed_first_client_close_still_closes_second_and_retains_only_failed_owner_for_retry() -> None:
    async def scenario() -> None:
        profile_id = uuid4()
        enrollment = _Client(profile_id, fail_once=True)
        admitted = _Client(profile_id)
        adapter = _adapter(enrollment, admitted)

        with pytest.raises(AsyncResourceCleanupError) as caught:
            await adapter.close()

        assert caught.value.__cause__ is enrollment.failure
        assert enrollment.close_calls == admitted.close_calls == 1
        assert not enrollment.closed.is_set()
        assert admitted.closed.is_set()

        await caught.value.retry_cleanup()

        assert enrollment.closed.is_set()
        assert enrollment.close_calls == 2
        assert admitted.close_calls == 1

    await asyncio.wait_for(scenario(), timeout=10)


@pytest.mark.asyncio
async def test_cleanup_retry_releases_the_canonical_client_channel_without_reopening_admission() -> None:
    class FailingCloseChannel(MemoryChannel):
        close_calls = 0

        @override
        def close(self) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("synthetic channel cleanup failure")
            super().close()

    channel = FailingCloseChannel()
    peer = MemoryChannel()
    channel.pair(peer)
    expected = RuntimeClientHello(product_version="test", storage_identity="a" * 64)
    deadline = time.monotonic() + 10
    write_document(
        peer,
        RuntimeServerHello(
            product_version=expected.product_version, storage_identity=expected.storage_identity, boot_id=uuid4()
        ),
        deadline=deadline,
    )
    connection = VerifiedRuntimeConnection(channel, expected=expected, deadline=deadline)
    client = RuntimeFrontendClient(connection, profile_id=uuid4(), frontend=OperationFrontendProjection.MCP)
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=client)
    try:
        with pytest.raises(AsyncResourceCleanupError) as caught:
            await adapter.close()
        assert channel.close_calls == 1
        assert adapter.client is None
        with pytest.raises(RuntimeRefusalError) as refused:
            connection.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 10)
        assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
        await caught.value.retry_cleanup()
        assert channel.close_calls == 2
        connection.close()
        assert channel.close_calls == 2
    finally:
        connection.close()
        peer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_close", [False, True])
async def test_unwinding_cancellation_keeps_exact_primary_and_failed_owner(fail_close: bool) -> None:
    profile_id = uuid4()
    enrollment = _Client(profile_id, fail_once=fail_close)
    admitted = _Client(profile_id)
    adapter = _adapter(enrollment, admitted)
    primary = asyncio.CancelledError("original bootstrap cancellation")
    try:
        with pytest.raises(asyncio.CancelledError) as caught:
            try:
                raise primary
            finally:
                await adapter.close()
        assert caught.value is primary
        assert enrollment.close_calls == admitted.close_calls == 1
        assert admitted.closed.is_set()
        if fail_close:
            failure = primary.__dict__.get("cleanup_error")
            assert isinstance(failure, AsyncResourceCleanupError)
            assert primary.__dict__.get("async_cleanup_error") is failure
            assert len(failure.resources) == 1
            assert not enrollment.closed.is_set()
            await failure.retry_cleanup()
            assert enrollment.close_calls == 2
            assert enrollment.closed.is_set()
        else:
            assert enrollment.closed.is_set()
            assert "cleanup_error" not in primary.__dict__
        await adapter.close()
        assert enrollment.close_calls == (2 if fail_close else 1)
        assert admitted.close_calls == 1
    finally:
        await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("aliased", [False, True])
async def test_unwinding_cancellation_merges_existing_canonical_owners_once(aliased: bool) -> None:
    class EarlierOwner:
        def __init__(self) -> None:
            self.close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("synthetic earlier cleanup failure")

    first = EarlierOwner()
    second = first if aliased else EarlierOwner()
    with pytest.raises(AsyncResourceCleanupError) as first_failure:
        await close_async_resources(first, task_name="mcp-earlier-first", primary_error=None)
    if aliased:
        second_failure = first_failure.value
    else:
        with pytest.raises(AsyncResourceCleanupError) as other_failure:
            await close_async_resources(second, task_name="mcp-earlier-second", primary_error=None)
        second_failure = other_failure.value
    primary = asyncio.CancelledError("original cancellation with earlier owners")
    body_error = ValueError("original failure before cancellation")
    primary.__dict__["body_error"] = body_error
    primary.__dict__["async_cleanup_error"] = first_failure.value
    primary.__dict__["cleanup_error"] = second_failure
    profile_id = uuid4()
    enrollment = _Client(profile_id, fail_once=True)
    admitted = _Client(profile_id)
    adapter = _adapter(enrollment, admitted)
    try:
        with pytest.raises(asyncio.CancelledError) as caught:
            try:
                raise primary
            finally:
                await adapter.close()
        assert caught.value is primary
        assert primary.__dict__.get("body_error") is body_error
        retained = primary.__dict__.get("cleanup_error")
        assert isinstance(retained, AsyncResourceCleanupError)
        assert primary.__dict__.get("async_cleanup_error") is retained
        assert len(retained.resources) == (2 if aliased else 3)
        await retained.retry_cleanup()
        assert first.close_calls == second.close_calls == 2
        assert enrollment.close_calls == 2
        assert admitted.close_calls == 1
        await adapter.close()
        assert enrollment.close_calls == 2
        assert admitted.close_calls == 1
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_new_cancellation_during_body_failure_cleanup_keeps_body_and_direct_retry_owner() -> None:
    async def scenario() -> None:
        profile_id = uuid4()
        enrollment = _Client(profile_id, blocked=True, fail_once=True)
        admitted = _Client(profile_id)
        adapter = _adapter(enrollment, admitted)
        body_error = ValueError("original stdio body failure")

        async def unwinding() -> None:
            try:
                raise body_error
            finally:
                await adapter.close()

        closing = asyncio.create_task(unwinding())
        try:
            assert await asyncio.to_thread(enrollment.started.wait, 5)
            closing.cancel("new caller cancellation during teardown")
            enrollment.release.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await closing
            assert caught.value.args == ("new caller cancellation during teardown",)
            assert caught.value.__dict__.get("body_error") is body_error
            retained = caught.value.__dict__.get("cleanup_error")
            assert isinstance(retained, AsyncResourceCleanupError)
            assert caught.value.__dict__.get("async_cleanup_error") is retained
            assert len(retained.resources) == 1
            assert enrollment.close_calls == admitted.close_calls == 1
            assert not enrollment.closed.is_set()
            assert admitted.closed.is_set()
            await retained.retry_cleanup()
            assert enrollment.closed.is_set()
            assert enrollment.close_calls == 2
            assert admitted.close_calls == 1
            await adapter.close()
            assert enrollment.close_calls == 2
            assert admitted.close_calls == 1
        finally:
            enrollment.release.set()
            if not closing.done():
                with suppress(asyncio.CancelledError, ValueError):
                    await closing
            await adapter.close()

    await asyncio.wait_for(scenario(), timeout=10)


@pytest.mark.asyncio
@pytest.mark.parametrize("new_cancellation", [False, True])
async def test_cancellation_adopts_failed_owner_from_supported_body_error_chain(new_cancellation: bool) -> None:
    class EarlierOwner:
        def __init__(self) -> None:
            self.close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("synthetic body cleanup failure")

    async def scenario() -> None:
        earlier = EarlierOwner()
        body_error = ValueError("original body with an earlier failed owner")
        await close_async_resources(earlier, task_name="mcp-earlier-body-owner", primary_error=body_error)
        assert isinstance(body_error.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        primary = asyncio.CancelledError("original cancellation carrying the body failure")
        primary.__dict__["body_error"] = body_error
        # A repeated reference exercises the supported-chain cycle guard.
        body_error.__dict__["body_error"] = primary
        profile_id = uuid4()
        enrollment = _Client(profile_id, blocked=new_cancellation, fail_once=True)
        admitted = _Client(profile_id)
        adapter = _adapter(enrollment, admitted)

        async def unwinding() -> None:
            try:
                raise primary
            finally:
                await adapter.close()

        closing = asyncio.create_task(unwinding())
        try:
            if new_cancellation:
                assert await asyncio.to_thread(enrollment.started.wait, 5)
                closing.cancel("new cancellation with an earlier body owner")
                enrollment.release.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await closing
            if new_cancellation:
                assert caught.value.args == ("new cancellation with an earlier body owner",)
            else:
                assert caught.value is primary
            assert caught.value.__dict__.get("body_error") is body_error
            retained = caught.value.__dict__.get("cleanup_error")
            assert isinstance(retained, AsyncResourceCleanupError)
            assert caught.value.__dict__.get("async_cleanup_error") is retained
            assert len(retained.resources) == 2
            assert earlier.close_calls == enrollment.close_calls == admitted.close_calls == 1
            await retained.retry_cleanup()
            assert earlier.close_calls == enrollment.close_calls == 2
            assert admitted.close_calls == 1
            await adapter.close()
            assert earlier.close_calls == enrollment.close_calls == 2
            assert admitted.close_calls == 1
        finally:
            enrollment.release.set()
            if not closing.done():
                with suppress(asyncio.CancelledError):
                    await closing
            await adapter.close()

    await asyncio.wait_for(scenario(), timeout=10)
