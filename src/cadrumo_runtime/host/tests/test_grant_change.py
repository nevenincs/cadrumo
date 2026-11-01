"""Authenticated grant-change requests still require fresh human consent."""

from __future__ import annotations

import json
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import OperationResultProjectionSuccessV1
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AutomationGrant
from cadrumo.application.user_profile.automation_enrollment import AutomationReceiptProjection, EnrollmentStage
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.enrollment_access import EnrollmentPrepare, EnrollmentReconcile
from cadrumo_client.contracts.enrollment_proposal import EnrollmentKind, EnrollmentProposal
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SessionRequest
from cadrumo_client.transport.automation_requester import AutomationRequesterJourney
from cadrumo_client.transport.enrollment_client import NativeEnrollmentClient
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.tests.delivered_credential import read_delivered_credential
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from .served_runtime import ServedRuntime, SyntheticLogin, connect_verified, serving_runtime
from .test_automation_enrollment import _login, _result, _submit_operation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows runtime workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@dataclass(frozen=True)
class _Change:
    kind: EnrollmentKind
    endpoint: WindowsEndpoint
    subject: AdministrationSubject
    grant: AutomationGrant
    original_key_id: UUID
    original_secret: bytes
    profile_id: UUID
    raw: VerifiedConnection
    human: VerifiedConnection
    foreign: VerifiedConnection


class _FreshReconciler:
    """Prove the exact delivered candidate (or unchanged key) on a separate connection."""

    def __init__(
        self,
        change: _Change,
        client: NativeEnrollmentClient,
        fresh_clients: list[FrontendClient],
        fresh_connections: list[VerifiedConnection],
    ) -> None:
        self._change = change
        self._client = client
        self._fresh_clients = fresh_clients
        self._fresh_connections = fresh_connections

    def __call__(self, submission: AutomationReceiptProjection, *, timeout: float) -> AutomationReceiptProjection:
        # The old API session cannot reconcile its own changed
        # generation. A separate connection proves the exact
        # delivered candidate (or unchanged key) afresh.
        change = self._change
        deadline = time.monotonic() + timeout
        fresh_raw = connect_verified(change.endpoint)
        fresh = FrontendClient(fresh_raw, profile_id=change.profile_id, frontend=OperationFrontendProjection.CLI)
        try:
            proof = (
                read_delivered_credential(self._client).get_secret_value()
                if change.kind is EnrollmentKind.ROTATE
                else change.original_secret
            )
            fresh.login_api_key(bytearray(proof), timeout=deadline - time.monotonic())
            observed = fresh.reconcile_enrollment(submission.request_id, timeout=deadline - time.monotonic())
        except BaseException:
            fresh.close()
            raise
        self._fresh_clients.append(fresh)
        self._fresh_connections.append(fresh_raw)
        return observed


def _request_grant_change(
    change: _Change,
) -> tuple[UUID, FrontendClient, UUID | None, NativeEnrollmentClient, EnrollmentProposal]:
    grant, kind, profile_id = change.grant, change.kind, change.profile_id
    # The person signs in first: a key reaches the profile only under a live sign-in.
    human_id = _login(change.human, profile_id, method="password", proof=PROFILE_INPUT.encode())
    api = FrontendClient(change.raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
    api.login_api_key(bytearray(change.original_secret), timeout=25)
    old_session = api.session_id
    for connection, session_id in ((change.foreign, api.session_id), (change.human, human_id)):
        refused = connection.enrollment_prepare(
            EnrollmentPrepare(
                request_id=uuid4(),
                profile_id=profile_id,
                frontend=OperationFrontendProjection.CLI,
                session_id=session_id,
            ),
            deadline=time.monotonic() + 5,
        )
        assert isinstance(refused, AccessRefusal)
    client = api.prepare_grant_change(change.subject.client_native)
    assert client.prepared.client_id == grant.client_id
    proposal = EnrollmentProposal(
        kind=kind,
        scope=changed(grant.scope, actions=frozenset({AccessAction.SUBMIT}))
        if kind is EnrollmentKind.CHANGE_SCOPE
        else grant.scope,
        expires_at=grant.expires_at + timedelta(days=30) if kind is EnrollmentKind.RENEW else grant.expires_at,
        key_expires_at=now() + timedelta(days=15) if kind is EnrollmentKind.ROTATE else None,
        unattended=grant.unattended,
        allow_os_lock=grant.allow_os_lock,
        target_grant_id=grant.grant_id,
        target_key_id=change.original_key_id if kind is EnrollmentKind.ROTATE else None,
    )
    with pytest.raises(AutomationCustodyError):
        client.submit(changed(proposal, target_grant_id=uuid4()))
    return human_id, api, old_session, client, proposal


def _submit_and_probe_copies(
    change: _Change,
    api: FrontendClient,
    human_id: UUID,
    client: NativeEnrollmentClient,
    proposal: EnrollmentProposal,
) -> tuple[AutomationRequesterJourney, AutomationReceiptProjection, list[FrontendClient], list[VerifiedConnection]]:
    fresh_clients: list[FrontendClient] = []
    fresh_connections: list[VerifiedConnection] = []
    reconcile = _FreshReconciler(change, client, fresh_clients, fresh_connections)
    journey = AutomationRequesterJourney(client, timeout=90, reconcile=reconcile)
    submitted = journey.submit(proposal)
    assert submitted.stage is EnrollmentStage.REQUESTED
    with pytest.raises(FrontendRefusedError):
        api.reconcile_enrollment(submitted.request_id)
    # A copied session/request pair authenticates neither a
    # different native connection nor the approving human.
    for connection, session_id in ((change.foreign, api.session_id), (change.human, human_id)):
        assert session_id is not None
        refused_receipt = connection.enrollment_inspect(
            EnrollmentReconcile(
                request_id=uuid4(),
                profile_id=change.profile_id,
                session_id=session_id,
                enrollment_request_id=submitted.request_id,
            ),
            deadline=time.monotonic() + 5,
        )
        assert isinstance(refused_receipt, AccessRefusal)
    assert change.subject.store.snapshot().grants[0] == change.grant
    assert len(change.subject.store.snapshot().keys) == 1
    return journey, submitted, fresh_clients, fresh_connections


def _approve_as_human(
    change: _Change,
    served: ServedRuntime,
    journey: AutomationRequesterJourney,
    submitted: AutomationReceiptProjection,
    human_id: UUID,
) -> AutomationReceiptProjection:
    profile_id, human = change.profile_id, change.human
    done = Event()

    def serve_requester() -> None:
        while not done.is_set() and journey.completion is None:
            journey.step()

    polling = served.pool.submit(serve_requester)
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
            tuple(item.stage for item in change.subject.store.enrollment_state().requests),
        )
        return (
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
                raise BaseExceptionGroup("approval and requester failed", [approval_error, delivery_error]) from None
            raise


def _assert_completed_grant(
    change: _Change,
    client: NativeEnrollmentClient,
    journey: AutomationRequesterJourney,
    proposal: EnrollmentProposal,
    completed: AutomationReceiptProjection,
) -> None:
    grant, subject = change.grant, change.subject
    assert completed.stage is EnrollmentStage.COMPLETE
    assert completed.grant_id == grant.grant_id
    requester_done = journey.completion
    assert requester_done is not None
    assert requester_done.terminal == completed  # Independent oracle; never forwarded to requester.
    current = subject.store.snapshot().grants[0]
    assert current.scope == proposal.scope and current.expires_at == proposal.expires_at
    if change.kind is EnrollmentKind.ROTATE:
        assert current.generation == grant.generation
        # Read only the candidate delivered to this exact
        # protected client, then prove it at fresh admission.
        # The human's result is not forwarded to the requester.
        assert requester_done.credential is not None
        assert requester_done.credential.key_id == completed.key_id
        assert read_delivered_credential(client).get_secret_value() != change.original_secret
        predecessor = next(k for k in subject.store.snapshot().keys if k.key_id == change.original_key_id)
        assert predecessor.expires_at <= now() + timedelta(seconds=60)
    else:
        assert current.generation == grant.generation + 1
        assert completed.key_id is None and completed.credential_reference is None
        assert requester_done.credential is None


def _assert_old_lease_retired(
    change: _Change,
    api: FrontendClient,
    old_session: UUID | None,
    fresh: FrontendClient,
    submitted: AutomationReceiptProjection,
    completed: AutomationReceiptProjection,
) -> None:
    # The runtime retires the old lease: a renewed or rescoped
    # grant is a new generation, and a rotated predecessor key
    # now expires before the lease would. Ask the runtime on the
    # old lease's own connection, not the client's cleared view.
    retired = change.raw.session(
        SessionRequest(
            action="session_status",
            request_id=uuid4(),
            profile_id=change.profile_id,
            session_id=old_session,
        ),
        deadline=time.monotonic() + 5,
    )
    # An access refusal, never a transport failure: the old
    # connection is still live and only its lease is gone.
    if isinstance(retired, AccessRefusal):
        assert isinstance(retired.code, AccessDenialCode)
    else:
        assert isinstance(retired, ProfileStatus)
        assert retired.status.denial is not None
    with pytest.raises((AutomationCustodyError, FrontendRefusedError)):
        api.prepare_grant_change(change.subject.client_native)
    assert fresh.session_id != old_session
    recovered = fresh.reconcile_enrollment(submitted.request_id)
    assert recovered == completed
    with pytest.raises(FrontendRefusedError):
        fresh.reconcile_enrollment(uuid4())


def _assert_lock_stops_reconcile(
    change: _Change,
    fresh: FrontendClient,
    fresh_connection: VerifiedConnection,
    submitted: AutomationReceiptProjection,
) -> None:
    # Reconciliation never restores the old volatile offer or
    # authorizes receipt disclosure after current-session lock.
    fresh_session = fresh.session_id
    assert fresh_session is not None
    fresh.lock()
    locked_reply = fresh_connection.enrollment_inspect(
        EnrollmentReconcile(
            request_id=uuid4(),
            profile_id=change.profile_id,
            session_id=fresh_session,
            enrollment_request_id=submitted.request_id,
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(locked_reply, AccessRefusal)


@pytest.mark.parametrize("kind", [EnrollmentKind.ROTATE, EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE])
def test_exact_key_requests_reviewed_grant_change(tmp_path: Path, kind: EnrollmentKind) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
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
        with (
            serving_runtime(
                endpoint,
                root,
                capture_login=lambda _channel: SyntheticLogin("preunlock-enrollment-native-login"),
                secret_store=lambda: subject.native,
                workers=3,
            ) as served,
            ExitStack() as cleanup,
        ):
            raw, human, foreign = connect_verified(endpoint), connect_verified(endpoint), connect_verified(endpoint)
            for connection in (raw, human, foreign):
                cleanup.callback(connection.close)
            change = _Change(
                kind,
                endpoint,
                subject,
                grant,
                original.key_id,
                original_secret.get_secret_value(),
                profile_id,
                raw,
                human,
                foreign,
            )
            human_id, api, old_session, client, proposal = _request_grant_change(change)
            journey, submitted, fresh_clients, fresh_connections = _submit_and_probe_copies(
                change, api, human_id, client, proposal
            )
            completed = _approve_as_human(change, served, journey, submitted, human_id)
            for opened in fresh_clients:
                cleanup.callback(opened.close)
            _assert_completed_grant(change, client, journey, proposal, completed)
            assert len(fresh_clients) == 1
            fresh = fresh_clients[0]
            _assert_old_lease_retired(change, api, old_session, fresh, submitted, completed)
            _assert_lock_stops_reconcile(change, fresh, fresh_connections[0], submitted)
