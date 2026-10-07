"""Native worker composition uses the installed canonical operation registry."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path
from threading import Event, RLock
from typing import NoReturn
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, changed, lease, worker_profiles
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.leases import operation_conflict_scope_reference
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from cadrumo.application.runtime.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessAllowed, AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.runtime.session_owner import ProfileWorkerSessionOwner

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def _no_activity_authority(_: object) -> NoReturn:
    raise AssertionError("activity observation must not request credentials or authority")


def _activity_owner(worker: ProfileWorkerProcess, root: Path) -> ProfileWorkerSessionOwner:
    owner = ProfileWorkerSessionOwner(
        worker.identity,
        storage_root=root,
        observe=_no_activity_authority,
        human_secret=_no_activity_authority,
        guard=RLock(),
    )
    owner._worker = worker
    return owner


def _profile_baseline(profile_id: object) -> tuple[int, str]:
    """Read the real encrypted record before handing custody to a native worker."""
    _, decode = profile_authority_contexts()
    authenticate_profile_for_invocation(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=decode,
    )
    try:
        record = ProfileRecordRepository.for_current_session(str(profile_id), profile_decode_context=decode).load(
            str(profile_id)
        )
        return record.record_revision, record.content_digest
    finally:
        close_active_bucket_session()


def test_worker_hosts_the_canonical_operation_services_and_rechecks_custody(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        worker = ProfileWorkerProcess(identity, storage_root=root)
        try:
            admitted = lease(identity)
            worker.install(admitted, bytearray(key))
            definition = "user-profile.field-mutation"
            expected = build_production_operation_registry().lookup_public_contract(definition)
            assert worker.describe(admitted.session_id, definition).contract == expected
            with pytest.raises(AutomationCustodyError):
                worker.describe(uuid4(), definition)
            with pytest.raises(AutomationCustodyError):
                worker.describe(admitted.session_id, "user-profile.automation-approve")
            worker.retire(admitted.session_id)
            with pytest.raises(AutomationCustodyError):
                worker.describe(admitted.session_id, definition)
        finally:
            worker.close()


class BoundaryAuthority:
    """Explicit authorization fault port; encryption, native transport and writes are real."""

    def __init__(self, *, deny_commit: bool) -> None:
        self.deny_commit = deny_commit
        self.deny_observe = False
        self.deny_resume = False
        self.calls: list[AccessAction] = []
        self.guard = RLock()
        self.attempted = Event()

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
        if isinstance(request, WorkerResponseScopeRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        self.attempted.set()
        with self.guard:
            self.calls.append(request.request.action)
            if self.deny_commit and request.request.action is AccessAction.COMMIT:
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
            if self.deny_observe and request.request.action is AccessAction.OBSERVE:
                raise ProfileAccessRefusedError(AccessDenialCode.DISCLOSURE_DENIED)
            if self.deny_resume and request.request.action is AccessAction.RESUME:
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
            yield AccessAllowed(
                profile_id=request.request.profile_id,
                session_id=request.session_id,
                expires_at=now() + timedelta(seconds=20),
            )

    def automation_inventory(
        self, request: WorkerAutomationInventoryRequest
    ) -> AbstractContextManager[WorkerAutomationInventoryAllowed]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_preflight(self, request: WorkerApprovalRequest) -> None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def approval_publication(
        self, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


@pytest.mark.parametrize("deny_commit", [False, True])
def test_installed_worker_uses_native_guards_for_real_profile_mutation(tmp_path: Path, deny_commit: bool) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        expected_revision, expected_digest = _profile_baseline(identity.binding.profile_id)
        authority = BoundaryAuthority(deny_commit=deny_commit)
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
        activity = _activity_owner(worker, root)
        try:
            admitted = lease(identity)
            worker.install(admitted, bytearray(key))
            assert activity.in_flight_operation_count(deadline=time.monotonic() + 3) == 0
            with worker._lock:
                assert activity.in_flight_operation_count(deadline=time.monotonic() + 0.05) is None
                assert not worker.stopping
            assert activity._activity_guard.acquire(timeout=3)
            activity._activity_guard.release()
            request = OperationRequest(
                definition_id="user-profile.field-mutation",
                subject_ref=f"profile:{identity.binding.profile_id}",
                payload=ProfileFieldMutationOperationRequest(
                    profile_id=identity.binding.profile_id,
                    expected_revision=expected_revision,
                    expected_content_digest=expected_digest,
                    path=PROFILE_OUTPUT_LANGUAGE_PATH,
                    value="es",
                ),
                idempotency_key="profile-language-mutation",
            )
            receipt = worker.submit(admitted.session_id, request, frontend=OperationFrontendProjection.MCP).receipt
            observed_lease = asyncio.run(
                OperationLeaseFilesystemRepository(storage_root=root).inspect(
                    operation_conflict_scope_reference(
                        definition_id=request.definition_id, subject_ref=request.subject_ref
                    ),
                    receipt.operation_id,
                    observed_at=now(),
                )
            )
            assert observed_lease.current is not None
            assert observed_lease.current.owner_id == identity.operation_owner_id
            assert worker.status().in_flight_operations == 1
            assert activity.in_flight_operation_count(deadline=time.monotonic() + 3) == 1
            with pytest.raises(ProfileAccessRefusedError):
                worker.start(uuid4(), receipt.operation_id)
            worker.retire(admitted.session_id)
            admitted = lease(identity)
            worker.install(admitted, bytearray(key))
            authority.deny_resume = True
            with pytest.raises(ProfileAccessRefusedError):
                worker.resume(admitted.session_id, receipt.operation_id, frontend=OperationFrontendProjection.MCP)
            authority.deny_resume = False
            worker.resume(admitted.session_id, receipt.operation_id, frontend=OperationFrontendProjection.MCP)
            observation_request = OperationObservationRequestV1(
                operation_id=receipt.operation_id, after_cursor=0, page_limit=32
            )
            deadline = time.monotonic() + 5
            while True:
                observation = worker.observe(admitted.session_id, observation_request).observation
                assert isinstance(observation, OperationObservationSuccessV1), observation
                if observation.projection.terminal_condition is not None:
                    break
                assert time.monotonic() < deadline
                time.sleep(0.01)
            snapshot = asyncio.run(OperationJournalRepository(storage_root=root).load(receipt.operation_id))
            expected = OperationTerminalCondition.REFUSED if deny_commit else OperationTerminalCondition.SUCCEEDED
            assert snapshot.terminal_condition is expected
            assert authority.calls[0] is AccessAction.SUBMIT
            assert authority.calls.count(AccessAction.START) >= 2
            assert authority.calls.count(AccessAction.COMMIT) == 1
            assert observation.projection.terminal_condition is expected
            assert activity.in_flight_operation_count(deadline=time.monotonic() + 3) == 0
            reconnected = lease(identity)
            worker.install(reconnected, bytearray(key))
            worker.retire(admitted.session_id)
            replay = worker.submit(reconnected.session_id, request, frontend=OperationFrontendProjection.MCP)
            assert replay.receipt == receipt
            assert worker.observe(reconnected.session_id, observation_request).observation == observation
            with pytest.raises(ProfileAccessRefusedError):
                worker.submit(
                    reconnected.session_id,
                    request.model_copy(update={"payload": request.payload.model_copy(update={"value": "en"})}),
                    frontend=OperationFrontendProjection.MCP,
                )
            authority.deny_observe = True
            with pytest.raises(ProfileAccessRefusedError) as refused:
                worker.observe(reconnected.session_id, observation_request)
            assert refused.value.reason is AccessDenialCode.DISCLOSURE_DENIED
            assert reconnected.session_id in worker.status().sessions
        finally:
            worker.close()
            worker.settle()
        authority.deny_observe = False
        replacement_identity = changed(identity, worker_id=uuid4(), runtime_boot_id=uuid4())
        replacement = ProfileWorkerProcess(replacement_identity, storage_root=root, authorization=authority)
        try:
            fresh = lease(replacement_identity)
            replacement.install(fresh, bytearray(key))
            assert (
                replacement.submit(fresh.session_id, request, frontend=OperationFrontendProjection.MCP).receipt
                == receipt
            )
            assert replacement.observe(fresh.session_id, observation_request).observation == observation
            _, ((_, _), (foreign_identity, foreign_key)) = profiles
            foreign = ProfileWorkerProcess(foreign_identity, storage_root=root, authorization=authority)
            try:
                foreign_session = lease(foreign_identity)
                foreign.install(foreign_session, bytearray(foreign_key))
                with pytest.raises(ProfileAccessRefusedError):
                    foreign.observe(foreign_session.session_id, observation_request)
                assert foreign_session.session_id in foreign.status().sessions
            finally:
                foreign.close()
                foreign.settle()
        finally:
            replacement.close()
            replacement.settle()
        _, decode = profile_authority_contexts()
        authenticate_profile_for_invocation(
            name=str(identity.binding.profile_id),
            passphrase_callback=lambda: PROFILE_INPUT,
            profile_decode_context=decode,
        )
        try:
            record = ProfileRecordRepository.for_current_session(
                identity.binding.profile_id, profile_decode_context=decode
            ).load(identity.binding.profile_id)
            assert (record_to_path_values(record).get(PROFILE_OUTPUT_LANGUAGE_PATH) == "es") is not deny_commit
        finally:
            close_active_bucket_session()


def test_custody_control_retires_while_operation_waits_for_profile_authority(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        expected_revision, expected_digest = _profile_baseline(identity.binding.profile_id)
        authority = BoundaryAuthority(deny_commit=False)
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
        try:
            admitted = lease(identity)
            worker.install(admitted, bytearray(key))
            request = OperationRequest(
                definition_id="user-profile.field-mutation",
                subject_ref=f"profile:{identity.binding.profile_id}",
                payload=ProfileFieldMutationOperationRequest(
                    profile_id=identity.binding.profile_id,
                    expected_revision=expected_revision,
                    expected_content_digest=expected_digest,
                    path=PROFILE_OUTPUT_LANGUAGE_PATH,
                    value="es",
                ),
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                with authority.guard:
                    pending = pool.submit(
                        worker.submit, admitted.session_id, request, frontend=OperationFrontendProjection.MCP
                    )
                    assert authority.attempted.wait(5)
                    worker.retire(admitted.session_id)
                    assert not worker.status().sessions
                with pytest.raises(AutomationCustodyError):
                    pending.result(timeout=5)
            assert authority.calls == [AccessAction.SUBMIT]
            worker.require_alive()
        finally:
            worker.close()
            worker.settle()
