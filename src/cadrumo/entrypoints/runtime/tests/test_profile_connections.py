"""Real local admission/worker flows with explicit native login and store fault ports."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.custody.automation_delivery import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
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
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenial, AutomationDenialKind
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.operations import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from ..profile_connections import RuntimeProfileConnections
from .operation_transport_support import PausedProjectionListener, ProjectionWriteBarrier

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@dataclass
class LoginObservation:
    owner: str
    login_id: str = "synthetic-native-login"
    active: bool = True
    locked: bool = False

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=self.active,
            locked=self.locked,
            unattended=LoginEligibility.ELIGIBLE if self.active else LoginEligibility.INELIGIBLE,
            credential_facilities=credential_facilities,
        )


def connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def login(client: VerifiedRuntimeConnection, profile: UUID, method: str, raw: bytes):
    buffer = bytearray(raw)
    request = RuntimeProfileLogin.model_validate(
        {"request_id": uuid4(), "profile_id": profile, "method": method, "frontend": OperationFrontendProjection.MCP}
    )
    result = client.login(request, buffer, deadline=time.monotonic() + 20)
    assert buffer == bytes(len(raw))
    return result


def test_real_connection_admission_lock_reconnect_and_native_dependency_loss(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as enrollment:
        request_id = uuid4()
        enrollment.service.request(request_id, enrollment.proposal)
        enrollment.approve(request_id)
        record = enrollment.store.enrollment_state().requests[0]
        secret = enrollment.owner.delivery.endpoint.possession(record)
        assert secret is not None
        close_active_bucket_session()
        profile = enrollment.store.binding.profile_id
        stop, boot, native_login = Event(), uuid4(), LoginObservation(owner_id())
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=lambda: enrollment.native,
        )
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        clients: list[VerifiedRuntimeConnection] = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                api, human, other = (connect(endpoint) for _ in range(3))
                clients.extend((api, human, other))
                admitted = login(api, profile, "api_key", secret.get_secret_value())
                assert isinstance(admitted, RuntimeProfileStatus), admitted
                assert admitted.status.denial is None
                api_id = admitted.status.session_id
                assert api_id is not None
                human_result = login(human, profile, "password", PROFILE_INPUT.encode())
                assert isinstance(human_result, RuntimeProfileStatus), human_result
                human_id = human_result.status.session_id
                assert human_id is not None
                stolen = other.session(
                    RuntimeSessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=api_id
                    ),
                    deadline=time.monotonic() + 3,
                )
                assert isinstance(stolen, RuntimeAccessRefusal)
                wrong = login(api, uuid4(), "api_key", secret.get_secret_value())
                assert isinstance(wrong, RuntimeAccessRefusal)
                refreshed = api.session(
                    RuntimeSessionRequest(
                        action="session_refresh", request_id=uuid4(), profile_id=profile, session_id=api_id
                    ),
                    deadline=time.monotonic() + 3,
                )
                assert isinstance(refreshed, RuntimeProfileStatus) and refreshed.status.denial is None
                locked = api.session(
                    RuntimeSessionRequest(
                        action="session_lock", request_id=uuid4(), profile_id=profile, session_id=api_id
                    ),
                    deadline=time.monotonic() + 3,
                )
                assert isinstance(locked, RuntimeSessionsLocked) and locked.session_ids == (api_id,)
                fresh = login(api, profile, "api_key", secret.get_secret_value())
                assert isinstance(fresh, RuntimeProfileStatus) and fresh.status.session_id != api_id
                assert fresh.status.session_id is not None
                # Abruptly lose the actual test-owned worker job, leaving both
                # frontend channels connected. A replacement needs new proof.
                lost_worker = profiles._profiles[profile].owner._worker
                assert lost_worker is not None
                lost_worker.close()
                deadline = time.monotonic() + 3
                while profile in profiles._profiles and time.monotonic() < deadline:
                    profiles.poll()
                    time.sleep(0.02)
                assert profile not in profiles._profiles
                fresh = login(api, profile, "api_key", secret.get_secret_value())
                assert isinstance(fresh, RuntimeProfileStatus) and fresh.status.session_id is not None
                resumed_human = login(human, profile, "password", PROFILE_INPUT.encode())
                assert isinstance(resumed_human, RuntimeProfileStatus)
                human_id = resumed_human.status.session_id
                assert human_id is not None
                enrollment.native.unavailable = True
                api_lost = api.session(
                    RuntimeSessionRequest(
                        action="session_status",
                        request_id=uuid4(),
                        profile_id=profile,
                        session_id=fresh.status.session_id,
                    ),
                    deadline=time.monotonic() + 3,
                )
                assert isinstance(api_lost, RuntimeAccessRefusal)
                still_human = human.session(
                    RuntimeSessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=human_id
                    ),
                    deadline=time.monotonic() + 3,
                )
                assert isinstance(still_human, RuntimeProfileStatus) and still_human.status.denial is None
                independent = login(other, profile, "password", PROFILE_INPUT.encode())
                assert isinstance(independent, RuntimeProfileStatus) and independent.status.denial is None
                native_login.locked = True
                retired = human.session(
                    RuntimeSessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=human_id
                    ),
                    deadline=time.monotonic() + 3,
                )
                assert isinstance(retired, RuntimeAccessRefusal) or (
                    isinstance(retired, RuntimeProfileStatus) and retired.status.denial is not None
                )
            finally:
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=12)
                endpoint.close()


@pytest.mark.parametrize("allow_observation", [False, True])
def test_api_authority_reaches_real_effects_and_guards_public_output(tmp_path: Path, allow_observation: bool) -> None:
    """Only native login/store facilities are doubled; grant-to-effect admission is real."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as enrollment:
        if allow_observation:
            requester = changed(enrollment.owner.requesting, destination_id=enrollment.owner.requesting.client_id)
            enrollment.owner.requesting = requester
            enrollment.owner.delivery.endpoint = NativeEnrollmentRecipient(
                requester=requester, secrets_store=enrollment.client_native
            )
            permissions = frozenset(
                (
                    DisclosurePermission(
                        destination_id=enrollment.owner.requesting.client_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                )
            )
            scope = changed(enrollment.proposal.scope, disclosures=permissions)
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
        secret = enrollment.owner.delivery.endpoint.possession(record)
        assert secret is not None
        close_active_bucket_session()
        profile = enrollment.store.binding.profile_id
        stop, boot, native_login = Event(), uuid4(), LoginObservation(owner_id())
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=lambda: enrollment.native,
        )
        barrier = ProjectionWriteBarrier()
        server = RuntimeTransportServer(
            PausedProjectionListener(endpoint, barrier),
            product_version="test",
            stop=stop,
            profiles=profiles,
            boot_id=boot,
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            clients: list[VerifiedRuntimeConnection] = []
            try:
                assert server.ready.wait(3)
                client = connect(endpoint)
                clients.append(client)
                refused = client.operation(
                    RuntimeOperationControl(
                        action="operation_start",
                        request_id=uuid4(),
                        profile_id=profile,
                        session_id=uuid4(),
                        operation_id="0" * 64,
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(refused, RuntimeAccessRefusal)
                admitted = login(client, profile, "api_key", secret.get_secret_value())
                assert isinstance(admitted, RuntimeProfileStatus) and admitted.status.session_id is not None
                session_id = admitted.status.session_id
                contract = client.operation(
                    RuntimeOperationContract(
                        request_id=uuid4(),
                        profile_id=profile,
                        session_id=session_id,
                        definition_id="user-profile.field-mutation",
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(contract, RuntimeOperationContractReply)
                submission = RuntimeOperationSubmit(
                    request_id=uuid4(),
                    profile_id=profile,
                    session_id=session_id,
                    definition_id="user-profile.field-mutation",
                    subject_ref=f"profile:{profile}",
                    payload_json=ProfileFieldMutationOperationRequest(
                        profile_id=profile, path=PROFILE_OUTPUT_LANGUAGE_PATH, value="es"
                    ).model_dump_json(),
                    idempotency_key="autonomous-language-request",
                )
                submitted = client.operation(submission, deadline=time.monotonic() + 10)
                assert isinstance(submitted, RuntimeOperationSubmitted), submitted
                locked = client.session(
                    RuntimeSessionRequest(
                        action="session_lock", request_id=uuid4(), profile_id=profile, session_id=session_id
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(locked, RuntimeSessionsLocked)
                admitted = login(client, profile, "api_key", secret.get_secret_value())
                assert isinstance(admitted, RuntimeProfileStatus) and admitted.status.session_id is not None
                assert admitted.status.session_id != session_id
                session_id = admitted.status.session_id
                replayed = client.operation(
                    changed(submission, request_id=uuid4(), session_id=session_id), deadline=time.monotonic() + 10
                )
                assert isinstance(replayed, RuntimeOperationSubmitted) and replayed.receipt == submitted.receipt
                resumed = client.operation(
                    RuntimeOperationControl(
                        action="operation_resume",
                        request_id=uuid4(),
                        profile_id=profile,
                        session_id=session_id,
                        operation_id=submitted.receipt.operation_id,
                    ),
                    deadline=time.monotonic() + 10,
                )
                assert isinstance(resumed, RuntimeOperationAcknowledged), resumed
                request = RuntimeOperationObserve(
                    request_id=uuid4(),
                    profile_id=profile,
                    session_id=session_id,
                    observation=OperationObservationRequestV1(
                        operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=32
                    ),
                )
                journal = OperationJournalRepository(storage_root=root)
                deadline = time.monotonic() + 8
                while True:
                    observation = client.operation(changed(request, request_id=uuid4()), deadline=deadline)
                    if allow_observation:
                        assert isinstance(observation, RuntimeOperationObserved), observation
                        assert isinstance(observation.observation, OperationObservationSuccessV1)
                    else:
                        assert isinstance(observation, RuntimeAccessRefusal), observation
                        assert observation.code is AccessDenialCode.DISCLOSURE_DENIED
                    snapshot = asyncio.run(journal.load(submitted.receipt.operation_id))
                    if snapshot.terminal_condition is not None:
                        break
                    assert time.monotonic() < deadline
                    time.sleep(0.02)
                assert snapshot.terminal_condition is OperationTerminalCondition.SUCCEEDED
                host = profiles._profiles[profile]
                if allow_observation:
                    human = connect(endpoint)
                    clients.append(human)
                    human_login = login(human, profile, "password", PROFILE_INPUT.encode())
                    assert isinstance(human_login, RuntimeProfileStatus) and human_login.status.session_id is not None
                    barrier.enabled.set()
                    releasing = pool.submit(
                        client.operation, changed(request, request_id=uuid4()), deadline=time.monotonic() + 5
                    )
                    assert barrier.entered.wait(3)
                    acquired = host.guard.acquire(blocking=False)
                    if acquired:
                        host.guard.release()
                    assert not acquired, "the final native projection write released its authority fence"
                    locking = pool.submit(
                        human.session,
                        RuntimeSessionRequest(
                            action="session_lock",
                            request_id=uuid4(),
                            profile_id=profile,
                            session_id=human_login.status.session_id,
                            target_session_id=session_id,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert not locking.done()
                    barrier.release.set()
                    assert isinstance(releasing.result(timeout=5), RuntimeOperationObserved)
                    locked = locking.result(timeout=5)
                    assert isinstance(locked, RuntimeSessionsLocked) and session_id in locked.session_ids
                    assert isinstance(
                        client.operation(changed(request, request_id=uuid4()), deadline=time.monotonic() + 5),
                        RuntimeAccessRefusal,
                    )
                    admitted = login(client, profile, "api_key", secret.get_secret_value())
                    assert isinstance(admitted, RuntimeProfileStatus) and admitted.status.session_id is not None
                    request = changed(request, request_id=uuid4(), session_id=admitted.status.session_id)
                grant = host.store.snapshot().grants[0]
                denial = AutomationDenial(
                    request_id=uuid4(),
                    binding=host.store.binding,
                    kind=AutomationDenialKind.GRANT,
                    target_id=grant.grant_id,
                )
                with host.guard:
                    host.authority.invalidate_automation(denial)
                    assert host.store.deny(denial).access_denied
                assert isinstance(
                    client.operation(changed(request, request_id=uuid4()), deadline=time.monotonic() + 5),
                    RuntimeAccessRefusal,
                )
                assert isinstance(login(client, profile, "api_key", secret.get_secret_value()), RuntimeAccessRefusal)
            finally:
                barrier.release.set()
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=12)
                endpoint.close()
        _, decode = profile_authority_contexts()
        login_profile(name=str(profile), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode)
        try:
            persisted = ProfileRecordRepository.for_current_session(profile, profile_decode_context=decode).load(
                profile
            )
            assert record_to_path_values(persisted)[PROFILE_OUTPUT_LANGUAGE_PATH] == "es"
        finally:
            close_active_bucket_session()
