"""A settled applicability refusal detail remains subject to current authority."""

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
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.access_management import RuntimeAutomationDenied, RuntimeAutomationDeny
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
    RuntimeSessionsLocked,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_enrollment import EnrollmentReceipt
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.tests import modelo_operation_test_support

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
]

_CREATE = MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
_PERIOD = Period.from_year_and_code(2025, "1P")


class _LoginObservation:
    login_id = "native-refusal-detail-authority-test-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _scope(destination_id: UUID) -> AccessScope:
    schema = build_production_operation_registry().lookup_public_contract(_CREATE).result_schema
    assert schema is not None
    return AccessScope(
        operations=frozenset({_CREATE}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.COMMIT,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=frozenset({_PERIOD}),
        allow_period_independent=False,
        allow_delegation=False,
    )


def _issue_scoped_key(subject: AdministrationSubject) -> tuple[UUID, bytes]:
    requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
    subject.owner.requesting = requester
    subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
        requester=requester, secrets_store=subject.client_native
    )
    scope = _scope(requester.client_id)
    facts = subject.owner.current
    assert facts.session is not None
    subject.owner.current = changed(
        facts,
        profile=changed(facts.profile, scope=scope),
        session=changed(facts.session, scope=scope),
    )
    request_id = uuid4()
    subject.service.request(request_id, changed(subject.proposal, scope=scope))
    receipt = subject.approve(request_id)
    assert isinstance(receipt, EnrollmentReceipt)
    record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
    credential = subject.owner.delivery.endpoint.possession(record)
    assert receipt.key_id is not None and credential is not None
    return receipt.key_id, credential.get_secret_value()


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _admit(
    connection: VerifiedRuntimeConnection, profile_id: UUID, *, method: Literal["password", "api_key"], proof: bytes
) -> UUID:
    secret = bytearray(proof)
    reply = connection.login(
        RuntimeProfileLogin(
            request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI, method=method
        ),
        secret,
        deadline=time.monotonic() + 25,
    )
    assert secret == bytes(len(proof))
    assert isinstance(reply, RuntimeProfileStatus), reply
    assert reply.status.session_id is not None
    return reply.status.session_id


def _observe(
    connection: VerifiedRuntimeConnection, *, profile_id: UUID, session_id: UUID, operation_id: str
) -> OperationObservationSuccessV1:
    deadline = time.monotonic() + 20
    while True:
        reply = connection.operation(
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
            ),
            deadline=deadline,
        )
        assert isinstance(reply, RuntimeOperationObserved), reply
        assert isinstance(reply.observation, OperationObservationSuccessV1), reply.observation
        if reply.observation.projection.terminal_condition is not None:
            return reply.observation
        assert time.monotonic() < deadline
        time.sleep(0.02)


@pytest.mark.parametrize("revocation", ["session_lock", "key_revoke"])
def test_refusal_detail_is_fenced_after_authority_revocation(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, revocation: str
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        # This canonical fixture persists a natural-person profile and a distinct M130 unit.
        modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=authority_operation)
        key_id, api_key = _issue_scoped_key(subject)
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
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                api, human = _connect(endpoint), _connect(endpoint)
                try:
                    api_session = _admit(api, profile_id, method="api_key", proof=api_key)
                    human_session = _admit(human, profile_id, method="password", proof=PROFILE_INPUT.encode())
                    contract = api.operation(
                        RuntimeOperationContract(
                            request_id=uuid4(), profile_id=profile_id, session_id=api_session, definition_id=_CREATE
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(contract, RuntimeOperationContractReply), contract
                    schema = contract.contract.result_schema
                    assert schema is not None
                    assert MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE in contract.contract.refusal_detail_codes
                    payload = ModeloWorkCreateRequest(
                        profile_id=profile_id,
                        modelo="202",
                        period=PublicPeriod.from_period(_PERIOD),
                        revision_id="2025-y-siguientes",
                        actor="native-refusal-detail-test",
                    )
                    submitted = api.operation(
                        RuntimeOperationSubmit(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=api_session,
                            definition_id=_CREATE,
                            subject_ref=profile_operation_subject(str(profile_id)),
                            payload_json=payload.model_dump_json(),
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(submitted, RuntimeOperationSubmitted), submitted
                    operation_id = submitted.receipt.operation_id
                    started = api.operation(
                        RuntimeOperationControl(
                            action="operation_start",
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=api_session,
                            operation_id=operation_id,
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(started, RuntimeOperationAcknowledged), started
                    observed = _observe(api, profile_id=profile_id, session_id=api_session, operation_id=operation_id)
                    terminal = observed.projection
                    assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
                    assert terminal.effect is OperationEffect.NONE
                    assert terminal.refusal_ref == MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
                    result_request = RuntimeOperationResult(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=api_session,
                        result=OperationResultProjectionRequestV1(
                            operation_id=operation_id,
                            terminal_revision=terminal.revision,
                            definition_contract_digest=contract.contract.definition_contract_digest,
                            result_schema=schema,
                        ),
                    )
                    released = api.operation(result_request, deadline=time.monotonic() + 5)
                    assert isinstance(released, RuntimeOperationProjected), released
                    typed = OperationResultProjectionSuccessV1[ModeloWorkCreateProjection].model_validate_json(
                        json.dumps(released.document)
                    )
                    assert typed.projection.profile_id == profile_id
                    assert isinstance(typed.projection.outcome, ModeloWorkCreateRefusal)
                    assert typed.projection.outcome.modelo == "202"
                    assert typed.projection.outcome.reason

                    if revocation == "session_lock":
                        locked = human.session(
                            RuntimeSessionRequest(
                                action="session_lock",
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=human_session,
                                target_session_id=api_session,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                        assert isinstance(locked, RuntimeSessionsLocked) and api_session in locked.session_ids
                    else:
                        revoked = human.deny_automation(
                            RuntimeAutomationDeny(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=human_session,
                                kind=AutomationDenialKind.KEY,
                                target_id=key_id,
                            ),
                            deadline=time.monotonic() + 10,
                        )
                        assert isinstance(revoked, RuntimeAutomationDenied) and revoked.receipt.access_denied
                    denied = api.operation(
                        result_request.model_copy(update={"request_id": uuid4()}), deadline=time.monotonic() + 5
                    )
                    assert isinstance(denied, RuntimeAccessRefusal), denied
                    assert denied.code in {
                        AccessDenialCode.SESSION_INACTIVE,
                        AccessDenialCode.CONNECTION_MISMATCH,
                        AccessDenialCode.KEY_INACTIVE,
                    }
                    # A still-authorized human sees the same terminal receipt, never a replay or mutation.
                    human_observed = _observe(
                        human, profile_id=profile_id, session_id=human_session, operation_id=operation_id
                    )
                    assert human_observed.projection.operation_id == operation_id
                    assert human_observed.projection.revision == terminal.revision
                    assert human_observed.projection.terminal_condition is OperationTerminalCondition.REFUSED
                    assert human_observed.projection.effect is OperationEffect.NONE
                    assert human_observed.projection.refusal_ref == MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
                finally:
                    api.close()
                    human.close()
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    running.result(timeout=20)
                except Exception:
                    if primary is None:
                        raise
                finally:
                    endpoint.close()
