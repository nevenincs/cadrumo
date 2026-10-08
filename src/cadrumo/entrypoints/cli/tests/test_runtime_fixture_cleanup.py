"""Portable fixture owners retain actual hosts across incomplete native shutdown."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import AbstractContextManager
from pathlib import Path
from threading import Event
from typing import override
from uuid import UUID

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.server import RuntimeListener
from cadrumo.adapters.local_runtime.tests.profile_worker_support import NativeRuntimeFixtureOwner
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CONTROL_NAMESPACE, WRAP_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessScope
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from . import native_api_cli_support

pytestmark = [pytest.mark.hex_entrypoint]


class _Listener:
    storage_identity = "a" * 64

    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.listens = 0
        self.closes = 0
        self.closed = False
        self.error = OSError("synthetic listener release refusal")

    def listen(self) -> None:
        self.listens += 1

    def accept(self, *, timeout: float) -> RuntimeByteChannel:
        raise AssertionError("a draining fixture must never accept a new client")

    def close(self) -> None:
        assert not self.closed, "native listener ownership was released twice"
        self.closes += 1
        if self.closes <= self.failures:
            raise self.error
        self.closed = True


def _terminal_owner(
    *, incomplete: bool = False, listener_failures: int = 0
) -> tuple[NativeRuntimeFixtureOwner, _Listener, Future[None], Event]:
    listener, stop, drained = _Listener(failures=listener_failures), Event(), Event()
    stop.set()
    server = RetainedRuntimeTransportServer(listener, product_version="fixture-cleanup", stop=stop)
    server.DRAIN_SECONDS = 0.01
    pending: Future[None] = Future()
    if incomplete:
        server._requests.add(pending)
        pending.add_done_callback(server._forget_request)
    running: Future[None] = Future()
    try:
        server.serve()
    except BaseException as error:
        running.set_exception(error)
    else:
        running.set_result(None)
    owner = NativeRuntimeFixtureOwner(listener, stop, timeout=0.01, drained=drained)
    owner.server, owner.running = server, running
    return owner, listener, pending, drained


@pytest.mark.asyncio
@pytest.mark.unit
async def test_incomplete_fixture_retry_settles_original_host_before_custody_retirement() -> None:
    owner, listener, pending, drained = _terminal_owner(incomplete=True)
    with pytest.raises(AsyncResourceCleanupError) as caught:
        await close_async_resources(owner, task_name="fixture-cleanup", primary_error=None)
    assert not owner.released and not listener.closed and not drained.is_set()
    assert owner.server is not None and owner.running is None
    assert listener.listens == 1 and listener.closes == 0
    pending.set_result(None)
    await caught.value.retry_cleanup()
    assert owner.released and listener.closed and drained.is_set()
    await caught.value.retry_cleanup()
    assert listener.listens == listener.closes == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fixture_retry_reuses_server_listener_owner_after_failed_native_release() -> None:
    owner, listener, _, drained = _terminal_owner(listener_failures=2)
    with pytest.raises(AsyncResourceCleanupError) as caught:
        await close_async_resources(owner, task_name="fixture-cleanup", primary_error=None)
    assert listener.closes == 2 and not listener.closed and not drained.is_set()
    await caught.value.retry_cleanup()
    assert owner.released and listener.closed and drained.is_set()
    await caught.value.retry_cleanup()
    assert listener.closes == 3 and listener.listens == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellation", [False, True])
@pytest.mark.unit
async def test_body_primary_retains_retryable_fixture_until_actual_drain(cancellation: bool) -> None:
    owner, listener, pending, drained = _terminal_owner(incomplete=True)
    primary = asyncio.CancelledError("synthetic caller cancellation") if cancellation else ValueError("synthetic body")
    with pytest.raises(type(primary)) as caught:
        try:
            raise primary
        finally:
            await close_async_resources(owner, task_name="fixture-cleanup", primary_error=primary)
    assert caught.value is primary
    cleanup = primary.__dict__.get("async_cleanup_error")
    if cancellation:
        cleanup = primary.__dict__.get("cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert not drained.is_set() and not listener.closed
    pending.set_result(None)
    await cleanup.retry_cleanup()
    assert listener.closed and drained.is_set()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_live_serve_timeout_retains_future_and_executor_without_joining() -> None:
    entered, release, stop = Event(), Event(), Event()

    class HeldListener(_Listener):
        @override
        def listen(self) -> None:
            super().listen()
            entered.set()
            assert release.wait(3)

    listener = HeldListener()
    server = RetainedRuntimeTransportServer(listener, product_version="fixture-cleanup", stop=stop)
    owner = NativeRuntimeFixtureOwner(listener, stop, timeout=0.01)
    owner.server = server
    owner.executor = ThreadPoolExecutor(max_workers=1)
    running = owner.executor.submit(server.serve)
    owner.running = running
    try:
        assert entered.wait(3)
        with pytest.raises(AsyncResourceCleanupError) as caught:
            await close_async_resources(owner, task_name="fixture-cleanup", primary_error=None)
        assert owner.running is running and owner.executor is not None
        assert not running.done() and not listener.closed and not owner.released
    finally:
        release.set()
        await asyncio.to_thread(running.result, timeout=3)
    await caught.value.retry_cleanup()
    assert owner.released and listener.closed and owner.executor is None
    assert listener.closes == listener.listens == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_live_auxiliary_approval_keeps_fixture_and_retirement_owned_until_settlement() -> None:
    owner, listener, _, drained = _terminal_owner()
    entered, release = Event(), Event()
    retired: list[bool] = []

    class Retirement:
        async def close(self) -> None:
            retired.append(True)

    def approve() -> None:
        entered.set()
        assert release.wait(3), "approval was not released"

    owner.after_drain = Retirement()
    owner.executor = ThreadPoolExecutor(max_workers=1)
    approval = owner.executor.submit(approve)
    owner.auxiliary.append(approval)
    try:
        assert entered.wait(3)
        with pytest.raises(AsyncResourceCleanupError) as caught:
            await close_async_resources(owner, task_name="fixture-approval-close", primary_error=None)
        assert owner.auxiliary == [approval] and not approval.done()
        assert owner.executor is not None and not owner.released
        assert not drained.is_set() and not retired
    finally:
        release.set()
        await asyncio.to_thread(approval.result, timeout=3)
        await owner.close()
    await caught.value.retry_cleanup()
    assert owner.released and owner.auxiliary == [] and owner.executor is None
    assert drained.is_set() and retired == [True]
    assert listener.closes == listener.listens == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellation", [False, True])
@pytest.mark.unit
async def test_failed_auxiliary_approval_preserves_primary_and_retries_native_owner_once(cancellation: bool) -> None:
    owner, listener, _, drained = _terminal_owner()
    primary = (
        asyncio.CancelledError("synthetic approval cancellation") if cancellation else ValueError("synthetic approval")
    )
    attempts: list[int] = []

    class Release:
        async def close(self) -> None:
            attempts.append(len(attempts) + 1)
            if len(attempts) <= 3:
                raise OSError("synthetic native approval release failure")

    resource = Release()

    def approve() -> None:
        try:
            raise primary
        finally:
            asyncio.run(close_async_resources(resource, task_name="approval-native-close", primary_error=primary))

    owner.executor = ThreadPoolExecutor(max_workers=1)
    approval = owner.executor.submit(approve)
    owner.auxiliary.append(approval)
    try:
        with pytest.raises(type(primary)) as original:
            await asyncio.to_thread(approval.result, timeout=3)
        assert original.value is primary and attempts == [1]
        with pytest.raises(type(primary)) as caught:
            await owner.close()
        assert caught.value is primary and attempts == [1, 2]
        assert owner.auxiliary == [] and not owner.released and not drained.is_set()
        cleanup = primary.__dict__.get("async_cleanup_error")
        assert isinstance(cleanup, AsyncResourceCleanupError)
        with pytest.raises(AsyncResourceCleanupError) as persistent:
            await cleanup.retry_cleanup()
        assert attempts == [1, 2, 3] and not owner.released
        await persistent.value.retry_cleanup()
        assert attempts == [1, 2, 3, 4]
        assert owner.released and drained.is_set() and listener.closed
        await cleanup.retry_cleanup()
        await owner.close()
        assert attempts == [1, 2, 3, 4] and listener.closes == 1
    finally:
        if owner.executor is not None:
            owner.executor.shutdown(wait=False, cancel_futures=False)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_auxiliary_primary_survives_a_later_terminal_server_failure() -> None:
    owner, listener, _, drained = _terminal_owner()
    approval_error = ValueError("synthetic approval failure")
    server_error = OSError("synthetic server failure")
    approval: Future[None] = Future()
    approval.set_exception(approval_error)
    running: Future[None] = Future()
    running.set_exception(server_error)
    owner.auxiliary.append(approval)
    owner.running = running
    with pytest.raises(ValueError) as caught:
        await owner.close()
    assert caught.value is approval_error
    assert approval_error.__dict__.get("terminal_errors") == (server_error,)
    assert owner.released and owner.running is None and owner.auxiliary == []
    assert drained.is_set() and listener.closed and listener.closes == 1
    await owner.close()
    assert listener.closes == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
@pytest.mark.unit
async def test_auxiliary_timeout_race_uses_the_actual_completed_outcome(failed: bool) -> None:
    owner, listener, _, drained = _terminal_owner()
    primary = ValueError("synthetic terminal approval failure")

    class CompletingFuture(Future[None]):
        @override
        def result(self, timeout: float | None = None) -> None:
            if not self.done():
                if failed:
                    self.set_exception(primary)
                else:
                    self.set_result(None)
                raise TimeoutError("synthetic wait expired immediately before completion")
            return super().result(timeout=timeout)

    approval = CompletingFuture()
    owner.auxiliary.append(approval)
    if failed:
        with pytest.raises(ValueError) as caught:
            await owner.close()
        assert caught.value is primary
    else:
        await owner.close()
    assert owner.released and owner.auxiliary == [] and approval.done()
    assert listener.closed and listener.closes == 1 and drained.is_set()
    await owner.close()
    assert listener.closes == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_contained_host_refusal_remains_exact_after_resource_release() -> None:
    owner, listener, _, drained = _terminal_owner()
    assert owner.server is not None
    primary = RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    owner.server._failed.set()
    running: Future[None] = Future()
    running.set_exception(primary)
    owner.running = running
    with pytest.raises(RuntimeRefusalError) as caught:
        await owner.close()
    assert caught.value is primary
    assert owner.released and listener.closed and drained.is_set()
    await owner.close()
    assert listener.closes == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_direct_close_cancellation_retains_live_serve_future_for_retry() -> None:
    entered, release, stop = Event(), Event(), Event()

    class HeldListener(_Listener):
        @override
        def listen(self) -> None:
            super().listen()
            entered.set()
            assert release.wait(3)

    listener = HeldListener()
    server = RetainedRuntimeTransportServer(listener, product_version="fixture-cleanup", stop=stop)
    owner = NativeRuntimeFixtureOwner(listener, stop, timeout=0.02)
    owner.server = server
    owner.executor = ThreadPoolExecutor(max_workers=1)
    running = owner.executor.submit(server.serve)
    owner.running = running
    try:
        assert entered.wait(3)
        closing = asyncio.create_task(owner.close())
        await asyncio.sleep(0)
        closing.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await asyncio.wait_for(closing, timeout=1)
        assert owner.running is running and not running.done()
        assert not owner.released and not listener.closed
        cleanup = caught.value.__dict__.get("async_cleanup_error")
        assert isinstance(cleanup, AsyncResourceCleanupError)
    finally:
        release.set()
        await asyncio.to_thread(running.result, timeout=3)
    await cleanup.retry_cleanup()
    assert owner.released and listener.closed and listener.closes == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_direct_serve_primary_retains_fixture_when_later_listener_release_fails() -> None:
    primary = OSError("synthetic serve body failure")
    stop, drained = Event(), Event()

    class RefusingListener(_Listener):
        @override
        def listen(self) -> None:
            super().listen()
            raise primary

    listener = RefusingListener(failures=2)
    server = RetainedRuntimeTransportServer(listener, product_version="fixture-cleanup", stop=stop)
    with pytest.raises(OSError) as serve_error:
        server.serve()
    assert serve_error.value is primary and listener.closes == 1
    running: Future[None] = Future()
    running.set_exception(primary)
    owner = NativeRuntimeFixtureOwner(listener, stop, timeout=0.1, drained=drained)
    owner.server, owner.running = server, running
    with pytest.raises(OSError) as caught:
        await owner.close()
    assert caught.value is primary
    assert listener.closes == 2 and not listener.closed and not drained.is_set()
    assert owner.server is server and not owner.released
    cleanup = primary.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    await cleanup.retry_cleanup()
    assert owner.released and listener.closed and drained.is_set()
    assert owner.server is None and listener.closes == 3
    await cleanup.retry_cleanup()
    assert listener.closes == 3 and listener.listens == 1


def _api_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, incomplete: bool
) -> tuple[
    AbstractContextManager[native_api_cli_support.NativeApiCliSession[None]], MemoryNativePort, _Listener, Future[None]
]:
    listener, pending = _Listener(), Future[None]()

    class ShortOwner(NativeRuntimeFixtureOwner):
        @override
        def __init__(
            self, endpoint: RuntimeListener, stop: Event, *, timeout: float, drained: Event | None = None
        ) -> None:
            super().__init__(endpoint, stop, timeout=0.01, drained=drained)

    class ControlledServer(RetainedRuntimeTransportServer):
        DRAIN_SECONDS = 0.01

        @override
        def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
            if incomplete:
                self._requests.add(pending)
                pending.add_done_callback(self._forget_request)
            assert self.stop.wait(3), "fixture did not request shutdown"

    def endpoint(*, storage_root: Path) -> _Listener:
        assert storage_root.is_dir()
        return listener

    def scope(_client_id: UUID) -> AccessScope:
        return AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        )

    monkeypatch.setattr(native_api_cli_support, "owner_id", lambda: "synthetic-owner")
    monkeypatch.setattr(native_api_cli_support, "WindowsRuntimeEndpoint", endpoint)
    monkeypatch.setattr(native_api_cli_support, "PosixRuntimeEndpoint", endpoint)
    monkeypatch.setattr(native_api_cli_support, "RetainedRuntimeTransportServer", ControlledServer)
    monkeypatch.setattr(native_api_cli_support, "NativeRuntimeFixtureOwner", ShortOwner)
    native = MemoryNativePort()
    context = native_api_cli_support.native_api_cli_session(
        tmp_path,
        scope_for_destination=scope,
        prepare_profile=lambda _profile_id, _root: None,
        server_native_store=native,
    )
    return context, native, listener, pending


@pytest.mark.usefixtures("authority_operation")
@pytest.mark.parametrize("retirement_failure", [False, True])
@pytest.mark.integration
def test_native_api_custody_retirement_remains_owned_after_incomplete_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, retirement_failure: bool
) -> None:
    context, native, listener, pending = _api_context(monkeypatch, tmp_path, incomplete=True)
    owned: set[tuple[str, str]] = set()
    with pytest.raises(AsyncResourceCleanupError) as caught, context:
        owned = {key for key in native.items if key[0] in {CONTROL_NAMESPACE, WRAP_NAMESPACE}}
        assert {namespace for namespace, _ in owned} == {CONTROL_NAMESPACE, WRAP_NAMESPACE}
        native.replace(CONTROL_NAMESPACE, "unrelated-control", SecretBytes(b"unrelated synthetic record"))
    assert owned <= native.items.keys() and not listener.closed
    pending.set_result(None)
    cleanup = caught.value
    if retirement_failure:
        native.fail_delete = True
        with pytest.raises(AsyncResourceCleanupError) as failed_retirement:
            asyncio.run(cleanup.retry_cleanup())
        assert owned <= native.items.keys() and listener.closed
        cleanup = failed_retirement.value
        native.fail_delete = False
    asyncio.run(cleanup.retry_cleanup())
    assert listener.closed
    assert not owned.intersection(native.items)
    assert native.read(CONTROL_NAMESPACE, "unrelated-control") is not None
    asyncio.run(cleanup.retry_cleanup())
    assert listener.closes == 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("authority_operation")
@pytest.mark.integration
async def test_native_api_fixture_cleanup_works_inside_sdk_event_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context, native, listener, _ = _api_context(monkeypatch, tmp_path, incomplete=False)
    with context:
        assert native.items
    assert listener.closed and not native.items
