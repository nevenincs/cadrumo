"""A recorded modelo read keeps its admitted period and original result."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
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
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.custody.automation_delivery import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.application.modelo.metadata_read_operation import (
    MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
    ModeloWorkMetadataProjection,
    ModeloWorkMetadataRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.public_period import PublicPeriod
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
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_DEFINITION = MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
_FIRST = Period.from_year_and_code(2026, "1T")
_OTHER = Period.from_year_and_code(2026, "2T")
_CREATED = datetime(2020, 1, 1, tzinfo=UTC)


class _LoginObservation:
    login_id = "modelo-history-test-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _unit(profile_id: UUID, *, period: Period, revision: str, name: str) -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile_id),
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=revision,
        ),
        bucket_id=str(profile_id),
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=revision,
        name=name,
        created_at=_CREATED,
        updated_at=_CREATED,
    )


def _repository(profile_id: UUID) -> WorkUnitCatalogueRepository:
    return WorkUnitCatalogueRepository(bucket_id=str(profile_id), objects=secure_object_repository_for_active_bucket())


def _scope(destination_id: UUID) -> AccessScope:
    registry = build_production_operation_registry()
    schema = registry.lookup_public_contract(_DEFINITION).result_schema
    assert schema is not None
    return AccessScope(
        operations=frozenset({_DEFINITION}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
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
        periods=frozenset({_FIRST}),
        allow_period_independent=False,
        allow_delegation=False,
    )


def _issue_scoped_key(subject: AdministrationSubject) -> bytes:
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
    record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
    credential = subject.owner.delivery.endpoint.possession(record)
    assert receipt.key_id is not None and credential is not None
    return credential.get_secret_value()


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _admit(
    connection: VerifiedRuntimeConnection,
    profile_id: UUID,
    *,
    method: Literal["password", "api_key"],
    proof: bytes,
) -> UUID:
    secret = bytearray(proof)
    reply = connection.login(
        RuntimeProfileLogin(
            request_id=uuid4(),
            profile_id=profile_id,
            frontend=OperationFrontendProjection.CLI,
            method=method,
        ),
        secret,
        deadline=time.monotonic() + 25,
    )
    assert secret == bytes(len(proof))
    assert isinstance(reply, RuntimeProfileStatus), reply
    assert reply.status.session_id is not None
    return reply.status.session_id


def _submit(
    connection: VerifiedRuntimeConnection,
    profile_id: UUID,
    session_id: UUID,
    *,
    period: Period,
) -> RuntimeOperationSubmitted | RuntimeAccessRefusal:
    request = ModeloWorkMetadataRequest(
        profile_id=profile_id,
        modelo="130",
        year=2026,
        period=PublicPeriod.from_period(period),
    )
    return _submit_payload(connection, profile_id, session_id, request.model_dump_json())


def _submit_payload(
    connection: VerifiedRuntimeConnection, profile_id: UUID, session_id: UUID, payload_json: str
) -> RuntimeOperationSubmitted | RuntimeAccessRefusal:
    reply = connection.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=_DEFINITION,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload_json=payload_json,
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(reply, (RuntimeOperationSubmitted, RuntimeAccessRefusal)), reply
    return reply


def _observe(
    connection: VerifiedRuntimeConnection, profile_id: UUID, session_id: UUID, operation_id: OperationId
) -> OperationObservationSuccessV1:
    reply = connection.operation(
        RuntimeOperationObserve(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=16),
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(reply, RuntimeOperationObserved), reply
    assert isinstance(reply.observation, OperationObservationSuccessV1), reply
    return reply.observation


def test_recorded_read_keeps_original_revision_after_new_catalogue_candidate(tmp_path: Path) -> None:
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
        original = _unit(profile_id, period=_FIRST, revision="2019-y-siguientes", name="Revision A")
        other_period = _unit(profile_id, period=_OTHER, revision="2019-y-siguientes", name="Other period")
        repository = _repository(profile_id)
        repository.save(upsert_work_unit(upsert_work_unit(repository.load(), original), other_period))
        api_key = _issue_scoped_key(subject)

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
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=api_session,
                            definition_id=_DEFINITION,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(contract, RuntimeOperationContractReply), contract
                    admitted = _submit(api, profile_id, api_session, period=_FIRST)
                    assert isinstance(admitted, RuntimeOperationSubmitted), admitted
                    operation_id = admitted.receipt.operation_id
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
                    deadline = time.monotonic() + 10
                    while True:
                        before = _observe(api, profile_id, api_session, operation_id).projection
                        if before.terminal_condition is not None:
                            break
                        assert time.monotonic() < deadline
                        time.sleep(0.02)
                    assert before.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert before.effect is OperationEffect.NONE

                    # administration_subject still owns the parent process's proven
                    # profile session. This is a real encrypted catalogue write;
                    # the worker and its operation never borrow that session.
                    later = _unit(profile_id, period=_FIRST, revision="2026-history-b", name="Revision B")
                    assert later.work_unit_id != original.work_unit_id
                    repository.save(upsert_work_unit(repository.load(), later))
                    assert {item.work_unit_id for item in repository.load()} == {
                        original.work_unit_id,
                        later.work_unit_id,
                        other_period.work_unit_id,
                    }
                    close_active_bucket_session()

                    historical = _observe(api, profile_id, api_session, operation_id).projection
                    assert historical.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert historical.revision == before.revision
                    schema = contract.contract.result_schema
                    assert schema is not None
                    result_request = RuntimeOperationResult(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=api_session,
                        result=OperationResultProjectionRequestV1(
                            operation_id=operation_id,
                            terminal_revision=historical.revision,
                            definition_contract_digest=contract.contract.definition_contract_digest,
                            result_schema=schema,
                        ),
                    )
                    result = api.operation(result_request, deadline=time.monotonic() + 5)
                    assert isinstance(result, RuntimeOperationProjected), result
                    typed = OperationResultProjectionSuccessV1[ModeloWorkMetadataProjection].model_validate_json(
                        json.dumps(result.document)
                    )
                    assert typed.projection.profile_id == profile_id
                    assert typed.projection.unit.work_unit_id == original.work_unit_id
                    assert typed.projection.unit.revision_id == original.revision_id
                    assert typed.projection.unit.name == "Revision A"
                    assert typed.projection.unit.period.to_period() == _FIRST

                    ambiguous = _submit(api, profile_id, api_session, period=_FIRST)
                    assert isinstance(ambiguous, RuntimeAccessRefusal), ambiguous
                    assert ambiguous.code is AccessDenialCode.OPERATION_DENIED
                    missing = _submit_payload(
                        api,
                        profile_id,
                        api_session,
                        ModeloWorkMetadataRequest(profile_id=profile_id, work_unit_id="a" * 64).model_dump_json(),
                    )
                    assert isinstance(missing, RuntimeAccessRefusal), missing
                    assert missing.code is AccessDenialCode.OPERATION_DENIED
                    malformed_period = _submit_payload(
                        api,
                        profile_id,
                        api_session,
                        json.dumps(
                            {
                                "profile_id": str(profile_id),
                                "modelo": "130",
                                "year": 2026,
                                "period": {"filing_year": 2026, "code": "not-a-period"},
                            }
                        ),
                    )
                    assert isinstance(malformed_period, RuntimeAccessRefusal), malformed_period
                    assert malformed_period.code is AutomationCustodyCode.INVALID
                    invalid_year = _submit_payload(
                        api,
                        profile_id,
                        api_session,
                        json.dumps(
                            {
                                "profile_id": str(profile_id),
                                "modelo": "130",
                                "year": 1899,
                                "period": {"filing_year": 2026, "code": "1T"},
                            }
                        ),
                    )
                    assert isinstance(invalid_year, RuntimeAccessRefusal), invalid_year
                    assert invalid_year.code is AutomationCustodyCode.INVALID
                    denied_period = _submit(api, profile_id, api_session, period=_OTHER)
                    assert isinstance(denied_period, RuntimeAccessRefusal), denied_period
                    assert denied_period.code is AccessDenialCode.PERIOD_DENIED

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
                    after_lock = api.operation(
                        result_request.model_copy(update={"request_id": uuid4()}), deadline=time.monotonic() + 5
                    )
                    assert isinstance(after_lock, RuntimeAccessRefusal), after_lock
                    assert after_lock.code in {AccessDenialCode.SESSION_INACTIVE, AccessDenialCode.CONNECTION_MISMATCH}
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
