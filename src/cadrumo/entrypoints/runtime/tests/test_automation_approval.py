"""Native renewal approval uses parent proof and canonical worker publication."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_delivery import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationResult,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "automation-approval-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply test-owned OS observations to the real installed runtime."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _login(
    client: VerifiedRuntimeConnection,
    profile_id: UUID,
    *,
    frontend: OperationFrontendProjection,
    method: Literal["password", "receipt", "api_key"],
    proof: bytes,
) -> UUID:
    secret = bytearray(proof)
    result = client.login(
        RuntimeProfileLogin(request_id=uuid4(), profile_id=profile_id, frontend=frontend, method=method),
        secret,
        deadline=time.monotonic() + 25,
    )
    assert secret == bytes(len(proof))
    assert isinstance(result, RuntimeProfileStatus)
    assert result.status.session_id is not None
    return result.status.session_id


def _seed_renewal(subject: AdministrationSubject, *, boot: UUID) -> tuple[UUID, str, bytes]:
    """Seed enrollment and reviewed renewal before native worker ownership begins."""
    instant = datetime.now(UTC)
    requester = changed(
        subject.owner.requesting,
        runtime_boot_id=boot,
        destination_id=subject.owner.requesting.client_id,
    )
    subject.owner.requesting = requester
    subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
        requester=requester, secrets_store=subject.client_native
    )
    scope = changed(
        subject.proposal.scope,
        operations=frozenset((AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,)),
        actions=frozenset(AccessAction),
        disclosures=frozenset(
            (
                DisclosurePermission(
                    destination_id=requester.client_id,
                    projection_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID + ".result",
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            )
        ),
    )
    facts = subject.owner.current
    assert facts.session is not None
    subject.owner.current = changed(
        facts,
        profile=changed(facts.profile, scope=scope),
        context=changed(
            facts.context,
            now=instant,
            runtime_boot_id=boot,
            connection_id=requester.connection_id,
            authenticated_client_id=requester.client_id,
        ),
        session=changed(
            facts.session,
            runtime_boot_id=boot,
            connection_id=requester.connection_id,
            client_id=requester.client_id,
            issued_at=instant,
            expires_at=instant + timedelta(hours=1),
            scope=scope,
        ),
    )
    subject.proposal = changed(
        subject.proposal,
        scope=scope,
        expires_at=instant + timedelta(days=365),
        key_expires_at=instant + timedelta(days=100),
    )
    initial_id = uuid4()
    subject.service.request(initial_id, subject.proposal)
    subject.approve(initial_id)
    original = subject.store.snapshot().grants[0]
    assert original.generation == 1
    initial_record = next(item for item in subject.store.enrollment_state().requests if item.request_id == initial_id)
    key = subject.owner.delivery.endpoint.possession(initial_record)
    assert key is not None
    renewal = changed(
        subject.proposal,
        kind=EnrollmentKind.RENEW,
        key_expires_at=None,
        target_grant_id=original.grant_id,
        expires_at=original.expires_at + timedelta(days=5),
    )
    requested = subject.service.request(uuid4(), renewal).receipt
    assert requested.stage is EnrollmentStage.REQUESTED
    return requested.request_id, requested.review_digest, key.get_secret_value()


def _submit(
    client: VerifiedRuntimeConnection, profile_id: UUID, session_id: UUID, request_id: UUID, digest: str
) -> RuntimeOperationReply | RuntimeAccessRefusal:
    return client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload_json=AutomationOperationRequest(
                profile_id=profile_id, request_id=request_id, review_digest=digest
            ).model_dump_json(),
        ),
        deadline=time.monotonic() + 10,
    )


def _run_approval(
    client: VerifiedRuntimeConnection,
    *,
    profile_id: UUID,
    session_id: UUID,
    request_id: UUID,
    digest: str,
    password: bytes,
) -> tuple[RuntimeOperationSubmitted, OperationObservationSuccessV1]:
    submitted = _submit(client, profile_id, session_id, request_id, digest)
    assert isinstance(submitted, RuntimeOperationSubmitted)
    requirement = submitted.receipt.secret_requirement
    assert requirement is not None
    assert requirement.secret_kind == "automation.password"  # noqa: S105 - public kind
    secret = bytearray(password)
    accepted = client.operation_secret(
        RuntimeOperationSecret(
            request_id=uuid4(), profile_id=profile_id, session_id=session_id, requirement=requirement
        ),
        secret,
        deadline=time.monotonic() + 15,
    )
    assert isinstance(accepted, RuntimeOperationAcknowledged)
    assert secret == bytes(len(password))
    started = client.operation(
        RuntimeOperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            operation_id=submitted.receipt.operation_id,
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(started, RuntimeOperationAcknowledged)
    deadline = time.monotonic() + 40
    while True:
        observed = client.operation(
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(
                    operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=32
                ),
            ),
            deadline=deadline,
        )
        assert isinstance(observed, RuntimeOperationObserved)
        assert isinstance(observed.observation, OperationObservationSuccessV1)
        if observed.observation.projection.terminal_condition is not None:
            return submitted, observed.observation
        assert time.monotonic() < deadline
        time.sleep(0.02)


def test_native_human_renews_existing_grant_and_key_session_cannot_approve(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    stop, boot = Event(), uuid4()
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as enrollment:
        renewal_id, digest, api_key = _seed_renewal(enrollment, boot=boot)
        profile_id = enrollment.store.binding.profile_id
        before = enrollment.store.snapshot()
        renewal = next(item for item in enrollment.store.enrollment_state().requests if item.request_id == renewal_id)
        close_active_bucket_session()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: enrollment.native,
        )
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                human, api = _connect(endpoint), _connect(endpoint)
                try:
                    human_id = _login(
                        human,
                        profile_id,
                        frontend=OperationFrontendProjection.CLI,
                        method="password",
                        proof=PROFILE_INPUT.encode(),
                    )
                    human_status = human.session(
                        RuntimeSessionRequest(
                            action="session_status",
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(human_status, RuntimeProfileStatus)
                    assert renewal.requester.destination_id not in {
                        permission.destination_id for permission in human_status.status.effective_scope.disclosures
                    }
                    api_id = _login(
                        api,
                        profile_id,
                        frontend=OperationFrontendProjection.CLI,
                        method="api_key",
                        proof=api_key,
                    )
                    contract = human.operation(
                        RuntimeOperationContract(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(contract, RuntimeOperationContractReply)
                    assert contract.contract.result_schema is not None
                    blocked = _submit(api, profile_id, api_id, renewal_id, digest)
                    assert isinstance(blocked, RuntimeAccessRefusal)
                    assert blocked.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
                    wrong, refused = _run_approval(
                        human,
                        profile_id=profile_id,
                        session_id=human_id,
                        request_id=renewal_id,
                        digest=digest,
                        password=b"wrong-synthetic-password",
                    )
                    assert refused.projection.terminal_condition is OperationTerminalCondition.REFUSED
                    assert refused.projection.result_ref is None
                    refused_state = enrollment.store.snapshot()
                    assert refused_state.revision == before.revision
                    assert refused_state.grants == before.grants
                    assert enrollment.store.enrollment_state().requests[-1].stage is EnrollmentStage.REQUESTED
                    completed, observed = _run_approval(
                        human,
                        profile_id=profile_id,
                        session_id=human_id,
                        request_id=renewal_id,
                        digest=digest,
                        password=PROFILE_INPUT.encode(),
                    )
                    assert completed.receipt.operation_id != wrong.receipt.operation_id
                    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert observed.projection.effect is OperationEffect.UPDATED
                    released = human.operation(
                        RuntimeOperationResult(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            result=OperationResultProjectionRequestV1(
                                operation_id=completed.receipt.operation_id,
                                terminal_revision=observed.projection.revision,
                                definition_contract_digest=contract.contract.definition_contract_digest,
                                result_schema=contract.contract.result_schema,
                            ),
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(released, RuntimeOperationProjected)
                    receipt = (
                        OperationResultProjectionSuccessV1[AutomationReceiptProjection]
                        .model_validate_json(json.dumps(released.document))
                        .projection
                    )
                    assert receipt.request_id == renewal_id
                    assert receipt.profile_id == profile_id
                    assert receipt.review_digest == digest
                    assert receipt.stage is EnrollmentStage.COMPLETE
                    assert receipt.grant_id == renewal.grant_id
                    assert receipt.key_id is None
                    after = enrollment.store.snapshot()
                    assert after.revision == before.revision + 1
                    assert after.grants[0].generation == before.grants[0].generation + 1
                    assert after.grants[0].expires_at == renewal.proposal.expires_at
                    assert after.grants[0].scope.disclosures == renewal.proposal.scope.disclosures
                    assert after.keys == before.keys
                    journal_root = root / storage_location(StorageCategory.OPERATION_JOURNAL).subpath
                    journal_bytes = b"".join(path.read_bytes() for path in journal_root.rglob("*") if path.is_file())
                    assert journal_bytes
                    for forbidden in (PROFILE_INPUT.encode(), b"wrong-synthetic-password", api_key):
                        assert forbidden not in journal_bytes
                    output = capsys.readouterr()
                    assert PROFILE_INPUT not in output.out + output.err
                    assert "wrong-synthetic-password" not in output.out + output.err
                finally:
                    human.close()
                    api.close()
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
