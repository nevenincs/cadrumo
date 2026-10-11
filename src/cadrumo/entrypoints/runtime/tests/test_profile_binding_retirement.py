"""A committed custody successor retires its old worker before re-admission."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from threading import Event
from typing import Any, Protocol, cast
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, lease, worker_profiles
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.enrollment_access import RuntimeEnrollmentPrepared
from cadrumo.application.runtime.installation import RuntimeInstallation
from cadrumo.application.runtime.profile_worker import ProfileWorkerDrained, ProfileWorkerIdentity
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

from .. import profile_connection_admission
from ..enrollment_offer import RuntimeEnrollmentOffer
from ..profile_connections import RuntimeProfileConnections
from ..profile_host import ProfileConnection, RuntimeProfileHost

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires actual native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]

_SUCCESSOR = "synthetic-worker-password-successor"


class _OwnedNativeHandle(Protocol):
    def Close(self) -> None:  # noqa: N802 -- native PyHANDLE method spelling.
        """Release the duplicate Windows handle owned by this test."""
        ...


def _running_host(
    *, root: Path, identity: ProfileWorkerIdentity, key: bytes
) -> tuple[RuntimeProfileConnections, RuntimeProfileHost, RuntimeConnectionContext]:
    native = MemoryNativePort()
    manager = RuntimeProfileConnections(
        storage_root=root,
        storage_identity="a" * 64,
        runtime_boot_id=identity.runtime_boot_id,
        stop=Event(),
        secret_store=lambda: native,
    )
    manager._installation = RuntimeInstallation(
        installation_id=identity.binding.installation_id,
        os_owner_id=identity.binding.os_owner_id,
        storage_identity=manager.storage_identity,
    )
    registry: OperationRegistry = build_production_operation_registry()
    manager._registry = registry
    host = RuntimeProfileHost(
        store=AutomationControlStore(root=root, binding=identity.binding, secrets_store=native),
        runtime_boot_id=identity.runtime_boot_id,
        registry=registry,
        connected=manager._connected,
        logins=manager._login_contexts,
        admitting=manager._admitting,
    )
    manager._profiles[identity.binding.profile_id] = host
    candidate = lease(identity)
    with host.owner.prepare_api_admission(candidate.connection_id):
        host.owner.activate(candidate, bytearray(key))
    context = RuntimeConnectionContext(
        uuid4(), identity.runtime_boot_id, RuntimePeer(os_owner_id=identity.binding.os_owner_id, process_id=1234)
    )
    return manager, host, context


def _commit_successor(root: Path, identity: ProfileWorkerIdentity) -> None:
    _create, decode = profile_authority_contexts()
    result = rotate_profile_passphrase(
        profile_id=identity.binding.profile_id,
        current_passphrase=PROFILE_INPUT,
        new_passphrase=_SUCCESSOR,
        new_passphrase_confirmation=_SUCCESSOR,
        root=root,
        profile_decode_context=decode,
    )
    assert result.password_generation == identity.binding.custody_generation + 1
    current = current_automation_profile_binding(
        profile_id=identity.binding.profile_id,
        installation_id=identity.binding.installation_id,
        os_owner_id=identity.binding.os_owner_id,
        root=root,
    )
    assert current.custody_generation == result.password_generation
    assert current.dek_epoch == identity.binding.dek_epoch


def _fence_held_against(monkeypatch: pytest.MonkeyPatch, host: RuntimeProfileHost) -> Event:
    """Say when a later caller finds this incarnation's fence held by another owner."""
    retire = host.retire_replaced_binding
    held = Event()

    def observe(*, deadline: float) -> bool | None:
        retired = retire(deadline=deadline)
        if retired is None:
            held.set()
        return retired

    monkeypatch.setattr(host, "retire_replaced_binding", observe)
    return held


def test_changed_binding_waits_for_guard_then_drains_actual_worker_before_successor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import win32api
    import win32con
    import win32event

    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        manager, host, context = _running_host(root=root, identity=identity, key=key)
        worker = host.owner.operation_worker()
        process = worker._process
        assert isinstance(process, WindowsOwnedProcess)
        process_handle = process._handle
        assert process_handle is not None
        retained_handle = win32api.DuplicateHandle(
            win32api.GetCurrentProcess(),
            process_handle,
            win32api.GetCurrentProcess(),
            0,
            False,
            win32con.DUPLICATE_SAME_ACCESS,
        )
        profile_id = identity.binding.profile_id
        try:
            assert host.retire_replaced_binding(deadline=time.monotonic() + 5) is False
            with ThreadPoolExecutor(max_workers=1) as pool:
                with host.guard:
                    _commit_successor(root, identity)
                    manager._last_poll = 0
                    pool.submit(manager.poll).result(timeout=3)
                    assert manager._profiles[profile_id] is host
                    held = _fence_held_against(monkeypatch, host)
                    admission = pool.submit(manager._host, profile_id, context)
                    # The commit body still holds the profile guard: admission neither refuses
                    # nor admits a successor while the old worker is uncontained.
                    assert held.wait(5)
                    assert not admission.done()
                    assert manager._profiles[profile_id] is host
                    worker.require_alive()
                successor = admission.result(timeout=15)

            assert successor is not host
            assert manager._profiles[profile_id] is successor
            assert win32event.WaitForSingleObject(retained_handle, 5000) == win32event.WAIT_OBJECT_0
            with pytest.raises(RuntimeRefusalError):
                worker.require_alive()
            assert successor.store.binding.custody_generation == identity.binding.custody_generation + 1
        finally:
            monkeypatch.undo()
            manager.close()
            cast(_OwnedNativeHandle, retained_handle).Close()


def test_admission_arriving_while_polling_contains_the_old_worker_waits_for_the_successor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        manager, host, context = _running_host(root=root, identity=identity, key=key)
        profile_id = identity.binding.profile_id
        worker = host.owner.operation_worker()
        _commit_successor(root, identity)
        actual_drain = worker.drain
        release, started = Event(), Event()

        def delayed_drain(*, deadline: float | None = None) -> ProfileWorkerDrained:
            started.set()
            assert release.wait(5)
            return actual_drain(deadline=deadline)

        monkeypatch.setattr(worker, "drain", delayed_drain)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                manager._last_poll = 0
                polling = pool.submit(manager.poll)
                assert started.wait(5)
                held = _fence_held_against(monkeypatch, host)
                admission = pool.submit(manager._host, profile_id, context)
                # Polling owns the containment under way. Losing that fence to it is not a
                # refusal of this admission, and no successor exists before the drain ends.
                assert held.wait(5)
                assert not admission.done()
                assert manager._profiles[profile_id] is host
                release.set()
                polling.result(timeout=15)
                successor = admission.result(timeout=15)

            assert successor is not host
            assert manager._profiles[profile_id] is successor
            assert successor.store.binding.custody_generation == identity.binding.custody_generation + 1
            with pytest.raises(RuntimeRefusalError):
                worker.require_alive()
        finally:
            release.set()
            monkeypatch.undo()
            manager.close()


def test_an_admission_waiting_on_a_held_fence_reads_no_binding_and_holds_no_connection_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        manager, host, context = _running_host(root=root, identity=identity, key=key)
        profile_id = identity.binding.profile_id
        read_binding = profile_connection_admission.current_automation_profile_binding
        binding_reads: list[float] = []

        def counted_read(**coordinates: Any) -> ProfileAccessBinding:
            binding_reads.append(time.monotonic())
            return read_binding(**coordinates)

        monkeypatch.setattr(profile_connection_admission, "current_automation_profile_binding", counted_read)
        retire = host.retire_replaced_binding
        held_tries: list[float] = []

        def observed_retire(*, deadline: float) -> bool | None:
            retired = retire(deadline=deadline)
            if retired is None:
                held_tries.append(time.monotonic())
            return retired

        monkeypatch.setattr(host, "retire_replaced_binding", observed_retire)
        wait_for_stop = manager.stop.wait
        guard_free_during_a_wait: list[bool] = []

        def borrow_connection_guard() -> bool:
            if not manager._guard.acquire(blocking=False):
                return False
            manager._guard.release()
            return True

        def observed_wait(timeout: float | None = None) -> bool:
            # The guard is reentrant, so only another thread can tell whether the admitting one holds it here.
            with ThreadPoolExecutor(max_workers=1) as borrower:
                guard_free_during_a_wait.append(borrower.submit(borrow_connection_guard).result(timeout=3))
            return wait_for_stop(timeout)

        monkeypatch.setattr(manager.stop, "wait", observed_wait)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                with host.guard:
                    _commit_successor(root, identity)
                    admission = pool.submit(manager._host, profile_id, context)
                    observed_until = time.monotonic() + 10
                    while len(held_tries) < 5:
                        assert time.monotonic() < observed_until, "the admission stopped trying the held fence"
                        assert not admission.done()
                        time.sleep(0.005)
                    reads_while_held = len(binding_reads)
                    tries_while_held = list(held_tries)
                successor = admission.result(timeout=15)

            assert successor is not host
            assert successor.store.binding.custody_generation == identity.binding.custody_generation + 1
            # One read found the binding replaced; the wait for its fence read nothing more.
            assert reads_while_held == 1
            # Another connection's work could take the connection-wide guard during every wait.
            assert guard_free_during_a_wait
            assert all(guard_free_during_a_wait)
            # Each wait is at least twice the one before, so a long hold is not polled at a fixed short interval.
            gaps = [later - earlier for earlier, later in pairwise(tries_while_held)]
            assert gaps[3] >= 0.07
            assert gaps[3] > gaps[0]
        finally:
            monkeypatch.undo()
            manager.close()


def test_repeated_containment_failure_keeps_retiring_host_mapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        manager, host, context = _running_host(root=root, identity=identity, key=key)
        worker = host.owner.operation_worker()
        _commit_successor(root, identity)

        def refused_containment(*, deadline: float | None = None) -> None:
            del deadline
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

        monkeypatch.setattr(worker, "drain", refused_containment)
        monkeypatch.setattr(worker, "close", refused_containment)
        try:
            manager._last_poll = 0
            with pytest.raises(ExceptionGroup):
                manager.poll()
            assert manager._profiles[identity.binding.profile_id] is host

            manager._last_poll = 0
            with pytest.raises(ExceptionGroup):
                manager.poll()
            assert manager._profiles[identity.binding.profile_id] is host
            with pytest.raises(AutomationCustodyError) as refused:
                manager._host(identity.binding.profile_id, context)
            assert refused.value.reason is AutomationCustodyCode.CONFLICT
            assert manager._profiles[identity.binding.profile_id] is host
        finally:
            monkeypatch.undo()
            try:
                manager._last_poll = 0
                manager.poll()
                assert identity.binding.profile_id not in manager._profiles
                with pytest.raises(RuntimeRefusalError):
                    worker.require_alive()
            finally:
                manager.close()


class _RetirementLogin:
    login_id = "retirement-incarnation-test"

    def __init__(self, owner: str) -> None:
        self.owner = owner

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _offer(host: RuntimeProfileHost, context: RuntimeConnectionContext) -> RuntimeEnrollmentOffer:
    client_id = uuid4()
    connection = ProfileConnection(
        context,
        _RetirementLogin(context.peer.os_owner_id),
        client_id,
        host.store.binding.profile_id,
        OperationFrontendProjection.MCP,
        method="enrollment",
    )
    return RuntimeEnrollmentOffer(
        prepared=RuntimeEnrollmentPrepared(
            request_id=uuid4(),
            runtime_boot_id=context.runtime_boot_id,
            connection_id=context.connection_id,
            enrollment_request_id=uuid4(),
            client_id=client_id,
            destination_id=client_id,
            profile_binding=host.store.binding,
            expires_at=now() + timedelta(minutes=5),
        ),
        connection=connection,
        host=host,
        deadline=time.monotonic() + 300,
        admitting=lambda: True,
        lock_generation=0,
    )


def test_admission_retires_old_worker_without_polling_and_preserves_new_incarnation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        manager, host, context = _running_host(root=root, identity=identity, key=key)
        worker = host.owner.operation_worker()
        old_offer = _offer(host, context)
        manager._enrollments._offers[context.connection_id] = old_offer
        _commit_successor(root, identity)
        actual_drain = worker.drain
        guard_available = Event()

        def observe_drain(*, deadline: float | None = None) -> ProfileWorkerDrained:
            # A worker callback on another thread must be able to borrow the
            # connection map while admission waits for process containment.
            def borrow_connections() -> None:
                with manager._guard:
                    guard_available.set()

            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(borrow_connections).result(timeout=3)
            return actual_drain(deadline=deadline)

        monkeypatch.setattr(worker, "drain", observe_drain)
        try:
            successor = manager._host(identity.binding.profile_id, context)
            assert guard_available.is_set()
            assert successor is not host
            assert successor.store.binding.custody_generation == identity.binding.custody_generation + 1
            with pytest.raises(RuntimeRefusalError):
                worker.require_alive()
            assert old_offer.closed
            assert context.connection_id not in manager._enrollments._offers

            new_offer = _offer(successor, context)
            new_offer.connection.session_id = uuid4()
            session_id = new_offer.connection.session_id
            manager._connections[context.connection_id] = new_offer.connection
            manager._enrollments._offers[context.connection_id] = new_offer
            manager._remove_retired_host(host)
            assert manager._profiles[identity.binding.profile_id] is successor
            assert new_offer.connection.session_id == session_id
            assert manager._enrollments._offers[context.connection_id] is new_offer
            assert not new_offer.closed
        finally:
            monkeypatch.undo()
            manager.close()
