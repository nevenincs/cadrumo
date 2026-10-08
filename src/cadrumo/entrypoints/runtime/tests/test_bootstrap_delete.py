"""Native deletion retains selected-target, predecessor and journal replay fences."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from queue import Queue
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.errors import KeyringUnavailableError
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.bucket_maintenance.contracts import AssessBucketDeletionCommand
from cadrumo.application.bucket_maintenance.service import BucketMaintenanceService
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.bootstrap_delete import (
    RuntimeProfileDelete,
    RuntimeProfileDeleted,
    RuntimeProfileDeletePrepare,
    RuntimeProfileDeletePrepared,
    RuntimeProfileDeleteRefused,
)
from cadrumo.application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.user_profile import login_session
from cadrumo.application.user_profile.custody_repository import ProfileCustodyTransactionRepository
from cadrumo.application.user_profile.custody_transactions import (
    ProfileCustodyDeleteConfirmation,
    ProfileCustodyTransactionReceipt,
)
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.application.user_profile.profile_pointer import active_profile_pointer_transaction
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from .test_access_management import _connect, _login
from .test_bootstrap_reset import _MutableLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize(
    "case", ["selected", "stale", "delete-replay", "unknown-after-prepare", "cleanup-retry", "disconnect", "hosted"]
)
def test_runtime_bootstrap_delete_uses_existing_custody_journal(
    tmp_path: Path,
    case: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login = _MutableLogin()
    captured_channels: list[RuntimeByteChannel] = []
    completed_after_disconnect = Event()

    def capture(channel: RuntimeByteChannel) -> _MutableLogin:
        captured_channels.append(channel)
        return login

    original_delete = ProfileCapsuleLifecycle.delete
    if case == "disconnect":

        def disconnect_after_acceptance(
            owner: ProfileCapsuleLifecycle, confirmation: ProfileCustodyDeleteConfirmation
        ) -> ProfileCustodyTransactionReceipt:
            captured_channels[-1].close()
            try:
                return original_delete(owner, confirmation)
            finally:
                completed_after_disconnect.set()

        monkeypatch.setattr(ProfileCapsuleLifecycle, "delete", disconnect_after_acceptance)

    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root,
        os_owner_id=owner_id(),
        storage_identity=endpoint.storage_identity,
    )
    stop, boot = Event(), uuid4()
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile = subject.store.binding.profile_id
        capsule = load_committed_profile_password_material(profile, root=root).capsule_path
        close_active_bucket_session()
        if case != "selected":
            with active_profile_pointer_transaction(root) as pointer:
                pointer.clear()
        with composed_profile_persistence_ports() as ports:
            assessment = BucketMaintenanceService(bucket_storage=ports.bucket_storage(), root=root).assess_deletion(
                AssessBucketDeletionCommand(bucket_id=str(profile)),
            )
        assert assessment.fingerprint is not None
        fingerprint = assessment.fingerprint
        if case == "stale":
            fingerprint = fingerprint.model_copy(update={"total_bytes": fingerprint.total_bytes + 1})
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=capture,
            secret_store=lambda: subject.native,
        )
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        readiness: Queue[str] = Queue()
        original_ready_set = server.ready.set

        def observe_original_ready() -> None:
            original_ready_set()
            readiness.put("ready")

        monkeypatch.setattr(server.ready, "set", observe_original_ready)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            running.add_done_callback(lambda _future: readiness.put("server_finished"))
            try:
                observed = readiness.get()
                if observed != "ready":
                    running.result()
                assert observed == "ready"
                hosted_wire = None
                if case == "hosted":
                    hosted_wire = _connect(endpoint)
                    admitted = _login(hosted_wire, profile, method="password", proof=PROFILE_INPUT.encode())
                    assert not isinstance(admitted, RuntimeAccessRefusal), admitted
                    with composed_profile_persistence_ports() as ports:
                        current = BucketMaintenanceService(
                            bucket_storage=ports.bucket_storage(), root=root
                        ).assess_deletion(
                            AssessBucketDeletionCommand(bucket_id=str(profile)),
                        )
                    assert current.fingerprint is not None
                    fingerprint = current.fingerprint
                wire = _connect(endpoint)
                try:
                    prepared = wire.delete_profile(
                        RuntimeProfileDeletePrepare(
                            request_id=uuid4(),
                            profile_id=profile,
                            frontend=OperationFrontendProjection.CLI,
                            fingerprint=fingerprint,
                        ),
                        deadline=time.monotonic() + 30,
                    )
                    if case in {"selected", "stale"}:
                        assert isinstance(prepared, RuntimeProfileDeleteRefused)
                        assert prepared.code == ("selected_profile" if case == "selected" else "custody_changed")
                        assert capsule.exists()
                        assert not profiles._profiles
                        return
                    assert isinstance(prepared, RuntimeProfileDeletePrepared)
                    assert capsule.exists()
                    request = RuntimeProfileDelete(
                        request_id=uuid4(),
                        profile_id=profile,
                        frontend=OperationFrontendProjection.CLI,
                        confirmation=prepared.confirmation,
                    )
                    if case == "unknown-after-prepare":
                        login.locked = True
                        refused = wire.delete_profile(request, deadline=time.monotonic() + 30)
                        assert isinstance(refused, RuntimeAccessRefusal)
                        assert refused.code.value == "needs_user"
                        assert capsule.exists()
                        return
                    if case == "cleanup-retry":
                        original_cleanup = login_session._revoke_profile_session_artefacts

                        def unavailable(**_coordinates: object) -> None:
                            raise KeyringUnavailableError("synthetic keychain refusal")

                        monkeypatch.setattr(login_session, "_revoke_profile_session_artefacts", unavailable)
                        refused = wire.delete_profile(request, deadline=time.monotonic() + 30)
                        assert isinstance(refused, RuntimeProfileDeleteRefused)
                        assert refused.transaction_id == request.confirmation.transaction_id
                        assert capsule.exists()
                        monkeypatch.setattr(login_session, "_revoke_profile_session_artefacts", original_cleanup)
                    if case == "disconnect":
                        with pytest.raises(RuntimeRefusalError):
                            wire.delete_profile(request, deadline=time.monotonic() + 30)
                        assert completed_after_disconnect.wait(5)
                        assert not capsule.exists()
                        monkeypatch.setattr(ProfileCapsuleLifecycle, "delete", original_delete)
                        wire.close()
                        wire = _connect(endpoint)
                    deleted = wire.delete_profile(request, deadline=time.monotonic() + 30)
                    assert isinstance(deleted, RuntimeProfileDeleted), deleted
                    assert not capsule.exists()
                    replay = wire.delete_profile(
                        request.model_copy(update={"request_id": uuid4()}), deadline=time.monotonic() + 30
                    )
                    assert isinstance(replay, RuntimeProfileDeleted), replay
                    assert replay.receipt == deleted.receipt
                    assert not profiles._profiles
                finally:
                    wire.close()
                    if hosted_wire is not None:
                        hosted_wire.close()
            finally:
                stop.set()
                running.result(timeout=25)


@pytest.mark.parametrize("overlap", ["handoff", "selected", "shutdown"])
def test_native_bootstrap_delete_fresh_admission_after_an_actual_poll_handoff(
    tmp_path: Path, overlap: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hold real polling after wire admission; custody stays fresh and owns durable completion."""
    login = _MutableLogin()
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    stop, boot = Event(), uuid4()
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile = subject.store.binding.profile_id
        capsule = load_committed_profile_password_material(profile, root=root).capsule_path
        close_active_bucket_session()
        with active_profile_pointer_transaction(root) as pointer:
            pointer.clear()
        with composed_profile_persistence_ports() as ports:
            assessment = BucketMaintenanceService(bucket_storage=ports.bucket_storage(), root=root).assess_deletion(
                AssessBucketDeletionCommand(bucket_id=str(profile))
            )
        assert assessment.fingerprint is not None
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: login,
            secret_store=lambda: subject.native,
        )
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        observations: Queue[str] = Queue()
        ready_set = server.ready.set

        def observe_ready() -> None:
            ready_set()
            observations.put("ready")

        monkeypatch.setattr(server.ready, "set", observe_ready)
        release_poll, poll_entered, poll_finished = Event(), Event(), Event()
        repository = ProfileCustodyTransactionRepository(root=root)
        journal_root = repository.journal_path(uuid4()).parent
        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(server.serve)
            running.add_done_callback(lambda _future: observations.put("server_finished"))
            request_cleanup = ExitStack()
            try:
                ready = observations.get()
                if ready != "ready":
                    running.result()
                assert ready == "ready"
                # The serving owner already has the protected native wire before its accept loop is held.
                wire = _connect(endpoint)
                request_cleanup.callback(wire.close)
                original_poll = profiles._poll_profiles

                def hold_actual_poll() -> None:
                    if not poll_entered.is_set():
                        poll_entered.set()
                        observations.put("poll_held")
                        release_poll.wait()
                    try:
                        original_poll()
                    finally:
                        poll_finished.set()

                monkeypatch.setattr(profiles, "_poll_profiles", hold_actual_poll)
                held = observations.get()
                if held != "poll_held":
                    running.result()
                assert held == "poll_held"
                capsule_before = {
                    path.relative_to(capsule): path.read_bytes() for path in capsule.rglob("*") if path.is_file()
                }
                journals_before = {path.name: path.read_bytes() for path in journal_root.glob("*.json")}
                original_wait = profiles._drain_guard._condition.wait

                def observe_registered_delete(timeout: float | None = None) -> bool:
                    if profiles._drain_guard._owner_role == "poll":
                        observations.put("delete_queued")
                    return original_wait(timeout)

                monkeypatch.setattr(profiles._drain_guard._condition, "wait", observe_registered_delete)
                preparing = pool.submit(
                    wire.delete_profile,
                    RuntimeProfileDeletePrepare(
                        request_id=uuid4(),
                        profile_id=profile,
                        frontend=OperationFrontendProjection.CLI,
                        fingerprint=assessment.fingerprint,
                    ),
                    deadline=time.monotonic() + 30,
                )
                preparing.add_done_callback(lambda _future: observations.put("prepare_finished"))
                request_cleanup.callback(preparing.result)
                queued = observations.get()
                if queued == "prepare_finished":
                    preparing.result()
                elif queued == "server_finished":
                    running.result()
                assert queued == "delete_queued"
                assert not preparing.done()
                assert capsule.exists()
                assert {
                    path.relative_to(capsule): path.read_bytes() for path in capsule.rglob("*") if path.is_file()
                } == (capsule_before)
                assert {path.name: path.read_bytes() for path in journal_root.glob("*.json")} == journals_before
                if overlap == "selected":
                    # Pointer locking must remain available while the request waits outside every root guard.
                    with active_profile_pointer_transaction(root) as pointer:
                        pointer.select(str(profile))
                elif overlap == "shutdown":
                    stop.set()
                release_poll.set()
                prepared = preparing.result()
                assert poll_finished.is_set()
                if overlap == "selected":
                    assert isinstance(prepared, RuntimeProfileDeleteRefused)
                    assert prepared.code == "selected_profile"
                elif overlap == "shutdown":
                    assert isinstance(prepared, RuntimeAccessRefusal)
                    assert prepared.code is RuntimeRefusalCode.DRAINING
                else:
                    assert isinstance(prepared, RuntimeProfileDeletePrepared)
                    assert repository.load_journal(prepared.confirmation.transaction_id).profile_id == profile
                    assert capsule.exists()
                    deleted = wire.delete_profile(
                        RuntimeProfileDelete(
                            request_id=uuid4(),
                            profile_id=profile,
                            frontend=OperationFrontendProjection.CLI,
                            confirmation=prepared.confirmation,
                        ),
                        deadline=time.monotonic() + 30,
                    )
                    assert isinstance(deleted, RuntimeProfileDeleted)
                    assert repository.load_receipt(prepared.confirmation.transaction_id) == deleted.receipt
                    assert not capsule.exists()
                if overlap != "handoff":
                    assert capsule.exists()
                    assert {path.name: path.read_bytes() for path in journal_root.glob("*.json")} == journals_before
            finally:
                # Always settle the held poll before waiting on serving requests or original native cleanup.
                release_poll.set()
                try:
                    request_cleanup.close()
                finally:
                    stop.set()
                    running.result()
