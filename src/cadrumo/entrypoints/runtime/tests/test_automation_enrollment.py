"""A pre-unlock requester receives an API key only through its native client."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event
from typing import Literal, override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.enrollment_access import (
    RuntimeEnrollmentInspect,
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentPrepared,
)
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationResult,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileLogin, RuntimeProfileStatus
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    AuthorityState,
    Availability,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.time.clock import now

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _ObservedClientPort(MemoryNativePort):
    """Record native method direction and reference, never private bytes."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, str, str]] = []

    @override
    def read(self, namespace: str, account: str) -> SecretBytes | None:
        self.events.append(("read", namespace, account))
        return super().read(namespace, account)

    @override
    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        self.events.append(("write", namespace, account))
        super().replace(namespace, account, value)


class _LoginObservation:
    login_id = "preunlock-enrollment-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
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
    method: Literal["password", "receipt", "api_key"],
    proof: bytes,
) -> UUID:
    mutable = bytearray(proof)
    status = client.login(
        RuntimeProfileLogin(
            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI, method=method
        ),
        mutable,
        deadline=time.monotonic() + 25,
    )
    assert mutable == bytes(len(proof))
    assert isinstance(status, RuntimeProfileStatus)
    assert status.status.session_id is not None
    return status.status.session_id


def _submit_operation(
    client: VerifiedRuntimeConnection,
    *,
    profile_id: UUID,
    session_id: UUID,
    definition_id: str,
    payload: AutomationOperationRequest,
    password: bytes | None = None,
) -> tuple[RuntimeOperationContractReply, RuntimeOperationSubmitted, OperationObservationSuccessV1]:
    contract = client.operation(
        RuntimeOperationContract(
            request_id=uuid4(), profile_id=profile_id, session_id=session_id, definition_id=definition_id
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(contract, RuntimeOperationContractReply)
    assert contract.contract.result_schema is not None
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload_json=payload.model_dump_json(),
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(submitted, RuntimeOperationSubmitted)
    if password is not None:
        requirement = submitted.receipt.secret_requirement
        assert requirement is not None
        mutable = bytearray(password)
        received = client.operation_secret(
            RuntimeOperationSecret(
                request_id=uuid4(), profile_id=profile_id, session_id=session_id, requirement=requirement
            ),
            mutable,
            deadline=time.monotonic() + 15,
        )
        assert isinstance(received, RuntimeOperationAcknowledged)
        assert mutable == bytes(len(password))
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
    deadline = time.monotonic() + 60
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
            return contract, submitted, observed.observation
        assert time.monotonic() < deadline
        time.sleep(0.02)


def _result(
    client: VerifiedRuntimeConnection,
    *,
    profile_id: UUID,
    session_id: UUID,
    contract: RuntimeOperationContractReply,
    submitted: RuntimeOperationSubmitted,
    observed: OperationObservationSuccessV1,
) -> RuntimeOperationProjected:
    schema = contract.contract.result_schema
    assert schema is not None
    released = client.operation(
        RuntimeOperationResult(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            result=OperationResultProjectionRequestV1(
                operation_id=submitted.receipt.operation_id,
                terminal_revision=observed.projection.revision,
                definition_contract_digest=contract.contract.definition_contract_digest,
                result_schema=schema,
            ),
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(released, RuntimeOperationProjected)
    return released


def test_preunlock_requester_receives_protected_credential_then_fresh_api_login(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        binding = current_automation_profile_binding(
            profile_id=profile_id,
            installation_id=installation.installation_id,
            os_owner_id=installation.os_owner_id,
            root=root,
        )
        server_native, client_native = MemoryNativePort(), _ObservedClientPort()
        store = AutomationControlStore(root=root, binding=binding, secrets_store=server_native)
        assert store.enrollment_state().requests == ()
        assert store.enrollment_state().grants == ()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: server_native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                requester, human, other = _connect(endpoint), _connect(endpoint), _connect(endpoint)
                try:
                    prepared = requester.enrollment_prepare(
                        RuntimeEnrollmentPrepare(
                            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.MCP
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(prepared, RuntimeEnrollmentPrepared)
                    assert prepared.profile_binding == binding
                    assert prepared.runtime_boot_id == boot
                    assert prepared.client_id == prepared.destination_id
                    client = NativeEnrollmentClient(
                        connection=requester, prepared=prepared, secrets_store=client_native
                    )
                    wrong = other.enrollment_inspect(
                        RuntimeEnrollmentInspect(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            enrollment_request_id=prepared.enrollment_request_id,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(wrong, RuntimeAccessRefusal)
                    wrong_request = requester.enrollment_inspect(
                        RuntimeEnrollmentInspect(
                            request_id=uuid4(), profile_id=profile_id, enrollment_request_id=uuid4()
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(wrong_request, RuntimeAccessRefusal)
                    proposal = EnrollmentProposal(
                        kind=EnrollmentKind.ENROLL,
                        scope=AccessScope(
                            operations=frozenset({"user-profile.field-mutation"}),
                            actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT}),
                            disclosures=frozenset(),
                            periods=None,
                            allow_period_independent=True,
                            allow_delegation=False,
                        ),
                        expires_at=now() + timedelta(days=30),
                        key_expires_at=now() + timedelta(days=15),
                        unattended=True,
                        allow_os_lock=False,
                    )
                    submitted = client.submit(proposal, timeout=10)
                    assert submitted.request_id == prepared.enrollment_request_id
                    assert submitted.stage is EnrollmentStage.REQUESTED
                    assert client.inspect(timeout=5) == submitted
                    human_id = _login(human, profile_id, method="password", proof=PROFILE_INPUT.encode())
                    inventory_contract, inventory_op, inventory_done = _submit_operation(
                        human,
                        profile_id=profile_id,
                        session_id=human_id,
                        definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()),
                    )
                    assert inventory_done.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    inventory = (
                        OperationResultProjectionSuccessV1[AutomationInventoryProjection]
                        .model_validate_json(
                            json.dumps(
                                _result(
                                    human,
                                    profile_id=profile_id,
                                    session_id=human_id,
                                    contract=inventory_contract,
                                    submitted=inventory_op,
                                    observed=inventory_done,
                                ).document
                            )
                        )
                        .projection
                    )
                    review = next(
                        item for item in inventory.requests if item.receipt.request_id == submitted.request_id
                    )
                    assert review.receipt.review_digest == submitted.review_digest
                    assert review.client_id == prepared.client_id
                    assert review.destination_id == prepared.destination_id

                    _, wrong_approval, rejected = _submit_operation(
                        human,
                        profile_id=profile_id,
                        session_id=human_id,
                        definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
                        payload=AutomationOperationRequest(
                            profile_id=profile_id, request_id=submitted.request_id, review_digest="0" * 64
                        ),
                        password=PROFILE_INPUT.encode(),
                    )
                    assert wrong_approval.receipt.operation_id
                    assert rejected.projection.terminal_condition is OperationTerminalCondition.REFUSED
                    assert store.snapshot().grants == ()

                    done = Event()

                    def poll_client() -> None:
                        deadline = time.monotonic() + 70
                        while not done.is_set() and time.monotonic() < deadline:
                            client.poll(timeout=10)

                    polling = pool.submit(poll_client)
                    try:
                        approval_contract, approval_op, approval_done = _submit_operation(
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
                        assert approval_done.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                        completed = (
                            OperationResultProjectionSuccessV1[AutomationReceiptProjection]
                            .model_validate_json(
                                json.dumps(
                                    _result(
                                        human,
                                        profile_id=profile_id,
                                        session_id=human_id,
                                        contract=approval_contract,
                                        submitted=approval_op,
                                        observed=approval_done,
                                    ).document
                                )
                            )
                            .projection
                        )
                    finally:
                        done.set()
                        polling.result(timeout=15)
                    assert completed.stage is EnrollmentStage.COMPLETE
                    assert completed.request_id == submitted.request_id
                    assert completed.review_digest == submitted.review_digest
                    assert completed.key_id is not None
                    assert completed.credential_reference is not None
                    assert store.snapshot().grants[0].state is AuthorityState.ACTIVE
                    assert store.snapshot().keys[0].state is AuthorityState.ACTIVE
                    reference = str(completed.credential_reference)
                    write_event = ("write", CLIENT_NAMESPACE, reference)
                    read_event = ("read", CLIENT_NAMESPACE, reference)
                    assert write_event in client_native.events
                    assert client_native.events[client_native.events.index(write_event) + 1 :].count(read_event) >= 2
                    assert (CLIENT_NAMESPACE, reference) in client_native.items
                    assert (CLIENT_NAMESPACE, reference) not in server_native.items
                    assert server_native.items != client_native.items
                    assert client.inspect(timeout=5) == completed
                    requester.close()
                    human.close()
                    client_native.unavailable = True
                    with pytest.raises(AutomationCustodyError, match="unavailable"):
                        client.credential()
                    client_native.unavailable = False
                    credential = client.credential()
                    assert client_native.events[-1] == read_event
                    api = _connect(endpoint)
                    try:
                        api_id = _login(api, profile_id, method="api_key", proof=credential.get_secret_value())
                        assert api_id != human_id
                    finally:
                        api.close()
                finally:
                    requester.close()
                    human.close()
                    other.close()
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


def test_client_native_store_failure_does_not_complete_enrollment(tmp_path: Path) -> None:
    """A published candidate remains pending when its client cannot store it."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        binding = current_automation_profile_binding(
            profile_id=profile_id,
            installation_id=installation.installation_id,
            os_owner_id=installation.os_owner_id,
            root=root,
        )
        server_native, client_native = MemoryNativePort(), _ObservedClientPort()
        client_native.fail_write = CLIENT_NAMESPACE
        store = AutomationControlStore(root=root, binding=binding, secrets_store=server_native)
        assert store.enrollment_state().requests == ()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: server_native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                requester, human = _connect(endpoint), _connect(endpoint)
                try:
                    prepared = requester.enrollment_prepare(
                        RuntimeEnrollmentPrepare(
                            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.MCP
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(prepared, RuntimeEnrollmentPrepared)
                    client = NativeEnrollmentClient(
                        connection=requester, prepared=prepared, secrets_store=client_native
                    )
                    submitted = client.submit(
                        EnrollmentProposal(
                            kind=EnrollmentKind.ENROLL,
                            scope=AccessScope(
                                operations=frozenset({"user-profile.field-mutation"}),
                                actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT}),
                                disclosures=frozenset(),
                                periods=None,
                                allow_period_independent=True,
                                allow_delegation=False,
                            ),
                            expires_at=now() + timedelta(days=30),
                            key_expires_at=now() + timedelta(days=15),
                            unattended=True,
                            allow_os_lock=False,
                        ),
                        timeout=10,
                    )
                    human_id = _login(human, profile_id, method="password", proof=PROFILE_INPUT.encode())
                    done = Event()

                    def poll_client() -> None:
                        deadline = time.monotonic() + 70
                        while not done.is_set() and time.monotonic() < deadline:
                            client.poll(timeout=10)

                    polling = pool.submit(poll_client)
                    try:
                        _, _, failed = _submit_operation(
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
                        assert failed.projection.terminal_condition is OperationTerminalCondition.REFUSED
                        assert failed.projection.effect is OperationEffect.UNKNOWN
                    finally:
                        done.set()
                        polling.result(timeout=15)
                    state = store.enrollment_state()
                    assert len(state.requests) == len(state.grants) == 1
                    assert state.requests[0].stage is EnrollmentStage.CANDIDATE
                    assert state.requests[0].credential_reference is not None
                    assert state.grants[0].grant.state is AuthorityState.PENDING
                    assert len(state.grants[0].keys) == 1
                    assert state.grants[0].keys[0].key.state is AuthorityState.PENDING
                    reference = str(state.requests[0].credential_reference)
                    assert ("write", CLIENT_NAMESPACE, reference) in client_native.events
                    assert (CLIENT_NAMESPACE, reference) not in client_native.items
                    assert (CLIENT_NAMESPACE, reference) not in server_native.items
                    assert client.inspect(timeout=5) is not None
                    with pytest.raises(AutomationCustodyError):
                        client.credential()

                    _, _, wrong_decline = _submit_operation(
                        human,
                        profile_id=profile_id,
                        session_id=human_id,
                        definition_id=AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
                        payload=AutomationOperationRequest(
                            profile_id=profile_id, request_id=submitted.request_id, review_digest="0" * 64
                        ),
                    )
                    assert wrong_decline.projection.terminal_condition is OperationTerminalCondition.REFUSED
                    assert store.enrollment_state().requests[0].stage is EnrollmentStage.CANDIDATE

                    decline_contract, decline_op, declined = _submit_operation(
                        human,
                        profile_id=profile_id,
                        session_id=human_id,
                        definition_id=AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
                        payload=AutomationOperationRequest(
                            profile_id=profile_id,
                            request_id=submitted.request_id,
                            review_digest=submitted.review_digest,
                        ),
                    )
                    assert declined.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert declined.projection.effect is OperationEffect.UPDATED
                    declined_receipt = (
                        OperationResultProjectionSuccessV1[AutomationReceiptProjection]
                        .model_validate_json(
                            json.dumps(
                                _result(
                                    human,
                                    profile_id=profile_id,
                                    session_id=human_id,
                                    contract=decline_contract,
                                    submitted=decline_op,
                                    observed=declined,
                                ).document
                            )
                        )
                        .projection
                    )
                    assert declined_receipt.stage is EnrollmentStage.DECLINED
                    assert declined_receipt.request_id == submitted.request_id
                    assert declined_receipt.review_digest == submitted.review_digest
                    assert store.enrollment_state().requests[0].stage is EnrollmentStage.DECLINED
                    assert store.snapshot().grants[0].state is AuthorityState.PENDING
                    assert store.snapshot().keys[0].state is AuthorityState.PENDING
                finally:
                    requester.close()
                    human.close()
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
