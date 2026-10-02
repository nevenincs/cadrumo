"""Runtime-wide shutdown drains published native workers before ownership ends."""

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, RLock
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.master_key.active_session import activate_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import load_test_profile_record
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeHumanProof
from cadrumo.application.user_profile.operations import ProfileFieldMutationOperationRequest
from cadrumo.core.operations import OperationEffect, OperationLifecycle
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost
from ..session_owner import ProfileWorkerSessionOwner
from .test_profile_worker_operations import BoundaryAuthority

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_runtime_drain_contains_all_workers_and_preserves_created_intent(tmp_path: Path) -> None:
    import win32api
    import win32con
    import win32event

    with worker_profiles(tmp_path) as (root, identities):
        stop = Event()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity="test-storage",
            runtime_boot_id=identities[0][0].runtime_boot_id,
            stop=stop,
        )
        handles: list[int] = []
        owners: list[ProfileWorkerSessionOwner] = []
        sessions = []
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
                    authorization=BoundaryAuthority(deny_commit=False),
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

            result = profiles.drain(deadline=time.monotonic() + 15)
            assert len(result.receipts) == 2
            assert result.missing_receipts == result.uncontained == result.unsettled == ()
            # A settled retry reports the original native receipts; it cannot
            # turn an emptied host map into a new empty shutdown success.
            assert profiles.drain(deadline=time.monotonic() + 1) == result
            profiles.close()
            assert profiles.drain(deadline=time.monotonic() + 1) == result
            assert stop.is_set()
            assert any(submitted.receipt.operation_id in receipt.recovery_required for receipt in result.receipts)
            for handle in handles:
                assert win32event.WaitForSingleObject(handle, 5000) == win32event.WAIT_OBJECT_0
            with pytest.raises(RuntimeRefusalError):
                worker.status()
            after = asyncio.run(OperationJournalRepository(storage_root=root).load(submitted.receipt.operation_id))
            assert after.lifecycle is OperationLifecycle.CREATED
            assert after.terminal_condition is None
            assert after.effect is OperationEffect.NONE
        finally:
            for owner in owners:
                owner.close()
                owner.settle()
            for handle in handles:
                win32api.CloseHandle(handle)
