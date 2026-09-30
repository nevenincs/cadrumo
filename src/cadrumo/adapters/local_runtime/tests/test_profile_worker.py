"""Real installed workers and synthetic encrypted profiles, without a native key store."""

from __future__ import annotations

import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, ExitStack, contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationId, OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from cadrumo.application.runtime.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest
from cadrumo.application.user_profile.access_contracts import (
    AccessAllowed,
    AccessDenialCode,
    AccessSession,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.operations import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.bucket_pointer import read_pointer
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from ..profile_worker import ProfileWorkerProcess
from .profile_worker_support import PROFILE_INPUT, changed, lease, worker_profiles

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.fixture
def profiles(tmp_path: Path):
    with worker_profiles(tmp_path) as subjects:
        yield subjects


class _AllowWorkerOperations:
    """Permit only the operation checks exercised by this installed-worker case."""

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed]:
        if isinstance(request, WorkerResponseScopeRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
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


def _login_human(profile_id: UUID) -> None:
    _, decode = profile_authority_contexts()
    login_profile(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=decode,
    )


def _record_snapshot(profile_id: UUID) -> tuple[int, str, dict[str, str]]:
    _, decode = profile_authority_contexts()
    login_profile(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=decode,
    )
    try:
        record = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
        return record.record_revision, record.content_digest, record_to_path_values(record)
    finally:
        close_active_bucket_session()


def _wait_for_terminal(worker: ProfileWorkerProcess, session_id: UUID, operation_id: OperationId):
    request = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32)
    deadline = time.monotonic() + 10
    while True:
        observation = worker.observe(session_id, request).observation
        assert isinstance(observation, OperationObservationSuccessV1), observation
        projection = observation.projection
        if projection.terminal_condition is not None:
            return projection
        assert time.monotonic() < deadline, f"operation {operation_id} did not settle"
        time.sleep(0.02)


def _field_request(
    profile_id: UUID, *, revision: int, digest: str, value: str, idempotency_key: str
) -> OperationRequest[ProfileFieldMutationOperationRequest]:
    return OperationRequest(
        definition_id="user-profile.field-mutation",
        subject_ref=f"profile:{profile_id}",
        payload=ProfileFieldMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=revision,
            expected_content_digest=digest,
            path=PROFILE_OUTPUT_LANGUAGE_PATH,
            value=value,
        ),
        idempotency_key=idempotency_key,
    )


def test_concurrent_profiles_never_retarget_and_disconnect_is_isolated(profiles) -> None:
    root, ((first, first_key), (second, second_key)) = profiles
    with ExitStack() as cleanup:
        a = ProfileWorkerProcess(first, storage_root=root)
        cleanup.callback(a.close)
        b = ProfileWorkerProcess(second, storage_root=root)
        cleanup.callback(b.close)
        a_lease, b_lease = lease(first), lease(second)
        a_buffer, b_buffer = bytearray(first_key), bytearray(second_key)
        a.install(a_lease, a_buffer)
        b.install(b_lease, b_buffer)
        assert not any(a_buffer) and not any(b_buffer)
        assert a.status().sessions == (a_lease.session_id,)
        assert b.status().sessions == (b_lease.session_id,)
        # A foreign profile's valid DEK cannot switch this process to B.
        with pytest.raises(AutomationCustodyError):
            a.install(b_lease, bytearray(second_key))
        assert a.status().sessions == (a_lease.session_id,)
        assert b.status().sessions == (b_lease.session_id,)
        b.retire(b_lease.session_id)
        assert not b.status().sessions
        fresh = lease(second)
        b.install(fresh, bytearray(second_key))
        assert b.status().sessions == (fresh.session_id,)


def test_worker_rejects_wrong_dek_before_acknowledging_custody(profiles) -> None:
    root, ((identity, key), (_other, wrong_key)) = profiles
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        secret = bytearray(wrong_key)
        with pytest.raises(AutomationCustodyError):
            worker.install(lease(identity), secret)
        assert not any(secret)
        admitted = lease(identity)
        worker.install(admitted, bytearray(key))
        assert worker.status().sessions == (admitted.session_id,)
    finally:
        worker.close()


def test_refresh_and_idle_expiry_release_only_the_affected_leases(profiles) -> None:
    root, ((identity, key), _) = profiles
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        short, independent = lease(identity, seconds=2), lease(identity)
        worker.install(short, bytearray(key))
        worker.install(independent, bytearray(key))
        refreshed = changed(
            short, issued_at=now(), issued_monotonic=time.monotonic(), expires_at=now() + timedelta(seconds=4)
        )
        worker.refresh(refreshed)
        worker.retire(independent.session_id)
        assert worker.status().sessions == (short.session_id,)
        deadline = time.monotonic() + 6
        while worker.status().sessions and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not worker.status().sessions
        with pytest.raises(AutomationCustodyError):
            worker.refresh(
                changed(
                    refreshed,
                    issued_at=now(),
                    issued_monotonic=time.monotonic(),
                    expires_at=now() + timedelta(seconds=30),
                )
            )
    finally:
        worker.close()


def test_password_candidate_does_not_replace_agents_or_select_another_profile(profiles) -> None:
    root, ((identity, key), _) = profiles
    selected = read_pointer(root)
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        api = lease(identity)
        worker.install(api, bytearray(key))
        password = bytearray(PROFILE_INPUT.encode())
        with worker.authenticate_human(password) as outcome:
            assert outcome.bucket_id == str(identity.binding.profile_id) and not outcome.session_persisted
            assert worker.status().sessions == (api.session_id,)
            human = AccessSession(
                session_id=uuid4(),
                binding=identity.binding,
                profile_lock_generation=0,
                runtime_boot_id=identity.runtime_boot_id,
                connection_id=uuid4(),
                client_id=uuid4(),
                kind=SessionKind.HUMAN,
                originating_login_id="synthetic-login",
                state=SessionState.ACTIVE,
                scope=api.scope,
                issued_at=now(),
                issued_monotonic=time.monotonic(),
                expires_at=min(outcome.idle_deadline, outcome.absolute_deadline),
            )
            worker.bind_human(human)
        assert not any(password)
        assert set(worker.status().sessions) == {api.session_id, human.session_id}
        worker.retire(human.session_id)
        assert worker.status().sessions == (api.session_id,)
        wrong = bytearray(b"wrong-synthetic-worker-input")
        with pytest.raises(AutomationCustodyError), worker.authenticate_human(wrong):
            pytest.fail("incorrect password must not create a candidate")
        assert not any(wrong)
        assert worker.status().sessions == (api.session_id,)
        assert read_pointer(root) == selected
    finally:
        worker.close()


def test_simultaneous_profile_operations_survive_human_switch_and_stale_revision_conflict(profiles) -> None:
    root, ((identity_a, key_a), (identity_b, key_b)) = profiles
    baseline_a = _record_snapshot(identity_a.binding.profile_id)
    baseline_b = _record_snapshot(identity_b.binding.profile_id)
    _login_human(identity_a.binding.profile_id)
    assert read_pointer(root).bucket_id == str(identity_a.binding.profile_id)

    authority = _AllowWorkerOperations()
    with ExitStack() as cleanup:
        worker_a = ProfileWorkerProcess(identity_a, storage_root=root, authorization=authority)
        cleanup.callback(worker_a.close)
        worker_b = ProfileWorkerProcess(identity_b, storage_root=root, authorization=authority)
        cleanup.callback(worker_b.close)
        lease_a, lease_b = lease(identity_a), lease(identity_b)
        worker_a.install(lease_a, bytearray(key_a))
        worker_b.install(lease_b, bytearray(key_b))

        # A real human login changes the shared default pointer while both workers retain
        # their immutable bindings and installed custody.
        _login_human(identity_b.binding.profile_id)
        assert read_pointer(root).bucket_id == str(identity_b.binding.profile_id)

        request_a = _field_request(
            identity_a.binding.profile_id,
            revision=baseline_a[0],
            digest=baseline_a[1],
            value="es",
            idempotency_key="agent-a-language-write",
        )
        request_b = _field_request(
            identity_b.binding.profile_id,
            revision=baseline_b[0],
            digest=baseline_b[1],
            value="ca",
            idempotency_key="agent-b-language-write",
        )
        submitted_a = worker_a.submit(lease_a.session_id, request_a, frontend=OperationFrontendProjection.MCP)
        submitted_b = worker_b.submit(lease_b.session_id, request_b, frontend=OperationFrontendProjection.MCP)
        with ThreadPoolExecutor(max_workers=2) as pool:
            started = (
                pool.submit(worker_a.start, lease_a.session_id, submitted_a.receipt.operation_id),
                pool.submit(worker_b.start, lease_b.session_id, submitted_b.receipt.operation_id),
            )
            for future in started:
                future.result(timeout=10)

        result_a = _wait_for_terminal(worker_a, lease_a.session_id, submitted_a.receipt.operation_id)
        result_b = _wait_for_terminal(worker_b, lease_b.session_id, submitted_b.receipt.operation_id)
        assert result_a.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert result_b.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert read_pointer(root).bucket_id == str(identity_b.binding.profile_id)

        stale_request = _field_request(
            identity_a.binding.profile_id,
            revision=baseline_a[0],
            digest=baseline_a[1],
            value="en",
            idempotency_key="agent-a-stale-language-write",
        )
        stale = worker_a.submit(lease_a.session_id, stale_request, frontend=OperationFrontendProjection.MCP)
        worker_a.start(lease_a.session_id, stale.receipt.operation_id)
        stale_result = _wait_for_terminal(worker_a, lease_a.session_id, stale.receipt.operation_id)
        assert stale_result.terminal_condition is OperationTerminalCondition.FAILED
        assert stale_result.failure_error_code == "FAIL_PROFILE_RECORD_CONFLICT"

    observed_a = _record_snapshot(identity_a.binding.profile_id)
    observed_b = _record_snapshot(identity_b.binding.profile_id)
    assert observed_a[0] > baseline_a[0]
    assert observed_a[2][PROFILE_OUTPUT_LANGUAGE_PATH] == "es"
    assert observed_b[0] > baseline_b[0]
    assert observed_b[2][PROFILE_OUTPUT_LANGUAGE_PATH] == "ca"
    _login_human(identity_b.binding.profile_id)
    assert read_pointer(root).bucket_id == str(identity_b.binding.profile_id)
