"""Native worker drain reports recoverable intent and contains its process."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.master_key.active_session import activate_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import load_test_profile_record
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import AccessAction
from cadrumo.application.user_profile.operations import ProfileFieldMutationOperationRequest
from cadrumo.core.operations import OperationEffect, OperationLifecycle
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from .test_profile_worker_operations import BoundaryAuthority

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_drain_contains_worker_and_preserves_created_operation_for_recovery(tmp_path: Path) -> None:
    import win32api
    import win32con
    import win32event

    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        authority = BoundaryAuthority(deny_commit=False)
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
        process_handle = worker._process._handle
        assert process_handle is not None
        current_process = win32api.GetCurrentProcess()
        retained_process_handle = win32api.DuplicateHandle(
            current_process,
            process_handle,
            current_process,
            0,
            False,
            win32con.DUPLICATE_SAME_ACCESS,
        )
        try:
            assert win32event.WaitForSingleObject(retained_process_handle, 0) == win32event.WAIT_TIMEOUT
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
                profile_record = load_test_profile_record(identity.binding.profile_id, root=root)
            admitted = lease(identity)
            worker.install(admitted, bytearray(key))
            request = OperationRequest(
                definition_id="user-profile.field-mutation",
                subject_ref=f"profile:{identity.binding.profile_id}",
                payload=ProfileFieldMutationOperationRequest(
                    profile_id=identity.binding.profile_id,
                    expected_revision=profile_record.record_revision,
                    expected_content_digest=profile_record.content_digest,
                    path=PROFILE_OUTPUT_LANGUAGE_PATH,
                    value="es",
                ),
            )
            receipt = worker.submit(admitted.session_id, request, frontend=OperationFrontendProjection.MCP).receipt
            before = asyncio.run(OperationJournalRepository(storage_root=root).load(receipt.operation_id))
            assert before.lifecycle is OperationLifecycle.CREATED

            drained = worker.drain()
            assert drained.identity == identity
            # The stop request can arrive after the receipt but before the worker releases its output guard.
            assert set(drained.unresolved) <= {receipt.operation_id}
            assert drained.recovery_required == (receipt.operation_id,)
            assert win32event.WaitForSingleObject(retained_process_handle, 5000) == win32event.WAIT_OBJECT_0
            with pytest.raises(RuntimeRefusalError):
                worker.require_alive()
            with pytest.raises(RuntimeRefusalError):
                worker.status()

            after = asyncio.run(OperationJournalRepository(storage_root=root).load(receipt.operation_id))
            assert after.lifecycle is OperationLifecycle.CREATED
            assert after.terminal_condition is None
            assert after.effect is OperationEffect.NONE
            assert authority.calls and set(authority.calls) == {AccessAction.SUBMIT}
        finally:
            worker.close()
            worker.settle()
            win32api.CloseHandle(retained_process_handle)
