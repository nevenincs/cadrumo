"""Native deletion retains selected-target, predecessor and journal replay fences."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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
from cadrumo.application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.user_profile import login_session
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
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
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
