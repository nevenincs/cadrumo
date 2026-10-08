"""Session-end settlement of a real Windows worker and its durable operation."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import NoReturn

import pytest

from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.application.operations.models import OperationReconciliationOutcome, OperationRequest
from cadrumo.application.operations.persistence.events import OperationReconciliationEvent
from cadrumo.application.operations.persistence.leases import operation_conflict_scope_reference
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeExitReason, RuntimeRefusalError
from cadrumo.application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.profile_host import RuntimeProfileHost
from cadrumo.entrypoints.runtime.shutdown import RuntimeStop

from .test_profile_worker_operations import BoundaryAuthority, _no_activity_authority, _profile_baseline

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def _no_credentials() -> NoReturn:
    raise AssertionError("session-end settlement must not open credentials")


def test_session_end_contains_native_worker_before_settling_its_live_lease(tmp_path: Path) -> None:
    import win32api
    import win32con
    import win32event

    with worker_profiles(tmp_path) as (root, ((original, key), _)):
        profile_id = original.binding.profile_id
        revision, digest = _profile_baseline(profile_id)
        stop = RuntimeStop()
        profiles = RuntimeProfileConnections(
            storage_root=root, storage_identity="test", runtime_boot_id=original.runtime_boot_id, stop=stop
        )
        registry = profiles.prepare_registry()
        host = RuntimeProfileHost(
            store=AutomationControlStore(root=root, binding=original.binding, secrets_store_factory=_no_credentials),
            runtime_boot_id=profiles.boot,
            registry=registry,
            connected=_no_activity_authority,
            logins=tuple,
            admitting=profiles._private_work_available,
        )
        worker = ProfileWorkerProcess(
            host.owner.identity, storage_root=root, authorization=BoundaryAuthority(deny_commit=False)
        )
        host.owner._worker = worker
        profiles._profiles[profile_id] = host
        retained_process = win32api.OpenProcess(win32con.SYNCHRONIZE, False, worker._process.pid)
        try:
            assert win32event.WaitForSingleObject(retained_process, 0) == win32event.WAIT_TIMEOUT
            admitted = lease(worker.identity)
            worker.install(admitted, bytearray(key))
            request = OperationRequest(
                definition_id="user-profile.field-mutation",
                subject_ref=f"profile:{profile_id}",
                payload=ProfileFieldMutationOperationRequest(
                    profile_id=profile_id,
                    expected_revision=revision,
                    expected_content_digest=digest,
                    path=PROFILE_OUTPUT_LANGUAGE_PATH,
                    value="es",
                ),
            )
            receipt = worker.submit(admitted.session_id, request, frontend=OperationFrontendProjection.MCP).receipt
            assert profiles.in_flight_operation_count(timeout=3) == 1
            assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=3)
            assert not stop.is_set()
            stop.request(RuntimeExitReason.SESSION_END_SETTLE)
            started = time.monotonic()
            result = profiles.drain(deadline=started + 15)
            assert time.monotonic() - started < 3.5
            assert not result.lacks_settlement_evidence
            assert result.parent_settled_profiles == (profile_id,)
            assert result.uncontained == result.unsettled == ()
            assert win32event.WaitForSingleObject(retained_process, 0) == win32event.WAIT_OBJECT_0
            with pytest.raises(RuntimeRefusalError):
                worker.require_alive()
            snapshot = asyncio.run(OperationJournalRepository(storage_root=root).load(receipt.operation_id))
            assert snapshot.terminal_condition is OperationTerminalCondition.INTERRUPTED
            assert snapshot.effect is OperationEffect.NONE
            assert any(
                isinstance(event, OperationReconciliationEvent)
                and event.outcome is OperationReconciliationOutcome.ORPHANED
                for event in snapshot.events
            )
            observed = asyncio.run(
                OperationLeaseFilesystemRepository(storage_root=root).inspect(
                    operation_conflict_scope_reference(
                        definition_id=request.definition_id, subject_ref=request.subject_ref
                    ),
                    receipt.operation_id,
                    observed_at=now(),
                )
            )
            assert observed.current is None
        finally:
            worker.close()
            worker.settle()
            win32api.CloseHandle(retained_process)
