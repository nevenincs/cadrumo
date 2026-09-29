"""A committed custody successor retires its old worker before re-admission."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Protocol, cast
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, lease, worker_profiles
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.installation import RuntimeInstallation
from cadrumo.application.runtime.profile_worker import ProfileWorkerDrained, ProfileWorkerIdentity
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost

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
    host.owner.activate(lease(identity), bytearray(key))
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
        process_handle = worker._process._handle
        assert process_handle is not None
        retained_handle = win32api.DuplicateHandle(
            win32api.GetCurrentProcess(),
            process_handle,
            win32api.GetCurrentProcess(),
            0,
            False,
            win32con.DUPLICATE_SAME_ACCESS,
        )
        release = Event()
        started = Event()
        try:
            assert host.retire_replaced_binding(deadline=time.monotonic() + 5) is False
            with host.guard:
                _commit_successor(root, identity)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    manager._last_poll = 0
                    pool.submit(manager.poll).result(timeout=3)
                assert manager._profiles[identity.binding.profile_id] is host

            actual_drain = worker.drain

            def delayed_drain(*, deadline: float | None = None) -> ProfileWorkerDrained:
                started.set()
                assert release.wait(5)
                return actual_drain(deadline=deadline)

            monkeypatch.setattr(worker, "drain", delayed_drain)
            with ThreadPoolExecutor(max_workers=1) as pool:
                manager._last_poll = 0
                polling = pool.submit(manager.poll)
                assert started.wait(5)
                assert manager._profiles[identity.binding.profile_id] is host
                with pytest.raises(AutomationCustodyError) as blocked:
                    manager._host(identity.binding.profile_id, context)
                assert blocked.value.reason is AutomationCustodyCode.CONFLICT
                release.set()
                polling.result(timeout=15)

            assert identity.binding.profile_id not in manager._profiles
            assert win32event.WaitForSingleObject(retained_handle, 5000) == win32event.WAIT_OBJECT_0
            with pytest.raises(RuntimeRefusalError):
                worker.require_alive()
            successor = manager._host(identity.binding.profile_id, context)
            assert successor.store.binding.custody_generation == identity.binding.custody_generation + 1
        finally:
            release.set()
            monkeypatch.undo()
            manager.close()
            cast(_OwnedNativeHandle, retained_handle).Close()


def test_repeated_containment_failure_keeps_retiring_host_mapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        manager, host, _context = _running_host(root=root, identity=identity, key=key)
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
