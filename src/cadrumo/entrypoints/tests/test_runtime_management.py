"""Shared status composition never invokes manager lifecycle methods."""

from __future__ import annotations

import asyncio
import json
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Literal, cast, override
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
)
from cadrumo.application.runtime.management_status import RuntimeListenerState, RuntimeManagerAvailability
from cadrumo.application.runtime.owner_control import RuntimeStopAccepted, RuntimeStopPreview
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.entrypoints.runtime_management import (
    RuntimeStopConsent,
    inspect_installed_runtime_management,
    inspect_runtime_management,
    preview_installed_runtime_stop,
)

from ...application.runtime.management_status import RuntimeManagementSnapshot
from ...application.runtime.owner_control import RuntimeStopPreviewRequest
from .. import runtime_management

pytestmark = [pytest.mark.hex_entrypoint]

_IDENTITY = "c" * 64


class StopChannel:
    """Script the public framed owner-control port and real release failures."""

    def __init__(self, *, failures: int, outcome: Literal["accepted", "lost", "refused"] = "accepted") -> None:
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
        self.boot = uuid4()
        self.connection_id = uuid4()
        self.inbound = bytearray()
        self.writes: list[bytes] = []
        self.close_calls = 0
        self.failures = failures
        self.outcome = outcome
        self.confirmations = 0
        self.confirming = Event()
        self.continue_reply = Event()
        self.continue_reply.set()
        self._confirm_reply = False
        self._queue(RuntimeServerHello(product_version="stop-test", storage_identity=_IDENTITY, boot_id=self.boot))

    def _queue(self, document: RuntimeServerHello) -> None:
        payload = canonical_json_bytes(document.model_dump(mode="json"))
        self.inbound.extend(b"J" + struct.pack("!I", len(payload)) + payload)

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        if self._confirm_reply:
            self.confirming.set()
            assert self.continue_reply.wait(max(0.0, deadline - time.monotonic()))
            self._confirm_reply = False
            if self.outcome == "lost":
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        assert deadline > time.monotonic()
        if len(self.inbound) < count:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        result = bytes(self.inbound[:count])
        del self.inbound[:count]
        return result

    def read_ready(self) -> bool:
        return bool(self.inbound)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > time.monotonic()
        self.writes.append(bytes(payload))
        assert payload[:1] == b"J"
        request = json.loads(payload[5:])
        if request.get("action") != "runtime_stop_confirm":
            return
        self.confirmations += 1
        self._confirm_reply = True
        reply = {
            "kind": "access_refusal" if self.outcome == "refused" else "runtime_stop_accepted",
            "request_id": request["request_id"],
            "runtime_boot_id": str(self.boot),
            "connection_id": str(self.connection_id),
        }
        if self.outcome == "refused":
            reply["code"] = RuntimeRefusalCode.PEER_UNTRUSTED.value
        else:
            reply["scope"] = "all_profiles_and_work"
        body = canonical_json_bytes(reply)
        self.inbound.extend(b"J" + struct.pack("!I", len(body)) + body)

    def close(self) -> None:
        self.close_calls += 1
        if self.close_calls <= self.failures:
            raise OSError("synthetic private release detail")


class StopEndpoint:
    """Native endpoint release port, independent of its connection."""

    storage_identity = _IDENTITY

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        if self.close_calls <= self.failures:
            raise OSError("synthetic private endpoint detail")


class StopFixture:
    """Exercise actual verified framing and consent with isolated native ports."""

    def __init__(
        self,
        *,
        channel_failures: int = 0,
        endpoint_failures: int = 0,
        outcome: Literal["accepted", "lost", "refused"] = "accepted",
    ) -> None:
        self.channel = StopChannel(failures=channel_failures, outcome=outcome)
        self.endpoint = StopEndpoint(endpoint_failures)
        self.connection = VerifiedRuntimeConnection(
            self.channel,
            expected=RuntimeClientHello(product_version="stop-test", storage_identity=_IDENTITY),
            deadline=time.monotonic() + 5,
        )
        self.preview = RuntimeStopPreview(
            request_id=uuid4(),
            runtime_boot_id=self.channel.boot,
            connection_id=self.channel.connection_id,
            preview_id=uuid4(),
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
        # The fixture substitutes only endpoint release, not consent/framing.
        self.consent = RuntimeStopConsent(
            endpoint=cast("WindowsRuntimeEndpoint", self.endpoint), connection=self.connection, preview=self.preview
        )

    async def open(self) -> RuntimeStopConsent:
        """Provide the public preview seam to owning frontend tests."""
        return self.consent


class _Endpoint:
    storage_identity = _IDENTITY

    def connect(self, *, timeout: float) -> RuntimeByteChannel:
        pytest.fail("composed status used an unconfigured native connection")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_ack_survives_failed_release_and_retries_only_native_owners() -> None:
    fixture = StopFixture(channel_failures=2, endpoint_failures=1)
    accepted = await fixture.consent.confirm()
    assert isinstance(accepted, RuntimeStopAccepted)
    assert fixture.consent.accepted is accepted
    assert not fixture.consent.uncertain
    with pytest.raises(AsyncResourceCleanupError) as failed:
        await fixture.consent.release()
    assert fixture.channel.close_calls == fixture.endpoint.close_calls == 1
    with pytest.raises(AsyncResourceCleanupError) as retry_failed:
        await failed.value.retry_cleanup()
    assert fixture.channel.close_calls == fixture.endpoint.close_calls == 2
    await retry_failed.value.retry_cleanup()
    assert fixture.channel.close_calls == 3
    assert fixture.endpoint.close_calls == 2
    assert fixture.consent.released
    await fixture.consent.release()
    with pytest.raises(RuntimeRefusalError) as replay:
        await fixture.consent.confirm()
    assert replay.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert fixture.channel.confirmations == 1
    assert fixture.channel.close_calls == 3 and fixture.endpoint.close_calls == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_lost_ack_retains_same_native_failure_owner_without_replay() -> None:
    fixture = StopFixture(channel_failures=2, outcome="lost")
    with pytest.raises(RuntimeRefusalError) as refused:
        await fixture.consent.confirm()
    primary = refused.value
    assert primary.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert fixture.consent.uncertain and fixture.consent.accepted is None
    assert fixture.channel.close_calls == 1
    await fixture.consent.release(primary_error=primary)
    assert fixture.channel.close_calls == 2
    cleanup = primary.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    await cleanup.retry_cleanup()
    assert fixture.channel.close_calls == 3 and fixture.endpoint.close_calls == 1
    assert fixture.consent.released
    with pytest.raises(RuntimeRefusalError):
        await fixture.consent.confirm()
    assert fixture.channel.confirmations == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_cancellation_retains_ack_before_failed_release() -> None:
    fixture = StopFixture(channel_failures=1)
    fixture.channel.continue_reply.clear()
    confirming = asyncio.create_task(fixture.consent.confirm())
    try:
        assert await asyncio.to_thread(fixture.channel.confirming.wait, 2)
        confirming.cancel("original-stop-cancellation")
        fixture.channel.continue_reply.set()
        with pytest.raises(asyncio.CancelledError) as cancelled:
            await confirming
        primary = cancelled.value
        assert primary.args == ("original-stop-cancellation",)
        assert fixture.consent.accepted is not None and not fixture.consent.uncertain
        with pytest.raises(asyncio.CancelledError) as releasing:
            await fixture.consent.release(primary_error=primary)
        assert releasing.value is primary
        cleanup = primary.__dict__.get("cleanup_error")
        assert isinstance(cleanup, AsyncResourceCleanupError)
        assert fixture.endpoint.close_calls == fixture.channel.close_calls == 1
        await cleanup.retry_cleanup()
        assert fixture.consent.released and fixture.channel.close_calls == 2
        assert fixture.endpoint.close_calls == 1 and fixture.channel.confirmations == 1
    finally:
        fixture.channel.continue_reply.set()
        if not confirming.done():
            await confirming


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_explicit_refusal_is_not_ambiguous_and_confirmation_is_single_use() -> None:
    fixture = StopFixture(outcome="refused")
    with pytest.raises(RuntimeRefusalError) as refused:
        await fixture.consent.confirm()
    assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert fixture.consent.confirmation_started and not fixture.consent.uncertain
    assert fixture.consent.accepted is None
    await fixture.consent.release(primary_error=refused.value)
    with pytest.raises(RuntimeRefusalError):
        await fixture.consent.confirm()
    assert fixture.channel.confirmations == 1 and fixture.consent.released


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_preview_failure_preserves_primary_and_exact_release_owners(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = StopFixture(channel_failures=2, endpoint_failures=1)
    # Preview is intentionally unavailable on this channel; actual framing
    # rejects the empty reply and retains its failed native release owner.
    monkeypatch.setattr("cadrumo.entrypoints.runtime_management.effective_storage_root", lambda: tmp_path)
    monkeypatch.setattr("cadrumo.entrypoints.runtime_management.version", lambda _name: "stop-test")
    monkeypatch.setattr(
        "cadrumo.entrypoints.runtime_management.WindowsRuntimeEndpoint", lambda **_kwargs: fixture.endpoint
    )
    monkeypatch.setattr(
        "cadrumo.entrypoints.runtime_management.PosixRuntimeEndpoint", lambda **_kwargs: fixture.endpoint
    )

    async def opened(*_args: object, **_kwargs: object) -> VerifiedRuntimeConnection:
        return fixture.connection

    monkeypatch.setattr("cadrumo.entrypoints.runtime_management.RuntimeLaunchDoor.open", opened)
    with pytest.raises(RuntimeRefusalError) as failed:
        await preview_installed_runtime_stop()
    primary = failed.value
    assert primary.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    cleanup = primary.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert fixture.channel.close_calls == 2 and fixture.endpoint.close_calls == 1
    await cleanup.retry_cleanup()
    assert fixture.channel.close_calls == 3 and fixture.endpoint.close_calls == 2
    assert fixture.channel.confirmations == 0


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


def _management_facts() -> RuntimeManagerInspection:
    return RuntimeManagerInspection(
        kind=RuntimeManagerKind.LINUX_USER_SERVICE,
        available=True,
        provisioned=True,
        binding_matches=True,
        login_autostart=False,
        process_state=RuntimeManagerProcessState.RUNNING,
    )


class _ComposedEndpoint:
    storage_identity = _IDENTITY

    def __init__(self, events: list[tuple[object, ...]]) -> None:
        self.events = events

    def close(self) -> None:
        self.events.append(("endpoint.close",))


class _ComposedManager(_Manager):
    def __init__(self, events: list[tuple[object, ...]]) -> None:
        super().__init__(_management_facts())
        self.events = events

    @override
    async def inspect(self) -> RuntimeManagerInspection:
        self.events.append(("manager.inspect",))
        return self.facts

    @override
    async def start(self) -> None:
        pytest.fail("the installed management composition launched a user service")

    @override
    async def stop(self) -> None:
        pytest.fail("the installed management composition stopped a user service")

    async def configure(self, *, login_autostart: bool) -> RuntimeManagerInspection:
        self.events.append(("manager.configure", login_autostart))
        return self.facts


class _ComposedConnection:
    def __init__(self, events: list[tuple[object, ...]]) -> None:
        self.events = events
        self.close_calls = 0

    def owner_control(self, request: RuntimeStopPreviewRequest, *, deadline: float) -> RuntimeStopPreview:
        assert deadline > time.monotonic()
        self.events.append(("owner_control", request.request_id))
        return RuntimeStopPreview(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            preview_id=uuid4(),
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )

    def close(self) -> None:
        self.close_calls += 1
        self.events.append(("connection.close",))


def _install_management_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    events: list[tuple[object, ...]],
    *,
    platform: str = "linux",
) -> _ComposedEndpoint:
    endpoint = _ComposedEndpoint(events)
    monkeypatch.setattr(runtime_management, "sys", SimpleNamespace(platform=platform))

    def storage_root() -> Path:
        events.append(("storage_root",))
        return tmp_path

    def package_version(package_name: str) -> str:
        events.append(("version", package_name))
        return "management-test"

    def windows_endpoint(*, storage_root: Path) -> _ComposedEndpoint:
        events.append(("windows_endpoint", storage_root))
        return endpoint

    def posix_endpoint(*, storage_root: Path, create_namespace: bool) -> _ComposedEndpoint:
        events.append(("posix_endpoint", storage_root, create_namespace))
        return endpoint

    monkeypatch.setattr(runtime_management, "effective_storage_root", storage_root)
    monkeypatch.setattr(runtime_management, "version", package_version)
    monkeypatch.setattr(runtime_management, "WindowsRuntimeEndpoint", windows_endpoint)
    monkeypatch.setattr(runtime_management, "PosixRuntimeEndpoint", posix_endpoint)
    return endpoint


def _install_management_manager(
    monkeypatch: pytest.MonkeyPatch,
    events: list[tuple[object, ...]],
    manager: _ComposedManager,
) -> None:
    def manager_factory(*, root: Path, endpoint: object, product_version: str) -> _ComposedManager:
        events.append(("manager_factory", root, endpoint, product_version))
        return manager

    monkeypatch.setattr(runtime_management, "installed_runtime_manager", manager_factory)


def _install_fake_launch_door(
    monkeypatch: pytest.MonkeyPatch,
    events: list[tuple[object, ...]],
    connection: _ComposedConnection,
) -> None:
    class FakeLaunchDoor:
        def __init__(self, endpoint: object, *, expected: RuntimeClientHello, manager: object = None) -> None:
            events.append(("door.construct", endpoint, expected, manager))

        async def open(self, *, timeout: float = 10) -> VerifiedRuntimeConnection:
            events.append(("door.open", timeout))
            return cast("VerifiedRuntimeConnection", connection)

    monkeypatch.setattr(runtime_management, "RuntimeLaunchDoor", FakeLaunchDoor)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("platform", "expected_constructor"),
    (
        ("win32", ("windows_endpoint",)),
        ("linux", ("posix_endpoint",)),
    ),
)
def test_installed_management_endpoint_preserves_platform_constructor_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, expected_constructor: tuple[str, ...]
) -> None:
    events: list[tuple[object, ...]] = []
    endpoint = _ComposedEndpoint(events)
    monkeypatch.setattr(runtime_management, "sys", SimpleNamespace(platform=platform))

    def windows_endpoint(*, storage_root: Path) -> _ComposedEndpoint:
        events.append(("windows_endpoint", storage_root))
        return endpoint

    def posix_endpoint(*, storage_root: Path, create_namespace: bool) -> _ComposedEndpoint:
        events.append(("posix_endpoint", storage_root, create_namespace))
        return endpoint

    monkeypatch.setattr(runtime_management, "WindowsRuntimeEndpoint", windows_endpoint)
    monkeypatch.setattr(runtime_management, "PosixRuntimeEndpoint", posix_endpoint)

    actual = runtime_management._installed_management_endpoint(storage_root=tmp_path)

    assert actual is endpoint
    if expected_constructor == ("windows_endpoint",):
        assert events == [("windows_endpoint", tmp_path)]
    else:
        assert events == [("posix_endpoint", tmp_path, False)]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_installed_inspection_composes_passive_endpoint_after_admission(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[tuple[object, ...]] = []
    endpoint = _install_management_environment(monkeypatch, tmp_path, events)
    manager = _ComposedManager(events)
    _install_management_manager(monkeypatch, events, manager)
    snapshot = RuntimeManagementSnapshot(
        listener=RuntimeListenerState.READY,
        manager_availability=RuntimeManagerAvailability.UNAVAILABLE,
    )

    async def inspect_composed(
        *,
        endpoint: object,
        expected: RuntimeClientHello,
        manager: object,
        manager_if_absent: RuntimeManagerAvailability,
        timeout: float = 3,
    ) -> RuntimeManagementSnapshot:
        events.append(("inspect", endpoint, expected, manager, manager_if_absent, timeout))
        return snapshot

    monkeypatch.setattr(runtime_management, "inspect_runtime_management", inspect_composed)

    actual = await runtime_management.inspect_installed_runtime_management()

    assert actual is snapshot
    assert events[:4] == [
        ("storage_root",),
        ("version", "cadrumo"),
        ("posix_endpoint", tmp_path, False),
        ("manager_factory", tmp_path, endpoint, "management-test"),
    ]
    inspected = events[4]
    assert inspected[0] == "inspect"
    assert inspected[1] is endpoint
    expected = cast("RuntimeClientHello", inspected[2])
    assert expected.product_version == "management-test" and expected.storage_identity == _IDENTITY
    assert inspected[3] is manager
    assert inspected[4:] == (RuntimeManagerAvailability.UNAVAILABLE, 3)
    assert events[5:] == [("endpoint.close",)]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_installed_start_wires_manager_and_closes_probe_before_endpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[tuple[object, ...]] = []
    endpoint = _install_management_environment(monkeypatch, tmp_path, events)
    manager = _ComposedManager(events)
    _install_management_manager(monkeypatch, events, manager)
    connection = _ComposedConnection(events)
    _install_fake_launch_door(monkeypatch, events, connection)
    snapshot = RuntimeManagementSnapshot(
        listener=RuntimeListenerState.READY,
        manager_availability=RuntimeManagerAvailability.UNAVAILABLE,
    )

    async def inspect_composed(
        *,
        endpoint: object,
        expected: RuntimeClientHello,
        manager: object,
        manager_if_absent: RuntimeManagerAvailability,
        timeout: float = 3,
    ) -> RuntimeManagementSnapshot:
        events.append(("inspect", endpoint, expected, manager, manager_if_absent, timeout))
        return snapshot

    monkeypatch.setattr(runtime_management, "inspect_runtime_management", inspect_composed)

    actual = await runtime_management.start_installed_runtime_management()

    assert actual is snapshot
    assert events[:4] == [
        ("storage_root",),
        ("version", "cadrumo"),
        ("posix_endpoint", tmp_path, False),
        ("manager_factory", tmp_path, endpoint, "management-test"),
    ]
    door = events[4]
    assert door[0] == "door.construct" and door[1] is endpoint and door[3] is manager
    expected = cast("RuntimeClientHello", door[2])
    assert expected.product_version == "management-test" and expected.storage_identity == _IDENTITY
    assert events[5:7] == [("door.open", 10), ("connection.close",)]
    inspected = events[7]
    assert inspected[0] == "inspect" and inspected[1] is endpoint and inspected[3] is manager
    assert inspected[4:] == (RuntimeManagerAvailability.UNAVAILABLE, 3)
    assert events[8:] == [("endpoint.close",)]
    assert manager.starts == manager.stops == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_installed_configuration_uses_manager_and_releases_endpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[tuple[object, ...]] = []
    endpoint = _install_management_environment(monkeypatch, tmp_path, events)
    manager = _ComposedManager(events)
    _install_management_manager(monkeypatch, events, manager)

    actual = await runtime_management.configure_installed_runtime_management(login_autostart=True)

    assert actual is manager.facts
    assert events == [
        ("storage_root",),
        ("version", "cadrumo"),
        ("posix_endpoint", tmp_path, False),
        ("manager_factory", tmp_path, endpoint, "management-test"),
        ("manager.configure", True),
        ("endpoint.close",),
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_installed_stop_preview_retains_same_connection_until_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[tuple[object, ...]] = []
    endpoint = _install_management_environment(monkeypatch, tmp_path, events)
    connection = _ComposedConnection(events)
    _install_fake_launch_door(monkeypatch, events, connection)

    consent = await runtime_management.preview_installed_runtime_stop()

    assert isinstance(consent, RuntimeStopConsent)
    assert events[:3] == [
        ("storage_root",),
        ("version", "cadrumo"),
        ("posix_endpoint", tmp_path, False),
    ]
    door = events[3]
    assert door[0] == "door.construct" and door[1] is endpoint and door[3] is None
    expected = cast("RuntimeClientHello", door[2])
    assert expected.product_version == "management-test" and expected.storage_identity == _IDENTITY
    assert events[4] == ("door.open", 5)
    assert events[5][0] == "owner_control"
    assert not consent.released and connection.close_calls == 0

    await consent.release()

    assert consent.released and connection.close_calls == 1
    assert events[6:] == [("connection.close",), ("endpoint.close",)]


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
