"""Native decision client uses reviewed consent and protected requester delivery."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    AutomationReceiptProjection,
    AutomationReviewProjection,
    EnrollmentStage,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope, AuthorityState
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.contracts.enrollment_access import EnrollmentPrepare, EnrollmentPrepared
from cadrumo_client.contracts.enrollment_proposal import EnrollmentKind, EnrollmentProposal
from cadrumo_client.transport.automation_decision import (
    AutomationDecisionCompletion,
    AutomationDecisionRunError,
    run_automation_decision,
)
from cadrumo_client.transport.automation_inventory import read_automation_inventory
from cadrumo_client.transport.enrollment_client import NativeEnrollmentClient
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .served_runtime import SyntheticLogin, connect_installed

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _proposal() -> EnrollmentProposal:
    return EnrollmentProposal(
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


def _requester(
    endpoint: WindowsEndpoint, profile_id: UUID, native_store: MemoryNativePort
) -> tuple[VerifiedConnection, NativeEnrollmentClient]:
    connection = connect_installed(endpoint)
    prepared = connection.enrollment_prepare(
        EnrollmentPrepare(request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.TUI),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(prepared, EnrollmentPrepared)
    return connection, NativeEnrollmentClient(connection=connection, prepared=prepared, secrets_store=native_store)


def _review(client: FrontendClient, request_id: UUID) -> AutomationReviewProjection:
    inventory = read_automation_inventory(client)
    matching = tuple(item for item in inventory.projection.requests if item.receipt.request_id == request_id)
    assert len(matching) == 1
    return matching[0]


@dataclass(frozen=True)
class _Decision:
    endpoint: WindowsEndpoint
    profile_id: UUID
    pool: ThreadPoolExecutor
    store: AutomationControlStore
    server_native: MemoryNativePort
    client_native: MemoryNativePort
    human: FrontendClient
    enrollment: NativeEnrollmentClient


def _review_and_refuse_wrong_password(
    decision: _Decision,
) -> tuple[AutomationReceiptProjection, AutomationReviewProjection, str]:
    human, enrollment = decision.human, decision.enrollment
    first = enrollment.submit(_proposal())
    assert first.stage is EnrollmentStage.REQUESTED
    human_password = bytearray(PROFILE_INPUT.encode())
    human.login_password(human_password, timeout=25)
    assert not any(human_password)
    review = _review(human, first.request_id)
    assert review.receipt.review_digest == first.review_digest
    assert review.client_id == enrollment.prepared.client_id

    wrong_password = bytearray(b"wrong-synthetic-decision-password")
    with pytest.raises(AutomationDecisionRunError) as wrong:
        run_automation_decision(human, review, decision="approve", password=wrong_password)
    assert not any(wrong_password)
    assert wrong.value.terminal_condition is OperationTerminalCondition.REFUSED
    assert wrong.value.effect is OperationEffect.NONE
    assert decision.store.snapshot().grants == ()
    return first, review, wrong.value.operation_id


def _approve_while_polling(decision: _Decision, review: AutomationReviewProjection) -> AutomationDecisionCompletion:
    done = Event()

    def poll_requester() -> None:
        while not done.is_set():
            # A delivery exchange waits behind the publication fence the approval holds
            # while it commits; a shorter poll ends the delivery being approved.
            decision.enrollment.poll(timeout=MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS)

    polling = decision.pool.submit(poll_requester)
    try:
        password = bytearray(PROFILE_INPUT.encode())
        approved = run_automation_decision(decision.human, review, decision="approve", password=password)
        assert not any(password)
        return approved
    finally:
        primary = sys.exception()
        done.set()
        try:
            polling.result()
        except Exception as error:
            if primary is None:
                raise
            primary.add_note(f"Requester polling cleanup also failed: {type(error).__name__}")


def _assert_approved_delivery(
    decision: _Decision,
    first: AutomationReceiptProjection,
    approved: AutomationDecisionCompletion,
    wrong_operation_id: str,
) -> AutomationInventoryProjection:
    store, human = decision.store, decision.human
    assert approved.operation_id != wrong_operation_id
    assert approved.effect is OperationEffect.UPDATED
    assert approved.receipt.stage is EnrollmentStage.COMPLETE
    assert approved.receipt.request_id == first.request_id
    assert approved.receipt.review_digest == first.review_digest
    assert approved.receipt.key_id is not None
    assert approved.receipt.credential_reference is not None
    assert store.snapshot().grants[0].state is AuthorityState.ACTIVE
    assert (CLIENT_NAMESPACE, str(approved.receipt.credential_reference)) in decision.client_native.items
    assert (CLIENT_NAMESPACE, str(approved.receipt.credential_reference)) not in decision.server_native.items
    assert decision.enrollment.inspect() == approved.receipt
    approved_inventory = read_automation_inventory(human).projection
    assert len(approved_inventory.grants) == len(approved_inventory.keys) == 1
    assert approved_inventory.grants[0].grant_id == approved.receipt.grant_id
    assert approved_inventory.grants[0].state is AuthorityState.ACTIVE
    assert approved_inventory.keys[0].key_id == approved.receipt.key_id
    assert approved_inventory.keys[0].state is AuthorityState.ACTIVE
    assert (
        next(item.receipt for item in approved_inventory.requests if item.receipt.request_id == first.request_id)
        == approved.receipt
    )
    return approved_inventory


def _decline_with_delivered_key(decision: _Decision, approved_inventory: AutomationInventoryProjection) -> None:
    store, human, endpoint = decision.store, decision.human, decision.endpoint
    credential = decision.enrollment.credential()
    api = FrontendClient(
        connect_installed(endpoint), profile_id=decision.profile_id, frontend=OperationFrontendProjection.CLI
    )
    try:
        api_key = bytearray(credential.get_secret_value())
        api.login_api_key(api_key, timeout=25)
        assert not any(api_key)

        second_requester, second_enrollment = _requester(endpoint, decision.profile_id, MemoryNativePort())
        try:
            second = second_enrollment.submit(_proposal())
            second_review = _review(human, second.request_id)
            with pytest.raises(FrontendRefusedError):
                run_automation_decision(api, second_review, decision="decline")
            grants_before_decline = store.snapshot().grants
            declined = run_automation_decision(human, second_review, decision="decline")
            assert declined.effect is OperationEffect.UPDATED
            assert declined.receipt.stage is EnrollmentStage.DECLINED
            assert declined.receipt.request_id == second.request_id
            assert declined.receipt.review_digest == second.review_digest
            assert store.snapshot().grants == grants_before_decline
            assert second_enrollment.inspect() == declined.receipt
            declined_inventory = read_automation_inventory(human).projection
            assert declined_inventory.grants == approved_inventory.grants
            assert declined_inventory.keys == approved_inventory.keys
            assert (
                next(
                    item.receipt for item in declined_inventory.requests if item.receipt.request_id == second.request_id
                )
                == declined.receipt
            )
        finally:
            second_requester.close()
    finally:
        api.close()


def test_native_reviewed_approve_and_decline_use_decision_client_and_requester_possession(tmp_path: Path) -> None:
    """Human decisions settle canonically; only the requester receives its key."""
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
        server_native, client_native = MemoryNativePort(), MemoryNativePort()
        store = AutomationControlStore(root=root, binding=binding, secrets_store=server_native)
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: SyntheticLogin("automation-decision-client-native-login"),
            secret_store=lambda: server_native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            try:
                while not server.ready.wait(0.01):
                    if running.done():
                        running.result()
                        pytest.fail("runtime stopped before readiness")
                requester, enrollment = _requester(endpoint, profile_id, client_native)
                human = FrontendClient(
                    connect_installed(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                )
                try:
                    decision = _Decision(
                        endpoint, profile_id, pool, store, server_native, client_native, human, enrollment
                    )
                    first, review, wrong_operation_id = _review_and_refuse_wrong_password(decision)
                    approved = _approve_while_polling(decision, review)
                    approved_inventory = _assert_approved_delivery(decision, first, approved, wrong_operation_id)
                    _decline_with_delivered_key(decision, approved_inventory)
                finally:
                    requester.close()
                    human.close()
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result()
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()
