"""Native deletion retains selected-target, predecessor and journal replay fences."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.errors import KeyringUnavailableError
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.bucket_deletion_contracts import BucketDeletionFingerprint
from cadrumo.application.bucket_maintenance.contracts import AssessBucketDeletionCommand
from cadrumo.application.bucket_maintenance.service import BucketMaintenanceService
from cadrumo.application.user_profile import login_session
from cadrumo.application.user_profile.access_contracts import OsLoginContext
from cadrumo.application.user_profile.custody_repository import ProfileCustodyTransactionRepository
from cadrumo.application.user_profile.custody_transactions import (
    ProfileCustodyDeleteConfirmation,
    ProfileCustodyTransactionReceipt,
)
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.application.user_profile.profile_pointer import active_profile_pointer_transaction
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.bootstrap_delete import (
    ProfileDelete,
    ProfileDeleted,
    ProfileDeletePrepare,
    ProfileDeletePrepared,
    ProfileDeleteRefused,
)
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .served_runtime import connect_verified
from .test_access_management import login
from .test_bootstrap_reset import MutableLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]


@dataclass(frozen=True)
class _DeleteRun:
    root: Path
    endpoint: WindowsEndpoint
    profile: UUID
    capsule: Path
    login: MutableLogin
    profiles: RuntimeProfileConnections
    monkeypatch: pytest.MonkeyPatch
    completed_after_disconnect: Event


def _deletion_fingerprint(root: Path, profile: UUID) -> BucketDeletionFingerprint:
    with composed_profile_persistence_ports() as ports:
        assessment = BucketMaintenanceService(bucket_storage=ports.bucket_storage(), root=root).assess_deletion(
            AssessBucketDeletionCommand(bucket_id=str(profile)),
        )
    assert assessment.fingerprint is not None
    return assessment.fingerprint


def _disconnect_after_acceptance(
    monkeypatch: pytest.MonkeyPatch,
    captured_channels: list[ByteChannel],
    completed_after_disconnect: Event,
    original_delete: Callable[
        [ProfileCapsuleLifecycle, ProfileCustodyDeleteConfirmation], ProfileCustodyTransactionReceipt
    ],
) -> None:
    def disconnect_after_acceptance(
        owner: ProfileCapsuleLifecycle, confirmation: ProfileCustodyDeleteConfirmation
    ) -> ProfileCustodyTransactionReceipt:
        captured_channels[-1].close()
        try:
            return original_delete(owner, confirmation)
        finally:
            completed_after_disconnect.set()

    monkeypatch.setattr(ProfileCapsuleLifecycle, "delete", disconnect_after_acceptance)


def _admit_hosted_profile(run: _DeleteRun) -> tuple[VerifiedConnection, BucketDeletionFingerprint]:
    hosted_wire = connect_verified(run.endpoint)
    admitted = login(hosted_wire, run.profile, method="password", proof=PROFILE_INPUT.encode())
    assert not isinstance(admitted, AccessRefusal), admitted
    return hosted_wire, _deletion_fingerprint(run.root, run.profile)


def _prepare_delete(
    run: _DeleteRun, wire: VerifiedConnection, fingerprint: BucketDeletionFingerprint, case: str
) -> ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused | AccessRefusal:
    if case == "other-os-owner":
        original_observe = run.login.observe

        def foreign_owner(*, credential_facilities: Availability) -> OsLoginContext:
            return original_observe(credential_facilities=credential_facilities).model_copy(
                update={"os_owner_id": "another-os-account"}
            )

        run.monkeypatch.setattr(run.login, "observe", foreign_owner)
    return wire.delete_profile(
        ProfileDeletePrepare(
            request_id=uuid4(),
            profile_id=run.profile,
            frontend=OperationFrontendProjection.CLI,
            fingerprint=fingerprint,
        ),
        deadline=time.monotonic() + 30,
    )


def _refused_before_prepare(
    run: _DeleteRun,
    case: str,
    prepared: ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused | AccessRefusal,
) -> bool:
    if case == "other-os-owner":
        assert isinstance(prepared, AccessRefusal)
        assert prepared.code.value == "needs_user"
        assert run.capsule.exists()
        return True
    if case == "stale":
        assert isinstance(prepared, ProfileDeleteRefused)
        assert prepared.code == "custody_changed"
        assert run.capsule.exists()
        assert not run.profiles._profiles
        return True
    return False


def _refuse_while_login_state_unknown(run: _DeleteRun, wire: VerifiedConnection, request: ProfileDelete) -> None:
    run.login.locked = True
    refused = wire.delete_profile(request, deadline=time.monotonic() + 30)
    assert isinstance(refused, AccessRefusal)
    assert refused.code.value == "needs_user"
    assert run.capsule.exists()


def _retry_after_cleanup_refusal(run: _DeleteRun, wire: VerifiedConnection, request: ProfileDelete) -> None:
    original_cleanup = login_session.revoke_profile_session_artefacts

    def unavailable(**_coordinates: object) -> None:
        raise KeyringUnavailableError("synthetic keychain refusal")

    run.monkeypatch.setattr(login_session, "revoke_profile_session_artefacts", unavailable)
    refused = wire.delete_profile(request, deadline=time.monotonic() + 30)
    assert isinstance(refused, ProfileDeleteRefused)
    assert refused.transaction_id == request.confirmation.transaction_id
    assert run.capsule.exists()
    run.monkeypatch.setattr(login_session, "revoke_profile_session_artefacts", original_cleanup)


def _delete_through_disconnect(
    run: _DeleteRun,
    wire: VerifiedConnection,
    request: ProfileDelete,
    original_delete: Callable[
        [ProfileCapsuleLifecycle, ProfileCustodyDeleteConfirmation], ProfileCustodyTransactionReceipt
    ],
) -> VerifiedConnection:
    with pytest.raises(RefusalError):
        wire.delete_profile(request, deadline=time.monotonic() + 30)
    assert run.completed_after_disconnect.wait(5)
    assert not run.capsule.exists()
    run.monkeypatch.setattr(ProfileCapsuleLifecycle, "delete", original_delete)
    wire.close()
    return connect_verified(run.endpoint)


def _delete_and_replay(run: _DeleteRun, wire: VerifiedConnection, request: ProfileDelete, case: str) -> None:
    deleted = wire.delete_profile(request, deadline=time.monotonic() + 30)
    assert isinstance(deleted, ProfileDeleted), deleted
    assert not run.capsule.exists()
    if case in {"selected", "selected-hosted"}:
        with active_profile_pointer_transaction(run.root) as pointer:
            assert pointer.read().bucket_id is None
    replay = wire.delete_profile(request.model_copy(update={"request_id": uuid4()}), deadline=time.monotonic() + 30)
    assert isinstance(replay, ProfileDeleted), replay
    assert replay.receipt == deleted.receipt
    assert not run.profiles._profiles


@pytest.mark.parametrize(
    "case",
    [
        "selected",
        "stale",
        "delete-replay",
        "unknown-after-prepare",
        "cleanup-retry",
        "disconnect",
        "hosted",
        "selected-hosted",
        "other-os-owner",
    ],
)
def test_runtime_bootstrap_delete_uses_existing_custody_journal(
    tmp_path: Path,
    case: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login = MutableLogin("native-access-management-test-login")
    captured_channels: list[ByteChannel] = []
    completed_after_disconnect = Event()

    def capture(channel: ByteChannel) -> MutableLogin:
        captured_channels.append(channel)
        return login

    original_delete = ProfileCapsuleLifecycle.delete
    if case == "disconnect":
        _disconnect_after_acceptance(monkeypatch, captured_channels, completed_after_disconnect, original_delete)

    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root,
        os_owner_id=owner_id(),
        storage_identity=endpoint.storage_identity,
    )
    stop, boot = Event(), uuid4()
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as subject:
        profile = subject.store.binding.profile_id
        capsule = load_committed_profile_password_material(profile, root=root).capsule_path
        close_active_bucket_session()
        if case not in {"selected", "selected-hosted"}:
            with active_profile_pointer_transaction(root) as pointer:
                pointer.clear()
        fingerprint = _deletion_fingerprint(root, profile)
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
        run = _DeleteRun(root, endpoint, profile, capsule, login, profiles, monkeypatch, completed_after_disconnect)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            running.add_done_callback(lambda _future: readiness.put("server_finished"))
            try:
                observed = readiness.get()
                if observed != "ready":
                    running.result()
                assert observed == "ready"
                hosted_wire = None
                if case in {"hosted", "selected-hosted"}:
                    hosted_wire, fingerprint = _admit_hosted_profile(run)
                wire = connect_verified(endpoint)
                try:
                    prepared = _prepare_delete(run, wire, fingerprint, case)
                    if _refused_before_prepare(run, case, prepared):
                        return
                    assert isinstance(prepared, ProfileDeletePrepared)
                    assert capsule.exists()
                    request = ProfileDelete(
                        request_id=uuid4(),
                        profile_id=profile,
                        frontend=OperationFrontendProjection.CLI,
                        confirmation=prepared.confirmation,
                    )
                    if case == "unknown-after-prepare":
                        _refuse_while_login_state_unknown(run, wire, request)
                        return
                    if case == "cleanup-retry":
                        _retry_after_cleanup_refusal(run, wire, request)
                    if case == "disconnect":
                        wire = _delete_through_disconnect(run, wire, request, original_delete)
                    _delete_and_replay(run, wire, request, case)
                finally:
                    wire.close()
                    if hosted_wire is not None:
                        hosted_wire.close()
            finally:
                stop.set()
                running.result(timeout=25)


@dataclass(frozen=True)
class _PollHandoff:
    root: Path
    profile: UUID
    capsule: Path
    journal_root: Path
    repository: ProfileCustodyTransactionRepository
    profiles: RuntimeProfileConnections
    pool: ThreadPoolExecutor
    observations: Queue[str]
    fail_fast: Callable[[], object]
    monkeypatch: pytest.MonkeyPatch
    cleanup: ExitStack
    release_poll: Event
    poll_entered: Event
    poll_finished: Event


def _snapshot_capsule(capsule: Path) -> dict[Path, bytes]:
    return {path.relative_to(capsule): path.read_bytes() for path in capsule.rglob("*") if path.is_file()}


def _snapshot_journals(journal_root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in journal_root.glob("*.json")}


def _queue_delete_behind_held_poll(
    handoff: _PollHandoff, wire: VerifiedConnection, fingerprint: BucketDeletionFingerprint
) -> tuple[Future[ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused | AccessRefusal], dict[str, bytes]]:
    profiles, observations, capsule = handoff.profiles, handoff.observations, handoff.capsule
    original_poll = profiles._poll_profiles

    def hold_actual_poll() -> None:
        if not handoff.poll_entered.is_set():
            handoff.poll_entered.set()
            observations.put("poll_held")
            handoff.release_poll.wait()
        try:
            original_poll()
        finally:
            handoff.poll_finished.set()

    handoff.monkeypatch.setattr(profiles, "_poll_profiles", hold_actual_poll)
    held = observations.get()
    if held != "poll_held":
        handoff.fail_fast()
    assert held == "poll_held"
    capsule_before = _snapshot_capsule(capsule)
    journals_before = _snapshot_journals(handoff.journal_root)
    original_wait = profiles._drain_guard._condition.wait

    def observe_registered_delete(timeout: float | None = None) -> bool:
        if profiles._drain_guard._owner_role == "poll":
            observations.put("delete_queued")
        return original_wait(timeout)

    handoff.monkeypatch.setattr(profiles._drain_guard._condition, "wait", observe_registered_delete)
    preparing = handoff.pool.submit(
        wire.delete_profile,
        ProfileDeletePrepare(
            request_id=uuid4(),
            profile_id=handoff.profile,
            frontend=OperationFrontendProjection.CLI,
            fingerprint=fingerprint,
        ),
        deadline=time.monotonic() + 30,
    )
    preparing.add_done_callback(lambda _future: observations.put("prepare_finished"))
    handoff.cleanup.callback(preparing.result)
    queued = observations.get()
    if queued == "prepare_finished":
        preparing.result()
    elif queued == "server_finished":
        handoff.fail_fast()
    assert queued == "delete_queued"
    assert not preparing.done()
    assert capsule.exists()
    assert _snapshot_capsule(capsule) == capsule_before
    assert _snapshot_journals(handoff.journal_root) == journals_before
    return preparing, journals_before


def _overlap_then_release_poll(
    handoff: _PollHandoff,
    overlap: str,
    stop: Event,
    preparing: Future[ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused | AccessRefusal],
) -> ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused | AccessRefusal:
    if overlap == "selected":
        # Pointer locking must remain available while the request waits outside every root guard.
        with active_profile_pointer_transaction(handoff.root) as pointer:
            pointer.select(str(handoff.profile))
    elif overlap == "shutdown":
        stop.set()
    handoff.release_poll.set()
    prepared = preparing.result()
    assert handoff.poll_finished.is_set()
    return prepared


def _assert_overlap_outcome(
    handoff: _PollHandoff,
    wire: VerifiedConnection,
    overlap: str,
    prepared: ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused | AccessRefusal,
    journals_before: dict[str, bytes],
) -> None:
    profile, capsule, repository = handoff.profile, handoff.capsule, handoff.repository
    if overlap == "selected":
        assert isinstance(prepared, ProfileDeletePrepared)
    elif overlap == "shutdown":
        assert isinstance(prepared, AccessRefusal)
        assert prepared.code is RefusalCode.DRAINING
    else:
        assert isinstance(prepared, ProfileDeletePrepared)
        assert repository.load_journal(prepared.confirmation.transaction_id).profile_id == profile
        assert capsule.exists()
        deleted = wire.delete_profile(
            ProfileDelete(
                request_id=uuid4(),
                profile_id=profile,
                frontend=OperationFrontendProjection.CLI,
                confirmation=prepared.confirmation,
            ),
            deadline=time.monotonic() + 30,
        )
        assert isinstance(deleted, ProfileDeleted)
        assert repository.load_receipt(prepared.confirmation.transaction_id) == deleted.receipt
        assert not capsule.exists()
    if overlap != "handoff":
        assert capsule.exists()
        if overlap == "shutdown":
            assert _snapshot_journals(handoff.journal_root) == journals_before


@pytest.mark.parametrize("overlap", ["handoff", "selected", "shutdown"])
def test_native_bootstrap_delete_fresh_admission_after_an_actual_poll_handoff(
    tmp_path: Path, overlap: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hold real polling after wire admission; custody stays fresh and owns durable completion."""
    login = MutableLogin("native-access-management-test-login")
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    stop, boot = Event(), uuid4()
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as subject:
        profile = subject.store.binding.profile_id
        capsule = load_committed_profile_password_material(profile, root=root).capsule_path
        close_active_bucket_session()
        with active_profile_pointer_transaction(root) as pointer:
            pointer.clear()
        fingerprint = _deletion_fingerprint(root, profile)
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
                wire = connect_verified(endpoint)
                request_cleanup.callback(wire.close)
                handoff = _PollHandoff(
                    root,
                    profile,
                    capsule,
                    journal_root,
                    repository,
                    profiles,
                    pool,
                    observations,
                    running.result,
                    monkeypatch,
                    request_cleanup,
                    release_poll,
                    poll_entered,
                    poll_finished,
                )
                preparing, journals_before = _queue_delete_behind_held_poll(handoff, wire, fingerprint)
                prepared = _overlap_then_release_poll(handoff, overlap, stop, preparing)
                _assert_overlap_outcome(handoff, wire, overlap, prepared, journals_before)
            finally:
                # Always settle the held poll before waiting on serving requests or original native cleanup.
                release_poll.set()
                try:
                    request_cleanup.close()
                finally:
                    stop.set()
                    running.result()
