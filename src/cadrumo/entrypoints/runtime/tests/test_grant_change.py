"""Authenticated grant-change requests still require fresh human consent."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.automation_requester import AutomationRequesterJourney
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import OperationResultProjectionSuccessV1
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.enrollment_access import RuntimeEnrollmentPrepare, RuntimeEnrollmentReconcile
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.user_profile.access_contracts import AccessAction
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.time.clock import now

from ..profile_connections import RuntimeProfileConnections
from .test_automation_enrollment import _connect, _login, _LoginObservation, _result, _submit_operation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows runtime workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize("kind", [EnrollmentKind.ROTATE, EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE])
def test_exact_key_requests_reviewed_grant_change(tmp_path: Path, kind: EnrollmentKind) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        original_id = uuid4()
        subject.service.request(original_id, subject.proposal)
        original = subject.approve(original_id)
        record = next(item for item in subject.store.enrollment_state().requests if item.request_id == original_id)
        original_secret = subject.owner.delivery.endpoint.possession(record)
        assert original_secret is not None and original.key_id is not None
        grant = subject.store.snapshot().grants[0]
        profile_id = grant.binding.profile_id
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    raw, human, foreign = _connect(endpoint), _connect(endpoint), _connect(endpoint)
                    for connection in (raw, human, foreign):
                        cleanup.callback(connection.close)
                    api = RuntimeFrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
                    api.login_api_key(bytearray(original_secret.get_secret_value()), timeout=25)
                    human_id = _login(human, profile_id, method="password", proof=PROFILE_INPUT.encode())
                    for connection, session_id in ((foreign, api.session_id), (human, human_id)):
                        refused = connection.enrollment_prepare(
                            RuntimeEnrollmentPrepare(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                frontend=OperationFrontendProjection.CLI,
                                session_id=session_id,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                        assert isinstance(refused, RuntimeAccessRefusal)
                    client = api.prepare_grant_change(subject.client_native)
                    assert client.prepared.client_id == grant.client_id
                    proposal = EnrollmentProposal(
                        kind=kind,
                        scope=changed(grant.scope, actions=frozenset({AccessAction.SUBMIT}))
                        if kind is EnrollmentKind.CHANGE_SCOPE
                        else grant.scope,
                        expires_at=grant.expires_at + timedelta(days=30)
                        if kind is EnrollmentKind.RENEW
                        else grant.expires_at,
                        key_expires_at=now() + timedelta(days=15) if kind is EnrollmentKind.ROTATE else None,
                        unattended=grant.unattended,
                        allow_os_lock=grant.allow_os_lock,
                        target_grant_id=grant.grant_id,
                        target_key_id=original.key_id if kind is EnrollmentKind.ROTATE else None,
                    )
                    with pytest.raises(AutomationCustodyError):
                        client.submit(changed(proposal, target_grant_id=uuid4()))
                    fresh_clients: list[RuntimeFrontendClient] = []
                    fresh_connections: list[VerifiedRuntimeConnection] = []

                    def reconcile(
                        submission: AutomationReceiptProjection, *, timeout: float
                    ) -> AutomationReceiptProjection:
                        # The old API session cannot reconcile its own changed
                        # generation. A separate connection proves the exact
                        # delivered candidate (or unchanged key) afresh.
                        deadline = time.monotonic() + timeout
                        fresh_raw = _connect(endpoint)
                        fresh = RuntimeFrontendClient(
                            fresh_raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                        )
                        try:
                            proof = (
                                client.read_delivered_credential().get_secret_value()
                                if kind is EnrollmentKind.ROTATE
                                else original_secret.get_secret_value()
                            )
                            fresh.login_api_key(bytearray(proof), timeout=deadline - time.monotonic())
                            observed = fresh.reconcile_enrollment(
                                submission.request_id, timeout=deadline - time.monotonic()
                            )
                        except BaseException:
                            fresh.close()
                            raise
                        fresh_clients.append(fresh)
                        fresh_connections.append(fresh_raw)
                        return observed

                    journey = AutomationRequesterJourney(client, timeout=90, reconcile=reconcile)
                    submitted = journey.submit(proposal)
                    assert submitted.stage is EnrollmentStage.REQUESTED
                    with pytest.raises(RuntimeFrontendRefusedError):
                        api.reconcile_enrollment(submitted.request_id)
                    # A copied session/request pair authenticates neither a
                    # different native connection nor the approving human.
                    for connection, session_id in ((foreign, api.session_id), (human, human_id)):
                        assert session_id is not None
                        refused_receipt = connection.enrollment_inspect(
                            RuntimeEnrollmentReconcile(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=session_id,
                                enrollment_request_id=submitted.request_id,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                        assert isinstance(refused_receipt, RuntimeAccessRefusal)
                    assert subject.store.snapshot().grants[0] == grant
                    assert len(subject.store.snapshot().keys) == 1
                    done = Event()

                    def serve_requester() -> None:
                        while not done.is_set() and journey.completion is None:
                            journey.step()

                    polling = pool.submit(serve_requester)
                    try:
                        contract, operation, observed = _submit_operation(
                            human,
                            profile_id=profile_id,
                            session_id=human_id,
                            definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
                            payload=AutomationOperationRequest(
                                profile_id=profile_id,
                                request_id=submitted.request_id,
                                review_digest=submitted.review_digest,
                            ),
                            password=PROFILE_INPUT.encode(),
                        )
                        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, (
                            observed.projection.terminal_condition,
                            observed.projection.failure_error_code,
                            tuple(item.stage for item in subject.store.enrollment_state().requests),
                        )
                        completed = (
                            OperationResultProjectionSuccessV1[AutomationReceiptProjection]
                            .model_validate_json(
                                json.dumps(
                                    _result(
                                        human,
                                        profile_id=profile_id,
                                        session_id=human_id,
                                        contract=contract,
                                        submitted=operation,
                                        observed=observed,
                                    ).document
                                )
                            )
                            .projection
                        )
                    finally:
                        approval_error = sys.exception()
                        if approval_error is not None:
                            done.set()
                        try:
                            polling.result(timeout=65)
                        except Exception as delivery_error:
                            if approval_error is not None:
                                raise BaseExceptionGroup(
                                    "approval and requester failed", [approval_error, delivery_error]
                                ) from None
                            raise
                    assert completed.stage is EnrollmentStage.COMPLETE
                    assert completed.grant_id == grant.grant_id
                    requester_done = journey.completion
                    assert requester_done is not None
                    assert requester_done.terminal == completed  # Independent oracle; never forwarded to requester.
                    assert len(fresh_clients) == 1
                    fresh = fresh_clients[0]
                    cleanup.callback(fresh.close)
                    current = subject.store.snapshot().grants[0]
                    assert current.scope == proposal.scope and current.expires_at == proposal.expires_at
                    if kind is EnrollmentKind.ROTATE:
                        assert current.generation == grant.generation
                        # Read only the candidate delivered to this exact
                        # protected client, then prove it at fresh admission.
                        # The human's result is not forwarded to the requester.
                        assert requester_done.credential is not None
                        assert requester_done.credential.key_id == completed.key_id
                        assert (
                            client.read_delivered_credential().get_secret_value() != original_secret.get_secret_value()
                        )
                        predecessor = next(k for k in subject.store.snapshot().keys if k.key_id == original.key_id)
                        assert predecessor.expires_at <= now() + timedelta(seconds=60)
                    else:
                        assert current.generation == grant.generation + 1
                        assert completed.key_id is None and completed.credential_reference is None
                        try:
                            status = api.status()
                        except RuntimeFrontendRefusedError as error:
                            assert error.reason == "connection_mismatch"
                        else:
                            assert status.status.denial is not None
                        with pytest.raises((AutomationCustodyError, RuntimeFrontendRefusedError)):
                            api.prepare_grant_change(subject.client_native)
                        assert requester_done.credential is None
                    assert fresh.session_id != api.session_id
                    recovered = fresh.reconcile_enrollment(submitted.request_id)
                    assert recovered == completed
                    with pytest.raises(RuntimeFrontendRefusedError):
                        fresh.reconcile_enrollment(uuid4())
                    # Reconciliation never restores the old volatile offer or
                    # authorizes receipt disclosure after current-session lock.
                    fresh_session = fresh.session_id
                    assert fresh_session is not None
                    fresh.lock()
                    locked_reply = fresh_connections[0].enrollment_inspect(
                        RuntimeEnrollmentReconcile(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=fresh_session,
                            enrollment_request_id=submitted.request_id,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(locked_reply, RuntimeAccessRefusal)
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()
