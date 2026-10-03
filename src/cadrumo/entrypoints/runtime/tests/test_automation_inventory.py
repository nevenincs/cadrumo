"""Installed human inventory stays private to the exact authenticated profile."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
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
    RuntimeOperationResult,
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
from cadrumo.application.user_profile.automation_enrollment import AutomationInventoryProjection
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from cadrumo.core.operations import OperationTerminalCondition, profile_operation_subject

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "automation-inventory-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply only test-owned OS facts to the installed worker."""
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
        deadline=time.monotonic() + 20,
    )
    assert secret == bytes(len(proof))
    assert isinstance(result, RuntimeProfileStatus)
    assert result.status.session_id is not None
    return result.status.session_id


def _inventory_request(profile_id: UUID) -> AutomationOperationRequest:
    return AutomationOperationRequest(profile_id=profile_id, request_id=uuid4())


@pytest.mark.parametrize("frontend", (OperationFrontendProjection.CLI, OperationFrontendProjection.TUI))
def test_password_human_sees_nonsecret_inventory_and_api_key_cannot_submit_or_read_result(
    tmp_path: Path, frontend: OperationFrontendProjection
) -> None:
    """The native worker releases a typed inventory only to current human authority."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as enrollment:
        requester = changed(enrollment.owner.requesting, destination_id=enrollment.owner.requesting.client_id)
        enrollment.owner.requesting = requester
        enrollment.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=enrollment.client_native
        )
        permissions = frozenset(
            (
                DisclosurePermission(
                    destination_id=requester.client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=requester.client_id,
                    projection_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID + ".result",
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            )
        )
        scope = changed(
            enrollment.proposal.scope,
            operations=frozenset((AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,)),
            actions=frozenset(
                (
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                )
            ),
            disclosures=permissions,
        )
        facts = enrollment.owner.current
        assert facts.session is not None
        enrollment.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        enrollment.proposal = changed(enrollment.proposal, scope=scope)
        enrollment_request = uuid4()
        enrollment.service.request(enrollment_request, enrollment.proposal)
        enrollment.approve(enrollment_request)
        record = enrollment.store.enrollment_state().requests[0]
        possession = enrollment.owner.delivery.endpoint.possession(record)
        assert possession is not None
        profile_id = enrollment.store.binding.profile_id
        close_active_bucket_session()

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: enrollment.native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                human, api = _connect(endpoint), _connect(endpoint)
                try:
                    human_id = _login(
                        human, profile_id, frontend=frontend, method="password", proof=PROFILE_INPUT.encode()
                    )
                    api_id = _login(
                        api,
                        profile_id,
                        frontend=frontend,
                        method="api_key",
                        proof=possession.get_secret_value(),
                    )
                    contract = human.operation(
                        RuntimeOperationContract(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(contract, RuntimeOperationContractReply)
                    assert contract.contract.result_schema is not None
                    submit = RuntimeOperationSubmit(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=human_id,
                        definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                        subject_ref=profile_operation_subject(str(profile_id)),
                        payload_json=_inventory_request(profile_id).model_dump_json(),
                    )
                    wrong_id = uuid4()
                    wrong = human.operation(
                        changed(
                            submit,
                            request_id=uuid4(),
                            payload_json=_inventory_request(wrong_id).model_dump_json(),
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(wrong, RuntimeAccessRefusal)
                    assert wrong.code is AccessDenialCode.PROFILE_MISMATCH
                    api_submit = api.operation(
                        changed(submit, request_id=uuid4(), session_id=api_id),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(api_submit, RuntimeAccessRefusal)
                    assert api_submit.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
                    submitted = human.operation(submit, deadline=time.monotonic() + 10)
                    assert isinstance(submitted, RuntimeOperationSubmitted)
                    operation_id = submitted.receipt.operation_id
                    started = human.operation(
                        RuntimeOperationControl(
                            action="operation_start",
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            operation_id=operation_id,
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(started, RuntimeOperationAcknowledged)
                    deadline = time.monotonic() + 25
                    while True:
                        observed = human.operation(
                            RuntimeOperationObserve(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=human_id,
                                observation=OperationObservationRequestV1(
                                    operation_id=operation_id, after_cursor=0, page_limit=32
                                ),
                            ),
                            deadline=deadline,
                        )
                        assert isinstance(observed, RuntimeOperationObserved)
                        assert isinstance(observed.observation, OperationObservationSuccessV1)
                        projection = observed.observation.projection
                        if projection.terminal_condition is not None:
                            break
                        assert time.monotonic() < deadline
                        time.sleep(0.02)
                    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    result_request = RuntimeOperationResult(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=human_id,
                        result=OperationResultProjectionRequestV1(
                            operation_id=operation_id,
                            terminal_revision=projection.revision,
                            definition_contract_digest=contract.contract.definition_contract_digest,
                            result_schema=contract.contract.result_schema,
                        ),
                    )
                    api_result = api.operation(
                        changed(result_request, request_id=uuid4(), session_id=api_id),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(api_result, RuntimeAccessRefusal)
                    assert api_result.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
                    released = human.operation(result_request, deadline=time.monotonic() + 5)
                    assert isinstance(released, RuntimeOperationProjected)
                    typed = OperationResultProjectionSuccessV1[AutomationInventoryProjection].model_validate_json(
                        json.dumps(released.document)
                    )
                    inventory = typed.projection
                    assert inventory.grants and inventory.keys and inventory.requests
                    assert inventory.grants[0].profile_id == profile_id
                    assert inventory.grants[0].grant_id == record.grant_id
                    assert inventory.grants[0].scope.operations == (AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,)
                    assert inventory.keys[0].grant_id == record.grant_id
                    assert inventory.requests[0].receipt.request_id == enrollment_request
                    assert inventory.grants[0].expires_at == enrollment.proposal.expires_at
                    encoded = json.dumps(released.document).casefold()
                    for forbidden in ("verifier", "wrapped_dek", "private_key", PROFILE_INPUT.casefold()):
                        assert forbidden not in encoded
                    if possession.get_secret_value().decode("ascii").casefold() in encoded:
                        pytest.fail("inventory result exposed API-key possession")
                finally:
                    human.close()
                    api.close()
            finally:
                stop.set()
                try:
                    running.result(timeout=20)
                finally:
                    endpoint.close()


def test_pristine_inventory_is_empty_and_missing_optional_store_does_not_block_password_status(tmp_path: Path) -> None:
    """A clean control store has an empty inventory; its later loss cannot invent one."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as enrollment:
        profile_id = enrollment.store.binding.profile_id
        assert enrollment.store.enrollment_state().grants == ()
        assert enrollment.store.enrollment_state().requests == ()
        close_active_bucket_session()

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: enrollment.native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                human = _connect(endpoint)
                try:
                    human_id = _login(
                        human,
                        profile_id,
                        frontend=OperationFrontendProjection.CLI,
                        method="password",
                        proof=PROFILE_INPUT.encode(),
                    )
                    contract = human.operation(
                        RuntimeOperationContract(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(contract, RuntimeOperationContractReply)
                    assert contract.contract.result_schema is not None
                    submitted = human.operation(
                        RuntimeOperationSubmit(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                            subject_ref=profile_operation_subject(str(profile_id)),
                            payload_json=_inventory_request(profile_id).model_dump_json(),
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(submitted, RuntimeOperationSubmitted)
                    operation_id = submitted.receipt.operation_id
                    started = human.operation(
                        RuntimeOperationControl(
                            action="operation_start",
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            operation_id=operation_id,
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(started, RuntimeOperationAcknowledged)
                    deadline = time.monotonic() + 25
                    while True:
                        observed = human.operation(
                            RuntimeOperationObserve(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=human_id,
                                observation=OperationObservationRequestV1(
                                    operation_id=operation_id, after_cursor=0, page_limit=32
                                ),
                            ),
                            deadline=deadline,
                        )
                        assert isinstance(observed, RuntimeOperationObserved)
                        assert isinstance(observed.observation, OperationObservationSuccessV1)
                        projection = observed.observation.projection
                        if projection.terminal_condition is not None:
                            break
                        assert time.monotonic() < deadline
                        time.sleep(0.02)
                    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    released = human.operation(
                        RuntimeOperationResult(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            result=OperationResultProjectionRequestV1(
                                operation_id=operation_id,
                                terminal_revision=projection.revision,
                                definition_contract_digest=contract.contract.definition_contract_digest,
                                result_schema=contract.contract.result_schema,
                            ),
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(released, RuntimeOperationProjected)
                    inventory = (
                        OperationResultProjectionSuccessV1[AutomationInventoryProjection]
                        .model_validate_json(json.dumps(released.document))
                        .projection
                    )
                    assert inventory.grants == inventory.keys == inventory.requests == ()

                    enrollment.native.unavailable = True
                    status = human.session(
                        RuntimeSessionRequest(
                            action="session_status",
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(status, RuntimeProfileStatus)
                    assert status.status.session_id == human_id
                    missing = human.operation(
                        RuntimeOperationSubmit(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                            subject_ref=profile_operation_subject(str(profile_id)),
                            payload_json=_inventory_request(profile_id).model_dump_json(),
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(missing, RuntimeOperationSubmitted)
                    unavailable_id = missing.receipt.operation_id
                    started = human.operation(
                        RuntimeOperationControl(
                            action="operation_start",
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=human_id,
                            operation_id=unavailable_id,
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(started, RuntimeOperationAcknowledged)
                    deadline = time.monotonic() + 25
                    while True:
                        observed = human.operation(
                            RuntimeOperationObserve(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=human_id,
                                observation=OperationObservationRequestV1(
                                    operation_id=unavailable_id, after_cursor=0, page_limit=32
                                ),
                            ),
                            deadline=deadline,
                        )
                        assert isinstance(observed, RuntimeOperationObserved)
                        assert isinstance(observed.observation, OperationObservationSuccessV1)
                        projection = observed.observation.projection
                        if projection.terminal_condition is not None:
                            break
                        assert time.monotonic() < deadline
                        time.sleep(0.02)
                    assert projection.terminal_condition is OperationTerminalCondition.REFUSED
                    assert projection.result_ref is None
                finally:
                    human.close()
            finally:
                stop.set()
                try:
                    running.result(timeout=20)
                finally:
                    endpoint.close()
