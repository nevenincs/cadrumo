"""A pre-unlock requester receives an API key only through its native client."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Literal, override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

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
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    AutomationReceiptProjection,
    EnrollmentStage,
)
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from cadrumo.core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo_client.contracts.access_vocabulary import AuthorityState
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS, exchange_deadline
from cadrumo_client.contracts.enrollment_access import EnrollmentInspect, EnrollmentPrepare, EnrollmentPrepared
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationContract,
    OperationContractReply,
    OperationControl,
    OperationObserve,
    OperationObserved,
    OperationProjected,
    OperationResult,
    OperationSecret,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileLogin, ProfileStatus
from cadrumo_client.transport.enrollment_client import NativeEnrollmentClient
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from .automation_proposal_support import enrollment_proposal
from .served_runtime import SyntheticLogin, connect_verified, serving_runtime

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


def _login(
    client: VerifiedConnection,
    profile_id: UUID,
    *,
    method: Literal["password", "receipt", "api_key"],
    proof: bytes,
) -> UUID:
    mutable = bytearray(proof)
    status = client.login(
        ProfileLogin(
            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI, method=method
        ),
        mutable,
        deadline=exchange_deadline(),
    )
    assert mutable == bytes(len(proof))
    assert isinstance(status, ProfileStatus)
    assert status.status.session_id is not None
    return status.status.session_id


def _submit_operation(
    client: VerifiedConnection,
    *,
    profile_id: UUID,
    session_id: UUID,
    definition_id: str,
    payload: AutomationOperationRequest,
    password: bytes | None = None,
) -> tuple[OperationContractReply, OperationSubmitted, OperationObservationSuccessV1]:
    contract = client.operation(
        OperationContract(
            request_id=uuid4(), profile_id=profile_id, session_id=session_id, definition_id=definition_id
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(contract, OperationContractReply)
    assert contract.contract.result_schema is not None
    submitted = client.operation(
        OperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload_json=payload.model_dump_json(),
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(submitted, OperationSubmitted)
    if password is not None:
        requirement = submitted.receipt.secret_requirement
        assert requirement is not None
        mutable = bytearray(password)
        received = client.operation_secret(
            OperationSecret(request_id=uuid4(), profile_id=profile_id, session_id=session_id, requirement=requirement),
            mutable,
            deadline=time.monotonic() + 15,
        )
        assert isinstance(received, OperationAcknowledged)
        assert mutable == bytes(len(password))
    started = client.operation(
        OperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            operation_id=submitted.receipt.operation_id,
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(started, OperationAcknowledged)
    while True:
        observed = client.operation(
            OperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(
                    operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=32
                ),
            ),
            deadline=time.monotonic() + 60,
        )
        assert isinstance(observed, OperationObserved)
        assert isinstance(observed.observation, OperationObservationSuccessV1)
        if observed.observation.projection.terminal_condition is not None:
            return contract, submitted, observed.observation
        time.sleep(0.02)


def _result(
    client: VerifiedConnection,
    *,
    profile_id: UUID,
    session_id: UUID,
    contract: OperationContractReply,
    submitted: OperationSubmitted,
    observed: OperationObservationSuccessV1,
) -> OperationProjected:
    schema = contract.contract.result_schema
    assert schema is not None
    released = client.operation(
        OperationResult(
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
    assert isinstance(released, OperationProjected)
    return released


@dataclass(frozen=True)
class _Preunlock:
    endpoint: WindowsEndpoint
    profile_id: UUID
    binding: ProfileAccessBinding
    boot: UUID
    pool: ThreadPoolExecutor
    store: AutomationControlStore
    server_native: MemoryNativePort
    client_native: _ObservedClientPort
    requester: VerifiedConnection
    human: VerifiedConnection
    other: VerifiedConnection


def _prepare_and_submit(
    run: _Preunlock,
) -> tuple[EnrollmentPrepared, NativeEnrollmentClient, AutomationReceiptProjection]:
    profile_id, requester = run.profile_id, run.requester
    prepared = requester.enrollment_prepare(
        EnrollmentPrepare(request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.TUI),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(prepared, EnrollmentPrepared)
    assert prepared.profile_binding == run.binding
    assert prepared.runtime_boot_id == run.boot
    assert prepared.client_id == prepared.destination_id
    client = NativeEnrollmentClient(connection=requester, prepared=prepared, secrets_store=run.client_native)
    wrong = run.other.enrollment_inspect(
        EnrollmentInspect(
            request_id=uuid4(),
            profile_id=profile_id,
            enrollment_request_id=prepared.enrollment_request_id,
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(wrong, AccessRefusal)
    wrong_request = requester.enrollment_inspect(
        EnrollmentInspect(request_id=uuid4(), profile_id=profile_id, enrollment_request_id=uuid4()),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(wrong_request, AccessRefusal)
    proposal = enrollment_proposal()
    submitted = client.submit(proposal, timeout=10)
    assert submitted.request_id == prepared.enrollment_request_id
    assert submitted.stage is EnrollmentStage.REQUESTED
    assert client.inspect(timeout=5) == submitted
    return prepared, client, submitted


def _review_and_refuse_wrong_digest(
    run: _Preunlock, prepared: EnrollmentPrepared, submitted: AutomationReceiptProjection
) -> UUID:
    profile_id, human = run.profile_id, run.human
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
    review = next(item for item in inventory.requests if item.receipt.request_id == submitted.request_id)
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
    assert run.store.snapshot().grants == ()
    return human_id


def _approve_while_polling(
    run: _Preunlock, client: NativeEnrollmentClient, submitted: AutomationReceiptProjection, human_id: UUID
) -> AutomationReceiptProjection:
    profile_id = run.profile_id
    done = Event()

    def poll_client() -> None:
        while not done.is_set():
            # A delivery exchange waits behind the publication fence the approval holds
            # while it commits; a shorter poll ends the delivery being approved.
            client.poll(timeout=MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS)

    polling = run.pool.submit(poll_client)
    try:
        approval_contract, approval_op, approval_done = _submit_operation(
            run.human,
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
        return (
            OperationResultProjectionSuccessV1[AutomationReceiptProjection]
            .model_validate_json(
                json.dumps(
                    _result(
                        run.human,
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
        primary = sys.exception()
        done.set()
        try:
            polling.result()
        except Exception as error:
            if primary is None:
                raise
            primary.add_note(f"Requester polling cleanup also failed: {type(error).__name__}")


def _assert_delivered_candidate(
    run: _Preunlock,
    client: NativeEnrollmentClient,
    submitted: AutomationReceiptProjection,
    completed: AutomationReceiptProjection,
) -> str:
    store, client_native, server_native = run.store, run.client_native, run.server_native
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
    return reference


def _login_with_delivered_credential(
    run: _Preunlock, client: NativeEnrollmentClient, reference: str, human_id: UUID
) -> None:
    read_event = ("read", CLIENT_NAMESPACE, reference)
    run.requester.close()
    run.human.close()
    run.client_native.unavailable = True
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        client.credential()
    run.client_native.unavailable = False
    credential = client.credential()
    assert run.client_native.events[-1] == read_event
    api = connect_verified(run.endpoint)
    try:
        api_id = _login(api, run.profile_id, method="api_key", proof=credential.get_secret_value())
        assert api_id != human_id
    finally:
        api.close()


def test_preunlock_requester_receives_protected_credential_then_fresh_api_login(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        endpoint = WindowsEndpoint(storage_root=root)
        installation_state = installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        binding = current_automation_profile_binding(
            profile_id=profile_id,
            installation_id=installation_state.installation_id,
            os_owner_id=installation_state.os_owner_id,
            root=root,
        )
        server_native, client_native = MemoryNativePort(), _ObservedClientPort()
        store = AutomationControlStore(root=root, binding=binding, secrets_store=server_native)
        assert store.enrollment_state().requests == ()
        assert store.enrollment_state().grants == ()
        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: SyntheticLogin("preunlock-enrollment-native-login"),
            secret_store=lambda: server_native,
            workers=3,
        ) as served:
            boot = served.boot
            pool = served.pool
            requester, human, other = (
                connect_verified(endpoint),
                connect_verified(endpoint),
                connect_verified(endpoint),
            )
            try:
                run = _Preunlock(
                    endpoint,
                    profile_id,
                    binding,
                    boot,
                    pool,
                    store,
                    server_native,
                    client_native,
                    requester,
                    human,
                    other,
                )
                prepared, client, submitted = _prepare_and_submit(run)
                human_id = _review_and_refuse_wrong_digest(run, prepared, submitted)
                completed = _approve_while_polling(run, client, submitted, human_id)
                reference = _assert_delivered_candidate(run, client, submitted, completed)
                _login_with_delivered_credential(run, client, reference, human_id)
            finally:
                requester.close()
                human.close()
                other.close()


def test_client_native_store_failure_does_not_complete_enrollment(tmp_path: Path) -> None:
    """A published candidate remains pending when its client cannot store it."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        endpoint = WindowsEndpoint(storage_root=root)
        installation_state = installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        binding = current_automation_profile_binding(
            profile_id=profile_id,
            installation_id=installation_state.installation_id,
            os_owner_id=installation_state.os_owner_id,
            root=root,
        )
        server_native, client_native = MemoryNativePort(), _ObservedClientPort()
        client_native.fail_write = CLIENT_NAMESPACE
        store = AutomationControlStore(root=root, binding=binding, secrets_store=server_native)
        assert store.enrollment_state().requests == ()
        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: SyntheticLogin("preunlock-enrollment-native-login"),
            secret_store=lambda: server_native,
            workers=3,
        ) as served:
            pool = served.pool
            requester, human = connect_verified(endpoint), connect_verified(endpoint)
            try:
                prepared = requester.enrollment_prepare(
                    EnrollmentPrepare(
                        request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(prepared, EnrollmentPrepared)
                client = NativeEnrollmentClient(connection=requester, prepared=prepared, secrets_store=client_native)
                submitted = client.submit(enrollment_proposal(), timeout=10)
                human_id = _login(human, profile_id, method="password", proof=PROFILE_INPUT.encode())
                done = Event()

                def poll_client() -> None:
                    while not done.is_set():
                        # A delivery exchange waits behind the publication fence the approval holds
                        # while it commits; a shorter poll ends the delivery being approved.
                        client.poll(timeout=MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS)

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
                    polling.result()
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
