"""Runtime-wide shutdown drains published native workers before ownership ends."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, RLock
from types import SimpleNamespace
from typing import cast, override

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.master_key.active_session import activate_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import load_test_profile_record
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeExitReason, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeHumanProof
from cadrumo.application.runtime.worker_authorization import WorkerAuthorityRequest
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessAllowed
from cadrumo.application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost
from ..session_owner import ProfileWorkerSessionOwner
from ..shutdown import RuntimeStop
from .test_profile_worker_operations import BoundaryAuthority

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize("session_end,running", [(False, False), (True, False), (True, True)])
def test_runtime_drain_contains_all_workers_and_settles_intent(
    tmp_path: Path, session_end: bool, running: bool
) -> None:
    import win32api
    import win32con
    import win32event

    with worker_profiles(tmp_path) as (root, identities):
        stop = RuntimeStop()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity="test-storage",
            runtime_boot_id=identities[0][0].runtime_boot_id,
            stop=stop,
        )
        profiles.prepare_registry()
        handles: list[int] = []
        owners: list[ProfileWorkerSessionOwner] = []
        sessions = []
        commit_entered, release_commit = Event(), Event()

        class PausedCommitAuthority(BoundaryAuthority):
            @override
            @contextmanager
            def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
                if running and request.request.action is AccessAction.COMMIT:
                    commit_entered.set()
                    if not release_commit.wait(timeout=15):
                        raise TimeoutError("test commit boundary was not released")
                with super().authorize(request) as allowed:
                    yield allowed

        try:
            for identity, key in identities:
                owner = ProfileWorkerSessionOwner(
                    identity,
                    storage_root=root,
                    observe=lambda _connection: (_ for _ in ()).throw(AssertionError("unexpected observation")),
                    human_secret=lambda _connection: nullcontext(
                        RuntimeHumanProof(method="password", secret=bytearray(), originating_login_id="unused")
                    ),
                    guard=RLock(),
                    authorization=PausedCommitAuthority(deny_commit=False),
                )
                admitted = lease(identity)
                sessions.append(admitted)
                with owner.prepare_api_admission(admitted.connection_id):
                    owner.activate(admitted, bytearray(key))
                worker = owner.operation_worker()
                process = worker._process
                assert isinstance(process, WindowsOwnedProcess)
                handle = process._handle
                assert handle is not None
                handles.append(
                    win32api.DuplicateHandle(
                        win32api.GetCurrentProcess(),
                        handle,
                        win32api.GetCurrentProcess(),
                        0,
                        False,
                        win32con.DUPLICATE_SAME_ACCESS,
                    )
                )
                owners.append(owner)
                host = SimpleNamespace(
                    store=SimpleNamespace(binding=identity.binding),
                    owner=owner,
                    approvals=SimpleNamespace(close=lambda: 0),
                )
                profiles._profiles[identity.binding.profile_id] = cast("RuntimeProfileHost", host)
            identity, key = identities[0]
            opened = datetime.now(UTC)
            with activate_session(
                BucketSession.open_resumed(
                    bucket_id=str(identity.binding.profile_id),
                    dek=key,
                    idle_minutes=15,
                    opened_at=opened,
                    idle_deadline=opened + timedelta(minutes=15),
                    absolute_deadline=opened + timedelta(minutes=240),
                    storage_root=root,
                )
            ):
                record = load_test_profile_record(identity.binding.profile_id, root=root)
            operation = OperationRequest(
                definition_id="user-profile.field-mutation",
                subject_ref=f"profile:{identity.binding.profile_id}",
                payload=ProfileFieldMutationOperationRequest(
                    profile_id=identity.binding.profile_id,
                    expected_revision=record.record_revision,
                    expected_content_digest=record.content_digest,
                    path=PROFILE_OUTPUT_LANGUAGE_PATH,
                    value="es",
                ),
            )
            worker = owners[0].operation_worker()
            submitted = worker.submit(sessions[0].session_id, operation, frontend=OperationFrontendProjection.MCP)
            before = asyncio.run(OperationJournalRepository(storage_root=root).load(submitted.receipt.operation_id))
            assert before.lifecycle is OperationLifecycle.CREATED

            if running:
                worker.start(
                    sessions[0].session_id, submitted.receipt.operation_id, frontend=OperationFrontendProjection.MCP
                )
                assert commit_entered.wait(timeout=5)
                entered = asyncio.run(
                    OperationJournalRepository(storage_root=root).load(submitted.receipt.operation_id)
                )
                assert entered.executor_entered_at is not None
            if session_end:
                stop.request(RuntimeExitReason.SESSION_END_SETTLE)
            if running:
                with ThreadPoolExecutor(max_workers=1) as drain_thread:
                    pending = drain_thread.submit(profiles.drain, deadline=time.monotonic() + 15)
                    try:
                        assert win32event.WaitForSingleObject(handles[0], 5000) == win32event.WAIT_OBJECT_0
                    finally:
                        release_commit.set()
                    result = pending.result(timeout=15)
            else:
                result = profiles.drain(deadline=time.monotonic() + 15)
            assert result.uncontained == result.unsettled == ()
            assert not result.lacks_settlement_evidence
            if session_end:
                assert result.receipts == ()
                assert result.missing_receipts == result.parent_settled_profiles
                assert len(result.parent_settled_profiles) == 2
            else:
                assert len(result.receipts) == 2
                assert result.missing_receipts == ()
            # A settled retry reports the original native receipts; it cannot
            # turn an emptied host map into a new empty shutdown success.
            assert profiles.drain(deadline=time.monotonic() + 1) == result
            profiles.close()
            assert profiles.drain(deadline=time.monotonic() + 1) == result
            assert stop.is_set()
            if not session_end:
                assert any(submitted.receipt.operation_id in receipt.recovery_required for receipt in result.receipts)
            for handle in handles:
                assert win32event.WaitForSingleObject(handle, 5000) == win32event.WAIT_OBJECT_0
            with pytest.raises(RuntimeRefusalError):
                worker.status()
            after = asyncio.run(OperationJournalRepository(storage_root=root).load(submitted.receipt.operation_id))
            if session_end:
                assert after.lifecycle is OperationLifecycle.TERMINAL
                assert after.terminal_condition is OperationTerminalCondition.INTERRUPTED
            else:
                assert after.lifecycle is OperationLifecycle.CREATED
                assert after.terminal_condition is None
            assert after.effect is (OperationEffect.UNKNOWN if running else OperationEffect.NONE)
        finally:
            release_commit.set()
            for owner in owners:
                owner.close()
                owner.settle()
            for handle in handles:
                win32api.CloseHandle(handle)
