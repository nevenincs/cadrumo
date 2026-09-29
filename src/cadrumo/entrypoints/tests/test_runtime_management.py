"""Shared status composition never invokes manager lifecycle methods."""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import override
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
)
from cadrumo.application.runtime.management_status import RuntimeListenerState, RuntimeManagerAvailability
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.runtime_management import inspect_installed_runtime_management, inspect_runtime_management

pytestmark = [pytest.mark.hex_entrypoint]

_IDENTITY = "c" * 64


class _Endpoint:
    storage_identity = _IDENTITY

    def connect(self, *, timeout: float) -> RuntimeByteChannel:
        pytest.fail("composed status used an unconfigured native connection")


class _Manager:
    def __init__(self, facts: RuntimeManagerInspection) -> None:
        self.facts = facts
        self.inspections = 0
        self.starts = 0
        self.stops = 0

    async def inspect(self) -> RuntimeManagerInspection:
        self.inspections += 1
        return self.facts

    async def start(self) -> None:
        self.starts += 1
        pytest.fail("status started a service")

    async def stop(self) -> None:
        self.stops += 1
        pytest.fail("status stopped a service")


class _RefusingManager(_Manager):
    @override
    async def inspect(self) -> RuntimeManagerInspection:
        raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)


class _TypedRefusingManager(_Manager):
    def __init__(self, facts: RuntimeManagerInspection, reason: RuntimeRefusalCode) -> None:
        super().__init__(facts)
        self.reason = reason

    @override
    async def inspect(self) -> RuntimeManagerInspection:
        raise RuntimeRefusalError(self.reason)


class _SlowManager(_Manager):
    @override
    async def inspect(self) -> RuntimeManagerInspection:
        await asyncio.sleep(0.1)
        return self.facts


@pytest.mark.unit
def test_management_snapshot_is_passive_and_separates_autostart(monkeypatch: pytest.MonkeyPatch) -> None:
    facts = RuntimeManagerInspection(
        kind=RuntimeManagerKind.WINDOWS_TASK,
        available=True,
        provisioned=True,
        binding_matches=True,
        login_autostart=False,
        process_state=RuntimeManagerProcessState.RUNNING,
    )
    manager = _Manager(facts)
    monkeypatch.setattr(
        "cadrumo.entrypoints.runtime_management.probe_runtime_listener",
        lambda *_args, **_kwargs: RuntimeListenerState.READY,
    )
    snapshot = asyncio.run(
        inspect_runtime_management(
            endpoint=_Endpoint(),
            expected=RuntimeClientHello(product_version="test", storage_identity=_IDENTITY),
            manager=manager,
            manager_if_absent=RuntimeManagerAvailability.UNAVAILABLE,
        )
    )
    assert snapshot.listener is RuntimeListenerState.READY
    assert snapshot.manager_availability is RuntimeManagerAvailability.AVAILABLE
    assert snapshot.manager is not None and not snapshot.manager.login_autostart
    assert manager.inspections == 1 and manager.starts == manager.stops == 0


@pytest.mark.unit
def test_unsupported_manager_does_not_prevent_passive_listener_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cadrumo.entrypoints.runtime_management.probe_runtime_listener",
        lambda *_args, **_kwargs: RuntimeListenerState.UNAVAILABLE,
    )
    snapshot = asyncio.run(
        inspect_runtime_management(
            endpoint=_Endpoint(),
            expected=RuntimeClientHello(product_version="test", storage_identity=_IDENTITY),
            manager=None,
            manager_if_absent=RuntimeManagerAvailability.UNSUPPORTED,
        )
    )
    assert snapshot.listener is RuntimeListenerState.UNAVAILABLE
    assert snapshot.manager_availability is RuntimeManagerAvailability.UNSUPPORTED
    assert snapshot.manager is None


@pytest.mark.unit
def test_manager_refusal_does_not_downgrade_verified_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cadrumo.entrypoints.runtime_management.probe_runtime_listener",
        lambda *_args, **_kwargs: RuntimeListenerState.READY,
    )
    manager = _RefusingManager(
        RuntimeManagerInspection(
            kind=RuntimeManagerKind.WINDOWS_TASK,
            available=True,
            provisioned=True,
            binding_matches=True,
            login_autostart=False,
            process_state=RuntimeManagerProcessState.UNKNOWN,
        )
    )
    snapshot = asyncio.run(
        inspect_runtime_management(
            endpoint=_Endpoint(),
            expected=RuntimeClientHello(product_version="test", storage_identity=_IDENTITY),
            manager=manager,
            manager_if_absent=RuntimeManagerAvailability.UNAVAILABLE,
        )
    )
    assert snapshot.manager_availability is RuntimeManagerAvailability.REFUSED
    assert snapshot.manager is None
    assert snapshot.listener is RuntimeListenerState.READY


@pytest.mark.unit
@pytest.mark.parametrize(
    ("reason", "availability"),
    (
        (RuntimeRefusalCode.UNAVAILABLE, RuntimeManagerAvailability.UNAVAILABLE),
        (RuntimeRefusalCode.DEADLINE_EXCEEDED, RuntimeManagerAvailability.UNKNOWN),
        (RuntimeRefusalCode.INVALID_FRAME, RuntimeManagerAvailability.REFUSED),
    ),
)
def test_manager_typed_refusals_keep_unavailability_timeout_and_malformed_output_distinct(
    monkeypatch: pytest.MonkeyPatch, reason: RuntimeRefusalCode, availability: RuntimeManagerAvailability
) -> None:
    monkeypatch.setattr(
        "cadrumo.entrypoints.runtime_management.probe_runtime_listener",
        lambda *_args, **_kwargs: RuntimeListenerState.READY,
    )
    facts = RuntimeManagerInspection(
        kind=RuntimeManagerKind.LINUX_USER_SERVICE,
        available=True,
        provisioned=False,
        binding_matches=False,
        login_autostart=False,
        process_state=RuntimeManagerProcessState.UNKNOWN,
    )
    snapshot = asyncio.run(
        inspect_runtime_management(
            endpoint=_Endpoint(),
            expected=RuntimeClientHello(product_version="test", storage_identity=_IDENTITY),
            manager=_TypedRefusingManager(facts, reason),
            manager_if_absent=RuntimeManagerAvailability.UNAVAILABLE,
        )
    )
    assert snapshot.manager_availability is availability
    assert snapshot.manager is None
    assert snapshot.listener is RuntimeListenerState.READY


@pytest.mark.unit
def test_manager_construction_refusal_does_not_skip_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cadrumo.entrypoints.runtime_management.probe_runtime_listener",
        lambda *_args, **_kwargs: RuntimeListenerState.READY,
    )
    snapshot = asyncio.run(
        inspect_runtime_management(
            endpoint=_Endpoint(),
            expected=RuntimeClientHello(product_version="test", storage_identity=_IDENTITY),
            manager=None,
            manager_if_absent=RuntimeManagerAvailability.REFUSED,
        )
    )
    assert snapshot.manager_availability is RuntimeManagerAvailability.REFUSED
    assert snapshot.listener is RuntimeListenerState.READY


@pytest.mark.unit
def test_one_deadline_does_not_start_listener_probe_after_slow_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_probe(*_args: object, **_kwargs: object) -> RuntimeListenerState:
        pytest.fail("listener probe started after the shared status deadline")

    monkeypatch.setattr("cadrumo.entrypoints.runtime_management.probe_runtime_listener", unexpected_probe)
    manager = _SlowManager(
        RuntimeManagerInspection(
            kind=RuntimeManagerKind.WINDOWS_TASK,
            available=True,
            provisioned=True,
            binding_matches=True,
            login_autostart=False,
            process_state=RuntimeManagerProcessState.UNKNOWN,
        )
    )
    snapshot = asyncio.run(
        inspect_runtime_management(
            endpoint=_Endpoint(),
            expected=RuntimeClientHello(product_version="test", storage_identity=_IDENTITY),
            manager=manager,
            manager_if_absent=RuntimeManagerAvailability.UNAVAILABLE,
            timeout=0.01,
        )
    )
    assert snapshot.manager_availability is RuntimeManagerAvailability.UNKNOWN
    assert snapshot.listener is RuntimeListenerState.UNKNOWN


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancelled_probe_waits_for_channel_owner_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    started, release, closed = Event(), Event(), Event()

    def held_probe(*_args: object, **_kwargs: object) -> RuntimeListenerState:
        started.set()
        assert release.wait(2)
        closed.set()
        return RuntimeListenerState.READY

    monkeypatch.setattr("cadrumo.entrypoints.runtime_management.probe_runtime_listener", held_probe)
    task = asyncio.create_task(
        inspect_runtime_management(
            endpoint=_Endpoint(),
            expected=RuntimeClientHello(product_version="test", storage_identity=_IDENTITY),
            manager=None,
            manager_if_absent=RuntimeManagerAvailability.UNAVAILABLE,
        )
    )
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done() and not closed.is_set()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows owner-only pipes")
def test_installed_snapshot_passively_observes_existing_runtime(tmp_path: Path) -> None:
    root = tmp_path / f"management-{uuid4()}"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    with override_settings(cadrumo_local_storage_root=root):
        absent = asyncio.run(inspect_installed_runtime_management(timeout=2))
        assert absent.listener is RuntimeListenerState.UNAVAILABLE
        stop = Event()
        server = RuntimeTransportServer(endpoint, product_version=version("cadrumo"), stop=stop)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                present = asyncio.run(inspect_installed_runtime_management(timeout=3))
                assert present.listener is RuntimeListenerState.READY
                assert present.manager_availability in {
                    RuntimeManagerAvailability.AVAILABLE,
                    RuntimeManagerAvailability.UNAVAILABLE,
                }
                assert not stop.is_set()
            finally:
                stop.set()
                running.result(timeout=10)
                endpoint.close()
